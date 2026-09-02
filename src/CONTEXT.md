# CONTEXT.md — CryptoTrace AI

> Read this first. This file exists so any new agent (human or AI) can understand
> the project in under five minutes, without re-deriving decisions that have
> already been made — and without assuming decisions exist that haven't been made yet.

---

## 1. Identity

- **Project name:** CryptoTrace AI
- **Tagline:** "ONE WALLET. COMPLETE INVESTIGATION."
- **Competition:** Smart India Hackathon (SIH) 2026
- **Problem Statement ID:** SIH26183
- **Official problem statement (verbatim, source of truth):**
  > "Real-Time Identification of Fraud-Linked Cryptocurrency Exchanges from
  > Victim-Reported Suspect Wallet Addresses through Automated Blockchain Analytics"
- **Organization (as stated in the problem statement):** Ministry of Home Affairs
- **Category:** Software
- **Theme:** Blockchain & Cybersecurity

**FACT vs interpretation:** The problem statement text above is OFFICIAL SIH SOURCE
MATERIAL. Everything past this point that is not a direct quote of that statement
is OUR PRODUCT INTERPRETATION, and is labeled accordingly throughout this document
set.

## 2. Founder-stage status (important)

This project is currently at the **FOUNDATION STAGE**. Treat it as:

> A PRODUCT IDEA WITH A STRONG PROBLEM HYPOTHESIS — NOT a finished architecture,
> NOT a finished codebase, NOT a validated business.

**Do not assume that any previously-generated code, if it exists in this
repository, reflects the current or correct product decisions.** Code may be
stale, exploratory, or wrong. These four documents (CONTEXT, PROJECT_BRAIN,
ARCHITECTURE, REQUIREMENTS) are the source of truth for product and technical
direction going forward. If code contradicts these documents, the documents win
unless a human founder explicitly says otherwise.

## 3. The problem (short form)

A fraud victim can usually identify **one** wallet address involved in the
scam — e.g., the wallet they sent funds to. From there:

- Funds typically move through several intermediary wallets ("hops") before
  reaching a cash-out point, commonly a cryptocurrency exchange or VASP
  (Virtual Asset Service Provider).
- Investigators today must manually explore this trail using generic
  blockchain explorers, spreadsheets, and ad-hoc tooling.
- This is slow, error-prone, hard to explain to non-technical stakeholders
  (courts, supervisors, victims), and hard to defend as evidence.

CryptoTrace AI's product interpretation: turn **one reported wallet** into an
**understandable, explainable investigation** — not just a longer list of
transactions.

## 4. Primary user

**Primary user: the investigator** — a person (e.g. cybercrime cell officer,
financial-crime analyst) who receives a victim-reported wallet and needs to
determine where funds went, who touched them, and where they likely exited
(which exchange/VASP), with enough evidence to act on or escalate.

Other user roles (supervisor, admin, buyer/approver) are **not assumed to be
the same person as the investigator** — see PROJECT_BRAIN.md §4 for the full
user model. This distinction matters for MVP scope: MVP targets the
investigator role only.

## 5. Core workflow (North Star)

```
TRACE → MAP → DETECT → EXPLAIN → REPORT
```

Extended conceptual flow (not all of this is MVP — see REQUIREMENTS.md):

```
ONE WALLET → BLOCKCHAIN DATA → TRACE FUND MOVEMENT → MAP NETWORK →
IDENTIFY INTERMEDIARIES → DETECT SUSPICIOUS PATTERNS →
ATTRIBUTE (where evidence permits) → ASSESS RISK → EXPLAIN WHY →
SHOW EVIDENCE → REPLAY → AI INVESTIGATION ASSISTANCE → REPORT
```

Product statement: **"We don't just show transactions. We explain the money
trail."**

## 6. What CryptoTrace AI is NOT

Explicit non-goals — restating these prevents scope creep and prevents the
product from being misread as something it isn't:

- Not a crypto trading app
- Not an investment/portfolio app
- Not a price predictor
- Not a wallet (does not hold funds or keys)
- Not an NFT platform
- Not a generic blockchain explorer (it must add investigation value beyond
  what Etherscan-class tools already give an investigator for free)
- Not a generic chatbot with blockchain data bolted on

