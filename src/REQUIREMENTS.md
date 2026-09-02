# REQUIREMENTS.md — CryptoTrace AI

> Formal requirements model. Traceability chain for every requirement:
> `OFFICIAL SIH REQUIREMENT → USER NEED → PRODUCT CAPABILITY → TECHNICAL
> CAPABILITY → BACKEND → FRONTEND → DATA → OUTPUT → DEMO`.
> SOURCE ∈ {OFFICIAL SIH, PRODUCT, TECHNICAL, ASSUMPTION, FUTURE}.
> PRIORITY ∈ {P0, P1, P2}. STATUS reflects documentation state, not build
> state, since no code has been written under this document set yet.

---

## Traceability overview

```
OFFICIAL SIH REQUIREMENT (SIH26183: victim wallet → fraud-linked exchange, real-time, automated)
        ↓
USER NEED (investigator: trace + explain + report faster/better than manual)
        ↓
PRODUCT CAPABILITY (TRACE → MAP → DETECT → EXPLAIN → REPORT)
        ↓
TECHNICAL CAPABILITY (trace/graph/pattern/attribution/risk/evidence engines)
        ↓
BACKEND (application layer + domain engines, per ARCHITECTURE.md)
        ↓
FRONTEND (case workspace UI, per ARCHITECTURE.md §9)
        ↓
DATA (blockchain provider + address-intelligence source, per ARCHITECTURE.md §14–15)
        ↓
OUTPUT (findings, evidence, report)
        ↓
DEMO (investigator walkthrough of one traced case)
```

---

## P0 — MVP core (proves the workflow end-to-end, one chain)

### REQ-001
- **Category:** Case Management
- **Description:** Investigator can create a case by submitting one wallet
  address (plus chain/asset if applicable).
- **Source:** OFFICIAL SIH (victim-reported wallet is the entry point) →
  PRODUCT (case as the unit of work)
- **User:** Investigator (primary)
- **Priority:** P0
- **Dependencies:** AUTH (REQ-002)
- **Success criteria:** A case record exists, owned by the submitting
  investigator, containing the input wallet.
- **Evidence:** N/A (input capture step)
- **Demo step:** Investigator enters a wallet address and starts a case.
- **Status:** DEFINED (documentation only — not built)

### REQ-002
- **Category:** Security / Auth
- **Description:** Investigator authenticates before accessing any case.
- **Source:** TECHNICAL (ARCHITECTURE.md §20–21)
- **User:** Investigator, Admin
- **Priority:** P0
- **Dependencies:** none
- **Success criteria:** Unauthenticated requests are rejected; a case is
  only visible to its owner (or explicitly authorized roles).
- **Evidence:** N/A
- **Demo step:** Login before case access is shown.
- **Status:** DEFINED

### REQ-003
- **Category:** Trace
- **Description:** System retrieves and traces transaction history from the
  input wallet, bounded by explicit parameters (max hops, time window, min
  amount).
- **Source:** OFFICIAL SIH (automated blockchain analytics) → TECHNICAL
  (ARCHITECTURE.md §12 TRACE)
- **User:** Investigator
- **Priority:** P0
- **Dependencies:** REQ-001, blockchain data provider integration (single
  chain — chain selection is an **open founder decision**, PROJECT_BRAIN.md
  §26 Q1)
- **Success criteria:** A bounded transaction set is produced with cycle
  protection and a defined stopping condition; no unlimited crawling.
- **Evidence:** Raw transactions retrieved, with provider/query provenance
  recorded.
- **Demo step:** Trace runs and completes within a demo-acceptable time.
- **Status:** DEFINED — **chain and provider choice UNRESOLVED (open
  question)**

### REQ-004
- **Category:** Graph
- **Description:** System builds a wallet-node/transaction-edge graph from
  the traced transaction set and renders it to reduce investigator
  cognitive load (not a 1:1 raw dump).
- **Source:** PRODUCT (MAP step) → TECHNICAL (ARCHITECTURE.md §12 GRAPH)
- **User:** Investigator
- **Priority:** P0
- **Dependencies:** REQ-003
- **Success criteria:** Graph renders for a traced case; visually
  distinguishes higher-relevance nodes/paths.
- **Evidence:** Graph is derived directly from the same transaction set as
  REQ-003 (no separate/divergent data source).
- **Demo step:** Investigator views the fund-flow graph for the case.
- **Status:** DEFINED

### REQ-005
- **Category:** Pattern Detection
- **Description:** System evaluates the traced graph against a defined set
  of deterministic suspicious-pattern rules (at minimum: splitting and
  rapid movement, per ARCHITECTURE.md §12 PATTERNS) and produces findings.
- **Source:** OFFICIAL SIH (fraud-linked identification) → PRODUCT (DETECT
  step)
- **User:** Investigator
- **Priority:** P0
- **Dependencies:** REQ-004
- **Success criteria:** Each triggered pattern produces a finding naming the
  specific transactions that triggered it.
