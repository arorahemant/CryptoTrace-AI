# API

Base path `/api/v1`. Authentication uses `POST /auth/login`. `POST /auth/register` is a denied compatibility endpoint and cannot create staff accounts. `POST /auth/reporter/register` creates only a reporter. An authenticated administrator provisions active investigators or supervisors with `POST /auth/users` and may activate or deactivate non-admin staff with `PATCH /auth/users/{user_id}`. Initial administrator creation uses `backend/app/provision_admin.py`; the staff API cannot create administrators.

Reporters create and read only their own submissions. Investigators read and mutate owned cases and may review or accept submissions. Supervisors may review all cases and submissions but cannot mutate cases or action requests. Administrators may review and mutate cases, accept submissions, and manage non-admin staff access. Ownership is enforced separately from role permissions; unauthorized case and assigned-submission reads return 404 where applicable.

Case APIs include create/list/detail, investigate, wallets, transactions, graph, fund-flow, timeline, findings, evidence GET/POST, audit history, WHY, replay, Copilot query, close, and report POST/GET. Case detail includes effective `permissions` and a separate `lifecycle` (`open` or `closed`). Successful analysis records processing completion and leaves the case in review. Only `POST /cases/{case_id}/close` records investigator closure and sets `closed_at`.

`GET /capabilities` returns each intake network, its assets, and a structured capability object. Capability fields are `data_origin` (`none`, `demo`, `observed`), `provider_state` (`available`, `not_connected`), `processing_state` (`not_started`, `running`, `completed`, `failed`), `result_state` (`not_available`, `available`, `empty`, `partial`, `stale`), provider/timestamps, and limitations. The same contract is included on affected case, submission, analysis, recommendation, Copilot, report, and action surfaces. Every current non-demo chain reports no observed data and no connected provider; absence of a demo marker never means live or verified data.

`GET /cases/{case_id}` includes an `assignment` accountability object for an authorized case. It exposes only the persisted investigator ID, display name, role, initial assignment timestamp (the case creation time), and latest case-scoped activity timestamp. It does not expose email, username, credentials, tokens, or IP data. `history_available` is currently `false` because reassignment history is not yet modeled.

`GET /cases/{case_id}/audit?limit=100&offset=0` returns the authorized case-scoped audit history. It includes actor, timestamp, action, resource context, and structured non-sensitive details; IP addresses are not exposed. Child-resource events are matched to their case through their persisted case reference.

`POST /cases/{case_id}/replay` returns ordered events with `event_id`, `step`, `transaction_hash`, timestamp, source/destination addresses, `highlight_nodes`, `highlight_edges`, amount, and cumulative amount. The frontend uses these fields to synchronize the graph cursor, timeline cursor, selected transaction, and evidence context.

`POST /cases/{case_id}/evidence` persists an investigator bookmark. If a transaction, finding, or wallet is supplied, it must belong to the same case; the record is returned by the subsequent evidence read.

Investigator-only public case validation uses `GET /public-cases`, `GET /public-cases/{case_id}`, and `GET /public-cases/{case_id}/comparison`. These endpoints return curated source-backed reference data and element-by-element results. They do not create an investigation from undisclosed wallets or transactions; unavailable public identifiers remain `NOT OBSERVABLE`, and external outcomes are `NOT COMPARABLE` to CryptoTrace operational requests.

Database connection failures return HTTP 503 with a retryable response and do not expose connection details.

The frontend uses `http://localhost:8000/api/v1` only during `next dev`. Production and installed-app builds must set `NEXT_PUBLIC_API_URL` to the hosted HTTPS API; if it is missing, requests fail closed with a configuration message instead of silently targeting the device's localhost.
