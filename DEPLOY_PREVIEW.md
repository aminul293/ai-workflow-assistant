# Login-protected test preview

## Scope and current state

This is an optional deployment configuration, not a deployed website. It packages
the actual Next.js frontend and FastAPI backend together. A hosting-account
connection and an explicit service creation step are still required. Consult the
CI run for the exact commit's verification result; the presence of these files is
not proof that a build passed.

Use fictional samples only. This is a single-owner prototype, not audited
production authentication, tenant isolation, or an always-on customer service.

## Render configuration

Import `render.yaml` as a Blueprint in a personal Render workspace, or create a
Docker web service from this repository using the same settings. Keep the root
directory blank, Dockerfile `./Dockerfile`, health check `/login`, and the free
instance type. Do not add paid disks or databases. Confirm the account's current
plan and usage limits before creating the service. Automatic redeploys are off;
manually deploy only a commit whose tests have passed.

The Blueprint generates a distinct APP_PASSWORD, SESSION_SECRET and
BACKEND_API_KEY at the provider. Retrieve the login password from the service's
Environment screen. The username is `owner`. Do not paste credentials into chat,
commit them, or use the example/CI passwords. GitHub write access does not provide
access to Render accounts.

`start_preview.py` reads Render's actual RENDER_EXTERNAL_URL and sets APP_ORIGIN
for redirects and request-origin checks. A custom domain requires setting
APP_ORIGIN to that exact HTTPS origin. Never guess the assigned onrender.com URL.
The backend listens on 127.0.0.1:8000 inside the container; only Next.js binds to
PORT. Startup applies migrations and waits for authenticated database readiness.
A failed server stops its companion. The container runs as the non-root node user.

The `/login` hosting health check tests frontend liveness, not ongoing database
readiness. After logging in, confirm the dashboard's Backend ready indicator.

## Costs and storage limitations

The configuration requests a free web instance and makes no model API calls.
This is not a guarantee about account charges or unlimited usage: provider
quotas, policies, and any existing account services still apply.

**Local SQLite is disposable. Free-instance restarts, redeploys and idle spin-down
can erase all sample messages, approvals and history.** Use Load sample inbox to
recreate fixtures. This preview intentionally refuses external DATABASE_URL and
live AI configuration. A durable database, backups, multi-user auth, rate limiting,
dependency locking and security review belong to a separate production milestone.

## Verification

- `python scripts/smoke_browser.py` runs desktop Chromium and mobile-sized WebKit
  against production Next.js and FastAPI through a local HTTPS bridge. It uses
  normal browser cookies and real API calls. The self-signed certificate exception
  is confined to this local test. It is not a physical-iPhone test or a substitute
  for reviewing screenshots and usability on a real phone.
- CI stores synthetic screenshots in `browser-test-results` for seven days.
- `docker build -t awa-preview:ci .` followed by
  `python scripts/smoke_container.py` tests the built image without deploying it.
- After hosting, verify HTTPS, wrong-password rejection, authenticated readiness,
  sample processing, approval/rejection, logout, and anonymous API rejection again
  against the assigned URL. Until then, cloud behavior remains unverified.

## References

Render documentation checked during preparation:
- https://render.com/docs/blueprint-spec
- https://render.com/docs/environment-variables
- https://render.com/docs/free
