# CryptoTrace AI

Investigator-focused prototype for tracing a reported wallet through normalized transactions, deterministic graph/pattern/risk analysis, evidence, replay, grounded explanations, and reports.

## Run locally

Backend production architecture is PostgreSQL (`docker compose up -d db`). SQLite is an explicit demo fallback only:

```powershell
cd backend
$env:USE_SQLITE='true'
python -m uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. Demo credentials are `investigator` / `investigate123`; review roles are `supervisor` / `supervisor123` and `admin` / `admin123`. All synthetic records and inferred exchange attribution are labelled demo/simulated. Never treat risk or pattern output as a legal conclusion.

## Verification

`backend/test_p0.py` is an isolated HTTP smoke journey. `backend/test_p0_full.py` validates the complete API workflow. The focused pytest suite covers historical timestamps, traversal bounds, chain-aware wallet validation, IDOR/RBAC, evidence persistence, and AI grounding/adversarial refusal. The frontend production build and lint checks pass with zero reported issues.

The local prototype applies a small in-memory failed-login throttle; production deployments should enforce distributed rate limiting at the gateway. See [docs/README.md](docs/README.md) for implementation-aligned project documentation.