## 7. Evidence rules (non-negotiable)

- Every finding investigators see must be traceable to underlying data:
  `FINDING → REASON → EVIDENCE → TRANSACTION`.
- The system must never present demo/synthetic data as if it were real
  observed blockchain data. Any non-live data shown must be labeled
  **DEMO DATA**.
- Confidence must be stated wherever attribution or pattern detection is
  probabilistic. "Likely" and "Unknown" are legitimate, expected states — not
  failures.

## 8. AI rules (non-negotiable)

- AI is an **explanation and assistance layer**, never the source of truth.
- Trust hierarchy (see PROJECT_BRAIN.md §18 and ARCHITECTURE.md §16 for full
  detail):
  ```
  OBSERVED DATA → DETERMINISTIC ANALYSIS → EVIDENCE → INFERENCE → AI SUMMARY
  ```
- AI must never assert identity or criminality (e.g. never "this person is a
  criminal"). Acceptable framing: "Suspicious transaction characteristics
  detected," "Likely attribution — confidence: X — supporting evidence: ...".
- AI outputs must be grounded in and cite the deterministic evidence already
  computed by the system, not generate new claims unsupported by data.

## 9. Security principles (summary — full detail in ARCHITECTURE.md §22)

Authentication, RBAC, case-level authorization (prevent IDOR/BOLA across
cases), audit logging of investigator actions, input validation, rate
limiting on external data calls, secrets management, and data minimization
are all treated as MVP-relevant, not "later" concerns, because this is an
investigation tool whose outputs may be relied upon.

## 10. Data honesty rules (non-negotiable — see PROJECT_BRAIN.md §20)

Never claim, unless explicitly and actually true and evidenced:
government integration, police integration, VASP partnership, validated
accuracy figures, legal admissibility, confirmed criminal identity, or true
real-time capability. Default to labeling: DEMO DATA, LIKELY/INFERRED,
UNKNOWN, ASSUMPTION, UNVALIDATED, FUTURE.

## 11. MVP principle

The MVP is the **smallest end-to-end slice that proves the core workflow**
(TRACE → MAP → DETECT → EXPLAIN → REPORT) on **one blockchain**, not an
accumulation of every feature discussed. See REQUIREMENTS.md for the P0/P1/P2
split and PROJECT_BRAIN.md §21 for MVP philosophy.

## 12. Terminology

| Term | Meaning in this project |
|---|---|
| VASP | Virtual Asset Service Provider — e.g. a cryptocurrency exchange, custodial service, or similar entity that can convert crypto to fiat or move it off-chain |
| Hop | One wallet-to-wallet transfer in a traced fund-movement path |
| Attribution | Associating a wallet address with a real-world entity (e.g. a named exchange) |
| Case | The unit of investigation work — one reported wallet and everything traced from it |
| Finding | A discrete claim the system surfaces to the investigator (e.g. "high-risk intermediary detected") |
| Evidence | The underlying transaction/data record(s) that support a finding |
| Replay | Time-ordered playback of the fund-movement / graph-construction sequence |
| Demo data | Non-live, clearly-labeled sample data used for demonstration where live data is unavailable or inappropriate |

## 13. Source-of-truth rules (repeat, because this matters)

1. The official SIH26183 problem statement text is authoritative and must not
   be silently altered.
2. Do not invent: government requirements, customer relationships, blockchain
   facts, capabilities, accuracy numbers, or VASP ownership.
3. Anything not directly supported by supplied source material must be
   labeled **UNKNOWN / ASSUMPTION / PROPOSED / UNVALIDATED / FUTURE** — never
   silently presented as fact.
4. These four documents (CONTEXT, PROJECT_BRAIN, ARCHITECTURE, REQUIREMENTS)
   must tell the same product story. If you find a contradiction between
   them, that is a bug in the documentation and should be flagged/fixed, not
   worked around.

## 14. Document map

| File | Purpose |
|---|---|
| `CONTEXT.md` | This file — fast onboarding |
| `PROJECT_BRAIN.md` | Founder/product/strategic reasoning — the "why" |
| `ARCHITECTURE.md` | Technical blueprint — the "how," conceptually, no code |
| `REQUIREMENTS.md` | Formal requirement list with traceability and priority |
