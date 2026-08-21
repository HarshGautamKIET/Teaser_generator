# AI Video Teaser Generator

Turn a long-form video into short, audience-specific teaser clips.

Upload a webinar or talk — or paste a link to one — pick a target **audience**, a teaser
**style**, and an output **shape**, and the system uses Gemini's multimodal video
understanding to find the strongest moments, ranks them, and cuts real MP4 teasers with
FFmpeg — each one labelled with an AI-written title, hook, score, and the reason it was
selected.

Built as a Cognizant Hackathon prototype.

## Status

**Working end to end.** Upload or URL ingestion, Gemini analysis, ranking, FFmpeg
rendering, and playback all run; the backend suite is 290 tests against a real Postgres.

## How it works

```text
Upload / URL  ->  FFprobe metadata  ->  Gemini video analysis  ->  candidate moments (JSON)
              ->  schema + timestamp validation  ->  audience/style ranking
              ->  FFmpeg trim + aspect-ratio crop  ->  playable MP4 teasers
```

The guiding principle:

> **Gemini chooses and explains. The backend validates and ranks. FFmpeg produces the media.**

Gemini never generates video, and its output is treated as untrusted input — every candidate
is schema-checked and every timestamp is validated against the real video duration before a
single frame is cut. Invalid candidates are discarded, never repaired.

Ranking is not just a score sort. A candidate the model rates below the `self_contained`
threshold is dropped outright — a fragment with a brilliant hook is still a fragment — and
selected moments must be separated by a minimum gap so one clip does not open on the
sentence the previous one cut through.

## Options

| Audience | Style | Aspect ratio |
| --- | --- | --- |
| General | Informative | 16:9 widescreen (default) |
| Developers | Promotional | 9:16 Shorts / Reels / TikTok |
| Business Leaders | Emotional | 1:1 square |
| Students | | 4:3 classic |
| | | 4:5 portrait |

Each run also accepts an optional free-text direction ("focus on the pricing discussion"),
bounded to 500 characters because it is interpolated into the model prompt.

Teasers target 30–60 seconds (20s minimum, 60s maximum). Teaser count, clip length, and
aspect ratio are per-run; audience, style, and defaults persist per account.

## Features

- **Two ways in** — direct file upload with progress, or server-side fetch from a URL
  (yt-dlp), polled until the bytes land.
- **Accounts** — Supabase Auth. Every video, run, and clip is owned by the user who made
  it, enforced in Postgres by row level security rather than by application code.
- **History** — Videos (generate again without re-uploading), Runs (every attempt and how
  it turned out, retryable with the original settings), Library (every clip across all
  runs), and a Dashboard of account totals.
- **Offline rehearsal** — `AI_PROVIDER=fake` produces clearly-labelled placeholders so the
  demo can be run with no network and no API key. It is never a silent fallback.

## Stack

React 19 + TypeScript (Vite) · FastAPI + Python · Gemini API · FFmpeg/FFprobe ·
Supabase (Postgres, Auth) · yt-dlp · Docker Compose

The architecture keeps clean seams — storage abstraction, service layer, thin routes, a
provider interface in front of Gemini — so local files can become S3 without touching the
frontend contract. There is deliberately no Kafka, Kubernetes, Celery, or vector database
here; jobs run in-process and interrupted ones are reconciled to `failed` on startup.

## Prerequisites

- Docker and Docker Compose
- A Gemini API key (skip with `AI_PROVIDER=fake`)
- For running outside Docker: Python, Node.js, and FFmpeg/FFprobe on your `PATH`
  (`ffmpeg -version`, `ffprobe -version`)

## Setup

**Full walkthrough for a fresh machine: [INSTALL.md](INSTALL.md)** — prerequisites, the
Supabase key generation, the three config values whose defaults do not work, VS Code setup,
and troubleshooting. The short version follows.

The Supabase stack in `docker/supabase` is vendored from the official self-hosted release
and configured by its **own** `.env`, which is generated, not committed:

```bash
cd docker/supabase
cp .env.example .env
sh utils/generate-keys.sh --update-env
sh utils/add-new-auth-keys.sh --update-env
sh run.sh secrets          # prints the values to copy into the repo-root .env
```

Then set `POOLER_TENANT_ID=teaser` and `ENABLE_EMAIL_AUTOCONFIRM=true` in that file — the
stock defaults reject the backend's database connection and make sign-up impossible without
an SMTP sender.

Then, at the repository root:

