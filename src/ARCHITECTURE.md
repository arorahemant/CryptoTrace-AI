# ARCHITECTURE.md — CryptoTrace AI

> Conceptual technical blueprint. No production code, no locked
> implementation. Every boundary below is a conceptual seam, not a mandated
> library/framework choice, unless explicitly marked otherwise. Labels
> (PROPOSED / ASSUMPTION / UNKNOWN / FUTURE) apply as in PROJECT_BRAIN.md.

---

## 1. Architecture principles

1. **Deterministic-first.** Anything that can be computed with explainable,
   reproducible logic should be — AI sits on top of this, not inside it, for
   core findings.
2. **Evidence-traceable by construction.** The data model must make
   `FINDING → REASON → EVIDENCE → TRANSACTION` a structural property, not an
   afterthought bolted onto the UI.
3. **Provider-agnostic where possible.** Do not hard-lock a blockchain data
   vendor or an LLM vendor into the core domain logic; isolate them behind
   boundaries (see §14, §16).
4. **No unlimited crawling.** Tracing must have explicit, configurable
   stopping conditions (see §12 domain: Trace).
5. **Small MVP surface.** One chain, one investigator role, one clear vertical
   slice, before breadth.
6. **Security is load-bearing, not decorative.** Case-level authorization
   and audit logging are core domain concerns, not infra afterthoughts.

## 2. Conceptual architecture (high level)

```
INVESTIGATOR
   ↓
INVESTIGATOR EXPERIENCE (UX layer — dashboard, case workspace, graph, etc.)
   ↓
FRONTEND
   ↓
API
   ↓
APPLICATION / SERVICE LAYER
   ↓
DOMAIN / INVESTIGATION ENGINES
   ↓
DATA / EXTERNAL PROVIDERS
   ↓
DATABASE
```

This is a layered/hexagonal-leaning conceptual shape: the domain engines
(trace, graph, patterns, attribution, risk, evidence, AI) are the core, with
external providers and the database both treated as replaceable edges, and
the frontend/API as the delivery mechanism.

## 3. MVP architecture

MVP realizes only the subset of the above needed to prove one vertical
slice, single-chain, single-role:

```
Investigator → Case workspace UI → API → Case + Trace services →
[Trace engine → Graph engine → Pattern engine → Attribution engine (heuristic-only likely at MVP) → Risk engine → Evidence assembly]
→ Report generator
       ↑
Blockchain data provider (single chain) ← rate-limited/cached
       ↑
Database (cases, cached transactions, findings, evidence, audit log)
```

AI (explanation layer) is **PROPOSED as P1, not necessarily P0** — see
REQUIREMENTS.md; the deterministic pipeline must work and be demonstrable on
its own, since AI is explicitly not allowed to be the thing "doing" the
investigation.

## 4. Future architecture

**[FUTURE]** Multi-chain provider abstraction with normalization layer;
pluggable address-intelligence sources with source-weighted confidence
aggregation; cross-case graph store for pattern reuse across investigations;
multi-tenant/organization deployment; async job queue for large trace jobs;
collaboration (multiple investigators on one case) with conflict handling.

## 5. System boundaries

- **Investigator-facing system** (frontend + API + application layer) vs.
  **investigation domain engines** (trace/graph/pattern/attribution/risk/
  evidence) vs. **external world** (blockchain data providers,
  address-intelligence sources, LLM provider).
- The domain engines should not directly depend on frontend/API concerns
  (no HTTP-specific logic inside trace/graph/pattern logic).

## 6. Trust boundaries

- **Untrusted input:** anything investigator-supplied (wallet address
  strings, case notes) and anything from external data providers must be
  validated/sanitized before use — wallet address strings in particular
  should never be trusted as pre-validated.
- **Semi-trusted:** external blockchain data providers — treated as
  authoritative for raw transaction data but not for interpretation
  (interpretation happens in our domain engines).
- **Trust boundary around AI:** the AI layer must only be given the
  evidence/context it's explicitly scoped to see (see §16) — it is not a
  trusted actor with open access to the whole case or the whole database.

## 7. Data flow (conceptual, MVP)

