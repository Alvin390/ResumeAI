# ResumeAI (MVP Scaffold)

Full‑stack scaffold for ResumeAI.

Tech stack:

- Frontend: React (Vite). TipTap editor planned. Tailwind planned.
- Backend: Django 5 + DRF. Celery ready (Redis broker). PostgreSQL.
- Auth libs present (django‑allauth) – only health endpoint is wired for now.
- Storage: PDFs/DOCX stored in PostgreSQL (bytea) per FILE_STORAGE_MODE=db.

This repo is prepared for Docker, but you can run locally without Docker (recommended first run on this machine).

## 1) Prereqs

- Python 3.11+
- Node 18+ (comes with npm)
- PostgreSQL 15+ running locally or via Docker (compose file provided)

Dev defaults (see `.env.example`): DB name/user/password are all `resumeai`, host `localhost`, port `5432` if you run Postgres yourself. In Docker, host would be `postgres`.

## 2) Configure environment

From the repo root:

```bash
cp .env.example .env
```

Adjust `.env` if your local Postgres is not the same as the defaults.

## 3) Start a local Postgres (option A: your own)

Create a database and user matching `.env`.

```sql
CREATE DATABASE resumeai;
CREATE USER resumeai WITH PASSWORD 'resumeai';
GRANT ALL PRIVILEGES ON DATABASE resumeai TO resumeai;
```

Option B: Use Docker (if Docker is available on your system):

```bash
docker compose up -d postgres redis
```

## 4) Backend: create venv, install, migrate, run

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Health check: http://localhost:8000/api/health/

## 5) Frontend: install and run

Open a new terminal:

```bash
cd frontend
npm install
npm run dev -- --host --port 3000
```

Open http://localhost:3000 and you should see the app, with backend health reported.

## 6) Next milestones (to be implemented)

- Accounts: email/password + email verification, Google & LinkedIn OAuth via allauth.
- Profile + optional CV upload at signup (stored in Postgres as BLOBs).
- Parser pipeline for PDF/DOCX (pdfplumber + python-docx + rules/heuristics).
- AI engine: Gemini primary with automatic DeepSeek fallback. Keys from env.
- Async generation via Celery (Redis), with in‑app + email notifications.
- Editor (TipTap), versioning (latest + prev 3), accept → export (PDF/DOCX).
- Admin usage dashboard and GDPR endpoints.

## 7) Notes on secrets and safety

- Do not paste real API keys into source files or commits. Use `.env` for local only.
- In production, use a secrets manager. Rotate any keys previously shared.

## 8) Docker (later)

When Docker is available on your system:

```bash
docker compose up --build -d
```

This will start Postgres, Redis, backend, and frontend containers. For now, local non‑Docker run is the fastest path.
