# Architecture

The API maps database operational failures to a safe HTTP 503 response; the configured database remains a startup/runtime dependency and is not replaced silently after production configuration.

FastAPI + async SQLAlchemy orchestrates provider → trace → graph → patterns → risk → evidence → timeline. PostgreSQL is production; SQLite is explicit DEMO_MODE fallback. Next.js 16/React Flow consumes backend API data.

Investigation execution is modeled as one current persisted snapshot per case. The service takes a PostgreSQL row lock (with a process-local lock for the SQLite/demo path), returns the existing snapshot for repeated requests, and records completed processing metadata only after the persistence pipeline has flushed. Successful analysis leaves the case in `review`; explicit authorized closure separately sets `completed` and `closed_at`. Request-transaction rollback leaves a failed run retryable without partial child records. Case authorization receives the already-resolved active user rather than querying the identity again.
