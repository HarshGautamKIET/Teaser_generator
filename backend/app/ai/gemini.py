"""Gemini multimodal video analysis (ADR-004).

Uploads the video through the Files API, asks for structured candidates, and
returns exactly what the model said. Validation happens downstream.
"""

import json
import logging
import time

from app.ai.base import AIError, AIProvider, AnalysisRequest, RawCandidateList
from app.ai.keyring import KeyRing, NoKeysRemainingError, is_quota_exhausted
from app.ai.prompt import SYSTEM_INSTRUCTION, build_prompt

logger = logging.getLogger(__name__)

FILE_ACTIVATION_TIMEOUT_SECONDS = 600
FILE_POLL_INTERVAL_SECONDS = 3
ANALYSIS_TEMPERATURE = 0.4


class GeminiProvider(AIProvider):
    """Gemini analysis, backed by a pool of keys.

    An analysis is one logical operation made of several calls -- upload, poll,
    generate -- and any of them can be the one that hits the quota. So the
    retry wraps the whole operation rather than an individual call: switching
    keys mid-analysis would leave the uploaded file owned by a key the next
    request no longer uses.
    """

    def __init__(self, keyring: KeyRing, model: str) -> None:
        if not len(keyring):
            raise AIError(
                "GEMINI_API_KEY is not set. Add it to .env to enable AI analysis."
            )
        self._keyring = keyring
        self._model = model
        self._clients: dict[str, object] = {}

    @property
    def name(self) -> str:
        # Position, never key material -- this reaches the API response.
        return f"gemini:{self._model} ({self._keyring.describe()})"

    # ------------------------------------------------------------------
    def _get_client(self, api_key: str):
        """One client per key, created lazily so import never needs credentials."""
        client = self._clients.get(api_key)
        if client is None:
            from google import genai

            client = genai.Client(api_key=api_key)
            self._clients[api_key] = client
        return client

    def _upload_and_activate(self, client, request: AnalysisRequest):
        """Upload the video and wait until Gemini has finished processing it.

        Quota failures are re-raised bare rather than wrapped in AIError, so the
        retry loop above can still recognise them.
        """
        from google.genai import types

        logger.info("Uploading %s to Gemini Files API", request.video_path.name)
        try:
            uploaded = client.files.upload(file=request.video_path)
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
