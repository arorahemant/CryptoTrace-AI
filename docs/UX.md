# UX

The approved visual direction is institutional forensic software: warm ivory/stone surfaces, graphite text, deep teal primary actions, restrained semantic colors, compact rectangular cards, and monospace data for wallet/transaction identifiers. The current frontend has begun this migration through shared theme tokens and preserves the functional state/API model while visual work continues.

Shared semantic primitives now define product surfaces, primary and secondary actions, fields, status chips, state panels, error messaging, focus rings, and modal treatment. These interactions use tonal shifts, border emphasis, and restrained elevation; the former glow animation has been removed. Login, case dashboard, wallet intake, and settings use these primitives directly rather than relying only on palette translation.

The login experience explains the product before asking for credentials. Demo role controls and credentials appear only when the capability endpoint reports that local demo accounts are enabled; otherwise the fields are empty. Authentication failures display the safe backend message.

Investigation, WHY, replay, report, and timeline-jump failures surface a visible dismissible error banner; API messages remain safe and do not expose internal details.

The investigator workspace keeps a compact case brief and expandable coverage strip above the primary 2D trail. Wallet, transfer, finding, evidence, and replay selections share one graph path state. Wallet clicks open the inspector; WHY is an explicit action. The existing recommendations, evidence, audit, replay, report, and local action-readiness workflow remains available. Reporter routes and backend authorization are unchanged.

The case brief identifies case status, network, risk, reported wallet, destination candidate, findings, and the next recommendation using loaded case/run records. The candidate is the backend-selected destination throughout the workflow. Ethereum risk remains unassessed and service attribution remains unknown unless supplied by the backend; no UI-created service identities or risk findings are added. Dashboard rows expose concise origin/coverage badges and the current destination when available, without extra per-case requests.

The Overview shows an Assigned Investigator accountability card populated from the authorized case-detail response. Display name, role, initial assignment time, and latest case-scoped activity come from persisted user/case/audit data; there is no hardcoded investigator title. Missing assignment fields are shown as unavailable. Reassignment history is not claimed because the current model does not record it.

The investigation navigation also exposes an authorized Audit Log view backed by `GET /cases/{case_id}/audit`. It is case-scoped, shows actor/action/resource/timestamp context, and deliberately omits stored IP addresses from the investigator UI.

Evidence cards expose the persisted source, timestamp, finding reference, and supporting transaction hash when available, keeping the investigator-visible chain `finding → evidence → transaction` explicit. The Evidence Center also summarizes the persisted record set and makes the full `finding → reason → transaction` review path visible before the investigator opens an individual evidence record.

The Evidence Center marks persisted items as `EVIDENCE RECORD`; saving a record does not independently verify its factual or legal status. Selecting an item hydrates its linked transaction when present in the same case. Replay controls retain graph, transaction, and evidence synchronization. The Copilot is labelled `STRUCTURED EXPLANATION`, uses deterministic case-derived context, and requires both available analysis and case mutation permission. Reports guard against pre-analysis generation and remain structured case output.

Investigation Copilot opens from a compact case section and offers suggested evidence-review questions plus free-form input. Answers continue to use the existing deterministic backend context. The UI does not imply that Copilot performs new blockchain searches or independent attribution. Suggested-question and input controls honor mutation permissions and case closure.

The shared API client keeps localhost as a development-only fallback. A production or installed-app build requires an explicit `NEXT_PUBLIC_API_URL`, preventing a phone from silently calling itself when the hosted HTTPS backend has not been configured.

The dashboard's New Case flow uses existing backend wallet/chain validation and capability responses. Switching away from Demo clears its sample wallet, amount, and incident text. Demo Network remains explicitly labeled DEMO DATA. Ethereum uses the Phase 2B Alchemy observation capability and historical interval controls; other unconnected networks remain unavailable for analysis.

The shared capability notice separates data origin, provider connection, processing, result availability, freshness, and limitations. `EMPTY` means no matching records in that result and does not establish that a wallet has no activity. `PARTIAL` warns that coverage is not exhaustive. Analysis completion remains separate from case closure, verified ownership, recovery, freezing, preservation, and government integration.

Settings is a read-only, authenticated account and environment surface reached from the Dashboard header. It deliberately avoids exposing tokens, provider credentials, or editable security settings; it shows the locally stored investigator profile, the application’s case-scoped security posture, provenance guidance, and the active institutional theme. Its redirect and logout behavior are code/build verified; browser verification remains unavailable.

Case rows, primary investigation controls, navigation items, transaction selection, replay controls, and React Flow controls expose keyboard semantics or phone-sized targets. The replay control also wraps its progress and event selector at narrow widths to avoid horizontal overflow. This is static/code-level accessibility hardening; real keyboard, touch, and responsive browser validation are still unavailable in the current environment.


## Phase 2C trail and inspectors

- **2D TRAIL** is the default. React Flow shows directed, individually selectable transfer events, exact amount strings, assets, timestamps, hop roles, and dashed expansion boundaries. A scrollable candidate-route strip keeps the reported wallet and backend-selected endpoint identifiable at smaller graph scales.
- **3D NETWORK** is a lazy-loaded, perspective-projected SVG view with rotate, pan, zoom buttons, keyboard camera controls, node/connection selection, selection focus, path isolation, reset, and a legend. Depth is a visual layout coordinate only. No WebGL/physics dependency or separate blockchain dataset is introduced. Selecting a path highlights observed graph connectivity; it does not prove common ownership, chronological fund continuity, or an unobserved route.
- Wallet inspectors show network, hop, expansion, counts, exact asset totals, destination classification, and attribution. Transfer inspectors show exact decimal strings and base units, asset identity, block/hash, event identity, source, status, and coverage. Missing metadata remains unavailable. Mainnet transaction links go to Etherscan only for valid Ethereum transaction hashes; Demo records have no explorer link.
- Finding cards expand on selection and expose their affected wallets, supporting transfers, evidence, and next-action navigation. Multiple events sharing a transaction hash require event selection; a hash is never treated as a unique transfer.
- Coverage is always visible, with run identity, observation interval, retrieval time, exhaustion and limitations available in the strip. A fresh Ethereum attempt clears graph selection, replay, evidence/report context, and Copilot answers. Late previous-attempt answers cannot repopulate the current run.
- Ethereum action requests and deeper-than-supported expansion are not offered. No new backend capabilities, continuous monitoring, freezing, government integrations, or verification claims are added.
- Investigator styling is route-scoped. Laptop/tablet layouts move navigation to a horizontal row; narrow layouts stack the trail and inspector. Both views expose keyboard controls and text legends; reduced motion is respected. Reporter intake and its mobile styling remain unchanged.

### Validation and limits

Run frontend regressions with Node 22.18+ (24 used for verification): `node --test lib/investigation.test.mjs` from `frontend`. Tests use the approved Phase 2B captured receipt, exact-value assertions, projection/selection checks, and server-rendered inspector markup. UI-only synthetic topology variants stay in tests.

TypeScript, production build, source accessibility/responsive review, and Phase 2A/2B plus authorization/reporter regressions are required. No browser was available for Phase 2C; live pointer/touch/keyboard behavior, screenshots, and visual layout acceptance have not been verified. The user authorized completing source-based verification without that browser review.