```
1. Investigator submits: wallet address + chain + parameters (hops, time window, min amount)
2. Application layer validates input → creates/updates Case
3. Trace engine queries blockchain data provider (through provider boundary, with caching)
4. Trace engine applies stopping conditions → produces a bounded transaction set
5. Graph engine builds node/edge structure from that set
6. Pattern engine evaluates deterministic rules over the graph → produces findings + evidence refs
7. Attribution engine checks addresses against available intelligence source(s) → confidence-tagged results
8. Risk engine computes a transparent prioritization score from findings
9. Evidence assembly links every finding to its transaction-level backing
10. (P1) AI explanation layer summarizes findings, grounded only in the evidence produced above
11. Investigator reviews in case workspace; actions are audit-logged
12. Report generator compiles findings + evidence + (if used) AI summary into a report artifact
```

## 8. Domain boundaries

| Domain | Responsibility |
|---|---|
| AUTH | Authentication + session handling |
| CASE MANAGEMENT | Case lifecycle, ownership, status |
| WALLET | Wallet address representation, validation |
| TRANSACTION | Normalized transaction records |
| NORMALIZATION | Converting raw provider data into the internal transaction model |
| TRACE | Multi-hop traversal from a starting wallet, bounded by parameters |
| FUND FLOW | Aggregated view of how value moved across hops |
| GRAPH | Node/edge model built from trace + fund flow |
| PATTERNS | Deterministic suspicious-pattern rule evaluation |
| ATTRIBUTION | Address → entity association with confidence tiers |
| RISK | Deterministic prioritization scoring |
| EVIDENCE | Assembly and linkage of finding → reason → evidence → transaction |
| REPLAY | (P1/P2) Time-ordered reconstruction of the trace/graph-building sequence |
| AI | Grounded explanation/summarization over evidence already produced |
| REPORT | Compilation of the above into an exportable artifact |
| AUDIT | Logging of investigator and system actions on a case |

## 9. Frontend boundary

Frontend responsibilities: investigator experience only — rendering case
workspace, graph, timeline, findings, evidence panel, (P1) AI panel, and
report preview/export. Frontend must not contain domain logic (e.g., pattern
rules or risk scoring must not be computed client-side) — it consumes
results from the API. **[PROPOSED]**

The current founder delivery decision makes this functional frontend the
shared source for both the desktop investigator experience and an intentional
mobile/Android app experience. App packaging and hosted delivery are delivery
gates, not current runtime claims. Both clients must preserve the same API
contracts, case authorization, investigation state, and data-provenance
labels; mobile is not a second implementation of the domain logic.

## 10. API boundary

API is the sole entry point between frontend and application/service layer.
Responsibilities: input validation, authentication/session enforcement,
authorization (case ownership checks — see §22), request shaping, and
translating domain results into a stable contract for the frontend. Exact
endpoint design is deferred — **not specified here**, since this document is
conceptual, not an API spec. **[PROPOSED boundary, UNSPECIFIED contract]**

## 11. Application / service layer