- **Evidence:** Finding → transaction linkage per ARCHITECTURE.md §17.
- **Demo step:** A flagged pattern is shown with its supporting
  transactions.
- **Status:** DEFINED — **exact rule thresholds UNSPECIFIED (founder/data
  decision)**

### REQ-006
- **Category:** Attribution
- **Description:** System attempts to attribute terminal/intermediary
  addresses to a known entity (candidate exchange/VASP), tagged
  KNOWN/VERIFIED, LIKELY/INFERRED, or UNKNOWN.
- **Source:** OFFICIAL SIH (identification of fraud-linked exchanges) →
  PRODUCT
- **User:** Investigator
- **Priority:** P0
- **Dependencies:** REQ-003; an address-intelligence data source
  (ARCHITECTURE.md §15 — **UNKNOWN/unresolved**)
- **Success criteria:** Every attribution result carries a tier and stated
  basis; UNKNOWN is a valid, non-error output.
- **Evidence:** Basis for the tier (matched label source, or heuristic
  signal) is shown.
- **Demo step:** A candidate exchange address is shown with its confidence
  tier and reasoning.
- **Status:** DEFINED — **attribution data source UNRESOLVED; MVP may only
  achieve LIKELY/UNKNOWN tiers without a real source, and this limitation
  must be disclosed, not hidden, in the demo**

### REQ-007
- **Category:** Risk
- **Description:** System computes a transparent, deterministic risk/
  prioritization score from the findings above.
- **Source:** PRODUCT (PROJECT_BRAIN.md §15 Risk Philosophy)
- **User:** Investigator
- **Priority:** P0
- **Dependencies:** REQ-005, REQ-006
- **Success criteria:** Score is explainable (traceable to which findings
  contributed) and is presented as prioritization, never as a legal/
  criminal determination.
- **Evidence:** Contributing findings are listed alongside the score.
- **Demo step:** Case risk score shown with its contributing factors.
- **Status:** DEFINED

### REQ-008
- **Category:** Evidence
- **Description:** Every finding (pattern, attribution, risk) is linked to
  its underlying transaction-level evidence in a consistent evidence store.
- **Source:** PRODUCT (Evidence Philosophy) — non-negotiable per
  PROJECT_BRAIN.md §14
- **User:** Investigator
- **Priority:** P0
- **Dependencies:** REQ-005, REQ-006, REQ-007
- **Success criteria:** Investigator can click any finding and see the
  exact transaction(s) behind it.
- **Evidence:** This requirement IS the evidence linkage; self-referential.
- **Demo step:** Investigator opens the evidence panel behind a finding.
- **Status:** DEFINED

### REQ-009
- **Category:** Reporting
- **Description:** System generates a structured report from case data,
  findings, evidence, attribution, and risk score.
- **Source:** PRODUCT (REPORT step)
- **User:** Investigator, Supervisor
- **Priority:** P0
- **Dependencies:** REQ-003 through REQ-008
- **Success criteria:** Report content matches what's shown in-app (no
  divergence); demo-data/confidence labeling is preserved in the report.
- **Evidence:** Report cites the same evidence IDs as the in-app panel.
- **Demo step:** Investigator generates and reviews the case report.
- **Status:** DEFINED — **export format UNSPECIFIED**

### REQ-010
- **Category:** Security / Audit
- **Description:** Investigator actions on a case (view, trace, include in
  report) are logged.
- **Source:** TECHNICAL (ARCHITECTURE.md §19 Audit boundary)
- **User:** Investigator, Admin
- **Priority:** P0
- **Dependencies:** REQ-002
- **Success criteria:** An audit trail exists per case with actor/
  timestamp/action.
- **Evidence:** N/A
- **Demo step:** (optional for demo) audit log shown for a case.
- **Status:** DEFINED

### REQ-011
- **Category:** Data Honesty
- **Description:** Any non-live/synthetic data used anywhere in the product
  (including demo scenarios) is visibly labeled DEMO DATA and never
  presented as live blockchain data.
- **Source:** PRODUCT — non-negotiable per PROJECT_BRAIN.md §20
- **User:** All
- **Priority:** P0
- **Dependencies:** none
- **Success criteria:** No screen or report can display synthetic data
  without a visible label.
- **Evidence:** N/A
- **Demo step:** If demo data is used, the label is visibly shown to judges.
- **Status:** DEFINED

---

## P1 — Strengthens the MVP story, not required for the first working slice

### REQ-012
- **Category:** AI
- **Description:** AI explanation layer summarizes case findings in
  investigator-readable language, grounded strictly in the evidence already
  produced by REQ-005–008.
- **Source:** PRODUCT (AI Philosophy) → TECHNICAL (ARCHITECTURE.md §16)
- **User:** Investigator
- **Priority:** P1
- **Dependencies:** REQ-008
- **Success criteria:** AI output never introduces a claim not backed by
  existing evidence; confidence levels are preserved, not invented.
