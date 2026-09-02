# Decisions

- Keep PostgreSQL as production architecture; allow SQLite only for explicit demo/local operation.
- Use deterministic explainable analysis for MVP.
- Return 404 for unauthorized case IDs.
- Refuse unsupported AI claims instead of guessing.
- Preserve historical demo timestamps and anchor configured windows to available history.
- Require an injected random `SECRET_KEY` (minimum 32 characters) when `DEMO_MODE=false`; generate an ephemeral process key only for local/demo startup when no key is configured.
- Treat investigation execution as an idempotent current snapshot per case. Repeated requests reuse persisted data; failed persistence is rolled back for retry rather than being hidden with an `IntegrityError` catch.
- Resolve the active user once through the case-route dependency and pass that identity through authorization checks.
- Record the current founder delivery decision as app-first: target an installable Android experience plus desktop support, a hosted HTTPS backend, production PostgreSQL, secure production configuration, and the complete phone investigation workflow without USB; this is scope, not a claim of current delivery.
- Use Capacitor as the intended Android shell when packaging begins because the existing Next.js frontend and API/state model are the functional source of truth. The current Next.js app is not a static export, so the least-risk packaging path is a Capacitor shell pointed at a hosted HTTPS frontend, with the same hosted API configured separately; native project generation is deferred until a hosted origin and Android build toolchain are available.