Orchestrates domain engines to fulfill a use case (e.g., "run a trace for
this case") — coordinates calls to TRACE → GRAPH → PATTERNS → ATTRIBUTION →
RISK → EVIDENCE in the right order, handles partial failure (e.g., provider
timeout mid-trace), and enforces business rules that span more than one
engine (e.g., "a case must have at least one completed trace before a
report can be generated").

The implementation uses one current persisted investigation snapshot per
case: repeated requests reuse the stored result, while a failed persistence
transaction remains retryable after rollback. Production database locking
and a process-local demo lock serialize competing runs. Case authorization
receives the active user resolved at the API boundary instead of resolving
that identity again inside the case check.

## 12. Investigation engines (domain core)

Each engine below is conceptual — see PROJECT_BRAIN.md for the "why" behind
each; this section defines conceptual inputs/outputs and constraints only.

**TRACE**
- Inputs: wallet, chain, asset, direction, time window, min amount, max hops
  [PROPOSED parameter set]
- Constraints: explicit max-hop bound, cycle protection (a wallet already
  visited in this trace is not re-expanded infinitely), a defined stopping
  condition set (max hops reached / no further qualifying transactions /
  relevance-ranking cutoff). **No unlimited crawler — this is a hard
  constraint, not a tuning preference.**
- Output: a bounded transaction set with hop metadata.

**GRAPH**
- WALLET = NODE, TRANSACTION = EDGE. [PROPOSED]
- Must support relevance-based visual reduction (not render every node with
  equal prominence) so it reduces investigator cognitive load rather than
  just re-displaying the raw trace. **Core principle: the graph must reduce
  complexity.**

**PATTERNS**
- Candidate deterministic pattern types (each evaluated, not assumed
  automatically included): rapid movement (short time between hops),
  splitting (one wallet's balance divided across many outputs), consolidation
  (many wallets funneling into one), layering (many small hops obscuring
  origin), repeated suspicious relationships (recurring counterparties across
  cases — likely P1/P2 since it needs cross-case data). For each: usefulness
  ASSUMPTION-based, requires defined trigger thresholds (UNSPECIFIED —
  founder/data decision), output must state which transactions triggered it,
  and confidence/limitations must be stated. **Pattern detection must never
  be equated with criminal identity in output language.**

**ATTRIBUTION**
- KNOWN/VERIFIED vs LIKELY/INFERRED vs UNKNOWN (see PROJECT_BRAIN.md §16).
- Requires an actual attribution data source at MVP; if none is available,
  MVP may only be able to produce LIKELY/UNKNOWN outputs — **this must be
  disclosed, not concealed, in demo and reporting.**

**RISK**
- Deterministic, transparent scoring for MVP (e.g., weighted sum of
  triggered pattern flags + attribution confidence), explicitly framed as
  **prioritization, not legal judgment.**

**EVIDENCE**
- Assembles and stores the finding → reason → evidence → transaction chain
  so it can be displayed in-app and reused verbatim in the report.

**REPLAY (P1/P2)**
- Only build if it provides genuine investigator value beyond the static
  graph — this is UNPROVEN (see PROJECT_BRAIN.md §12). If pursued, requires
  synchronization across EVENT → TIMELINE → GRAPH → TRANSACTION → EVIDENCE
  so scrubbing a timeline updates the graph and evidence panel consistently.

**AI (P1)**
- See §16 AI boundary below.

**REPORT**
- Compiles case metadata, trace summary, graph snapshot, findings with
  evidence, attribution with confidence, risk summary, and (if used) AI
  summary into an exportable artifact. Must not restate conclusions without
  their evidence links.

## 13. Database boundary

Conceptually needs to persist: cases, case ownership/access, cached/
normalized transactions, graph snapshots or graph-derivable data, findings,
evidence links, attribution results, risk scores, audit log entries, and (if
built) report artifacts. **No specific database technology is mandated
here** — that's an implementation decision to make once query patterns
(graph traversal vs. relational case data) are clearer; a hybrid
(relational store for case/audit + graph-capable store or in-memory graph
library for trace/graph data) is a reasonable **[PROPOSED]** direction, not
a locked choice.

## 14. Blockchain-provider boundary

- Must be abstracted behind an interface so the specific vendor/API is
  swappable (**do not lock a vendor prematurely** — explicit instruction).
- Needs: normalization (raw provider format → internal transaction model),
  caching (avoid re-fetching the same address/transaction repeatedly),
  rate-limit handling, cost awareness (many providers charge per call/
  volume — UNKNOWN what budget is available), data-quality handling
  (missing/delayed data), and failure handling (provider downtime should
  degrade gracefully, not crash a trace).
- **Minimum viable chain support:** UNKNOWN/founder decision — this document
  does not select a chain, since that requires weighing data-provider
  availability, cost, and demo relevance, none of which are settled here.
- **Historical data needs:** UNKNOWN — depends on how far back a typical
  victim report requires tracing; not researched.

## 15. Address-intelligence boundary

Separate boundary from the raw blockchain-data provider, because address/
VASP attribution typically comes from a different kind of source (labeling
databases, community lists, commercial intelligence feeds) with its own
credibility and cost profile. **UNKNOWN** what source(s), if any, will be
available/affordable at MVP — this must not be invented. If no credible
source is available, the ATTRIBUTION engine should be designed to operate
honestly in LIKELY/UNKNOWN territory using heuristic signals only (e.g.
deposit-pattern heuristics), clearly disclosed as heuristic, not "verified."

## 16. AI boundary

- AI may access: the evidence/findings already produced by deterministic
  engines for the specific case in view. **[PROPOSED, restrictive by
  design]**
- AI may NOT access: raw unrelated case data, other investigators' cases,
  or generate findings not already backed by the deterministic pipeline.
- AI may NOT claim: certain identity, criminality, legal conclusions.
- Grounding approach: **[PROPOSED]** retrieval/context should be
  constructed by the application layer from the evidence store and passed
  to the AI call explicitly (a RAG-like pattern) rather than allowing the
  model open-ended access, specifically so outputs are checkable against
  what was provided.
- Uncertainty communication: AI output should preserve and surface the
  confidence levels already computed by the deterministic engines, not
  invent its own.
- Hallucination control: **[UNVALIDATED]** — needs actual evaluation
  (AI Evaluation Engineer function in the founder-analysis role list) before
  being trusted in any real deployment; this document defines the intended
  boundary, not a tested guarantee.
- Evidence referencing: AI-generated text describing a finding should be
  traceable back to the same evidence IDs the deterministic pipeline
  produced, so the report generator (§12 REPORT) can cite consistently.

## 17. Evidence boundary

The evidence store is the single place `finding → reason → evidence →
transaction` linkage lives; both the frontend evidence panel and the report
generator must read from this same store, not maintain separate
representations that could drift out of sync.

## 18. Reporting boundary

Report generation reads from case data + findings + evidence + (if present)
AI summary; it does not independently re-derive conclusions. Output format
UNSPECIFIED at this conceptual stage (PDF/structured document is a
reasonable **[PROPOSED]** direction). Report must carry the same DEMO DATA /
confidence labeling as the live UI — no "cleaning up" claims for a nicer-
looking report.

## 19. Audit boundary

Every investigator action that materially affects a case (creating a trace,
viewing a finding, including something in a report, changing case status)
should be logged with actor, timestamp, and case ID, primarily to support
the evidence/trust model and secondarily for security review (see §22).

## 20. Authentication

**[PROPOSED, standard]** Investigator accounts, session-based or
token-based auth. No specific technology mandated here. Must exist at MVP —
this is not a "later" feature given the case-ownership requirement below.

## 21. Authorization

Case-level authorization is required at MVP: an investigator should only be
able to access cases they own or are explicitly granted access to.
**Explicit IDOR/BOLA protection** — case IDs must not be guessable/
enumerable into unauthorized access. Role distinctions (investigator vs.
supervisor vs. admin, per PROJECT_BRAIN.md §4) should be reflected in
authorization checks, not just UI hiding.

## 22. Security boundaries

- **RBAC:** role-based checks at the API layer, not just frontend.
- **Secrets:** blockchain-provider API keys, LLM API keys, DB credentials
  managed outside source control; conceptually a secrets manager or
  environment-based injection, not hardcoding. Production startup rejects a
  missing or weak `SECRET_KEY`; local demo mode uses an ephemeral process key
  only when no key is configured.
- **API security:** input validation on all external inputs (wallet address
  format, numeric parameters), output encoding where relevant.
- **Input validation:** wallet address strings are attacker-influenced input
  and must be validated/sanitized before being used in provider queries or
  stored.
- **Rate limiting:** both inbound (protect the API from abuse) and outbound
  (respect/manage blockchain-provider rate limits).
- **Audit logs:** see §19.
- **Privacy / data minimization:** store only what the investigation needs;
  avoid retaining unrelated personal data about victims beyond what a case
  requires. **[PROPOSED — actual privacy/legal requirements are UNKNOWN and
  out of scope for this document to determine.]**
- **AI boundaries:** see §16.

## 23. Scalability

**[UNKNOWN/FUTURE-leaning]** No load figures exist. Conceptually, trace jobs
over many hops could become expensive; an async job model (submit trace →
poll/notify on completion) is a reasonable **[PROPOSED]** direction for
anything beyond small hop counts, deferred past MVP if a synchronous
call suffices for demo-scale traces.

## 24. Failure handling

Provider downtime/timeouts, partial trace failures, and attribution-source
unavailability should degrade to a clearly-labeled partial/uncertain result
("trace incomplete — provider error" / "attribution unavailable") rather
than silently producing an incomplete result presented as complete, or
crashing the whole investigation.

## 25. Performance considerations

**[UNKNOWN]** No specific targets set here — that requires an actual demo
scenario (expected hop count, transaction volume) to be defined by the
founders, which this document does not invent.

## 26. Observability

**[PROPOSED, minimal for MVP]** Basic logging of provider call failures,
trace duration, and pattern/risk engine execution, primarily to support
debugging during the hackathon build rather than as a production
observability stack.

## 27. Architectural risks

- Coupling the AI layer too tightly to a single LLM vendor/prompt without an
  evaluation harness risks silent quality regressions.
- Under-specifying "stopping conditions" for TRACE risks either an
  unusably slow demo (too many hops) or a misleadingly thin one (too few).
- If no real address-intelligence source is available, the ATTRIBUTION
  engine risks becoming either non-functional or, worse, over-confident
  heuristic guessing dressed up as attribution — the evidence/confidence
  discipline in §16 and PROJECT_BRAIN.md §16 exists specifically to prevent
  this.
- Building REPLAY or a broad AI copilot before the deterministic P0
  pipeline is solid would invert the intended priority order
  (`deterministic-first`, principle #1).
