"""Gemini multimodal video analysis (ADR-004).

Uploads the video through the Files API, asks for structured candidates, and
returns exactly what the model said. Validation happens downstream.
"""

import io
import json
import logging
import mimetypes
import time

from collections.abc import Callable
from pathlib import Path

from app.ai.base import (
    AIError,
    AIProvider,
    AnalysisRequest,
    RawCandidateList,
    RawTranscript,
)
from app.ai.keyring import KeyRing, NoKeysRemainingError, is_quota_exhausted
from app.ai.prompt import (
    SYSTEM_INSTRUCTION,
    TRANSCRIPTION_INSTRUCTION,
    build_prompt,
    build_transcription_prompt,
)

logger = logging.getLogger(__name__)

FILE_ACTIVATION_TIMEOUT_SECONDS = 600
FILE_POLL_INTERVAL_SECONDS = 3
ANALYSIS_TEMPERATURE = 0.4
# The Files API client reads the source in 8 MiB chunks and sends one request
# per chunk. Videos whose type cannot be guessed never reach here -- the upload
# routes restrict extensions -- but the SDK demands a type for a stream, and a
# wrong guess is better diagnosed by Gemini than by an exception here.
FALLBACK_MIME_TYPE = "video/mp4"
# Transcription is a perception task with one right answer, unlike choosing
# which moments are strongest. Sampling away from it only invents words.
TRANSCRIPTION_TEMPERATURE = 0.0


class CallbackFailed(Exception):
    """Carries whatever `on_progress` raised back out through the SDK.

    The upload runs inside `client.files.upload`, and everything that comes out
    of that call is otherwise indistinguishable from a network failure and
    reported as one. A cancelled run stopping its own transfer is not a Gemini
    failure, so the reason travels wrapped and is unwrapped on the way out.
    """

    def __init__(self, cause: BaseException) -> None:
        super().__init__(str(cause))
        self.cause = cause


class UploadStream(io.RawIOBase):
    """The source file, wrapped so a long transfer can be watched and stopped.

    The Files API client offers no progress hook: it takes a path or a file
    object and returns when the last chunk lands. The handle it reads from is
    therefore the only place a transfer that takes tens of minutes can say how
    far it has got, and the only place it can be abandoned partway.

    Passing a stream rather than a path costs the `X-Goog-Upload-File-Name`
    header the SDK sets for paths -- a display name nothing reads -- and
    requires the MIME type to be supplied, because the SDK guesses it from a
    filename it no longer sees.
    """

    def __init__(
        self, path: Path, on_progress: Callable[[int, int], None] | None
    ) -> None:
        self._file = path.open("rb")
        self._total = path.stat().st_size
        self._sent = 0
        self._on_progress = on_progress

    def read(self, size: int = -1) -> bytes:
        chunk = self._file.read(size)
        self._sent += len(chunk)
        if self._on_progress is not None:
            try:
                self._on_progress(self._sent, self._total)
            except Exception as exc:
                raise CallbackFailed(exc) from exc
        return chunk

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        # The SDK measures the file by seeking to the end and back before it
        # reads anything. Counting that as bytes sent would report the transfer
        # complete before it began, so the position it lands on *is* the count.
        position = self._file.seek(offset, whence)
        self._sent = position
        return position

    def tell(self) -> int:
        return self._file.tell()

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def close(self) -> None:
        self._file.close()
        super().close()


