# AI Video Teaser Generator

Turn a long-form video into short, audience-specific teaser clips.

Upload a webinar, product demo, or training session — or paste a link to one — say which
of those it is, pick a target **audience**, a teaser **style**, and an output **shape**,
and the system uses Gemini's multimodal video understanding to find the strongest moments,
ranks them, and cuts real MP4 teasers with FFmpeg — each one labelled with an AI-written
title, hook, score, and the reason it was selected. The same call also returns a summary
of the video written for that audience, its chapters, and its topic keywords.

Built as a Cognizant Hackathon prototype.

## Status

**Working end to end.** Upload or URL ingestion, Gemini analysis, ranking, FFmpeg
rendering, and playback all run; the backend suite is 551 tests against a real Postgres,
and a separate evaluation gate scores the selection rules on every pull request.

## How it works

```text
Upload / URL  ->  FFprobe metadata  ->  Gemini video analysis  ->  candidate moments (JSON)
                                                               +  summary / chapters / keywords
              ->  schema + timestamp validation  ->  audience/style ranking
              ->  snap cut points onto nearby pauses in the speech
              ->  (optional) transcribe each clip's audio -> burned-in captions
              ->  FFmpeg trim + aspect-ratio crop or fit  ->  playable MP4 teasers
              ->  assemble the strongest beats + title cards  ->  one preview spot
```

The guiding principle:

> **Gemini chooses and explains. The backend validates and ranks. FFmpeg produces the media.**

Gemini never generates video, and its output is treated as untrusted input — every candidate
is schema-checked and every timestamp is validated against the real video duration before a
single frame is cut. Invalid candidates are discarded, never repaired.

Cut points are not taken literally. The model gives timestamps to the second and cannot
hear where its own chosen moment begins, so a clip that is right about *what* to show is
routinely a word or two wrong about where to start — and nothing downstream noticed, since
every timestamp was checked against the video's duration and none was ever checked against
its audio. Each boundary is now moved onto a nearby pause, found with FFmpeg's
`silencedetect` rather than a speech-recognition model: locating the pauses is enough to
cut between two words instead of through one, and it adds no dependency. The two ends snap
to opposite things — a clip starts where speech *resumes* and stops where it *pauses* —
and either end declines to move when there is no pause within two seconds, because a
boundary in continuous speech is one that should stay where the ranking put it.

Ranking is not just a score sort. A candidate the model rates below the `self_contained`
threshold is dropped outright — a fragment with a brilliant hook is still a fragment — and
selected moments must be separated by a minimum gap so one clip does not open on the
sentence the previous one cut through.

## Options

| Recording type | Audience | Style | Aspect ratio |
| --- | --- | --- | --- |
| Talk or Webinar (default) | General | Informative | 16:9 widescreen (default) |
| Product Demo | Developers | Promotional | 9:16 Shorts / Reels / TikTok |
| Training | Business Leaders | Emotional | 1:1 square |
| | Students | | 4:3 classic |
| | | | 4:5 portrait |

**Recording type** is not a label — it selects a pipeline profile. The tuning constants
were chosen for a talk, and applying them to the other two loses clips rather than merely
weakening them: a demo's payoff depends on the steps that set it up, and training material
is cumulative by design, so both score low on self-containment and are discarded during
validation. So the type sets the self-containment floor, the spacing between clips, the
preferred clip length, the guidance in the prompt, and whether a frame is cropped or
padded to reach the output shape — screen recordings are fitted rather than centre-cropped,
because taking 16:9 to 9:16 keeps under a third of the width and the UI text with it.
The webinar profile overrides nothing, so it is exactly the behaviour the settings are
tuned for.

Each run also accepts an optional free-text direction ("focus on the pricing discussion"),
bounded to 500 characters because it is interpolated into the model prompt.

Teasers target 30–60 seconds (20s minimum, 60s maximum). Teaser count, clip length, and
aspect ratio are per-run; audience, style, and defaults persist per account.

## Features

- **Two ways in** — direct file upload with progress, or server-side fetch from a URL
  (yt-dlp), polled until the bytes land.
- **The video as a whole** — alongside the clips, each run records an audience-tailored
  summary, the chapters the video moves through, and its topic keywords. They come from
  the same Gemini call, since it has already watched the whole video to find the moments.
  They are additional to the teasers, never a precondition: a run that returns moments and
  no summary is a run with clips and no summary, not a failed one.