- **Evidence:** AI text is traceable to the same evidence IDs it describes.
- **Demo step:** AI-generated case summary shown alongside its grounding.
- **Status:** DEFINED — **grounding enforcement mechanism UNVALIDATED, needs
  actual evaluation before being trusted**

### REQ-013
- **Category:** Case Management
- **Description:** Supervisor role can review a case/report without
  necessarily having trace/graph tool access.
- **Source:** PRODUCT (User model, PROJECT_BRAIN.md §4)
- **User:** Supervisor
- **Priority:** P1
- **Dependencies:** REQ-002, REQ-009
- **Success criteria:** Supervisor can view but role permissions differ from
  investigator.
- **Evidence:** N/A
- **Demo step:** Optional — role-based view shown.
- **Status:** DEFINED

### REQ-014
- **Category:** Investigation Model
- **Description:** Replay of the trace/graph-construction sequence,
  synchronized across timeline/graph/transaction/evidence.
- **Source:** PRODUCT (Investigation Model) — value UNPROVEN per
  PROJECT_BRAIN.md §12
- **User:** Investigator
- **Priority:** P1 (candidate for DEFER — see status)
- **Dependencies:** REQ-003, REQ-004
- **Success criteria:** UNDEFINED pending a founder decision on whether this
  provides genuine value.
- **Evidence:** N/A
- **Demo step:** N/A
- **Status:** **RESEARCH** — classified per the founder decision framework;
  do not build before P0 is solid (ARCHITECTURE.md §27)

### REQ-015
- **Category:** Admin
- **Description:** Admin can manage investigator accounts and roles.
- **Source:** TECHNICAL
- **User:** Admin
- **Priority:** P1
- **Dependencies:** REQ-002
- **Success criteria:** Admin can create/deactivate accounts and assign
  roles.
- **Evidence:** N/A
- **Demo step:** Optional.
- **Status:** DEFINED

---

## P2 / FUTURE — explicitly deferred

### REQ-016
- **Category:** Data Strategy
- **Description:** Multi-blockchain support with a normalized cross-chain
  data model.
- **Source:** FUTURE
- **Priority:** P2
- **Status:** FUTURE — not started, not designed in detail here.

### REQ-017
- **Category:** Investigation Model
- **Description:** Cross-case pattern intelligence (recognizing recurring
  networks/wallets across multiple investigations).
- **Source:** FUTURE
- **Priority:** P2
- **Status:** FUTURE

### REQ-018
- **Category:** Collaboration
- **Description:** Multiple investigators collaborating on one case
  concurrently.
- **Source:** FUTURE
- **Priority:** P2
- **Status:** FUTURE

### REQ-019
- **Category:** Integrations
- **Description:** Integration with external case-management or law-
  enforcement systems.
- **Source:** FUTURE — **no such integration exists or is assumed to be
  obtainable; must never be claimed as current capability (PROJECT_BRAIN.md
  §20)**
- **Priority:** P2
- **Status:** FUTURE / UNKNOWN feasibility

### REQ-020
- **Category:** Data Strategy
- **Description:** Paid/commercial-grade address-intelligence integration
  for higher-confidence KNOWN/VERIFIED attribution.
- **Source:** FUTURE — cost/access UNKNOWN
- **Priority:** P2
- **Status:** FUTURE

---

## Gaps, ambiguities, and unresolved items (explicit — not silently closed)

1. **Chain/asset selection for MVP (REQ-003):** unresolved, requires a
   founder decision weighing data-provider availability, cost, and demo
   relevance.
2. **Address-intelligence source (REQ-006):** unresolved; without one, MVP
   attribution may be limited to heuristic LIKELY/UNKNOWN tiers only — this
   is a real capability gap, not a documentation gap, and should shape how
   the product is pitched.
3. **Pattern rule thresholds (REQ-005):** not numerically specified; needs
   either data-driven tuning or a documented, defensible default.
4. **"Real-time" interpretation:** the official problem statement's
   real-time requirement has not been translated into a concrete technical
   target (true streaming vs. on-demand current data) — see
   PROJECT_BRAIN.md §26 Q4.
5. **Report export format (REQ-009):** unspecified.
6. **Replay value (REQ-014):** unvalidated; flagged RESEARCH rather than
   committed P1.
7. **Legal/evidentiary standard for the evidence model:** explicitly
   UNKNOWN and out of scope; REQ-008/009 must not claim legal admissibility.
8. **Buyer/approver identity and procurement path:** UNKNOWN, not invented,
   not required to be resolved for MVP but relevant to any business framing
   used with judges.

Every gap above should be either resolved by an explicit founder decision
(recorded by updating this file) or deliberately carried forward as a
disclosed limitation — never silently assumed away.
