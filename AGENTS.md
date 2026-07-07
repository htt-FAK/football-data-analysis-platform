# AGENTS.md

Full-stack football data platform: FastAPI + SQLAlchemy backend, React 19 + Vite + TS frontend, MySQL + Redis + Hadoop HDFS storage. Primary use case is the **2026 World Cup** dashboard (`/worldcup`). Code comments and commit messages are in Chinese; match that convention.

## Commands

Backend (run from `backend/`):
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000   # entry = app/main.py
```
Frontend (run from `frontend/`):
```bash
npm install
npm run dev        # Vite dev server on :5173, proxies /api -> 127.0.0.1:8000
npm run build      # tsc -b && vite build  (typecheck is part of build)
npm run lint       # eslint
```
- No test suite exists. The only "test" is `python verify_fotmob_xg.py` (end-to-end Fotmob xG check; needs backend running + MySQL + working UC browser).
- Frontend has **no `typecheck` script** — run `npx tsc -b` or `npm run build` to typecheck.
- Import alias: `@/` → `frontend/src/` (configured in `vite.config.ts` and tsconfig).

## Setup gotchas (agents get these wrong)

- **DB schema is NOT created by SQLAlchemy.** `Base.metadata.create_all` is never called. Tables come from `init_database.sql` (12 tables), which is **gitignored** — do not assume it's present or that models auto-migrate. Schema changes are applied via manual `ALTER TABLE` (see `verify_fotmob_xg.py` step 2 for the idempotent pattern).
- Config is env-driven via `python-dotenv`. `.env` lives in `backend/.env` (gitignored); template is repo-root `.env.example`. `app/config.py` loads it and holds all defaults.
- Copy env as `cp ../.env.example .env` from inside `backend/` — `load_dotenv()` reads CWD.

## Architecture wiring (not obvious from filenames)

- **Routers** are aggregated in `app/api/__init__.py` and mounted with explicit prefixes in `app/main.py` (e.g. `leagues_router` → `/api/v1/leagues`). To add an endpoint group: create `app/api/<x>.py` exposing `router`, export it in `__init__.py`, then `include_router(..., prefix=...)` in `main.py`.
- **Global response middleware**: every JSON response passes through `repair_json_text_middleware` → `services/text_repair.repair_payload`. It re-serializes with `ensure_ascii=False`. If a response looks mangled/re-encoded, this is why.
- **Crawlers** all subclass `crawlers/base.py::BaseCrawler` (built-in retry w/ exponential backoff capped 30s, random delay, browser headers, SHA256 dedup hash, HDFS raw dump). Add a source by subclassing and implementing `crawl(target)`, then register it in the `_dispatch_crawl` if/elif chain in `scheduler/jobs.py`.
- **Scheduler** (`scheduler/jobs.py`, APScheduler) starts in the FastAPI lifespan only when `ENABLE_SCHEDULER=True`. Jobs: live crawl (30s), World Cup schedule refresh (900s), daily full crawl (06:00), Excel export (cron), AI prediction scan (900s).
- **Fotmob xG crawl is off by default** (`ENABLE_FOTMOB_XG_CRAWL=False`). It needs `undetected-chromedriver` + a real Chrome to bypass Cloudflare, so it can't run on headless servers. Don't "fix" it by enabling in server config.
- FIFA World Cup ingest hardcodes `league_name="世界杯"`, `season_name="2026"` (see `_ingest_context` / constants in `jobs.py`).

## Conventions

- CORS is fully open (`allow_origins=["*"]`) — intentional for this project.
- Frontend auto-appends trailing slashes to API paths to avoid 307-redirect CORS breakage (see git history). Keep that when touching `frontend/src/api/`.
- Deploy target is a specific server (`deploy.sh`, TencentOS + Hadoop 3.3.6 pseudo-distributed). `deploy.sh` contains hardcoded prod DB credentials — do not commit new secrets into it.

## Stale references (ignore)

- `scripts/README_爬虫使用说明.md` references `scripts/standalone_fifa_crawler.py` and Windows paths that no longer exist. Trust `scripts/run_fifa_worldcup_ingest.py` and the crawler classes instead.