- **One assembled preview** — every clip is a single moment cut to stand alone, which is
  the right shape for repurposing a talk and the wrong one for answering "what is this?".
  So each run also builds one spot from the opening seconds of several moments, joined by
  a card at the front, each moment's own title over its beat, and a card at the end. The
  cards are the point rather than decoration: they supply the context the fragments are
  missing, which is exactly the context the self-containment rules insist individual clips
  must never need. It costs no tokens — the moments, titles and summary all came from the
  analysis that already ran — so it is on by default (`ENABLE_PREVIEW`).
- **Captions** — off by default (`ENABLE_CAPTIONS`), because each clip costs one extra
  model call. Only the clip's own audio is transcribed, never the whole source: three
  clips of about a minute each rather than the two hours the analysis step had to watch.
  The words are burned into the picture for sound-off viewing and stored alongside the
  clip, so they can be read without decoding it.
- **Accounts** — Supabase Auth. Every video, run, and clip is owned by the user who made
  it, enforced in Postgres by row level security rather than by application code.
- **History** — Videos (generate again without re-uploading), Runs (every attempt and how
  it turned out, retryable with the original settings), Library (every clip across all
  runs), and a Dashboard of account totals.
- **A run that explains itself** — every run records what it discarded and why: how many
  moments the model proposed, how many survived each check, how many cut points found a
  pause to move onto, and how cleanly each finished clip begins. All of these decisions
  were always being made; none of them left the log. A run that proposed eight moments and
  kept one used to look identical to a run that kept all eight.
- **Offline rehearsal** — `AI_PROVIDER=fake` produces clearly-labelled placeholders so the
  demo can be run with no network and no API key. It is never a silent fallback.

## Evaluation

The pipeline can pass every test in the suite and still get worse. Nothing in a test run
compares the clips it produced against the clips it should have produced, so a prompt
change that damages the output is invisible until somebody watches thirty videos.

Four things address that, in increasing order of what they cost to obtain.

**What each run discards.** Free, and running on every run already. Drop reasons are
counted under stable names (`bounds`, `too_short`, `not_self_contained`, `too_close`,
`outranked`), so a demo profile dropping 60% of candidates where a webinar drops 10% is
a fact rather than a suspicion. Shown on the run detail screen and stored on the job.

**Cut quality, measured rather than judged.** After each clip is cut, the mean volume of
its first 150ms is compared with the clip's own average. A clip that opens mid-word opens
at roughly the level of the rest of it; one that opens on a pause opens well below it. The
difference is the cut. Relative, never absolute — an absolute threshold would measure the
recording's gain rather than the cut. This is the only quality signal here that needs no
annotator, no model call and no user, so a corpus accumulates whether or not anybody
labels anything.

**Labels collected from the product.** A keep/discard control on every clip. The usual way
to get ground truth is to sit a team down with a stranger's webinar; here the person who
uploaded the source judges their own content at the moment they are deciding whether to
post it, and the answer they are already forming is exactly the label. Kept clips become
annotated spans; discarded ones deliberately do not, because a prediction that matched
nothing is already counted once.

**Retrieval metrics, against baselines.** Precision/Recall/F1 at K with temporal-IoU
matching, scored beside `uniform`, `random`, `keyword` and `audio_peak`. `audio_peak` is
the one that matters — it approximates what highlight tools did before language models, so
the gap between it and this pipeline is the empirical case that watching the video is
doing work rather than decorating a heuristic. A baseline that could not be computed is
named with its reason, never omitted: an absent row reads as one the pipeline beat.

```bash
cd backend
python -m app.evaluation gate                            # the CI check, no DB or key needed
python -m app.evaluation report --job <id>  --user <id>  # what one run discarded
python -m app.evaluation score  --video <id> --user <id> # vs annotations and baselines
python -m app.evaluation ablate --video <id> --user <id> # one component off per row
```

`gate` runs on every pull request and fails the build when mean precision@3 drops below
its recorded floor, or when the pipeline stops beating a baseline it is required to beat.
It reads committed fixtures rather than re-running the pipeline, so the same commit always
scores the same and a moved number is always the diff's fault. See
[backend/evaluation/](backend/evaluation/) for how to add an asset.

**Honest status.** The committed fixtures are synthetic — hand-built so the gate's own
failure modes could be tested. They protect the selection and ranking rules against
regression and prove nothing about clip quality. `audio_peak`, the comparison that matters
most, has not yet been run against a real annotated source.

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