class GeminiProvider(AIProvider):
    """Gemini analysis, backed by a pool of keys.

    An analysis is one logical operation made of several calls -- upload, poll,
    generate -- and any of them can be the one that hits the quota. So the
    retry wraps the whole operation rather than an individual call: switching
    keys mid-analysis would leave the uploaded file owned by a key the next
    request no longer uses.
    """

    def __init__(
        self,
        keyring: KeyRing,
        model: str,
        request_timeout_seconds: int,
        generate_timeout_seconds: int,
    ) -> None:
        if not len(keyring):
            raise AIError(
                "GEMINI_API_KEY is not set. Add it to .env to enable AI analysis."
            )
        self._keyring = keyring
        self._model = model
        self._request_timeout_seconds = request_timeout_seconds
        self._generate_timeout_seconds = generate_timeout_seconds
        self._clients: dict[str, object] = {}

    @property
    def name(self) -> str:
        # Position, never key material -- this reaches the API response.
        return f"gemini:{self._model} ({self._keyring.describe()})"

    # ------------------------------------------------------------------
    def request_http_options(self):
        """The bound on one HTTP request: a chunk, a poll, a delete.

        Per request rather than per upload, because that is the only unit the
        SDK exposes -- and the useful one. A 173 MB source is 22 chunk requests;
        bounding the whole transfer would mean choosing between killing a slow
        but healthy upload and never noticing a dead one, while bounding the
        chunk distinguishes them.
        """
        from google.genai import types

        # The SDK's unit is milliseconds. Configured in seconds because every
        # other duration in this application is.
        return types.HttpOptions(timeout=self._request_timeout_seconds * 1000)

    def generate_http_options(self):
        """The bound on the analysis call, which is longer than any other.

        It has to watch the whole video before it answers, so it is the one
        request whose duration scales with the source rather than with the
        network.
        """
        from google.genai import types

        return types.HttpOptions(timeout=self._generate_timeout_seconds * 1000)

    def _get_client(self, api_key: str):
        """One client per key, created lazily so import never needs credentials.

        The client-level timeout is what reaches the chunk uploads: the Files
        API builds its own per-request options and leaves the timeout unset, and
        the SDK falls back to the client's. Setting it only on the individual
        calls would leave the longest-running request in the system unbounded.
        """
        client = self._clients.get(api_key)
        if client is None:
            from google import genai

            client = genai.Client(
                api_key=api_key, http_options=self.request_http_options()
            )
            self._clients[api_key] = client
        return client

    def _upload_and_activate(self, client, request: AnalysisRequest):
        """Upload the video and wait until Gemini has finished processing it.

        Quota failures are re-raised bare rather than wrapped in AIError, so the
        retry loop above can still recognise them.
        """
        from google.genai import types

        logger.info("Uploading %s to Gemini Files API", request.video_path.name)
        mime_type = (
            mimetypes.guess_type(request.video_path.name)[0] or FALLBACK_MIME_TYPE
        )
        try:
            with UploadStream(request.video_path, request.on_progress) as source:
                uploaded = client.files.upload(
                    file=source,
                    config=types.UploadFileConfig(mime_type=mime_type),
                )
        except CallbackFailed as exc:
            # The run stopped itself. Reported as whatever it stopped for, never
            # as a Gemini failure.
            raise exc.cause from None
        except Exception as exc:
            if is_quota_exhausted(exc):
                raise
            raise AIError(f"Could not upload the video to Gemini: {exc}") from exc

        deadline = time.monotonic() + FILE_ACTIVATION_TIMEOUT_SECONDS
        while uploaded.state == types.FileState.PROCESSING:
            if time.monotonic() > deadline:
                self._delete_file(client, uploaded.name)
                raise AIError("Gemini did not finish processing the video in time.")
            time.sleep(FILE_POLL_INTERVAL_SECONDS)
            try:
                uploaded = client.files.get(name=uploaded.name)
            except Exception as exc:
                if is_quota_exhausted(exc):
                    raise
                raise AIError(
                    f"Could not check the uploaded video state: {exc}"
                ) from exc

        if uploaded.state != types.FileState.ACTIVE:
            self._delete_file(client, uploaded.name)
            raise AIError(
                f"Gemini could not process the video (state: {uploaded.state})."
            )
        logger.info("Gemini file %s is active", uploaded.name)
        return uploaded

    def _delete_file(self, client, name) -> None:
        """Best-effort cleanup; a leftover file must never fail the job."""
        if not name:
            return
        try:
            client.files.delete(name=name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not delete Gemini file %s: %s", name, exc)

    # ------------------------------------------------------------------
    def analyze_video(self, request: AnalysisRequest) -> RawCandidateList:
        """Analyse the video, moving to the next key each time one runs out."""
        attempts = 0
        while True:
            attempts += 1
            try:
                key = self._keyring.current()
            except NoKeysRemainingError as exc:
                raise AIError(
                    f"{exc} Add more keys to GEMINI_API_KEYS, or wait for the "
                    "quota window to reset."
                ) from exc

            try:
                return self._analyze_with(key, request)
            except Exception as exc:
                if not is_quota_exhausted(exc):
                    raise

                logger.warning(
                    "Gemini quota reached on attempt %d: %s", attempts, exc
                )
                if not self._keyring.retire(key):
                    raise AIError(
                        "Every Gemini API key is out of quota. Add more keys to "
                        "GEMINI_API_KEYS, or wait for the quota window to reset."
                    ) from exc
                # Loop: the next key gets the whole operation from the start.

    def _analyze_with(self, api_key: str, request: AnalysisRequest) -> RawCandidateList:
        from google.genai import types

        client = self._get_client(api_key)
        uploaded = self._upload_and_activate(client, request)

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=RawCandidateList,  # forces structured output (FR-007)
            # Long-form video at default resolution overruns the context window;
            # low resolution is sufficient for locating moments.
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
            temperature=ANALYSIS_TEMPERATURE,
            # Finding moments is a perception task, not a reasoning one. Minimal
            # thinking cuts latency substantially with no loss of quality here.
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.MINIMAL
            ),
            http_options=self.generate_http_options(),
        )

        try:
            response = client.models.generate_content(
                model=self._model,
                contents=[uploaded, build_prompt(request)],
                config=config,
            )
        except Exception as exc:
            if is_quota_exhausted(exc):
                raise
            raise AIError(f"Gemini analysis failed: {exc}") from exc
        finally:
            self._delete_file(client, uploaded.name)

        return self._parse(response)

    # ------------------------------------------------------------------
    def transcribe(self, audio_path: Path, duration_seconds: float) -> RawTranscript:
        """Transcribe one clip's audio, retrying across keys like analysis does.

        The audio is sent inline rather than through the Files API. A clip is a
        minute of speech extracted to mono 16kHz -- a few hundred kilobytes,
        far inside the inline request limit -- so uploading it, polling for
        activation and deleting it afterwards would be three round trips to
        avoid one small request body.

        Transcribing the clips rather than the source is the whole reason this
        is affordable: three minutes of audio per run instead of the two hours
        the analysis step had to watch.
        """
        attempts = 0
        while True:
            attempts += 1
            try:
                key = self._keyring.current()
            except NoKeysRemainingError as exc:
                raise AIError(f"{exc} Captions could not be generated.") from exc

            try:
                return self._transcribe_with(key, audio_path, duration_seconds)
            except Exception as exc:
                if not is_quota_exhausted(exc):
                    raise

                logger.warning(
                    "Gemini quota reached transcribing on attempt %d: %s",
                    attempts, exc,
                )
                if not self._keyring.retire(key):
                    raise AIError(
                        "Every Gemini API key is out of quota, so captions "
                        "could not be generated."
                    ) from exc

    def _transcribe_with(
        self, api_key: str, audio_path: Path, duration_seconds: float
    ) -> RawTranscript:
        from google.genai import types

        client = self._get_client(api_key)
        config = types.GenerateContentConfig(
            system_instruction=TRANSCRIPTION_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=RawTranscript,
            temperature=TRANSCRIPTION_TEMPERATURE,
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.MINIMAL
            ),
        )

        try:
            response = client.models.generate_content(
                model=self._model,
                contents=[
                    types.Part.from_bytes(
                        data=audio_path.read_bytes(), mime_type="audio/wav"
                    ),
                    build_transcription_prompt(duration_seconds),
                ],
                config=config,
            )
        except Exception as exc:
            if is_quota_exhausted(exc):
                raise
            raise AIError(f"Gemini transcription failed: {exc}") from exc

        return self._parse_transcript(response)

    @staticmethod
    def _parse_transcript(response) -> RawTranscript:
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, RawTranscript):
            return parsed

        text = getattr(response, "text", None)
        if not text:
            raise AIError("Gemini returned an empty transcription.")

        try:
            return RawTranscript.model_validate(json.loads(text))
        except json.JSONDecodeError as exc:
            raise AIError(
                "Gemini returned a transcription that was not valid JSON."
            ) from exc
        except Exception as exc:
            raise AIError(
                f"Gemini transcription did not match the required schema: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    @staticmethod
    def _parse(response) -> RawCandidateList:
        """Turn the model response into candidates, or fail loudly."""
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, RawCandidateList):
            return parsed

        text = getattr(response, "text", None)
        if not text:
            raise AIError("Gemini returned an empty response.")

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIError("Gemini returned output that was not valid JSON.") from exc

        try:
            return RawCandidateList.model_validate(payload)
        except Exception as exc:
            raise AIError(
                f"Gemini output did not match the required schema: {exc}"
            ) from exc
