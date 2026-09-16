# Destination Intelligence and Investigation Copilot

## Current behavior

The investigation graph includes `destination_intelligence`. The inspector,
findings, recommendations, action readiness, Copilot and generated reports use
the shared destination service and attribution resolver. Ethereum keeps the
destination address selected by the bounded observation run. Supported stored
attribution may describe that address; it does not silently choose a new route.
Historical run capability metadata remains an observation snapshot; the shared
destination result describes current stored attribution for that candidate.

The panel separates the observed path and transfer evidence from attribution
sources. It shows candidate, network, classification, status, basis, source,
verification timestamp, observation timestamp, freshness and limitations.
References select existing wallets, individual transfer events, findings or
evidence in the same workspace. No duplicate evidence records are created.

| Status | Meaning |
| --- | --- |
| VERIFIED | A stored record has authoritative provenance, a source reference, a valid verification timestamp and supporting references that resolve to this address in the case/current observation. This records source-backed attribution, not independently confirmed ownership or current custody. |
| LIKELY / INFERRED | A supported inference, or explicitly labeled Demo intelligence. Investigator verification is required. |
| UNKNOWN | No sufficiently supported attribution record is available. No entity name is exposed. |

Verification freshness is `verification_recorded_not_revalidated`, or `unknown`
without a valid verification timestamp. The application does not claim an old
verification remains current. Malformed/future verification timestamps cannot
establish VERIFIED. Real cases cannot consume Demo attribution. Unsupported
cross-case, cross-address or old-run evidence references are removed.

## Attribution extension boundary

`AttributionSource.lookup(AttributionScope)` defines the source contract.
`StoredAttributionSource` is the only connected source. The scope contains
network, run ID, observed addresses and supporting record references. It has no
complaint narrative, victim identity, account credentials or API endpoint.

Blockchain observations → shared CryptoTrace attribution resolver → stored
case intelligence → normalized investigator result.

**FUTURE INTEGRATION:** a separately authorized external source adapter may use
the same interface and UI result shape. No commercial provider is connected or
claimed. Before connecting one, validate documented access, explicit data-sharing
authorization, backend-only credentials, allowed provenance, schema validation,
case/run reference checks, failure behavior and freshness rules. External claims
are untrusted; a vendor-provided status string alone must never grant VERIFIED.
An unavailable source must return unknown/availability metadata without invented
labels or Demo fallback. No external provider requests are implemented here.

## Copilot contract

`POST /cases/{case_id}/ai/query` retains authentication, case ownership and
`case.write` permission. Optional `wallet_address` and `finding_id` fields select
objects inside the current case. Unknown selections return NOT AVAILABLE.

Answers are deterministic local explanations, including when model credentials
are configured. No model, blockchain search or third-party attribution call is
made. The previous unused external-model helper now delegates to local analysis.
The context includes all persisted transfers, removing the previous 50-record
query cap and 20-record explanation subset. Amount labels use exact strings;
missing exact amounts remain NOT AVAILABLE.

The additive response fields include `run_id`, `destination`, `attribution_status`,
`data_origin`, `coverage`, `sections`, `supporting_records`, `next_review_step`
and `limitations`. The legacy `answer`, `grounded`, `sources`, `suggested_questions`
and capability fields remain. References carry an existing object kind and ID;
transfer references preserve event identity rather than collapsing by transaction
hash. Finding-specific event IDs take precedence over legacy hash references.
Responses and source references are saved with their run ID in the existing
conversation record. The UI clears the previous answer before a new request or
investigation attempt and accepts only the current run's response.

The compact workspace shows Answer, Key evidence, Supporting transfers, Next
review step, and Sources & limitations. It explicitly distinguishes DEMO DATA
from PROVIDER-OBSERVED DATA and keeps PARTIAL visible. Questions about ownership,
invented records, freeze status and government actions cannot manufacture facts.

## Action readiness and case brief

The case brief shows case identity/status, network/risk, reported wallet,
observed transfer/address counts, top findings, destination/attribution and next
action; the adjacent coverage strip remains authoritative for observation limits.

Action readiness shows evidence count, supporting transfer count, destination,
required attribution review and local request-package readiness. Existing Demo
request preparation remains a local workflow. Ethereum external action stays
unavailable. Viewing evidence or audit records uses existing authorized screens.
No freezing, external submission, government action or new export service is added.

## Validation and limits

Regression coverage includes attribution semantics/provenance, invalid metadata,
unsupported references, same destination/run across consumers, evidence links,
Copilot grounding, unavailable context, local-only execution, Demo and the captured
benign high-activity Ethereum example (62 events, 62 addresses, 4 transactions).
The high-activity fixture is replayed offline; its source data and provider limits
remain unchanged. It still yields partial coverage and zero invented findings.

Live browser/pointer testing was unavailable during this phase. Component render,
selection callback, accessibility markup, responsive CSS, TypeScript and build
checks cover the available UI validation. Dense reference lists remain scrollable
and individually selectable; a browser review across desktop/tablet is still useful.
