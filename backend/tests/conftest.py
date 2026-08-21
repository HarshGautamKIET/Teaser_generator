"""Test fixtures.

These tests run against a REAL Postgres, not an in-memory stand-in. That is a
deliberate cost: the security model is row level security plus a non-privileged
login role, and neither exists in SQLite. A suite that mocked them would pass
while the property it claims to protect was broken.

Start the stack first:

    docker compose up -d

Storage is still redirected to a temporary directory, and the AI provider is
still `fake`, so nothing here touches real media or the Gemini API.
"""

import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import psycopg
import pytest

_TMP = Path(tempfile.mkdtemp(prefix="teaser_tests_"))

# --- Database -------------------------------------------------------------
# Two connections, on purpose:
#   * the app connects as `teaser_app`, which is powerless until it assumes the
#     `authenticated` role -- exactly as in production.
#   * fixtures connect as `postgres` to create users and truncate between tests,
#     which the app role deliberately cannot do.
# Host port 5432 is Supavisor, so the app user needs its tenant suffix.
APP_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://teaser_app.teaser:{pw}@localhost:5432/postgres",
)
ADMIN_DSN = os.environ.get(
    "TEST_ADMIN_DSN", "postgresql://postgres.teaser:{pw}@localhost:5432/postgres"
)


def _read_env_file() -> dict[str, str]:
    """Read the repository-root .env without importing app config."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    values: dict[str, str] = {}
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


_ENV = _read_env_file()
_APP_PW = os.environ.get("APP_DB_PASSWORD") or _ENV.get("APP_DB_PASSWORD", "")
_PG_PW = os.environ.get("POSTGRES_PASSWORD") or _ENV.get("POSTGRES_PASSWORD", "")

if "{pw}" in APP_DB_URL:
    APP_DB_URL = APP_DB_URL.format(pw=_APP_PW)
if "{pw}" in ADMIN_DSN:
    ADMIN_DSN = ADMIN_DSN.format(pw=_PG_PW)

os.environ["DATABASE_URL"] = APP_DB_URL
os.environ["UPLOAD_DIR"] = f"{_TMP.as_posix()}/uploads"
os.environ["GENERATED_DIR"] = f"{_TMP.as_posix()}/generated"
os.environ["MAX_UPLOAD_MB"] = "1"
os.environ["ALLOWED_VIDEO_EXTENSIONS"] = ".mp4,.mov,.mkv,.webm"
os.environ["GEMINI_API_KEY"] = "test-key-not-real"
# Belt and braces: no test may ever reach the real Gemini API.
os.environ["AI_PROVIDER"] = "fake"
os.environ["LOG_LEVEL"] = "WARNING"
# Short limits keep the fixture videos small and the suite fast.
os.environ["TEASER_MIN_SECONDS"] = "2"
os.environ["TEASER_MAX_SECONDS"] = "5"
os.environ["MAX_SOURCE_DURATION_SECONDS"] = "60"
# The fixture video is eight seconds long. The production default of fifteen
# seconds between clips is longer than the whole source, so it is switched off
# here rather than scaled: these tests are about ranking and counting, and the
# separation rule has its own tests in test_self_contained.py which set the gap
# explicitly instead of inheriting it.
os.environ["TEASER_MIN_GAP_SECONDS"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import AuthUser, get_current_user  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402

SETTINGS = get_settings()
SOURCE_SECONDS = 8

APP_TABLES = ("app.teasers", "app.jobs", "app.videos")

# Fixed for the session so helpers can reference an owner without threading a
# fixture through every call. Random per run so concurrent runs cannot collide.
OWNER_ID = str(uuid.uuid4())
OTHER_ID = str(uuid.uuid4())


def _database_ready() -> str | None:
    """None if the database is usable, otherwise why it is not."""
    if not _APP_PW or not _PG_PW:
        return (
            "APP_DB_PASSWORD / POSTGRES_PASSWORD not found. Copy .env.example to "
            ".env and fill them in (see `cd docker/supabase && sh run.sh secrets`)."
        )
    try:
        with psycopg.connect(ADMIN_DSN, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("select to_regclass('app.videos')")
                if cur.fetchone()[0] is None:
                    return "Schema `app` is missing. Run: docker compose up -d migrate"
    except Exception as exc:  # noqa: BLE001
        return f"Cannot reach Postgres at {ADMIN_DSN.split('@')[-1]}: {exc}"
    return None


_DB_PROBLEM = _database_ready()

def pytest_collection_modifyitems(config, items):
    """Skip the whole suite, with one usable message, when the DB is not up.

    A module-level `pytestmark` in conftest.py only marks tests defined in
    conftest.py itself, so it would leave every other file to fail with a raw
    connection error instead.

    On CI this becomes fatal rather than a skip. A developer without the stack
    running wants an explanation and their prompt back; an automated run that
    skips all of it and reports success is a green tick over nothing.
    """
    if _DB_PROBLEM is None:
        return
    if os.environ.get("CI"):
        raise pytest.UsageError(f"Database not usable on CI: {_DB_PROBLEM}")
    skip = pytest.mark.skip(reason=_DB_PROBLEM)
    for item in items:
        item.add_marker(skip)


def _tool_available(path: str) -> bool:
    return Path(path).is_file() or shutil.which(path) is not None


requires_ffmpeg = pytest.mark.skipif(
    not (_tool_available(SETTINGS.ffmpeg_path) and _tool_available(SETTINGS.ffprobe_path)),
    reason="FFmpeg/FFprobe not available (set FFMPEG_PATH/FFPROBE_PATH in .env)",
)


@pytest.fixture(scope="session")
def settings():
    return SETTINGS


@pytest.fixture(scope="session")
def admin_conn():
    """Privileged connection used only to set up and tear down fixtures."""
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        yield conn


@pytest.fixture(scope="session")
def test_users(admin_conn) -> dict[str, str]:
    """Two persistent auth users, so tests can prove isolation between them.

    Created directly in auth.users rather than through the Auth API: the suite
    needs a user id to own rows, not a working password grant.
    """
    users = {"owner": OWNER_ID, "other": OTHER_ID}
    with admin_conn.cursor() as cur:
        for label, user_id in users.items():
            cur.execute(
                """
                insert into auth.users (id, email)
                values (%s, %s)
                on conflict (id) do nothing
                """,
                (user_id, f"pytest-{label}-{user_id[:8]}@example.test"),
            )
    yield users

    with admin_conn.cursor() as cur:
        # Cascades to app.* through the user_id foreign keys.
        cur.execute(
            "delete from auth.users where id = any(%s)", (list(users.values()),)
        )


@pytest.fixture(autouse=True)
def clean_tables(admin_conn):
    """Empty the app tables before each test.

    TRUNCATE, not a schema rebuild: the RLS policies, grants, and roles are
    owned by migrations/*.sql and must be the ones under test, not a fresh
    approximation built by create_all().
    """
    with admin_conn.cursor() as cur:
        cur.execute(f"truncate {', '.join(APP_TABLES)} cascade")
    yield


@pytest.fixture(scope="session")
def sample_video_path(settings) -> Path:
    """A real, small MP4 generated once per test session."""
    path = _TMP / "sample_source.mp4"
    if path.is_file():
        return path
    subprocess.run(
        [
            settings.ffmpeg_path, "-y",
            "-f", "lavfi", "-i", f"testsrc=size=640x360:rate=15:duration={SOURCE_SECONDS}",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={SOURCE_SECONDS}",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(path),
        ],
        capture_output=True, text=True, check=True, timeout=120,
    )
    return path


@pytest.fixture(scope="session")
def video_bytes(sample_video_path) -> bytes:
    return sample_video_path.read_bytes()


def _client_for(user_id: str, monkeypatch) -> TestClient:
    """A TestClient authenticated as `user_id`.

    Token verification is replaced rather than exercised: minting real ES256
    tokens would require the Auth service's private key, and would test GoTrue
    rather than this application. `verify_token` itself is covered directly in
    test_auth.py. What matters here is that every request below carries a real
    user identity all the way into the RLS-scoped session.
    """
    from app.api.routes import videos

    scheduled: list[tuple] = []
    monkeypatch.setattr(
        videos, "run_job_in_background", lambda *args: scheduled.append(args)
    )

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthUser(
        id=user_id, email=f"{user_id[:8]}@example.test", role="authenticated"
    )

    client = TestClient(app)
    client.scheduled_jobs = scheduled
    client.user_id = user_id
    return client


@pytest.fixture
def client(test_users, monkeypatch):
    """Signed in as the owner. The default caller for most tests."""
    with _client_for(test_users["owner"], monkeypatch) as test_client:
        yield test_client


@pytest.fixture
def other_client(test_users, monkeypatch):
    """Signed in as a different user, for cross-account isolation tests."""
    with _client_for(test_users["other"], monkeypatch) as test_client:
        yield test_client


@pytest.fixture
def anonymous_client(monkeypatch):
    """No dependency override: exercises the real 401 path."""
    from app.api.routes import videos

    monkeypatch.setattr(videos, "run_job_in_background", lambda *args: None)
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def uploaded_video(client, video_bytes):
    """Upload the sample video and return the parsed response body."""
    response = client.post(
        "/api/videos/upload",
        files={"file": ("webinar.mp4", video_bytes, "video/mp4")},
    )
    assert response.status_code == 201, response.text
    return response.json()
