# Architecture

The API maps database operational failures to a safe HTTP 503 response; the configured database remains a startup/runtime dependency and is not replaced silently after production configuration.

FastAPI + async SQLAlchemy orchestrates provider → trace → graph → patterns → risk → evidence → timeline. PostgreSQL is production; SQLite is explicit DEMO_MODE fallback. Next.js 16/React Flow consumes backend API data.
