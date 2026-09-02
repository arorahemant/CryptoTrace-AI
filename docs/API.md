# API

Base path `/api/v1`. Auth: `POST /auth/login`. Case APIs include create/list/detail, investigate, wallets, transactions, graph, fund-flow, timeline, findings, evidence GET/POST, WHY, replay, AI query, and report POST/GET. Case routes require bearer auth and owner/supervisor/admin access.

`POST /cases/{case_id}/replay` returns ordered events with `event_id`, `step`, `transaction_hash`, timestamp, source/destination addresses, `highlight_nodes`, `highlight_edges`, amount, and cumulative amount. The frontend uses these fields to synchronize the graph cursor, timeline cursor, selected transaction, and evidence context.

`POST /cases/{case_id}/evidence` persists an investigator bookmark. If a transaction, finding, or wallet is supplied, it must belong to the same case; the record is returned by the subsequent evidence read.

Database connection failures return HTTP 503 with a retryable response and do not expose connection details.
