# AI Video Teaser Generator

Turn a long-form video into short, audience-specific teaser clips.

Upload a webinar or talk, pick a target **audience** and a teaser **style**, and the system
uses Gemini's multimodal video understanding to find the strongest moments, ranks them, and
cuts real vertical MP4 teasers with FFmpeg — each one labelled with an AI-written title, hook,
score, and the reason it was selected.

Built as a Cognizant Hackathon prototype.

## Status

**Design phase.** The specification is complete; implementation has not started yet —
see Phase 0 in [TASKS.md](docs/TASKS.md). The setup steps below describe the intended layout
and will work once the scaffold lands.

## How it works

```text
Upload  ->  FFprobe metadata  ->  Gemini video analysis  ->  candidate moments (JSON)
        ->  schema + timestamp validation  ->  audience/style ranking
        ->  FFmpeg trim + 9:16 crop  ->  playable MP4 teasers
```

The guiding principle:

> **Gemini chooses and explains. The backend validates and ranks. FFmpeg produces the media.**

Gemini never generates video, and its output is treated as untrusted input — every candidate
is schema-checked and every timestamp is validated against the real video duration before a
single frame is cut. Invalid candidates are discarded, never repaired.

## Options

| Audience | Style |
| --- | --- |
| General | Informative |
| Developers | Promotional |
| Business Leaders | Emotional |
| Students | |

Teasers target 30–60 seconds (20s minimum, 60s maximum) and are configurable.

## Stack

React + TypeScript · FastAPI + Python · Gemini API · FFmpeg/FFprobe · SQLite · local filesystem

The architecture keeps clean seams — storage abstraction, service layer, thin routes — so
SQLite can become Postgres and local files can become S3 without touching the frontend
contract. There is deliberately no Kafka, Kubernetes, Celery, or vector database here;
see [DECISIONS.md](docs/DECISIONS.md).

## Prerequisites

- Python and Node.js
- FFmpeg and FFprobe on your `PATH` (`ffmpeg -version`, `ffprobe -version`)
- A Gemini API key

## Setup

```bash
cp .env.example .env      # then add your GEMINI_API_KEY
```

Backend (from `backend/`):

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1      # Windows; use `source .venv/bin/activate` elsewhere
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Serves the API on <http://127.0.0.1:8000>, with interactive docs at `/docs`.

Frontend (from `frontend/`):

```bash
npm install
npm run dev
```

Opens on <http://localhost:5173>.

If FFmpeg is not on your `PATH`, point `FFMPEG_PATH` and `FFPROBE_PATH` in
`.env` at the executables instead.

## Tests

```bash
cd backend  && python -m pytest      # 87 tests
cd frontend && npm run typecheck
```

Never commit `.env`, API keys, source videos, or generated media.

## API

Base path `/api`. Full contract in [API_DESIGN.md](docs/API_DESIGN.md).

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/videos/upload` | Upload a source video |
| GET | `/api/videos/{video_id}` | Video metadata and status |
| POST | `/api/videos/{video_id}/generate` | Start teaser generation |
| GET | `/api/jobs/{job_id}` | Poll processing state |
| GET | `/api/videos/{video_id}/teasers` | Generated teasers and media URLs |
| GET | `/api/health` | Health check |

Job states: `queued → validating → analyzing → ranking → generating → completed \| failed`

## Layout

```text
backend/    FastAPI app: routes, services, ai/, media/, storage/, tests
frontend/   React + TypeScript client (Vite)
docs/       Requirements, architecture, and design documents
storage/    Uploaded videos and generated teasers (git-ignored)
```

## Documentation

| Document | Contents |
| --- | --- |
| [REQUIREMENTS.md](docs/REQUIREMENTS.md) | Functional and non-functional requirements, scope, acceptance criteria |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, request flow, boundaries, extension points |
| [AI_DESIGN.md](docs/AI_DESIGN.md) | Gemini prompt inputs, candidate schema, scoring weights, validation |
| [VIDEO_PIPELINE.md](docs/VIDEO_PIPELINE.md) | FFprobe/FFmpeg pipeline, durations, output format, file layout |
| [API_DESIGN.md](docs/API_DESIGN.md) | REST contract and error envelope |
| [DECISIONS.md](docs/DECISIONS.md) | Architecture decision records |
| [SECURITY.md](docs/SECURITY.md) | Secrets, untrusted uploads, untrusted AI output, safe FFmpeg invocation |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | Local development guide |
| [TASKS.md](docs/TASKS.md) | Phased implementation roadmap |
| [DEMO_PLAN.md](docs/DEMO_PLAN.md) | Hackathon demo script and talking points |

## License

MIT — see [LICENSE](LICENSE).
