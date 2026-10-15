# GitHub setup

Repository: aminul293/ai-workflow-assistant (public by owner choice).

The complete application source is now on main. The earlier incremental import
is finished; no ZIP import step is required.

CI runs on push, pull request or manual workflow dispatch. It uses read-only
repository permissions and synthetic data. Jobs cover backend tests and HTTP
smoke checks, frontend source/routing checks, the full Next.js build and a
full-stack HTTP test. No deployment or external AI calls are triggered.

Do not commit secrets. Live hosting configuration and browser verification are
separate next steps after a successful CI run. Dependency ranges remain from
the prototype; generate and review lockfiles before any production release.
