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
| Audit Logs | COMPLETE | Case creation/view, investigation completion, evidence save, and report generation persist AuditLog records; authorized case-scoped read API and investigator Audit Log tab are build/test covered |
| Investigation idempotency | COMPLETE | One persisted snapshot per case; repeated and concurrent runs reuse the snapshot; persistence failure rolls back and a later retry succeeds |
| Authentication | COMPLETE | Protected case routes return 401 without token; production rejects missing/weak signing secrets; demo uses an ephemeral process key |
| Authorization | COMPLETE | Owner access, supervisor access, investigator IDOR denial, and unauthenticated denial tested across sensitive routes; one active user dependency is reused per request |
| Error Handling | PARTIAL | Provider timeout, malformed response, empty wallet, AI timeout, attribution absence, login-throttle, and database-unavailable safe-503 paths are covered; live-provider failure behavior remains unverified |
| Browser Verification | BLOCKED | No in-app or extension browser was available (`browsers.list()` empty); no visual walkthrough is claimed |
| PostgreSQL Verification | BLOCKED | PostgreSQL configuration and Docker Compose are present, but Docker/runtime connection was unavailable for this pass |
| Live Blockchain Provider | NOT STARTED | DemoProvider is the exercised source; no live provider credentials or network calls were used |

Current validation: clean backend environment installed 86 declared packages with bcrypt 4.0.1; backend regression is 32 passed and explicit P0 validation is 90/90. The Pydantic class-based-config warning is removed, and no bcrypt warning appeared during clean-environment startup/authentication. P0 remediation tests cover secret enforcement, JWT validation, idempotent/retry-safe investigation execution, and single-request user resolution. Frontend TypeScript, lint, and production build pass; lint reports 0 errors and 0 warnings. Local runtime verification used the SQLite fallback. The legacy project venv reference remains broken and points to a deleted uv Python executable, but an ignored clean backend/.venv is now available for repeatable validation. PostgreSQL runtime, browser walkthrough, and live-provider behavior remain unverified.

## P1 triage after P0 remediation - 2026-09-03

| Finding | Status | Decision / evidence |
|---|---|---|
| JWT claim hardening | PARTIAL | Expiry, signature, algorithm allow-list, UUID subject validation, and active-user lookup are enforced. Issuer/audience/JTI claims are not yet required; defer until a multi-issuer or token-revocation deployment exists. |
| Shared rate-limit scalability | PARTIAL | Failed-login throttling exists in-process and returns 429/Retry-After. A shared store or gateway policy is required for multi-worker production; not material to the single-process demo. |
| Registration flooding | PARTIAL | Public registration is input-validated and always creates investigator role, but has no abuse throttle. Harden before public deployment; not required by the private demo workflow. |
| Pagination | PARTIAL | Case artifacts are returned as bounded prototype collections; trace itself is capped at 200 transactions and 10 requested hops. Add cursor pagination before larger production datasets. |
| Graph explosion | COMPLETE (prototype scope) | Trace BFS, cycle protection, max-hop validation, and the 200-transaction cap bound graph input. Larger-scale pagination remains a P1 scalability task. |
| Pattern-engine complexity | PARTIAL | Rapid-movement pairing is quadratic in per-wallet incoming/outgoing records, but current trace input is bounded to 200 transactions. Optimize only when larger provider-backed traces are introduced. |
| Request/body limits | PARTIAL | Pydantic bounds investigator fields and AI questions to 1,000 characters; no global body-size middleware is configured. Add at the deployment edge before exposing the API publicly. |
| LLM context budgets | PARTIAL | The structured context limits transactions and output tokens, but does not enforce a serialized prompt byte/token budget across every collection. The demo has bounded data; add explicit budgeting before live LLM use. |
| Provider selection / live provider | NOT STARTED | The exercised service intentionally uses the labelled DemoProvider; no live credentials or network provider is configured. Do not represent this as live blockchain support. |

No P1 item above justified a code change in this pass. The P0 gate remains green and the private checkpoint is pushed at 83553247b2ec669e1468e686cd22626db00caa12.

## App-first delivery governance - 2026-09-03

