# Staging deployment architecture

## One-time production admin bootstrap

The existing backend may create its first legitimate admin without Render Shell
using `POST /api/v1/auth/bootstrap-first-admin`. This is disabled by default and
is independent of normal login and demo settings. These are later deployment
steps, not instructions to change the current service during development.

1. Deploy the reviewed backend to the existing `CryptoTrace-AI` service
   `srv-dacjhbuk1f9s73cjlh70` (public URL
   `https://cryptotrace-ai-z7hp.onrender.com`). Verify startup has applied Alembic
   `0009_first_admin_bootstrap` to the service's existing PostgreSQL database.
   No separate service or external database connection is needed.
2. Keep the existing production environment unchanged: `APP_ENV=production`,
   `DEMO_MODE=false`, `SEED_DEMO_ACCOUNTS=false`, `DEBUG=false`,
   `USE_SQLITE=false` (or unset), and the existing `DATABASE_URL`, `SECRET_KEY`,
   `CORS_ORIGINS`, and `ALCHEMY_API_KEY`. Do not copy their values elsewhere.
3. In this service's Render Environment settings add only
   `FIRST_ADMIN_BOOTSTRAP_TOKEN`, with a new cryptographically random secret
   containing at least 32 random bytes encoded as 64 hexadecimal characters
   (accepted input: 32–128 non-whitespace ASCII characters). Keep it in the
   operator's password manager; do not include it in source or command arguments.
   Apply the environment change to the existing service.
4. From a trusted HTTPS client with request/response recording disabled, send a
   single POST to the service's bootstrap endpoint. Supply the token only through
   `X-First-Admin-Bootstrap-Token` and JSON fields `username`, `email`, `full_name`,
   `password`. Enter the password through the client's secret-input facility;
   use 12–72 characters and no more than 72 UTF-8 bytes. Do not send a role or a
   reserved demo identity. Never put the password in an environment variable.
5. A 201 response with `Administrator provisioned` confirms the transaction
   committed. Remove `FIRST_ADMIN_BOOTSTRAP_TOKEN` from Render and apply that
   change. Sign in normally through the existing application. Do not copy a JWT
   into logs or reports. The endpoint remains permanently consumed even if the
   environment variable is accidentally retained or re-added.

Bootstrap cannot reset/reactivate an existing admin. An existing non-demo admin,
even inactive, returns 409. An identity conflict also returns 409 without changing
accounts. A 429 requires waiting for the database-wide 15-minute attempt window;
rotation/restart does not clear it. A 503 requires investigating service/database
readiness without dumping request data or secrets. Do not remove the consumption
row to recover an account. `python -m app.provision_admin` still exists for trusted
interactive operator environments and shares the same permanent guard.

The older staging sections below describe historical checkpoints; their previous
claims that no migrations exist are superseded by the versioned Alembic runtime.

This document describes the lowest-risk staging path and configuration
contract for the current repository. The hosted-service facts recorded below
do not by themselves prove that the backend is using PostgreSQL.

## Recommendation

Use one Render project for the staging components:

```text
Browser / Capacitor Android client
        ↓ HTTPS
Render static site: exported Next.js frontend
        ↓ HTTPS + exact CORS allowlist
Render Python web service: existing FastAPI backend
        ↓ private PostgreSQL connection
Render managed PostgreSQL database
```

The frontend uses Next.js static export and produces `frontend/out`; it does
not require a Node server at runtime. The FastAPI backend remains a separate
Render web service backed by managed PostgreSQL and an explicit CORS allowlist.
The Render dashboard configuration is external to this repository and must be
verified there before deployment; this repository does not contain a Render
Blueprint or deploy hook.

Vercel for the frontend plus Render or Railway for the backend/database is
also technically viable. Vercel has first-party Next.js App Router/SSR
support and environment-variable management, but it introduces a second
platform and an additional cross-origin boundary for this staging milestone.
Railway can host Next.js, FastAPI, and PostgreSQL in one project as well. The
single-Render route is therefore the simpler operational starting point, not
a claim that Render is the final provider choice.

## Service configuration

The repository is a monorepo with two independent services.

