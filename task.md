# CryptoTrace AI P0 status - 2026-09-03

| Capability | Status | Evidence / limitation |
|---|---|---|
| Continuation recovery | COMPLETE | Verified private Git baseline is preserved at ba84e0b; this follow-up checkpoint records the validated P0 remediation |
| Login | COMPLETE | JWT login exercised over HTTP |
| Investigator Dashboard | PARTIAL | Backend-integrated dashboard builds; primary action failures now surface a visible dismissible error; browser connection unavailable for final visual QA |
| Case Creation | COMPLETE | Isolated HTTP creation exercised |
| Wallet Intake | PARTIAL | Chain-aware demo/EVM/Bitcoin format validation; live provider/address existence not verified |
| Blockchain/Data Layer | PARTIAL | Coherent labelled demo provider; no live provider |
| Normalization | COMPLETE | Canonical transaction persistence exercised |
| Trace | COMPLETE | Bounded BFS; historical-window regression tests pass |
| Fund Flow | COMPLETE | Endpoint populated from investigation state |
| Graph | PARTIAL | Backend graph/primary path and risk/attribution context exercised; React Flow zoom/pan, node/edge selection, money-trail focus, and wallet search are wired; browser interactions unverified |
| Intermediaries | COMPLETE | Deterministic pass-through/centrality analysis |
| Patterns | COMPLETE | Deterministic findings returned |
| Risk | COMPLETE | Explainable prioritization output returned |
| Evidence | COMPLETE | Generated pattern evidence persists with the originating finding ID and supporting transaction hash; investigator-saved evidence persists through POST/GET round-trip |
| WHY | COMPLETE | Wallet-specific reasons exercised |
| Replay | PARTIAL | Actual events include event ID/order, transaction, timestamp, node/edge highlights; UI selection synchronization is implemented and browser synchronization is unverified |
| AI | COMPLETE | Supported and adversarial grounding suite passes, including missing/future transaction variants; unsupported claims refuse confidently before an LLM call |
| Reports | COMPLETE | Structured report POST/GET exercised |
| Audit Logs | COMPLETE | Case creation/view, investigation completion, evidence save, and report generation persist AuditLog records and are covered by tests |
| Investigation idempotency | COMPLETE | One persisted snapshot per case; repeated and concurrent runs reuse the snapshot; persistence failure rolls back and a later retry succeeds |
| Authentication | COMPLETE | Protected case routes return 401 without token; production rejects missing/weak signing secrets; demo uses an ephemeral process key |
| Authorization | COMPLETE | Owner access, supervisor access, investigator IDOR denial, and unauthenticated denial tested across sensitive routes; one active user dependency is reused per request |
| Error Handling | PARTIAL | Provider timeout, malformed response, empty wallet, AI timeout, attribution absence, login-throttle, and database-unavailable safe-503 paths are covered; live-provider failure behavior remains unverified |
| Browser Verification | BLOCKED | No in-app or extension browser was available (`browsers.list()` empty); no visual walkthrough is claimed |
| PostgreSQL Verification | BLOCKED | PostgreSQL configuration and Docker Compose are present, but Docker/runtime connection was unavailable for this pass |
| Live Blockchain Provider | NOT STARTED | DemoProvider is the exercised source; no live provider credentials or network calls were used |

Current validation: clean backend environment installed 86 declared packages with bcrypt 4.0.1; backend regression is 30 passed and explicit P0 validation is 90/90. The Pydantic class-based-config warning is removed, and no bcrypt warning appeared during clean-environment startup/authentication. P0 remediation tests cover secret enforcement, JWT validation, idempotent/retry-safe investigation execution, and single-request user resolution. Frontend TypeScript, lint, and production build pass; lint reports 0 errors and 0 warnings. Local runtime verification used the SQLite fallback. The legacy project venv reference remains broken and points to a deleted uv Python executable, but an ignored clean backend/.venv is now available for repeatable validation. PostgreSQL runtime, browser walkthrough, and live-provider behavior remain unverified.
