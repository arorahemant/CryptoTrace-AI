# API

Base path `/api/v1`. Auth: `POST /auth/login`. Case APIs include create/list/detail, investigate, wallets, transactions, graph, fund-flow, timeline, findings, evidence GET/POST, audit history, WHY, replay, AI query, and report POST/GET. Case routes require bearer auth and owner/supervisor/admin access.

`GET /cases/{case_id}/audit?limit=100&offset=0` returns the authorized case-scoped audit history. It includes actor, timestamp, action, resource context, and structured non-sensitive details; IP addresses are not exposed. Child-resource events are matched to their case through their persisted case reference.

`POST /cases/{case_id}/replay` returns ordered events with `event_id`, `step`, `transaction_hash`, timestamp, source/destination addresses, `highlight_nodes`, `highlight_edges`, amount, and cumulative amount. The frontend uses these fields to synchronize the graph cursor, timeline cursor, selected transaction, and evidence context.

`POST /cases/{case_id}/evidence` persists an investigator bookmark. If a transaction, finding, or wallet is supplied, it must belong to the same case; the record is returned by the subsequent evidence read.

Database connection failures return HTTP 503 with a retryable response and do not expose connection details.