| Service | Root directory | Build command | Runtime / publish setting | Health check |
|---|---|---|---|---|
| Next.js static frontend | `frontend` | `npm ci && npm run build` | Publish directory: `out` | `/` |
| FastAPI backend | `backend` | `pip install -r requirements.txt` | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` | `/api/v1/health` |
| PostgreSQL | managed datastore | provider-managed | provider-managed | provider-managed |

For the Render backend service, set the service-level environment variable
`PYTHON_VERSION=3.12.14`. This is the authoritative Python runtime pin. Render
documents the environment variable as the highest-precedence mechanism and
requires a fully qualified version. Do not also add `.python-version`: Render
documents that file at the repository root, while this monorepo service uses
`backend` as its isolated Root Directory. The service-level variable avoids
an ambiguous file lookup and applies directly to this Python Web Service.

The frontend is configured with `output: "export"`. Render must build from the
`frontend` root and serve the generated `out` directory as a static site. The
investigation route is `/investigate?caseId=<id>` so the exported
`investigate.html` can serve every case without a dynamic server route.

Expected values after a real staging service is created are placeholders only:

```text
Frontend URL: https://<frontend-service-name>.onrender.com
Backend URL:  https://<backend-service-name>.onrender.com
API base:     https://<backend-service-name>.onrender.com/api/v1
Database:     provider-internal PostgreSQL connection string
```

No value above is a real project URL.

## Environment contract

### Frontend service

| Variable | Staging value | Secret? | Notes |
|---|---|---:|---|
| `NEXT_PUBLIC_API_URL` | `https://<backend-service-name>.onrender.com/api/v1` | No | Required at build time for hosted/installed clients; it is intentionally public in the browser bundle. |
| `NODE_ENV` | Provider/Next-managed | No | Do not use it to store credentials. |

There are no other application-specific frontend environment variables in
the current source. Backend keys must never be prefixed with
`NEXT_PUBLIC_`.

### Backend service

| Variable | Staging requirement | Production requirement | Notes |
|---|---|---|---|
| `PYTHON_VERSION` | `3.12.14` | `3.12.14` until the dependency stack is deliberately revalidated | Render service-level runtime pin; non-secret and fully qualified. |
| `APP_ENV` | `staging` | `production` | Only `local` may enable privileged demo accounts. |
| `DEMO_MODE` | Explicitly `true` | `false` with configured Alchemy and production settings | Demo data may be used in staging, but privileged demo account seeding is local-only. Non-demo startup requires backend `ALCHEMY_API_KEY` plus the existing production settings. Explicit Demo Network remains synthetic. |
| `SEED_DEMO_ACCOUNTS` | `false` | `false` | `true` is accepted only with `APP_ENV=local` and `DEMO_MODE=true`. |
| `REPORTER_DEMO_LOGIN_ENABLED` | Optional | Optional | `true` enables only the existing seeded reporter demo identity. It does not seed or enable investigator, supervisor, or administrator demo accounts. |
| `INVESTIGATOR_DEMO_LOGIN_ENABLED` | Optional | Optional | `true` enables only the existing seeded investigator demo identity. It does not seed or enable supervisor or administrator demo accounts. |
| `DEBUG` | `false` recommended | `false` | Production configuration rejects `true`. |
| `DATABASE_URL` | Managed PostgreSQL URL | Required managed PostgreSQL URL | The runtime accepts generic `postgresql://` input and normalizes it to the asyncpg dialect. SQLite is not allowed when `DEMO_MODE=false`. |
| `SECRET_KEY` | Random injected value recommended | Required random value, at least 32 characters | Never commit it. Demo mode can generate an ephemeral process key. |
| `CORS_ORIGINS` | Exact frontend HTTPS origin | Exact frontend origin plus a verified native origin when needed | Comma-separated; wildcard and empty values are rejected. Do not add a Capacitor origin until the actual shell/origin is verified. |
| `USE_SQLITE` | Explicitly `false` with hosted PostgreSQL | Unset/false | `DEMO_MODE=true` defaults to SQLite even when `DATABASE_URL` exists; hosted demo staging must override that default. `true` is rejected in non-demo mode. |
| `OPENAI_API_KEY` | Optional | Optional, if live LLM summaries are approved | Backend-only; no live call is currently verified. |
| `AI_MODEL` | Optional | Optional | Used only by the configured LLM path. |
| `ALCHEMY_API_KEY` | Backend only, optional for Demo | Required for Ethereum observations | Never pass to frontend/Android. Configuration is not proof of connectivity; inspect run capability. |
| `ETHERSCAN_API_KEY` | Not used by current provider | Not sufficient by itself | Configuration field exists, but no live provider adapter consumes it. |
| `BLOCKCHAIN_RPC_URL` | Not used by current provider | Not sufficient by itself | Configuration field exists, but no live provider adapter consumes it. |
| `MAX_TRACE_HOPS` | Default acceptable | Review before live traffic | Existing bounded tracing control. |
| `MAX_TRACE_TRANSACTIONS` | Default acceptable | Review before live traffic | Existing bounded tracing control. |
| `TRACE_TIME_WINDOW_HOURS` | Default acceptable | Review before live traffic | Existing tracing control. |
| `MIN_TRACE_AMOUNT` | Default acceptable | Review before live traffic | Existing tracing control. |