```bash
cp .env.example .env       # add GEMINI_API_KEY and the Supabase values above
docker compose up -d --build
```

That brings up Supabase, applies `backend/migrations/*.sql` (schema, RLS policies, and the
non-privileged `teaser_app` login role), and starts the API and the frontend.

| Service | URL |
| --- | --- |
| Frontend | <http://localhost:3001> |
| API (docs at `/docs`) | <http://localhost:8001> |
| Supabase Studio | <http://localhost:8000> |

### Running the app outside Docker

Supabase still has to be up (`docker compose up -d db api-gw auth rest migrate`).

Backend (from `backend/`):

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1      # Windows; use `source .venv/bin/activate` elsewhere
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend (from `frontend/`):

```bash
npm install
npm run dev                     # http://localhost:5173
```

Note the `.teaser` suffix on the database username in `.env` when connecting from the host:
port 5432 is published by Supavisor, which requires `<role>.<tenant>`. Inside Compose the
backend reaches Postgres directly and uses the bare role name.

If FFmpeg is not on your `PATH`, point `FFMPEG_PATH` and `FFPROBE_PATH` at the executables.

## Tests

The backend suite runs against a **real** Postgres, not an in-memory stand-in — the
security model is RLS plus a powerless login role, and neither exists in SQLite. Storage is
redirected to a temp directory and the AI provider is `fake`, so nothing touches real media
or the Gemini API.

```bash
docker compose up -d                     # Postgres must be running
cd backend  && python -m pytest          # 290 passed
cd frontend && npm run typecheck
```

Never commit `.env`, API keys, source videos, or generated media.

## Security notes

- **Untrusted AI output** — every candidate is schema-validated and every timestamp bounded
  by the real duration before FFmpeg is invoked. Invalid candidates are discarded.
- **SSRF** — URL ingestion checks the address at `connect()`, not at parse time, so
  redirects to link-local metadata endpoints and DNS rebinding cannot get past it. The
  check is thread-local, because the app legitimately dials private addresses (the
  database) all the time.
- **Tenant isolation** — the backend logs in as `teaser_app`, a `NOBYPASSRLS` role with no
  privileges of its own that must `SET ROLE authenticated` to read anything. Access tokens
  are verified locally against Supabase's published JWKS.
- **Keys** — `GEMINI_API_KEYS` accepts a pool tried in order, so a key that hits its quota
  hands off to the next rather than failing the run.

## API

Base path `/api`. Every endpoint except `/api/health` requires a `Bearer` access token.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/videos/upload` | Upload a source video |
| POST | `/api/videos/from-url` | Queue a server-side fetch from a URL (202) |
| GET | `/api/videos` | Source videos owned by the caller |
| GET | `/api/videos/{video_id}` | Video metadata and status |
| POST | `/api/videos/{video_id}/generate` | Start teaser generation (202) |
| GET | `/api/videos/{video_id}/teasers` | Teasers for a video, latest run or `?job_id=` |
| GET | `/api/jobs` | Every run, optionally `?video_id=` |
| GET | `/api/jobs/{job_id}` | Poll processing state |
| POST | `/api/jobs/{job_id}/cancel` | Stop a running job |
| GET | `/api/teasers` | Every clip the caller owns, across all runs |
| GET | `/api/teasers/{teaser_id}/media` | The MP4 itself, ownership-checked |
| GET | `/api/health` | Health check |

Video states: `fetching → uploaded → ready \| failed`

Job states: `queued → validating → analyzing → ranking → generating → completed \| failed \| cancelled`

Cancellation is cooperative: the run is marked `cancelled` immediately, and the worker stops
at its next stage boundary. An analysis call already in flight has to return first, so a
cancel during analysis takes effect before any clip is cut rather than instantly. Clips
already rendered for a cancelled run are deleted — their rows are only written once the
whole set succeeds, so nothing would reference the files.

Errors share one envelope: `{"error": {"code": ..., "message": ...}}`.

## Layout

```text
backend/app/       FastAPI app: routes, services, ai/, media/, storage/, auth, config
backend/migrations/ SQL schema, RLS policies, and the app login role
backend/tests/     pytest suite (runs against real Postgres)
frontend/src/      React + TypeScript client (Vite)
design-system/     Tokens, styles, and component guidelines used by the frontend build
docker/supabase/   Vendored self-hosted Supabase stack
storage/           Uploaded videos and generated teasers (git-ignored)
```

## Author

Harsh Gautam
