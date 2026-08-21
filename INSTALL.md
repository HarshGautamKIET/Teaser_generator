# Installation Guide

Getting the AI Video Teaser Generator running from scratch on a new laptop with VS Code.

Everything runs in Docker. You do not need Python, Node.js, or FFmpeg installed on the host
unless you want to run the backend or frontend outside containers — [that path is covered at
the end](#appendix-a-running-outside-docker).

Budget 20–30 minutes, most of it waiting on image pulls.

---

## Contents

1. [What gets installed](#1-what-gets-installed)
2. [Prerequisites](#2-prerequisites)
3. [Clone the repository](#3-clone-the-repository)
4. [Configure Supabase](#4-configure-supabase)
5. [Configure the application](#5-configure-the-application)
6. [Start everything](#6-start-everything)
7. [Create an account and run it](#7-create-an-account-and-run-it)
8. [VS Code setup](#8-vs-code-setup)
9. [Running the tests](#9-running-the-tests)
10. [Day-to-day commands](#10-day-to-day-commands)
11. [Troubleshooting](#11-troubleshooting)
12. [Appendix A: Running outside Docker](#appendix-a-running-outside-docker)
13. [Appendix B: Full reset](#appendix-b-full-reset)

---

## 1. What gets installed

Two Docker Compose stacks that come up together as one:

- **Supabase** (self-hosted, vendored in `docker/supabase`) — Postgres, Auth, the API
  gateway, Studio, and supporting services.
- **This application** — the FastAPI backend and the React frontend, plus a one-shot
  `migrate` job that applies the SQL schema.

When it is up you will have:

| Service | URL | Notes |
| --- | --- | --- |
| Frontend | <http://localhost:3001> | The app itself |
| Backend API | <http://localhost:8001> | Interactive docs at `/docs` |
| Supabase Studio | <http://localhost:8000> | Basic-auth login, see step 4 |
| Postgres (Supavisor) | `localhost:5432` | Session mode |
| Postgres (pooled) | `localhost:6543` | Transaction mode |

Ports 3001, 5432, 6543, 8000, and 8001 must be free. See
[Troubleshooting](#port-is-already-allocated) if one is not.

---

## 2. Prerequisites

Install these first.

### Docker Desktop (required)

<https://www.docker.com/products/docker-desktop/>

On Windows, enable the WSL 2 backend when prompted — it is the default and it is
considerably faster than Hyper-V. Give Docker at least **6 GB of RAM** in
*Settings → Resources*; the Supabase stack alone runs a dozen containers.

Verify:

```bash
docker --version
docker compose version
```

Docker Desktop must be **running** before any command in this guide. On Windows it does not
start with the machine unless you enable that in settings.

### Git (required)

<https://git-scm.com/downloads>

On Windows this also installs **Git Bash**, which you need — the Supabase setup scripts are
POSIX shell and use `openssl`. PowerShell and CMD cannot run them.

Verify (in Git Bash):

```bash
git --version
openssl version
```

### VS Code (required)

<https://code.visualstudio.com/>

### A Gemini API key (recommended)

Get one free at <https://aistudio.google.com/apikey>.

You can skip this and set `AI_PROVIDER=fake` instead, which produces clearly-labelled
placeholder teasers so you can exercise the whole pipeline offline. Real analysis needs a
real key.

### Not required

Python, Node.js, and FFmpeg are all baked into the images. Install them only for
[Appendix A](#appendix-a-running-outside-docker).

---

## 3. Clone the repository

**Use Git Bash on Windows**, not PowerShell, for every shell command in this guide.

```bash
git clone <repository-url> Teaser_generator
cd Teaser_generator
```

Confirm you are in the right place — this should list `docker-compose.yml`, `backend`,
`frontend`, and `docker`:

```bash
ls
```

---

## 4. Configure Supabase

Supabase has its **own** `.env`, separate from the application's. It is not committed —
it holds generated secrets — so you create it now.

### 4.1 Create the file

```bash
cd docker/supabase
cp .env.example .env
```

### 4.2 Generate the secrets

Two scripts, in this order. The second reads `JWT_SECRET` written by the first.

```bash
sh utils/generate-keys.sh --update-env
sh utils/add-new-auth-keys.sh --update-env
```

The first generates the database password, dashboard password, and JWT secret. The second
generates the EC key pair and the publishable/secret API keys.

`add-new-auth-keys.sh` needs Node.js 16+ **or** Docker. If you have no Node it falls back to
`node:22-alpine` and pulls it automatically — this is normal and takes a minute.

### 4.3 Edit three values

**Do not skip this.** The stock `.env.example` defaults do not work with this application.
Open `docker/supabase/.env` and change these three lines:

| Set this | To this | Why |
| --- | --- | --- |
| `POOLER_TENANT_ID` | `teaser` | The backend connects as `teaser_app.teaser`. The pooler rejects a connection whose tenant suffix does not match this, with a confusing `no tenant id` error. |
| `ENABLE_EMAIL_AUTOCONFIRM` | `true` | The self-hosted stack ships without an SMTP sender. Left at `false`, sign-up succeeds but the confirmation email is never sent, and **you can never log in**. |
| `SITE_URL` | `http://localhost:5173` | Default auth redirect target. |

In VS Code: `Ctrl+P`, type `supabase/.env`, then `Ctrl+F` for each key.

Leave everything else as generated.

### 4.4 Note the values you need next

```bash
sh run.sh secrets
```

This prints, among others:

```
POSTGRES_PASSWORD=...
DASHBOARD_PASSWORD=...
SUPABASE_PUBLISHABLE_KEY=...
SUPABASE_SECRET_KEY=...
```

Keep this terminal open — you need `POSTGRES_PASSWORD` and `SUPABASE_PUBLISHABLE_KEY` in the
next step. `DASHBOARD_PASSWORD` is what logs you into Supabase Studio later, with username
`supabase`.

`SUPABASE_SECRET_KEY` is **not** used by this application. Never put it in the root `.env`.

---

## 5. Configure the application

Back at the repository root:

```bash
cd ../..
cp .env.example .env
```

Open `.env` in VS Code and fill in five values.

### 5.1 Gemini

```ini
GEMINI_API_KEY=your-key-from-ai-studio
```

Optionally set `GEMINI_API_KEYS` to a comma-separated pool — when one key hits its quota the
next takes over for the life of the process. `GEMINI_API_KEY` is appended automatically, so
setting only that one is fine.

No key? Set `AI_PROVIDER=fake` and leave the key blank.

### 5.2 Database passwords

```ini
POSTGRES_PASSWORD=<paste POSTGRES_PASSWORD from `sh run.sh secrets`>
APP_DB_PASSWORD=<generate a new one, see below>
```

`POSTGRES_PASSWORD` **must match** the value in `docker/supabase/.env` exactly — the
`migrate` job connects as the superuser to create the schema.

`APP_DB_PASSWORD` is new and yours to choose. It is the password for `teaser_app`, the
restricted role the backend actually logs in as. Generate one:

```bash
openssl rand -hex 24
```

### 5.3 Supabase publishable key

```ini
VITE_SUPABASE_PUBLISHABLE_KEY=<paste SUPABASE_PUBLISHABLE_KEY from `sh run.sh secrets`>
```

This one is safe in the browser bundle — it identifies the project, not the user. Anything
prefixed `VITE_` is compiled into the frontend and shipped to the client, so never put a
secret key here.

### 5.4 Leave the rest alone

The defaults for ports, storage paths, upload limits, and teaser lengths all work as-is. In
Compose, `DATABASE_URL` and `SUPABASE_URL` are overridden with internal service addresses,
so the values in `.env` only matter if you run outside Docker.

### 5.5 Checklist

Before continuing, confirm all five:

- [ ] `GEMINI_API_KEY` set (or `AI_PROVIDER=fake`)
- [ ] `POSTGRES_PASSWORD` set, and identical to the one in `docker/supabase/.env`
- [ ] `APP_DB_PASSWORD` set to a fresh random value
- [ ] `VITE_SUPABASE_PUBLISHABLE_KEY` set
- [ ] `docker/supabase/.env` has `POOLER_TENANT_ID=teaser` and `ENABLE_EMAIL_AUTOCONFIRM=true`

---

## 6. Start everything

From the repository root:

```bash
docker compose up -d --build
```

First run pulls roughly 15 images and builds two — expect **10 to 20 minutes** depending on
your connection. Later runs take seconds.

The order matters and Compose handles it: Postgres comes up and passes its healthcheck, the
`migrate` job applies `backend/migrations/*.sql` and exits, then the backend starts.

### Verify

```bash
docker compose ps
```

Every Supabase service should read `Up (healthy)`; `backend` and `frontend` read `Up`. The
`migrate` service will **not** be listed — it runs to completion and exits, which is
correct.

Then check the API answers:

```bash
curl http://localhost:8001/api/health
```

```
{"status":"ok"}
```

And open <http://localhost:3001> — you should see the login screen.

If `migrate` failed, nothing else will work. Read its output:

```bash
docker compose logs migrate
```

---

## 7. Create an account and run it

1. Open <http://localhost:3001>.
2. Click **Sign up**, enter any email address and a password of at least 8 characters.
   The address is never contacted — with `ENABLE_EMAIL_AUTOCONFIRM=true` the account is
   live immediately.
3. If you are dropped back to the login form with "Check your email to confirm the
   account", `ENABLE_EMAIL_AUTOCONFIRM` is still `false`. Fix it in
   `docker/supabase/.env`, then `docker compose restart auth`, and sign up again.
4. Log in.

Then, for a first run:

1. **Source Video** — drop in an MP4, or paste a URL and let the server fetch it. Start
   with something short; a 5–10 minute talk analyses far faster than a 2-hour webinar.
2. **Audience & Style** — pick who the clips are for, the output shape, and optionally type
   a direction like "focus on the pricing discussion".
3. **Generate Teasers** — the progress panel walks through validating, analyzing, ranking,
   and generating.
4. **Teasers** — ranked clips, each with its title, hook, score, and the reason it was
   picked. They are playable in place.

Generated files live in the `teaser-media` Docker volume, not in your working tree.

---

## 8. VS Code setup

```bash
code .
```

### Extensions worth having

| Extension | ID | For |
| --- | --- | --- |
| Python | `ms-python.python` | Backend editing, test running |
| Pylance | `ms-python.vscode-pylance` | Type checking |
| Docker | `ms-azuretools.vscode-docker` | Container and log inspection from the sidebar |
| ESLint | `dbaeumer.vscode-eslint` | Frontend linting |
| Tailwind / CSS IntelliSense | `bradlc.vscode-tailwindcss` | Design-system tokens |

Install from the Extensions panel (`Ctrl+Shift+X`).

### Editing with the stack in Docker

You do not need a local interpreter to run the app — but IntelliSense will not resolve
`fastapi`, `sqlalchemy`, or the rest without one. If you want working autocomplete on the
backend, create the venv from [Appendix A](#appendix-a-running-outside-docker) and point VS
Code at it: `Ctrl+Shift+P` → *Python: Select Interpreter* → `./backend/.venv/Scripts/python.exe`.

For the frontend, `npm install` inside `frontend/` is enough to make TypeScript resolve.

### The Docker extension

The whale icon in the sidebar lists every container. Right-click any of them for **View
Logs**, **Attach Shell**, or **Restart** — faster than remembering the CLI flags while
debugging.

### A note on `.env` files

`.gitignore` covers `.env` and `.env.*` at every level. Both files you created hold real
secrets. Never commit either, and do not paste their contents into issues or chats.

---

## 9. Running the tests

The backend suite runs against a **real** Postgres, not an in-memory substitute. That is
deliberate: the security model is row level security plus a powerless login role, and
neither exists in SQLite — a suite that mocked them would pass while the thing it claims to
protect was broken.

So the stack has to be up first.

```bash
docker compose up -d
cd backend
python -m venv .venv
.venv/Scripts/activate          # Windows; `source .venv/bin/activate` elsewhere
pip install -r requirements.txt
python -m pytest
```

Expected:

```
290 passed
```

The run takes around two minutes. Storage is redirected to a temp directory and the AI
provider is forced to `fake`, so tests never touch real media or the Gemini API.

Frontend type checking needs no database:

```bash
cd frontend
npm install
npm run typecheck
```

---

## 10. Day-to-day commands

Run these from the repository root.

| Task | Command |
| --- | --- |
| Start everything | `docker compose up -d` |
| Stop everything (keeps data) | `docker compose stop` |
| Stop and remove containers (keeps data) | `docker compose down` |
| Rebuild after changing backend or frontend code | `docker compose up -d --build backend frontend` |
| Follow all logs | `docker compose logs -f` |
| Follow one service | `docker compose logs -f backend` |
| Service status | `docker compose ps` |
| Shell into the backend | `docker compose exec backend sh` |
| Re-run migrations | `docker compose up migrate` |

Managing the Supabase stack on its own, from `docker/supabase`:

| Task | Command |
| --- | --- |
| Show generated keys | `sh run.sh secrets` |
| Start / stop | `sh run.sh start` / `sh run.sh stop` |
| Status | `sh run.sh status` |
| Logs for one service | `sh run.sh logs auth` |

---

## 11. Troubleshooting

### `docker compose up` fails immediately with a variable error

```
error while interpolating services.frontend.build.args.VITE_SUPABASE_PUBLISHABLE_KEY:
required variable is not set
```

A required value is missing from the root `.env`. The three that fail this way are
`VITE_SUPABASE_PUBLISHABLE_KEY`, `POSTGRES_PASSWORD`, and `APP_DB_PASSWORD`. Revisit
[step 5](#5-configure-the-application).

### `no tenant id` / `ENOIDENTIFIER`

`POOLER_TENANT_ID` in `docker/supabase/.env` is not `teaser`. Host port 5432 is published by
Supavisor, not Postgres, and it requires the username to carry the tenant as
`<role>.<tenant>`. Fix the value, then:

```bash
docker compose restart supavisor
```

### Sign-up says "check your email" and you can never log in

`ENABLE_EMAIL_AUTOCONFIRM` is `false` and there is no SMTP sender configured. Set it to
`true` in `docker/supabase/.env`, then `docker compose restart auth`.

To rescue an account already stuck this way, open Studio at <http://localhost:8000>
(username `supabase`, password `DASHBOARD_PASSWORD`) and confirm the user in the Auth
section — or just sign up again with a different address.

### `migrate` exits non-zero

```bash
docker compose logs migrate
```

Almost always `POSTGRES_PASSWORD` in the root `.env` not matching the one in
`docker/supabase/.env`. They must be identical. Fix it and re-run `docker compose up migrate`.

### Port is already allocated

Something else owns 3001, 5432, 6543, 8000, or 8001 — a local Postgres service is the usual
culprit on 5432. Either stop it, or override the port in the root `.env`:

```ini
BACKEND_PORT=8002
FRONTEND_PORT=3002
```

If you change `FRONTEND_PORT`, also update `CORS_ORIGINS` and `VITE_API_BASE_URL` to match,
then rebuild — a mismatch here is invisible until the first API call, because login talks to
Supabase directly rather than to this API.

### The app loads but every action fails with `NETWORK_ERROR`

The frontend cannot reach the backend. Check `docker compose ps` shows `backend` as `Up`,
and that `VITE_API_BASE_URL` in `.env` points at the port the backend is actually published
on. Vite compiles that value in at **build** time, so after changing it you must rebuild:

```bash
docker compose up -d --build frontend
```

### Generation fails with a quota or API-key error

Check the backend log: `docker compose logs backend`. Either the Gemini key is wrong, or it
is out of quota. Set `GEMINI_API_KEYS` to a comma-separated pool to fail over automatically,
or set `AI_PROVIDER=fake` to keep working offline. Either change needs a restart:

```bash
docker compose up -d backend
```

### URL ingestion fails on a link that works in a browser

Extractors break whenever a site changes its player. Rebuilding the backend pulls a current
`yt-dlp`:

```bash
docker compose build --no-cache backend && docker compose up -d backend
```

Note that fetches to private and link-local addresses are refused by design — the SSRF guard
checks the address at connect time, so a redirect to an internal endpoint is blocked too.

### Everything is slow, or containers are being killed

Docker Desktop needs more memory. *Settings → Resources → Memory*, set at least 6 GB, and
restart Docker.

---

## Appendix A: Running outside Docker

Useful for debugging with breakpoints, or for frontend work with hot reload.

Supabase still has to be running — only the application services move to the host:

```bash
docker compose up -d db api-gw auth rest migrate
```

You also need **FFmpeg and FFprobe on your `PATH`**, which the container otherwise provides:

- Windows: `winget install Gyan.FFmpeg`
- macOS: `brew install ffmpeg`
- Debian/Ubuntu: `sudo apt install ffmpeg`

Verify with `ffmpeg -version` and `ffprobe -version`. If you would rather not put them on
`PATH`, set `FFMPEG_PATH` and `FFPROBE_PATH` in `.env` to the absolute paths instead.

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate              # Windows; `source .venv/bin/activate` elsewhere
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Serves on <http://127.0.0.1:8000>, docs at `/docs`. Note this collides with the Supabase
gateway on 8000 — either stop the Dockerised backend and accept the difference, or run
uvicorn with `--port 8002`.

`DATABASE_URL` in `.env` is already set for host access, including the `.teaser` tenant
suffix the pooler requires. Never point it at the `postgres` role: that role has `BYPASSRLS`
and would make every user's rows visible to every other user.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Serves on <http://localhost:5173> with hot reload. That origin is already in the default
`CORS_ORIGINS` and is the configured `SITE_URL`, so auth redirects work without further
changes.

---

## Appendix B: Full reset

### Restart cleanly, keeping data

```bash
docker compose down
docker compose up -d
```

### Wipe the database and all generated media

This destroys every account, video, run, and clip. There is no undo.

```bash
docker compose down -v
rm -rf docker/supabase/volumes/db/data
docker compose up -d --build
```

`down -v` removes the named volumes, including `teaser-media`. The `rm` clears the Postgres
data directory, which is a bind mount and therefore survives `down -v` on its own — miss it
and the old database comes back with the new stack.

Your `.env` files are untouched, so you do not need to regenerate keys.

### Start over completely

Delete the clone and begin at [step 3](#3-clone-the-repository). Run `docker compose down -v`
first, or the volumes are orphaned.
