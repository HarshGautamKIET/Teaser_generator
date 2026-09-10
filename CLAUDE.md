# AI Video Teaser Generator — project instructions

Long-form video in, short audience-specific teaser clips out. React + FastAPI +
Gemini + FFmpeg + Supabase. See [README.md](README.md) for what it does and
[INSTALL.md](INSTALL.md) for how to run it.

## The decisions log is not optional

**[docs/DECISIONS.md](docs/DECISIONS.md) is updated in the same commit as any
substantive change.** Read the section covering whatever you are about to touch
before you touch it, and add or amend an entry before you finish.

Substantive means: a new capability or dependency, a schema or API change, a
tuned constant or threshold, a choice where a reasonable person would have
chosen otherwise, or a deliberate decision *not* to do something the task
implies. Not: typos, renames, formatting.

Every entry carries four things — **Decision**, **Why**, **Alternatives
rejected**, **What this costs**. An entry with no cost stated is usually one
whose cost has not been found yet. Write the reason, not the rule: restating
what the code does is not an entry.

If a change contradicts an existing entry, amend that entry and **say so in your
reply** — a reversal is itself a decision. If a change was not substantive, say
that no entry was needed, so the reader knows the file was considered.

## The system in five lines

Gemini chooses and explains; the backend validates and ranks; FFmpeg produces
the media. Gemini never generates video, and its output is untrusted input.
Every candidate is schema-checked and every timestamp bounded against the real
FFprobe duration before a frame is cut. Invalid candidates are **dropped, never
repaired** — a silently corrected hallucination destroys the drop-rate signal
that says the prompt is broken.

## Hard rules

1. **Nothing unvalidated reaches FFmpeg.** Every AI-supplied timestamp passes
   `analysis_service` and `media_service.validate_clip_window` first.
2. **`AI_PROVIDER=fake` is never a silent fallback.** A missing key fails the
   run. Fabricated output that looks real is worse than an error.
3. **Never connect as `postgres`.** The app is `teaser_app` — `NOBYPASSRLS`, no
   privileges of its own — and must `SET ROLE authenticated`. Fail closed.
4. **Subprocesses take argument lists, never a shell**, and always a timeout.
5. **A missing row belongs to nobody: 404, not 403.** A 403 confirms the id is
   real.
6. **Do not point the test suite at the development database.** Every test
   truncates `app.videos`, `app.jobs`, `app.teasers` and `app.teaser_feedback`.

## Verification

Nothing is "working" without the command and its output. Both:

```bash
# Backend — real Postgres, throwaway database. See README for the full setup.
docker compose run --rm --no-deps -v "$PWD/backend:/src" -w /src \
  -e APP_DB_PASSWORD -e POSTGRES_PASSWORD \
  -e TEST_DATABASE_URL="postgresql+psycopg://teaser_app:$APP_DB_PASSWORD@db:5432/teaser_test" \
  -e TEST_ADMIN_DSN="postgresql://postgres:$POSTGRES_PASSWORD@db:5432/teaser_test" \
  --entrypoint sh backend -c "python -m pytest"

cd frontend && npm run typecheck
```

On Git Bash for Windows, prefix with `MSYS_NO_PATHCONV=1` and write `-w //src`.

If a change touched selection, ranking, or the prompt, also run the gate — the
test suite can pass in full while the clips get worse:

```bash
cd backend && python -m app.evaluation gate
```

A new migration has to be applied to the test database before the suite will
pass: `docker compose run --rm -e PGDATABASE=teaser_test migrate`.

## Conventions

- Comments explain **why**, at the density of the surrounding file. This
  codebase comments the reasoning behind a decision and not the mechanics of the
  line below it. Match that; do not add a comment restating an obvious call.
- Migrations are idempotent and numbered. The schema is owned by
  `backend/migrations/*.sql`, never by `create_all()` — RLS, grants and triggers
  have no ORM equivalent, and `app/models.py` must be kept in step by hand.
- New nullable columns mean "use the server default". Do not copy the default in
  at write time: a run recorded before a setting existed must stay
  distinguishable from one that chose that value.
- `app/evaluation` imports from `app/services`, never the reverse. Evaluation
  can be deleted without touching a line that serves a request.
- No emoji in code, docs, or commit messages. No `Co-Authored-By` lines.