| Gate | Status | Evidence / limitation |
|---|---|---|
| App-first founder decision | COMPLETE | Recorded in the governing context, project brain, architecture notes, and decision log; this supersedes the earlier unresolved mobile wording without claiming delivery. |
| Shared desktop/mobile functional source | PARTIAL | Existing frontend/API/state remain the source to reuse; mobile-specific architecture and validation are not yet implemented. |
| Installable Android application | NOT STARTED | No Android package exists yet. |
| Hosted HTTPS backend | NOT STARTED | Local FastAPI is verified; no hosted deployment has been performed. |
| Production PostgreSQL runtime | BLOCKED | Configuration and Docker Compose exist; runtime verification remains environment-blocked. |
| Production API endpoint configuration | PARTIAL | Production frontend requests now fail closed unless `NEXT_PUBLIC_API_URL` is explicitly set; hosted HTTPS endpoint is not yet provisioned. |
| Production database mode guard | COMPLETE | Backend rejects SQLite URLs and `USE_SQLITE=true` when `DEMO_MODE=false`; demo fallback remains available only in demo mode and regression-tested |

## App-first release prerequisites - 2026-09-03

| Gate | Status | Evidence / limitation |
|---|---|---|
| Android build toolchain | BLOCKED | Java 17 and Android SDK/API 34 emulator files are present, but Gradle and Android Studio are unavailable, adb execution is blocked, and no emulator/device validation has occurred |
| Mobile shell dependency | NOT STARTED | Capacitor was evaluated but not committed because no hosted frontend URL or Android build/validation environment is available; the existing web frontend remains the functional source |
| Hosted frontend/API | BLOCKED | No hosted HTTPS endpoint or deployment credentials are configured; production API client now fails closed without `NEXT_PUBLIC_API_URL` |
| Mobile workflow validation | BLOCKED | No real phone/emulator and no browser session are available for login-to-report validation |

## Frontend architecture preparation - 2026-09-03

| Gate | Status | Evidence / limitation |
|---|---|---|
| Institutional visual foundation | PARTIAL | Shared warm-neutral/teal tokens and safe palette translation are implemented; full screen-by-screen Stitch migration remains. |
| Replay component boundary | COMPLETE | Replay controls are isolated in `frontend/components/investigation/ReplayBar.tsx`; state and callbacks remain owned by the investigation workspace. |
| Dashboard phone-width structure | COMPLETE | Responsive content spacing, metric grid, case rows, and modal overflow are implemented and build-verified. |
| Investigation phone-width structure | PARTIAL | Navigation/graph/inspector stack responsively; touch/browser validation remains blocked. |
| Installable web experience | PARTIAL | `manifest.webmanifest`, standalone display metadata, theme color, and viewport metadata are present; this is not Android APK packaging. |
| Stitch screen migration | PARTIAL | Handoff reviewed and flagship visual language recorded; functional pages still contain legacy utility classes pending incremental migration. |

## Audit Log surface - 2026-09-03

| Gate | Status | Evidence / limitation |
|---|---|---|
| Case-scoped audit API | COMPLETE | `GET /cases/{case_id}/audit` enforces the existing owner/supervisor/admin case authorization and filters child-resource audit records by persisted case reference; IDOR regression coverage added |
| Investigator Audit Log UI | COMPLETE | Investigation navigation renders actor, action, timestamp, resource context, and structured details from the API; IP addresses are intentionally omitted |

## Evidence traceability surface - 2026-09-03

| Gate | Status | Evidence / limitation |
|---|---|---|
| Evidence context visibility | COMPLETE | Investigator evidence cards now render persisted source, timestamp, finding reference, and supporting transaction hash when returned by the existing evidence API |

## Stitch screen progression - 2026-09-03

| Screen / surface | Status | Evidence / limitation |
|---|---|---|
| Wallet Intake | COMPLETE | Existing dashboard case-creation flow now uses the institutional intake treatment, explicit Demo Network provenance, accessible field/dialog semantics, and existing backend validation; API behavior unchanged |
| Transaction Trace | PARTIAL | Existing investigation transaction data now uses a Stitch-aligned trace treatment with backend-derived transfer/hop/flagged summaries, explicit source → movement → destination cards, timestamp/source display, and direct mouse/keyboard selection; browser visual verification remains blocked |
| Flagship Investigation Overview | PARTIAL | Existing React Flow workspace now uses restrained institutional graph styling with backend-driven topology counts; money-trail focus, timeline, findings, evidence, replay, AI, and report state remain connected; browser verification is unavailable |
| Findings & Risk Analysis | PARTIAL | Backend-grounded findings/risk/WHY surface now uses a Stitch-aligned priority summary, deterministic-analysis label, affected-wallet WHY actions, and clickable supporting transaction hashes; browser visual verification remains blocked |
| Evidence Center | PARTIAL | Persisted traceability and save flow are present; the Evidence Center now exposes case-derived record counts, an explicit finding → reason → transaction chain, FACT provenance, and linked transaction context; browser visual verification remains blocked |
| Investigation Replay | PARTIAL | ReplayBar boundary, synchronized event state, event jump selector, labeled replay region, and accessible progress semantics exist; full visual treatment and browser interaction remain unverified |
| AI Copilot Workspace | PARTIAL | Case-grounded AI tab now labels AI Summary output, shows current finding/transfer/evidence grounding counts, offers core investigator prompts, and provides a pre-investigation empty/disabled state; browser visual verification remains blocked |
| Forensic Report | PARTIAL | Structured report generation/retrieval now identifies current-investigation output and Demo context, prevents pre-investigation generation, and presents a case-scoped document header; browser visual verification remains blocked |
| Audit Log | COMPLETE | Authorized case-scoped API and investigator UI are implemented and build/test covered |
| Settings | PARTIAL | Authenticated read-only Settings route and Dashboard entry now show account, security posture, provenance guidance, and active theme without exposing secrets; browser verification remains unavailable |

