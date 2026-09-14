# CryptoTrace AI
## ONE WALLET. COMPLETE INVESTIGATION.

SIH26183 — Blockchain & Cybersecurity

### 🚀 Live Demo
https://cryptotrace-ai-1.onrender.com

### 🔧 Backend API
https://cryptotrace-ai-z7hp.onrender.com

### 📱 Android APK
[APK download link]

### 📂 Source Code
https://github.com/arorahemant/CryptoTrace-AI

# CryptoTrace AI

Investigator-focused prototype for tracing a reported wallet through normalized transactions, deterministic graph/pattern/risk analysis, evidence, replay, grounded explanations, and reports.

## Run locally

Backend production architecture is PostgreSQL (`docker compose up -d db`). SQLite is an explicit demo fallback only:

```powershell
cd backend
$env:USE_SQLITE='true'
$env:APP_ENV='local'
$env:DEMO_MODE='true'
$env:SEED_DEMO_ACCOUNTS='true'
python -m uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. With the explicit local demo settings above, credentials are `investigator` / `investigate123`, `supervisor` / `supervisor123`, `admin` / `admin123`, and `reporter` / `report123`. These accounts are unavailable when demo seeding is disabled or the environment is not local. Public staff registration is disabled. Administrators may provision investigators or supervisors; separate public reporter registration creates only reporter accounts. All synthetic records and inferred exchange attribution are labelled demo/simulated. Never treat risk or pattern output as a legal conclusion.

## Verification

`backend/test_p0.py` is an isolated HTTP smoke journey. `backend/test_p0_full.py` validates the complete API workflow. The pytest suite covers historical timestamps, traversal bounds, chain-aware wallet validation, IDOR/RBAC, reporter isolation, capability states, evidence persistence, and grounded deterministic Copilot responses. Run the checks in the current environment before relying on this description; this document does not assert a permanently passing build.

The local prototype applies a small in-memory failed-login throttle; production deployments should enforce distributed rate limiting at the gateway. See [docs/README.md](docs/README.md) for implementation-aligned project documentation.
