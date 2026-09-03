# Implementation documentation

These notes describe the current prototype, not aspirational completion. The P0 pipeline is FastAPI + SQLAlchemy + PostgreSQL (production), with an explicit SQLite demo fallback, and Next.js 16 + React Flow.

Current truth: structured demo investigation works through trace, graph, patterns, risk, persisted evidence bookmarking, WHY, replay, grounded AI fallback, and report. Strict per-case authorization and frontend lint/build checks are covered by executable verification. Live-chain providers, PostgreSQL runtime verification, and browser QA remain incomplete. See the root `README.md` and `task.md` for run instructions and the verified status matrix.

The staging deployment contract and provider-selection rationale are documented in [DEPLOYMENT.md](DEPLOYMENT.md). It does not claim that any hosting, database, domain, or deployment exists.