## Accessibility and touch hardening - 2026-09-03

| Surface | Status | Evidence / limitation |
|---|---|---|
| Dashboard case navigation | PARTIAL | Case rows now support keyboard activation and visible focus; actual browser/assistive-technology validation is unavailable |
| Investigation controls | PARTIAL | Primary actions, navigation, money-trail focus, transaction selection, and replay controls have phone-sized targets and accessible labels; replay controls wrap at narrow widths; touch/browser validation is unavailable |

## Android packaging readiness audit - 2026-09-03

| Gate | Status | Evidence / limitation |
|---|---|---|
| Android shell strategy | COMPLETE | Capacitor is the least-risk intended wrapper because the existing Next.js frontend remains the functional source; no native project is claimed yet |
| Frontend consumption model | PARTIAL | The app uses a dynamic Next.js route and is not configured for static export; packaging therefore requires a hosted HTTPS frontend origin or a separately verified static-export decision |
| Production API origin | PARTIAL | `NEXT_PUBLIC_API_URL` is explicit and production-fail-closed; no hosted HTTPS API endpoint is configured |
| Mobile web readiness | PARTIAL | Responsive layouts, touch-sized primary controls, responsive replay controls, modal overflow handling, and larger mobile ReactFlow controls are code/build verified; no real device validation |
| Android build toolchain | BLOCKED | Java 17 and Android SDK/API 34 emulator files are present, but Capacitor packages, Gradle, and Android Studio are unavailable, adb execution is blocked, and no emulator/device validation has occurred |
| Hosted frontend/API and CORS origin | BLOCKED | No hosted frontend/API URL or deployment credentials are available; production CORS must explicitly allow the eventual HTTPS frontend/native origin |

## Review-surface hardening - 2026-09-03

| Surface | Status | Evidence / limitation |
|---|---|---|
| AI pre-investigation state | COMPLETE | Copilot displays the grounded case context counts, exposes the core investigator prompts only after investigation data exists, and disables input before that state is available |
| Report pre-investigation state | COMPLETE | Report generation is unavailable until an investigation exists; generated output uses a case-scoped document header and retains structured fact/analysis/inference sections |
| Timeline empty state | COMPLETE | Timeline exposes an event count and a clear pre-investigation empty state rather than rendering a blank panel |
| Data-honesty copy | COMPLETE | Login footer identifies the SIH problem context instead of suggesting an institutional affiliation; demo/analysis/inference labels remain explicit |

## Staging deployment architecture - 2026-09-03

| Gate | Status | Evidence / limitation |
|---|---|---|
| Recommended staging topology | DOCUMENTED | `docs/DEPLOYMENT.md` recommends one Render project with dynamic Next.js, FastAPI, and managed PostgreSQL services; no service has been provisioned |
| Dynamic Next.js hosting | PREPARED | Existing `/investigate/[id]` remains dynamic; deployment must use a Node web service, not static export |
| Production configuration validation | IMPROVED | Non-demo settings now require non-local `DATABASE_URL`, exact non-empty `CORS_ORIGINS`, a safe `SECRET_KEY`, and `DEBUG=false`; frontend still requires explicit `NEXT_PUBLIC_API_URL` in hosted builds |
| PostgreSQL URL compatibility | PREPARED | Generic `postgresql://` and `postgres://` values normalize to the asyncpg SQLAlchemy dialect; actual PostgreSQL connectivity remains unverified |
| Non-demo provider safety | COMPLETE | Startup refuses `DEMO_MODE=false` while the only implemented provider is `DemoProvider`; no live integration was added |
| PostgreSQL migrations | BLOCKED | Startup still uses `Base.metadata.create_all`; Alembic configuration and migration history are absent, so the migration plan is documented but not implemented |
| Capacitor impact | DOCUMENTED | Hosted frontend/API origin, WebView storage, native origin, and deep-link validation requirements are recorded; Capacitor remains uninitialized |
