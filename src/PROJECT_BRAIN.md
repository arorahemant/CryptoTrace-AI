# PROJECT_BRAIN.md — CryptoTrace AI

> The central product/strategy document. Every claim below is labeled:
> **FACT** (directly from supplied source material) · **ASSUMPTION** ·
> **HYPOTHESIS** · **PROPOSED** · **UNVALIDATED** · **FUTURE** · **UNKNOWN**.
> Unlabeled prose is structural/explanatory text, not a claim.

---

## 1. Executive definition

CryptoTrace AI is a **[PROPOSED]** investigator-focused blockchain fraud
investigation platform that takes a single victim-reported cryptocurrency
wallet address and produces a structured, evidence-linked investigation of
where the funds moved, which intermediary wallets and patterns are involved,
and which exchange/VASP the funds likely reached — with explanations an
investigator can act on and a human, not the AI, remains responsible for
conclusions.

This is **[FACT]** grounded in problem statement SIH26183 ("Real-Time
Identification of Fraud-Linked Cryptocurrency Exchanges from Victim-Reported
Suspect Wallet Addresses through Automated Blockchain Analytics") but the
specific product shape (case workspace, graph, replay, AI copilot, etc.) is
**[PROPOSED]** — our interpretation, not dictated by the problem statement.

## 2. Problem

**OFFICIAL SIH PROBLEM [FACT]:** Investigators need a way to go from a
victim-reported suspect wallet to identification of the fraud-linked
exchange(s) the funds moved through, using automated blockchain analytics, in
close to real time.

**OUR PRODUCT INTERPRETATION [PROPOSED]:** The bottleneck is not just "can we
trace a wallet" (blockchain explorers already do this) — it's that raw
transaction data does not answer an investigator's actual questions:
*Where did this money end up? Which of these fifty wallets actually matter?
Why should I believe this address is an exchange? What do I put in my
report?* CryptoTrace's job is to compress a large, noisy transaction graph
into a small number of defensible findings.

**ASSUMPTION:** Investigators currently rely on manual use of public
explorers, spreadsheets, and personal judgment, with no case-management or
evidence-linkage layer purpose-built for this workflow. This has not been
validated with real investigators and should be treated as a hypothesis to
test, not a researched fact — see §25 Open Questions.

## 3. Root causes

- **[ASSUMPTION]** Blockchain transaction graphs grow combinatorially with
  hop count, so manual tracing does not scale past a few hops.
- **[ASSUMPTION]** Generic explorers show data, not investigative meaning —
  they don't distinguish "this wallet matters" from "this wallet is noise."
- **[ASSUMPTION]** Attribution of an address to a real-world exchange
  currently depends on scattered, informal knowledge (community labels,
  ad-hoc lists) rather than a structured, confidence-scored process.
- **[ASSUMPTION]** There is no standard way to turn a trace into something
  presentable as evidence (report, audit trail) without manual write-up.

## 4. Users

Per the governing instruction: **do not assume user, buyer, and approver are
the same person.**

| Role | Definition | Status |
|---|---|---|
| **Primary user** | The investigator: receives a reported wallet, runs the investigation, makes/records findings | PROPOSED |
| **Secondary user** | A senior investigator or forensic analyst who may review/deepen findings on escalated cases | PROPOSED |
| **Supervisor** | Reviews case findings/reports before they leave the team; may not use the tracing/graph tools directly | PROPOSED |
| **Admin** | Manages users, access, and system configuration; not necessarily an investigator | PROPOSED |
| **Buyer/Approver** | UNKNOWN — for an SIH context, likely a department or ministry-level decision, not an individual investigator. Not assumed, not invented. | UNKNOWN |
| **Future user** | Compliance/AML teams at VASPs, cross-agency collaborators | FUTURE |

### Investigator detail

- **Job:** Turn a victim complaint containing one wallet address into an
  actionable lead (destination exchange, key intermediaries) and a
  defensible written record. [PROPOSED]
- **Pain:** Manual multi-hop tracing is slow; determining which of many
  branches matter is subjective; write-up for reports/escalation is manual.
  [ASSUMPTION]
- **Inputs:** One wallet address, approximate incident date/amount if known,
  possibly the blockchain/asset involved. [PROPOSED]
- **Decisions:** Which branch to prioritize, whether an attribution is
  credible enough to act on, what to escalate. [PROPOSED]
- **Required evidence:** Transaction-level backing for every claim; ability
  to reproduce/re-derive a finding. [PROPOSED, following the evidence
  philosophy in §14]
- **Required outputs:** A report suitable for internal escalation
  (NOT asserted to be a court-admissible legal document — see §20 Data
  Honesty). [PROPOSED]
- **Success criteria:** Investigator can, faster than manual method, identify
  a credible destination VASP and the key intermediary path, with evidence
  attached. [HYPOTHESIS — not measured yet]

## 5. Job-to-be-done (JTBD)

**Draft JTBD:** "When I receive a single wallet address from a fraud victim,
I want to understand where the funds went and which exchange they likely
reached, so I can act on or escalate the case with confidence, without
manually tracing dozens of transactions by hand."

**Challenge:** Does this statement over-promise "confidence"? A more honest
version separates *speed* (real, buildable) from *certainty* (not something
the system can promise, since attribution is often probabilistic).

**Refined JTBD [PROPOSED]:** "When I receive a single wallet address from a
fraud victim, I want the system to trace and explain the fund movement and
surface the most likely exchange destination *with the evidence and
confidence behind that conclusion made explicit*, so I can make a faster,
better-supported investigative decision than manual tracing allows — not so
the system decides for me."

## 6. Product promise

**Promises [PROPOSED]:**
- Turn one wallet into a traced, visualized fund-movement graph.
- Surface intermediaries and candidate destination VASPs with confidence
  levels and supporting evidence.
- Flag suspicious transaction patterns using transparent, explainable logic.
- Let the investigator see *why* something was flagged, down to the
  transaction level.
- Produce a structured report summarizing the investigation.

**Does NOT promise [PROPOSED — explicit non-promises]:**
- Certain/verified identification of a criminal individual.
- Legal admissibility of output as evidence (a jurisdiction-specific legal
  question, UNKNOWN, not ours to assert).
- Full real-time monitoring of live fraud as it happens (MVP is
  investigation of already-reported wallets, not a live-monitoring system —
  see §21 MVP).
- Coverage of every blockchain/asset on day one.

**Where automation is appropriate:** Data retrieval, graph construction,
deterministic pattern flagging, confidence scoring, evidence assembly,
report drafting. [PROPOSED]

**Where human judgment is required:** Deciding whether to escalate,
interpreting ambiguous attribution, any legal/procedural decision, final
sign-off on a report. [PROPOSED — and treated as non-negotiable, not a
temporary MVP limitation]

**Successful investigation = [PROPOSED]:** investigator reaches a
well-evidenced conclusion (even if that conclusion is "destination unknown,
here is what we do know") faster and with better documentation than the
manual baseline.

## 7. Value proposition

For investigators handling crypto-fraud complaints, CryptoTrace AI turns a
single reported wallet into an evidence-linked, explainable investigation —
instead of a raw transaction list requiring manual multi-hop tracing — so
they can identify likely cash-out points and produce a defensible report
faster. **[PROPOSED / HYPOTHESIS on the "faster" claim]**

## 8. Investigation story (narrative)

A victim reports wallet `0xABC...` as where they sent funds. The
investigator enters this into CryptoTrace. The system retrieves transaction
history, traces fund movement through however many hops the investigator
configures, and builds a graph. Deterministic pattern logic flags a
suspicious splitting pattern at hop 2 and a likely-exchange deposit address
at hop 4, with a stated confidence and the specific transactions behind each
claim. The investigator reviews the graph, opens the evidence panel behind
the "likely exchange" finding, judges it credible, and generates a report
that includes the trace, the flagged patterns, the attribution with its
confidence level, and the transaction-level evidence. **[PROPOSED — this is
an illustrative scenario, not a specification of exact UI]**

## 9. Core workflow

```
TRACE → MAP → DETECT → EXPLAIN → REPORT
```
This is the North Star and applies to MVP as well as future scope. **[PROPOSED]**

## 10. Product principles

1. Every AI-surfaced claim must be traceable to deterministic evidence.
   [PROPOSED, non-negotiable]
2. The graph must reduce complexity, not just visualize raw data. [PROPOSED]
3. Confidence is stated, not implied. [PROPOSED]
4. Demo data is never presented as live data. [PROPOSED, non-negotiable]
5. MVP proves the workflow end-to-end on one chain before breadth. [PROPOSED]
6. Human investigators remain the decision-makers. [PROPOSED, non-negotiable]

## 11. USP (unique selling points, as currently proposed)

- Single-wallet-in, structured-investigation-out workflow purpose-built for
  fraud investigators (rather than a general-purpose explorer). [HYPOTHESIS]
- Evidence-linked findings with explicit confidence, rather than a flat
  transaction list. [HYPOTHESIS]
- AI used strictly as an explanation/summarization layer over deterministic
  analysis, not as the analytical engine itself — a deliberate, statable
  design choice for trust. [PROPOSED]

**Important:** None of the above should be presented as "no one else does
this" — see §12 Differentiation Analysis for classification against likely
existing competitors.

## 12. Differentiation analysis

Per instruction, we assume competitors already exist (blockchain forensics
firms, generic explorers with labeling, open-source graph tools) and do not
claim novelty without basis.

| Capability | Classification | Note |
|---|---|---|
| Transaction tracing | COMMON | Available in explorers and commercial forensics tools |
| Graph visualization of fund flow | COMMON | Many tools already do this |
| Automated pattern detection (splitting, layering, etc.) | HYPOTHESIS | Plausible differentiator for an SIH-scope MVP, but commercial forensics tools (e.g. Chainalysis-class products) likely already do more sophisticated versions — UNPROVEN vs. them specifically |
| VASP attribution with explicit confidence tiers | HYPOTHESIS | The *explicit confidence tiering + evidence UI* may be a differentiator; raw attribution/labeling already exists elsewhere via commercial address-intelligence datasets |
| Case-based investigator workflow (vs. raw explorer) | HYPOTHESIS | Plausible differentiator for this problem statement's likely target users |
| Evidence-linked, audit-friendly findings | HYPOTHESIS | Differentiator if implemented rigorously; easy to claim, hard to actually build well |
| Investigation replay | UNPROVEN | Value not yet validated with investigators; see §22 Replay treatment in ARCHITECTURE.md |
| AI-generated explanation grounded in deterministic evidence | HYPOTHESIS | The specific commitment to "AI never the source of truth" is a defensible, statable design principle even if not literally unique |
| Multi-chain support | FUTURE | Not MVP |
| Deployment cost / accessibility for smaller agencies | UNKNOWN | No cost research done |

**Conclusion:** Differentiation should be framed to judges as "a
purpose-built, evidence-first investigator workflow with disciplined AI
boundaries" — not as "nothing like this exists." The latter claim is not
supportable and should never appear in any pitch material generated from
this project.

## 13. Product boundaries

In scope conceptually: single-wallet-initiated tracing, graph construction,
deterministic pattern detection, VASP attribution with confidence, risk
prioritization, evidence panel, AI explanation layer, reporting, case
management, audit logging.

Out of scope, always: trading, portfolio management, price prediction,
custody/wallet functionality, NFT features, being a general-purpose
chatbot. (Restated from CONTEXT.md §6 because it recurs as a scope-creep
risk during building.)

## 14. Evidence philosophy

Chain: **FINDING → REASON → EVIDENCE → TRANSACTION.** **[PROPOSED,
non-negotiable]**

- **What counts as evidence:** the specific on-chain transaction(s) (with
  hashes, addresses, amounts, timestamps) that a finding is derived from.
- **Provenance:** every piece of retrieved data should record its source
  (which provider, what query) so it can be re-derived.
- **Confidence:** every non-deterministic finding (attribution, pattern
  match above a simple threshold) carries a stated confidence level, not a
  bare assertion.
- **Reproducibility:** given the same input data, the same deterministic
  finding should be re-derivable — this constrains how much of the pipeline
  can be "black box AI" vs. auditable logic.
- **Auditability:** actions investigators take (viewing, flagging,
  including in report) should be logged.
- **Report linkage:** the generated report must link back to the same
  evidence chain shown in-app, not restate conclusions without their
  backing.

## 15. Risk philosophy

Risk score = **investigation prioritization signal**, explicitly **not**
legal judgment or a determination of guilt. **[PROPOSED, non-negotiable —
also stated in CONTEXT.md and repeated here deliberately because it's a
common failure mode: turning a triage score into an accusation.]**

Prefer a transparent, deterministic scoring approach for MVP (e.g., a
weighted rule-based score referencing specific detected patterns) over an
opaque ML risk model, unless a documented reason justifies otherwise. This
keeps the score explainable, which the evidence philosophy requires.

## 16. Attribution philosophy

Three-tier model: **KNOWN/VERIFIED → LIKELY/INFERRED → UNKNOWN.**
**[PROPOSED]**

- **KNOWN/VERIFIED:** the address is confirmed via a trustworthy, citable
  source (e.g. an official/verified label from a reputable
  address-intelligence source). Requires an actual data source — UNKNOWN
  what source(s) will be used at MVP; this must not be invented. See
  ARCHITECTURE.md §15 Address-Intelligence boundary.
- **LIKELY/INFERRED:** heuristic evidence suggests but does not confirm
  (e.g. deposit-pattern behavior consistent with known exchange hot-wallet
  patterns).
- **UNKNOWN:** no sufficient basis for a claim — this must be a fully valid,
  expected, non-embarrassing output state, not something the UI hides or
  discourages.

**Never claim VASP ownership without sufficient evidence.** This is treated
as a hard rule, not a best-effort guideline.

## 17. AI philosophy

AI's job: explain and summarize what deterministic analysis has already
found, in investigator-readable language, with citations back to evidence.
AI is not the analytical engine and is not permitted to originate findings
that lack a deterministic/evidentiary basis. **[PROPOSED, non-negotiable]**

## 18. Responsible AI

Trust hierarchy:

```
OBSERVED DATA
   ↓
DETERMINISTIC ANALYSIS
   ↓
EVIDENCE
   ↓
INFERENCE
   ↓
AI SUMMARY
```

**Is this sufficient?** It's a reasonable ordering but insufficient on its
own without enforcement mechanisms (see ARCHITECTURE.md §16 AI boundary) —
e.g., grounding/RAG constraints so the AI model cannot free-associate beyond
the evidence it's given, and evaluation of AI outputs for
over-claiming/hallucination before this is trusted in a real deployment.
**[UNVALIDATED — the hierarchy is a design intent, not yet a tested
guarantee]**

**AI must never claim:** individual criminality, certain identity, legal
conclusions, based solely on wallet activity.

**Preferred phrasing patterns:** "Suspicious transaction characteristics
detected." / "Likely attribution." / "Confidence: X." / "Supporting
evidence: ..." — these are prescribed output patterns, not just examples.

## 19. Security philosophy

Because outputs may inform real investigative decisions, security is an MVP
concern, not a "harden later" concern: authentication, RBAC, case-level
authorization (explicit IDOR/BOLA prevention across cases — one
investigator must not be able to pull another's case by guessing an ID),
audit logs, input validation on all external-facing inputs (including wallet
addresses, which are attacker-controlled strings), rate limiting on
blockchain-provider calls, secrets management, and data minimization
(collect/store only what the investigation needs). **[PROPOSED — full
technical detail in ARCHITECTURE.md §22]**

## 20. Data honesty

Never claim, unless actually true and supportable: government integration,
police integration, VASP partnership, validated accuracy figures, legal
admissibility, confirmed criminal identity, true real-time capability.
Default labels where uncertain: **DEMO DATA, LIKELY/INFERRED, UNKNOWN,
ASSUMPTION, UNVALIDATED, FUTURE.** **[Non-negotiable — restated from
CONTEXT.md deliberately, as this is the single easiest rule to violate
under demo/pitch pressure.]**

## 21. MVP (see REQUIREMENTS.md for full P0/P1/P2 breakdown)

MVP philosophy: the smallest system that proves
`TRACE → MAP → DETECT → EXPLAIN → REPORT` end-to-end, on **one blockchain**,
for **one investigator role**, using **real data where feasible and clearly
labeled demo data where not.** MVP is not "everything discussed in this
document" — most of what's above (replay, multi-chain, AI copilot,
cross-case intelligence) is P1/P2/FUTURE unless stated otherwise in
REQUIREMENTS.md.

## 21A. Current founder delivery decision — app-first scope evolution

The foundation-stage MVP definition above remains the first verified vertical
slice. The current founder/CTO decision expands the delivery target beyond a
local browser prototype: **CryptoTrace AI is APP-FIRST and requires an
installable Android experience.**

Required target capabilities are a professional desktop investigator
experience, an intentional mobile investigator experience, an installable
Android application, a hosted HTTPS backend, production PostgreSQL, secure
production configuration, and the complete core investigation workflow on a
phone without USB or localhost dependency.

This section records scope, not completion. Hosted deployment, PostgreSQL
runtime verification, Android packaging, and mobile validation remain
separate delivery gates until actually demonstrated. The existing frontend,
API contracts, investigation state, and deterministic Demo Mode remain the
functional source for both desktop and mobile experiences; the app must not
become a disconnected second product.

## 22. Future vision

**[FUTURE, not committed]:** multiple blockchains and cross-chain fund-flow
analysis, richer/paid address-intelligence integrations, cross-case pattern
intelligence (e.g. recognizing the same laundering network across multiple
victim reports), multi-investigator collaboration, enterprise/agency
deployment models, and integrations with external case-management or law
enforcement systems (none of which are assumed to exist or be obtainable —
UNKNOWN).

## 23. Business hypotheses

Treated strictly as hypotheses — **no customers, revenue, or partnerships
are invented.**

| Segment | Who uses | Who pays (UNKNOWN unless stated) | Existing alternatives | Why switch (HYPOTHESIS) |
|---|---|---|---|---|
| Cybercrime cells | Investigators | UNKNOWN — likely government budget, not validated | Manual explorer use, informal tools | Faster, more defensible workflow |
| Law-enforcement orgs | Investigators/analysts | UNKNOWN | Same as above, possibly commercial forensics tools if budget allows | Lower cost / purpose fit — UNVALIDATED |
| Financial-crime / AML teams | Analysts | UNKNOWN | Commercial blockchain analytics vendors | UNKNOWN — commercial tools may already be superior; this is a genuine competitive risk, not glossed over |
| VASP compliance teams | Compliance staff | UNKNOWN | In-house/commercial compliance tooling | FUTURE segment, not MVP focus |
| Forensic organizations | Analysts | UNKNOWN | Commercial forensics suites | UNKNOWN |

**Data required for a real go-to-market read (UNKNOWN, not researched
here):** actual investigator interviews, budget/procurement process for the
target organization type, and a real comparison against commercial
forensics tools' capability and price. None of this exists yet.

## 24. Competitive assumptions

**[ASSUMPTION]** Commercial blockchain-forensics vendors (general category,
not named without verification) likely already offer tracing, attribution,
and risk scoring at a more mature level than an SIH-stage MVP can reach.
CryptoTrace's realistic competitive angle for a hackathon-stage product is
workflow fit, cost, and explainability discipline — not raw data breadth or
attribution-database size, which are expensive to build and unvalidated
here.

## 25. Risks

- **Data access risk:** blockchain data providers, and especially
  authoritative VASP/address-attribution sources, may be rate-limited,
  paid, or unavailable at hackathon scale. [ASSUMPTION-based risk, data
  strategy deferred to ARCHITECTURE.md §14]
- **Attribution credibility risk:** without a real address-intelligence
  data source, "KNOWN/VERIFIED" attribution may not be achievable at MVP;
  the system may need to operate mostly in LIKELY/UNKNOWN territory, which
  must be presented honestly, not inflated for a better demo.
- **AI over-claiming risk:** without grounding enforcement, the AI layer
  could generate confident-sounding but unsupported claims — the single
  biggest way this product could become actively harmful/misleading rather
  than merely incomplete.
- **Scope-creep risk:** the extended workflow list (replay, AI copilot,
  multi-chain) is large enough to consume all hackathon time without ever
  reaching a working P0 slice.
- **Validation risk:** the entire problem/user analysis above is
  UNVALIDATED with real investigators; the product is being designed from
  the problem statement and reasoning, not from field research.

## 26. Open questions (must not be silently resolved by invention)

1. What blockchain(s)/asset(s) should MVP support first? UNKNOWN — needs a
   founder decision (see ARCHITECTURE.md §14 for tradeoffs).
2. What data source(s) will provide address/VASP attribution, and at what
   confidence and cost? UNKNOWN.
3. Is there any real access to investigators for validation during build?
   UNKNOWN.
4. What does "real-time" in the official problem statement actually require
   for demo purposes — literally live, or "current data, retrieved on
   demand"? UNKNOWN, needs a founder decision; do not silently assume "true
   real-time streaming."
5. Who is the actual buyer/approver for a tool like this? UNKNOWN.
6. What jurisdiction's evidentiary standards (if any) should inform the
   evidence model? UNKNOWN — treated as out of scope for MVP; the system
   should not claim legal admissibility either way.

## 27. Founder decision framework

For any product decision under discussion, evaluate it against:

`Is it useful? Technically feasible? Realistic within MVP? Already common?
Actually differentiated? Defensible? Demonstrable? Potentially misleading?
Does it require evidence? Does it create legal/ethical/security risk? What
would a professional investigator need? What would an SIH judge
misunderstand?`

Then classify as **KEEP / SIMPLIFY / DEFER / REMOVE / RESEARCH** and record
the reasoning. This framework should be applied to every future feature
proposal for this project, not just the ones evaluated in this document.
