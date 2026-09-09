# Deploying ONE to Render

Two services and a database:

| Piece | Render type | What it does |
| --- | --- | --- |
| `one-api` | Web Service (Python) | FastAPI backend **and** the hourly scheduler (in-process thread) |
| `one-web` | Static Site | The Next.js UI, exported to plain HTML/CSS/JS |
| `one-db` | PostgreSQL | Content, picks, comments, feedback, outcome metrics |

The frontend is a **static export**, so there is no Node server to run — it is
just files, served free, and it talks to the API from the browser.

---

## 1. Push the repo to GitHub

Render deploys from a Git host. From the project root:

```bash
git remote add origin https://github.com/<you>/<repo>.git
```

```bash
git push -u origin main
```

Secrets are safe: `.gitignore` excludes `.env`, the SQLite database, `venv/`,
and `node_modules/`. Verify before pushing with `git ls-files | grep env`
(it should return nothing but `backend/.env.example`).

## 2. Create the services

**Option A — Blueprint (one step).** In Render, choose *New → Blueprint*, point
it at the repo, and it reads [`render.yaml`](render.yaml). Render's Blueprint
schema does change between versions; if it complains, use Option B.

**Option B — Manual (always works).**

*Database:* New → PostgreSQL, name `one-db`, free plan. Copy its **Internal
Database URL**.

*API:* New → Web Service, from the repo.
- Root Directory: `backend`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
- Health Check Path: `/health`
- Environment variables: see the table below.

*Frontend:* New → Static Site, from the repo.
- Root Directory: `frontend`
- Build Command: `npm ci && npm run build`
- Publish Directory: `out`
- Environment variable: `NEXT_PUBLIC_API_URL` = the API's URL
  (e.g. `https://one-api.onrender.com`)

## 3. Environment variables

Set on **`one-api`**:

| Key | Value |
| --- | --- |
| `DATABASE_URL` | The Postgres Internal Database URL |
| `GEMINI_API_KEY` | From Google AI Studio |
| `YOUTUBE_API_KEY` | From Google Cloud Console |
| `ADMIN_TOKEN` | Any long random string — signs admin sessions |
| `ADMIN_USERNAME` | Your sign-in name for `/admin/` |
| `ADMIN_PASSWORD` | Your sign-in password for `/admin/` |
| `ALLOWED_ORIGINS` | The frontend URL, e.g. `https://one-web.onrender.com` |
| `RUN_SCHEDULER` | `1` |

Set on **`one-web`**:

| Key | Value |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | The API URL, e.g. `https://one-api.onrender.com` |

Deploy the API first so you know its URL, then the frontend.

## 4. First run

The database starts empty, so the site shows *"We are discovering something
amazing..."* until the pipeline runs. The scheduler runs one cycle at startup:
it ingests from YouTube and the RSS feeds, scores everything with Gemini, and
promotes the top pick. Give it a few minutes, then reload.

Watch the API service's logs to follow the ingestion and scoring, and check
`/admin/` (with your `ADMIN_TOKEN`) to see the review queue fill up.

---

## Things that will bite you

**Free web services sleep.** After ~15 minutes of no traffic Render spins the
service down; the next request takes ~50 seconds to wake it. While asleep the
scheduler is not running either, so hours get skipped. The site still works —
`/hourly` falls back to the most recent pick and flags it `is_stale` — but the
hourly rhythm is only real on a paid instance or with an external pinger.

**`NEXT_PUBLIC_API_URL` is baked in at build time,** not read at runtime.
Changing it requires redeploying the static site, not just restarting it.

**Free Postgres has a time limit.** Render has historically expired free
databases after a fixed period (verify the current policy on their pricing
page). When it expires you lose the archive and all the incrementality data, so
move to a paid database before that data matters to you.

**Do not raise `--workers` above 1** while `RUN_SCHEDULER=1`, or every worker
runs its own scheduler and duplicates the ingestion API calls. For more
capacity, set `RUN_SCHEDULER=0` and run `python run_hourly.py` as a separate
Background Worker instead.

**SQLite is not a deployment option here.** With no `DATABASE_URL` the app falls
back to a local SQLite file, but Render's free filesystem is ephemeral — the
archive and the 7-day view deltas would reset on every deploy. Use Postgres.

**`/admin/` is reachable by anyone who finds the URL.** It shows a sign-in form
and every endpoint behind it returns 403 without a valid session, but it is not a
secret page. Sessions expire after `ADMIN_SESSION_HOURS` and live in
sessionStorage, so they die with the browser tab.

**If the API returns 500 on every route but `/health` is fine,** the database
schema is behind the code. Check `curl https://<api>/status` -- it reports
`schema.missing_columns` and keeps answering even when the database is the broken
part. Redeploying applies migrations at startup; to apply them without a deploy,
run `python migrate.py` as a Render one-off job (it exits non-zero if anything is
still missing).

**If the Python build fails on a wheel** (usually `psycopg2-binary` on a
brand-new interpreter), pin the runtime: add `PYTHON_VERSION` = `3.12.8` to the
API service's environment variables and redeploy. `requirements.txt` uses
minimum-version floors, so it otherwise installs whatever is current.

**The chat is unmoderated and public.** There is no rate limiting, spam
filtering, or delete tooling yet. Worth knowing before sharing the link widely.

---

## Running locally

```bash
cd backend && venv/Scripts/python.exe dev_server.py
```

`dev_server.py` exists because this machine runs Python 3.6.0, which cannot
import pydantic (and therefore cannot run FastAPI) -- it predates `typing.Deque`
from 3.6.1. The dev server delegates to the same `app/queries.py` the deployed
FastAPI app uses, so behaviour cannot drift. On a modern Python, run the real
thing instead:

```bash
cd backend && python -m uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm run dev
```

The scheduler is separate locally (or set `RUN_SCHEDULER=1`):

```bash
cd backend && venv/Scripts/python.exe run_hourly.py
```

One-shot scripts: `run_pipeline.py` (ingest + score), `auto_schedule.py`
(promote the next pick), `check_outcomes.py` (record 7-day view deltas).
