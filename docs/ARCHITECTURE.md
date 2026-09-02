# Architecture

The API maps database operational failures to a safe HTTP 503 response; the configured database remains a startup/runtime dependency and is not replaced silently after production configuration.

FastAPI + async SQLAlchemy orchestrates provider → trace → graph → patterns → risk → evidence → timeline. PostgreSQL is production; SQLite is explicit DEMO_MODE fallback. Next.js 16/React Flow consumes backend API data.

Investigation execution is modeled as one current persisted snapshot per case. The service takes a PostgreSQL row lock (with a process-local lock for the SQLite/demo path), returns the existing snapshot for repeated requests, and only marks a case `completed` or `review` after the full persistence pipeline has been flushed. Request-transaction rollback leaves a failed run retryable without partial child records. Case authorization receives the already-resolved active user rather than querying the identity again.
