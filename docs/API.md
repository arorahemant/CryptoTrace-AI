# API

Base path `/api/v1`. Authentication uses `POST /auth/login`. `POST /auth/register` is a denied compatibility endpoint and cannot create staff accounts. `POST /auth/reporter/register` creates only a reporter. An authenticated administrator provisions active investigators or supervisors with `POST /auth/users` and may activate or deactivate non-admin staff with `PATCH /auth/users/{user_id}`. Initial administrator creation uses `backend/app/provision_admin.py`; the staff API cannot create administrators.

`POST /auth/bootstrap-first-admin` is a separate, one-time operator bootstrap,
disabled unless `FIRST_ADMIN_BOOTSTRAP_TOKEN` is explicitly configured. Send that
secret only in the `X-First-Admin-Bootstrap-Token` header over HTTPS. The JSON body
requires `username`, `email`, `full_name`, and `password`; no `role` or extra fields
are accepted. Passwords require 12–72 characters and at most 72 UTF-8 bytes.
The endpoint always creates an active, non-demo admin using the existing bcrypt
hasher. It returns only `{"detail":"Administrator provisioned"}` (201), never a
JWT or account fields. Sign in separately using the unchanged login endpoint.

Failures contain only a fixed `detail`: 404 when disabled/misconfigured, 403 for
missing/invalid token, 409 for unavailable bootstrap or identity conflict, 422
for invalid input, 429 for exhausted attempts, and 503 for internal/database
failure. Responses use `Cache-Control: no-store`. A database-wide budget allows
10 attempts per 15-minute window, including invalid tokens and invalid bodies;
it survives worker restarts and token rotation. Authenticated bodies are limited
to 8 KiB and five seconds to read/validate.

An existing non-demo admin (including an inactive one) blocks bootstrap. A
permanent singleton record prevents reuse even after deleting/demoting the admin,
rotating the token, or redeploying. The operator CLI shares this guard. Migration
`0009_first_admin_bootstrap` initializes the guard and marks it consumed on
databases already containing a non-demo admin. Bootstrap fails closed if this
migration's state is missing. See [Deployment](DEPLOYMENT.md#one-time-production-admin-bootstrap).

Reporters create and read only their own submissions. Investigators read and mutate owned cases and may review or accept submissions. Supervisors may review all cases and submissions but cannot mutate cases or action requests. Administrators may review and mutate cases, accept submissions, and manage non-admin staff access. Ownership is enforced separately from role permissions; unauthorized case and assigned-submission reads return 404 where applicable.

Case APIs include create/list/detail, investigate, wallets, transactions, graph, fund-flow, timeline, findings, evidence GET/POST, audit history, WHY, replay, Copilot query, close, and report POST/GET. Case detail includes effective `permissions` and a separate `lifecycle` (`open` or `closed`). Successful analysis records processing completion and leaves the case in review. Only `POST /cases/{case_id}/close` records investigator closure and sets `closed_at`.

`GET /capabilities` returns each intake network, its assets, and a structured capability object. Capability fields are `data_origin` (`none`, `demo`, `observed`), `provider_state` (`available`, `not_connected`), `processing_state` (`not_started`, `running`, `completed`, `failed`), `result_state` (`not_available`, `available`, `empty`, `partial`, `stale`), provider/timestamps, and limitations. The same contract is included on affected case, submission, analysis, recommendation, Copilot, report, and action surfaces. Ethereum Mainnet now supports bounded Alchemy observations. Its capability also includes `can_investigate`, `observation_state`, `coverage`, and the shared `destination`. Other real chains remain unconnected; absence of a demo marker never means observed or verified data.

`GET /cases/{case_id}` includes an `assignment` accountability object for an authorized case. It exposes only the persisted investigator ID, display name, role, initial assignment timestamp (the case creation time), and latest case-scoped activity timestamp. It does not expose email, username, credentials, tokens, or IP data. `history_available` is currently `false` because reassignment history is not yet modeled.

`GET /cases/{case_id}/audit?limit=100&offset=0` returns the authorized case-scoped audit history. It includes actor, timestamp, action, resource context, and structured non-sensitive details; IP addresses are not exposed. Child-resource events are matched to their case through their persisted case reference.