It needs a **throwaway database**, and refuses to guess one: every test truncates
`app.videos`, `app.jobs` and `app.teasers`, so pointing it at the database serving
`docker compose up` would delete your own uploads and runs. Both variables are required —
the admin DSN is the connection that issues the `TRUNCATE`, so letting it fall back while
the app URL was set would send the writes to a scratch database and the truncation to the
real one.

Create the scratch database once:

```bash
docker compose exec db psql -U postgres -c "create database teaser_test"
docker cp .github/ci/bootstrap.sql teaser-supabase-db:/tmp/bootstrap.sql
docker compose exec db psql -U postgres -d teaser_test -f /tmp/bootstrap.sql
docker compose run --rm -e PGDATABASE=teaser_test migrate
```

`bootstrap.sql` supplies the `auth` schema that migration 0001 expects and Supabase would
otherwise have created. Re-run the last line whenever a migration is added.

Then run the suite. Compose does not publish `db` to the host — port 5432 belongs to
Supavisor, which requires `<role>.<tenant>` — so the simplest route is a container on the
Compose network, which reaches `db` directly:

```bash
# The two passwords live in .env, not in your shell.
export APP_DB_PASSWORD=$(grep -E '^APP_DB_PASSWORD=' .env | cut -d= -f2-)
export POSTGRES_PASSWORD=$(grep -E '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)

docker compose run --rm --no-deps -v "$PWD/backend:/src" -w /src \
  -e APP_DB_PASSWORD -e POSTGRES_PASSWORD \
  -e TEST_DATABASE_URL="postgresql+psycopg://teaser_app:$APP_DB_PASSWORD@db:5432/teaser_test" \
  -e TEST_ADMIN_DSN="postgresql://postgres:$POSTGRES_PASSWORD@db:5432/teaser_test" \
  --entrypoint sh backend -c "python -m pytest"    # 551 passed

cd frontend && npm run typecheck
```

On Git Bash for Windows, prefix that with `MSYS_NO_PATHCONV=1` and write `-w //src`, or the
container paths are rewritten into Windows ones. CI does the same thing against its own
throwaway Postgres — see `.github/workflows/ci.yml` for the values it uses.

Never commit `.env`, API keys, source videos, or generated media.

## Security notes

- **Untrusted AI output** — every candidate is schema-validated and every timestamp bounded
  by the real duration before FFmpeg is invoked. Invalid candidates are discarded. The
  summary, chapters and keywords are held to the same standard and a different consequence:
  they are normalised, capped and bounded too, but a chapter that fails is dropped from a
  contents list rather than costing the run a clip.
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
| GET | `/api/jobs/{job_id}/preview/media` | The run's assembled preview, ownership-checked |
| POST | `/api/jobs/{job_id}/cancel` | Stop a running job |
| GET | `/api/teasers` | Every clip the caller owns, across all runs |
| GET | `/api/teasers/{teaser_id}/media` | The MP4 itself, ownership-checked |
| PUT | `/api/teasers/{teaser_id}/feedback` | Record a `keep`/`discard` verdict |
| DELETE | `/api/teasers/{teaser_id}/feedback` | Withdraw a verdict (204 either way) |
| GET | `/api/teasers/feedback/summary` | Kept, discarded, and still unjudged |
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
backend/app/          FastAPI app: routes, services, ai/, media/, storage/, auth, config
backend/app/evaluation/ Metrics, baselines, ablations, and the CI gate
backend/evaluation/   Annotated corpus, recorded runs, and the gate's thresholds
backend/migrations/   SQL schema, RLS policies, and the app login role
backend/tests/        pytest suite (runs against real Postgres)
frontend/src/         React + TypeScript client (Vite)
design-system/        Tokens, styles, and component guidelines used by the frontend build
docker/supabase/      Vendored self-hosted Supabase stack
docs/DECISIONS.md     Why the project is shaped the way it is
storage/              Uploaded videos and generated teasers (git-ignored)
```

`app/evaluation` imports from `app/services`, never the reverse — evaluation can be
deleted without touching a line that serves a request.

Every non-obvious choice here, and the alternatives rejected, is recorded in
[docs/DECISIONS.md](docs/DECISIONS.md). Read the relevant section before changing
something it covers.

## Author

Harsh Gautam