`APP_NAME`, `APP_VERSION`, `API_PREFIX`, `ACCESS_TOKEN_EXPIRE_MINUTES`, and
`ALGORITHM` have code defaults. `DATABASE_SYNC_URL` is retained as a future
migration-tooling placeholder but is not used by the current async runtime.

## Database readiness boundary

The SQLAlchemy models are PostgreSQL-compatible at the dialect level, and the
async engine uses `asyncpg` with connection-pool health settings. The current
startup path still calls `Base.metadata.create_all` through `init_db()`.

That is acceptable only as a temporary staging/demo convenience. There is no
Alembic configuration or migration history in this repository, so production
schema evolution is not yet safe to automate.

For the current fresh staging gate, `create_all` is the lowest-risk bootstrap:
it creates missing tables and indexes but does not alter, migrate, or drop an
existing schema. Startup logs the selected SQLAlchemy dialect without logging
the connection URL. A successful `backend: postgresql` schema-ready log plus a
hosted persistence/redeploy test is required before marking PostgreSQL active.
Do not use `create_all` as a substitute for migrations after the model schema
begins evolving.

Safest migration plan before non-demo production:

1. Baseline the current schema against a disposable PostgreSQL database.
2. Add Alembic configuration and one reviewed initial migration matching the
   current models; do not fabricate a migration history for an unknown
   database.
3. Run the migration against a fresh staging PostgreSQL database and execute
   the full backend/P0 suite against PostgreSQL.
4. Add a provider-supported pre-deploy migration command.
5. Use additive, backward-compatible migrations before switching application
   instances, with backups and a tested rollback procedure.
6. Remove or disable automatic `create_all` for the non-demo deployment path.

No migration rewrite is included in this checkpoint.

## Deployment order

1. Create a staging PostgreSQL database and keep its connection value in the
   provider secret store.
2. Create the backend web service in the same region. Set `DEMO_MODE=true`,
   `USE_SQLITE=false`, `DATABASE_URL`, a random `SECRET_KEY`, `DEBUG=false`,
   and the exact planned frontend origin in `CORS_ORIGINS`.
3. Confirm the backend service starts and its health endpoint responds.
4. Configure the frontend Render static site to build from `frontend`, publish
   `out`, and set
   `NEXT_PUBLIC_API_URL` to the actual backend HTTPS API base. This value must
   be present before the frontend build.
5. Replace any temporary CORS value with the actual frontend HTTPS origin and
   redeploy the backend.
6. Run hosted login, case creation, investigation, authorization, report,
   and API smoke checks. Treat all records as explicitly demo data.
7. Only after staging is stable, plan PostgreSQL migrations, live provider
   integration, and production secrets.

## Rollback

Application rollback is the previously successful frontend/backend commit or
provider deployment. Roll back the backend and frontend together when an API
contract change is involved. Database rollback must use a tested backup or a
forward-fix migration; do not assume that reverting application code reverts a
schema. Until migrations exist, do not perform destructive production schema
changes through startup `create_all`.

## Capacitor and Android

Capacitor wraps the same exported frontend with `webDir: "out"`; it does not
introduce a second UI. `npx cap sync android` copies the verified export into
the native project, and the generated `frontend/android/gradlew.bat` wrapper
builds the Android application. Android Studio is not required for this build
path. Physical-device validation remains a separate gate and must not be
claimed from an APK build alone.

The WebView uses the hosted HTTPS API from the exported bundle. Its native
origin is `https://localhost`, which must remain explicitly listed alongside
the desktop origin in backend `CORS_ORIGINS`; wildcard CORS is prohibited.

## Current status

The following staging resources were supplied and their public services have
responded over HTTPS:

```text
Frontend: https://cryptotrace-frontend.onrender.com
Backend:  https://cryptotrace-ai-z7hp.onrender.com
Postgres resource name: cryptotrace-postgres
```

The backend must have all of the following effective runtime configuration
before the PostgreSQL reliability gate is run:

```text
DATABASE_URL=<cryptotrace-postgres internal connection URL; secret>
USE_SQLITE=false
APP_ENV=staging
DEMO_MODE=true
SEED_DEMO_ACCOUNTS=false
DEBUG=false
SECRET_KEY=<random value of at least 32 characters; secret>
CORS_ORIGINS=https://cryptotrace-frontend.onrender.com,https://localhost
PYTHON_VERSION=3.12.14
```

PostgreSQL remains unverified until a redeployed backend logs
`Database schema ready (backend: postgresql)`, the hosted vertical slice is
exercised, and the created case remains retrievable after another Render
service instance is started. The application applies versioned Alembic
migrations through `0007_access_capability` during startup; hosted execution
of that migration remains unverified.