`POST /cases/{case_id}/replay` returns ordered transfer events with `event_id`, `transfer_id`, `run_id`, `step`, `transaction_hash`, timestamp, addresses, `highlight_nodes`, and `highlight_edges`. Graph edge IDs match transfer IDs. New events carry exact `amount_base_units` (integer string), `token_decimals`, `amount_exact` (decimal string), and chain-qualified `asset_id`. Numeric `amount` is a compatibility projection, not an accounting input. `transfer_volume_by_asset` keeps assets separate; deprecated `cumulative_amount` and `total_amount_traced` are null because adding movements across hops does not measure unique funds. Origin outflow is separately reported by asset.

Demo Network retains the Phase 2A snapshot-reuse behavior. New runs have a UUID and stored trace parameters; repeated investigation requests explicitly return `snapshot_reused: true` with the same run ID. Legacy snapshots use `legacy:<case-id>` and legacy transfer records remain `legacy_approximate`, without invented base units or decimals. Migration `0008_transfer_metadata` adds event uniqueness and exact projection metadata without backfilling legacy precision.

The graph preserves parallel transfer edges. Its primary route uses bounded shortest-path traversal with lexicographic ties, never summed hop values. Destination selection is shared across graph, findings, recommendations, readiness, and reports: supported service address, candidate VASP, last observed wallet, then unexpanded frontier; ties use hop distance and address. Expansion limits/errors remain separate from attribution. Routes are structural review aids, not proof of temporal continuity, custody, recoverability, or ownership. Ethereum observations never generate automatic VASP attributions.

`POST /cases/{case_id}/evidence` persists an investigator bookmark. If a transfer, transaction, finding, or wallet is supplied, it must belong to the same case. A hash containing multiple transfer events requires `transfer_id`; legacy event IDs remain usable. Exact transfer metadata is copied server-side, not trusted from client metadata.

Investigator-only public case validation uses `GET /public-cases`, `GET /public-cases/{case_id}`, and `GET /public-cases/{case_id}/comparison`. These endpoints return curated source-backed reference data and element-by-element results. They do not create an investigation from undisclosed wallets or transactions; unavailable public identifiers remain `NOT OBSERVABLE`, and external outcomes are `NOT COMPARABLE` to CryptoTrace operational requests.

Database connection failures return HTTP 503 with a retryable response and do not expose connection details.

The frontend uses `http://localhost:8000/api/v1` only during `next dev`. Production and installed-app builds must set `NEXT_PUBLIC_API_URL` to the hosted HTTPS API; if it is missing, requests fail closed with a configuration message instead of silently targeting the device's localhost.

## Phase 2B Ethereum observations

`POST /cases/{case_id}/investigate` for Ethereum requires `from_block` (non-negative integer); optional `to_block` must be at least the start and no later than finalized. Missing/reversed input returns 422. An omitted end is pinned once to finalized. `max_hops` is capped at 2; the server caps transfers at 100, provider requests at 200, and the observation run at 10 seconds with sequential requests and at most two retries. `direction` supports incoming, outgoing, or both. Ethereum ignores Demo amount/time-window filters.

Expected provider failure is a persisted result with `processing_state=failed`, `result_state=not_available`, a fresh `run_id`, safe error codes and coverage; it does not roll back into the prior successful result. Partial observations retain only reconciled current-run records and carry partial coverage. Unavailable current observation endpoints return 409 rather than serving an old snapshot. Unexpected internal failures invalidate the old snapshot and return 500 with safe capability metadata.

Each Ethereum POST starts a fresh run (`snapshot_reused=false`). Graph, transfer/evidence metadata, capability, recommendations, readiness and reports refer to that run and its selected candidate. Archived evidence/reports never become current-run artifacts. Report GET returns 404 when no report exists for the current successful run. Ethereum external-action creation or status changes return 409; readiness stays false. Findings are empty and risk is unassessed in this observation-only slice.

See [Blockchain data](BLOCKCHAIN_DATA.md) for exact reconciliation, supported categories, states and limitations. No schema migration beyond the existing head is required.
