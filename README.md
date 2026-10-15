# AI Workflow Assistant

**Repository status: INCOMPLETE SOURCE IMPORT (October 15, 2026)**

This repository is currently public by the owner's choice. It contains initial documentation, ignore rules, a frontend package manifest, a Python dependency manifest and a CI workflow, **but not yet the application source**. Do not deploy this repository in its current state; CI jobs that require the missing app and tests will fail.

## Intended application (v1.0 source package)
- FastAPI backend with controlled AI workflow pipeline
- Next.js frontend, login prototype, dashboard, sample inbox and approvals
- Database models and Alembic migration
- Unit and integration tests

Local ZIP package previously passed 17 backend checks and 11 frontend source checks, but the full Next.js build and browser end-to-end tests have not been verified.

## Next steps
Import the remaining frontend and backend directories from the prepared project ZIP, verify no secrets or private data are included, run CI, fix build failures, and only then prepare private deployment.

Never commit API keys, .env files, customer data, local databases, or employer-owned code.
