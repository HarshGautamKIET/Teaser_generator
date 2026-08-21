"""Application configuration, loaded from environment variables.

All settings come from the repository-root `.env` file (see `.env.example`).
Secrets are never hardcoded.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
ENV_FILE = REPO_ROOT / ".env"


def _resolve(raw: str) -> Path:
    """Resolve a configured path against the repo root so behaviour does not
    depend on the current working directory."""
    path = Path(raw)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",          # .env also holds frontend (VITE_*) keys
        case_sensitive=False,
    )

    # --- AI ---
    # "gemini" for real analysis, "fake" for offline rehearsal (never a silent
    # fallback -- it must be selected deliberately).
    ai_provider: str = "gemini"
    gemini_api_key: str = ""
    # Optional comma-separated pool, tried in order. When a key hits its quota
    # the next one takes over for the rest of the process's life. The single
    # key above is appended to whatever is listed here, so setting only that
    # one keeps working unchanged.
    gemini_api_keys: str = ""
    gemini_model: str = "gemini-3.6-flash"

    # --- Server ---
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"

    # --- Supabase ---
    # Base URL of the Supabase API gateway. Inside docker compose this is the
    # service name (http://api-gw:8000); from the host it is localhost:8000.
    supabase_url: str = "http://localhost:8000"

    # --- Database ---
    # Supabase Postgres, connected as `teaser_app` -- a NOBYPASSRLS role that
    # holds no privileges of its own and must SET ROLE authenticated to read
    # anything (migrations/0002_app_role.sql). Never point this at `postgres`:
    # that role bypasses RLS and would make every user's rows visible.
    database_url: str = (
        "postgresql+psycopg://teaser_app:CHANGE_ME@localhost:5432/postgres"
    )

    # --- Storage ---
    storage_backend: str = "local"
    upload_dir: str = "./storage/uploads"
    generated_dir: str = "./storage/generated"

    # --- Upload validation (FR-002) ---
    max_upload_mb: int = 500
    max_source_duration_seconds: int = 7200
    allowed_video_extensions: str = ".mp4,.mov,.mkv,.webm"

    # --- Teaser output (VIDEO_PIPELINE.md) ---
    teaser_min_seconds: int = 20
    teaser_preferred_min_seconds: int = 30
    teaser_preferred_max_seconds: int = 60
    teaser_max_seconds: int = 60
    teaser_count: int = 3
    candidate_count: int = 8

    # A teaser has to stand on its own. Candidates the model scores below this
    # on `self_contained` are discarded outright rather than merely ranked
    # lower -- a fragment with a brilliant hook is still a fragment.
    teaser_min_self_contained: float = 7.0
    # Minimum silence between two selected moments. Non-overlap alone still
    # allows clip 2 to begin on the sentence clip 1 ended in the middle of.
    teaser_min_gap_seconds: int = 15
    # Longest run direction a caller may supply. Bounded because it is
    # interpolated into a model prompt.
    max_custom_prompt_chars: int = 500
    # Fallback for a run that does not choose one. Widescreen: most sources are
    # already 16:9, so the default crops nothing away.
    teaser_aspect_ratio: str = "16:9"
    enable_captions: bool = False

    # --- FFmpeg ---
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"

    # ------------------------------------------------------------------
    # Derived values
    # ------------------------------------------------------------------
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_extensions(self) -> set[str]:
        return {
            e.strip().lower() if e.strip().startswith(".") else f".{e.strip().lower()}"
            for e in self.allowed_video_extensions.split(",")
            if e.strip()
        }

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def upload_path(self) -> Path:
        return _resolve(self.upload_dir)

    @property
    def generated_path(self) -> Path:
        return _resolve(self.generated_dir)

    @property
    def supabase_jwks_url(self) -> str:
        """Where access-token signing keys are published (app/auth.py)."""
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
