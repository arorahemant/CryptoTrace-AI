# Security

The declared dependency set pins bcrypt 4.0.1 for Passlib 1.7.4 compatibility. Authentication tests run with that pinned version.

Bearer JWTs protect case routes. A non-demo configuration fails closed unless a random `SECRET_KEY` of at least 32 characters is injected. Demo mode generates an ephemeral process key when none is configured. Privileged demo accounts are seeded only when `APP_ENV=local`, `DEMO_MODE=true`, and `SEED_DEMO_ACCOUNTS=true`; marked or reserved staff demo accounts cannot log in when that gate is closed. `REPORTER_DEMO_LOGIN_ENABLED=true` is a separate hosted opt-in that permits only the existing, non-privileged `reporter@cryptotrace.ai` demo identity through the normal reporter authentication and ownership checks; it neither seeds nor enables staff accounts. `INVESTIGATOR_DEMO_LOGIN_ENABLED=true` separately permits only the existing `investigator@cryptotrace.ai` demo identity and does not enable the supervisor or administrator demo identities.

Public `POST /auth/register` cannot create staff accounts. Public reporter registration creates only a reporter. The first administrator is created through the interactive operator CLI; authenticated administrators may provision only investigators or supervisors through the API and may activate or deactivate non-admin staff.

The first admin can alternatively be created through the explicitly enabled
`POST /auth/bootstrap-first-admin` operator endpoint. Its dedicated
`FIRST_ADMIN_BOOTSTRAP_TOKEN` is a `SecretStr`, excluded from settings repr and
serialization, and compared in constant time with the request header. Missing,
empty, or malformed configuration disables the feature without affecting login.
Use a cryptographically random token containing at least 32 random bytes; the
accepted representation is 32–128 non-whitespace ASCII characters. Keep it
independent of every other service secret. Neither token nor plaintext password
is stored in the database or included in bootstrap responses, audit details, or
application log messages. Request validation and caught failures return fixed
errors, including malformed JSON and database errors.

The database singleton serializes requests; PostgreSQL also shares advisory lock
2618301 with the operator CLI. Admin existence is checked under the lock. Admin
creation, the `operator_admin_bootstrapped` audit event, and permanent consumption
commit atomically. The consumption row has no account foreign key and cannot be
reset through the API or by restarting the service. The global database attempt
budget is 10 per 15 minutes and includes failed requests. Exhausting it can delay
the operator; it does not affect login or any other endpoint. Demo admins do not
count as production admins, but reserved demo identities cannot be bootstrapped.

Remove the bootstrap environment variable after success. Do not enable request
header/body capture in a reverse proxy, APM or HTTP client for this route. Send
secrets only through HTTPS headers/body, never in URLs, command-line arguments,
source, or shell history. Restoring an older database backup also restores its
bootstrap state; keep the token removed during recovery. No mechanism inside the
same database can preserve a consumption record across restoring a pre-bootstrap
backup or deliberate database tampering.

Permissions are explicit for Reporter, Investigator, Supervisor, and Admin. Reporters create and read only their own submissions. Investigators mutate owned cases and may accept submissions. Supervisors review cases and submissions without case mutation rights. Administrators may review and mutate cases and manage non-admin staff. Case ownership and assigned-submission ownership are checked server-side. Unauthorized case and assigned-submission reads return 404 where applicable.

Analysis completion and investigator closure are separate. Successful processing records an analysis summary and leaves the case in review. An authorized write-capable user must explicitly close the case, which sets `closed_at`. Closure does not assert recovery, freezing, preservation, attribution verification, or any external action.

Capability responses distinguish data origin, provider connection, processing state, result state, timestamps, and limitations. Only the explicit Alchemy Ethereum Mainnet adapter can produce real observations. Unconfigured and unsupported chains return no observed data; configured-but-untested Ethereum does not claim connectivity. Legacy flags or arbitrary old summaries cannot establish a current observed run. Demo results remain synthetic. Action-request status is only a workflow record inside CryptoTrace and does not verify an external organization's action.

Evidence references are validated against the authorized case. Copilot responses currently use deterministic case-derived explanations; configured external LLM output is not used as factual attribution. Known/verified attribution requires authoritative provenance, a source reference, verification time, and supporting evidence or transaction hashes; otherwise it is downgraded to likely/inferred.

Login failures are throttled in-process at five failures per source IP per 60 seconds. Production still needs a shared rate-limit store or gateway. CORS uses an exact allowlist and rejects wildcard origins when credentials are enabled. Provider and LLM credentials remain backend-only. Case audit responses omit stored IP addresses.

No PostgreSQL production runtime has been verified in this phase. The in-process login throttle and SQLite demo fallback remain prototype controls requiring deployment-specific hardening. The database selector rejects SQLite when `DEMO_MODE=false`; this phase must not be described as production secure or fully secure.

Alchemy credentials are backend-only `SecretStr` settings excluded from settings serialization and repr. Requests use a fixed HTTPS host with redirects disabled. Provider bodies, request URLs, exceptions and headers are never logged or copied into errors/reports. Provenance contains public method names and chain/block identifiers only. The test suite clears operator credentials and uses sanitized public fixtures. Failed Ethereum attempts invalidate prior snapshots; archived evidence and reports cannot support the current run. Ethereum observations cannot create or advance an external asset-action request.
