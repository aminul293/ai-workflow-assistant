# AI Workflow Assistant

Development prototype for a solo AI automation agency. The complete application
source is now imported. This is **not a deployed or production-ready service**.

## Included

- FastAPI API, SQLAlchemy models, Alembic migration and SQLite development database.
- Next.js dashboard, synthetic inbox, read-only workflow canvas, tasks and approvals.
- Four controlled processing roles: intake, classification, planning and quality review.
- Offline classification by default; optional OpenAI mode is not live-verified.
- Prototype login, signed cookies, server-side API proxy and audit events.
- No live mailbox integration, CRM writeback or outbound email.

## Development setup

Use Python 3.11 and Node.js 22. Install the backend dependencies:

```sh
cd backend
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env: replace placeholder BACKEND_API_KEY with a generated secret.
# Export the values into this shell, then migrate the configured database.
set -a; . ./.env; set +a
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```sh
cd frontend
cp .env.example .env.local
# Edit .env.local: same BACKEND_API_KEY; unique APP_PASSWORD;
# SESSION_SECRET must be at least 32 random characters.
# APP_ORIGIN must match your browser URL (default http://localhost:3000).
npm install
npm run dev
```

Open http://localhost:3000. Sign in, load synthetic samples, open Smart Inbox,
process one message, then review its draft in Approvals. Approval records a
local decision; it sends nothing. Never commit real .env files or passwords.

`BACKEND_URL` must be the backend origin, e.g. http://127.0.0.1:8000, without an
/api suffix. The browser calls /api/proxy/api/...; the proxy forwards exactly
/api/... and keeps BACKEND_API_KEY on the server. Its timeout is 30 seconds.

## Verification

```sh
(cd backend && PYTHONPATH=. AI_PROVIDER=mock python -m pytest -q)
(cd frontend && npm test)
python scripts/smoke_backend.py
(cd frontend && npm run build)
python scripts/smoke_fullstack.py
```

The source and routing checks are not browser tests. The full-stack HTTP script
requires a successful frontend build, creates temporary data, and explicitly
replays its test cookie on loopback HTTP. It does not verify browser cookie or
visual behavior. GitHub Actions performs all commands above in a fresh runner.
Check the Actions run for the exact commit before claiming the build is green.

## Known limits

Single-owner prototype authentication is not a production identity system.
Before deployment: review authentication and rate limiting, tenant isolation,
concurrent duplicate handling, backups, dependencies, real-browser behavior,
HTTPS and secret storage. No hosting resources are created by this repository.
No paid AI calls are needed for default tests. See VERIFICATION.md for the
checks performed at import time. Existing migration 0001 uses model metadata;
future schema changes need explicit, immutable Alembic revisions.

Origin protection uses explicit APP_ORIGIN rather than the internal request
URL. Set APP_ORIGIN to the exact frontend origin, including the port locally.
Missing configuration fails closed; foreign-origin mutations remain blocked.
