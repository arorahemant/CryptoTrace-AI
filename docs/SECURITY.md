# Security

The declared dependency set pins bcrypt 4.0.1 for Passlib 1.7.4 compatibility. Authentication tests run with that pinned version.

Bearer JWTs protect case routes. A non-demo configuration fails closed unless a random `SECRET_KEY` of at least 32 characters is injected. Demo mode generates an ephemeral process key when none is configured. Privileged demo accounts are seeded only when `APP_ENV=local`, `DEMO_MODE=true`, and `SEED_DEMO_ACCOUNTS=true`; marked or reserved demo accounts cannot log in when that gate is closed.

Public `POST /auth/register` cannot create staff accounts. Public reporter registration creates only a reporter. The first administrator is created through the interactive operator CLI; authenticated administrators may provision only investigators or supervisors through the API and may activate or deactivate non-admin staff.

Permissions are explicit for Reporter, Investigator, Supervisor, and Admin. Reporters create and read only their own submissions. Investigators mutate owned cases and may accept submissions. Supervisors review cases and submissions without case mutation rights. Administrators may review and mutate cases and manage non-admin staff. Case ownership and assigned-submission ownership are checked server-side. Unauthorized case and assigned-submission reads return 404 where applicable.

Analysis completion and investigator closure are separate. Successful processing records an analysis summary and leaves the case in review. An authorized write-capable user must explicitly close the case, which sets `closed_at`. Closure does not assert recovery, freezing, preservation, attribution verification, or any external action.

Capability responses distinguish data origin, provider connection, processing state, result state, timestamps, and limitations. No live blockchain provider has been verified. Non-demo cases therefore return `data_origin=none`, `provider_state=not_connected`, and no available result even if legacy flags or summaries exist. Demo results remain synthetic. Action-request status is only a workflow record inside CryptoTrace and does not verify an external organization's action.

Evidence references are validated against the authorized case. Copilot responses currently use deterministic case-derived explanations; configured external LLM output is not used as factual attribution. Known/verified attribution requires authoritative provenance, a source reference, verification time, and supporting evidence or transaction hashes; otherwise it is downgraded to likely/inferred.

Login failures are throttled in-process at five failures per source IP per 60 seconds. Production still needs a shared rate-limit store or gateway. CORS uses an exact allowlist and rejects wildcard origins when credentials are enabled. Provider and LLM credentials remain backend-only. Case audit responses omit stored IP addresses.

No PostgreSQL production runtime has been verified in this phase. The in-process login throttle and SQLite demo fallback remain prototype controls requiring deployment-specific hardening. The database selector rejects SQLite when `DEMO_MODE=false`; this phase must not be described as production secure or fully secure.
