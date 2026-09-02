# UX

The approved visual direction is institutional forensic software: warm ivory/stone surfaces, graphite text, deep teal primary actions, restrained semantic colors, compact rectangular cards, and monospace data for wallet/transaction identifiers. The current frontend has begun this migration through shared theme tokens and preserves the functional state/API model while visual work continues.

Investigation, WHY, replay, report, and timeline-jump failures surface a visible dismissible error banner; API messages remain safe and do not expose internal details.

The Next.js workspace presents case scope/risk at the top, navigation and filters on the left, React Flow graph in the center, and wallet/finding/evidence/AI/report details on the right. Primary actions call real APIs. React Flow provides zoom/pan and node/edge selection; wallet search selects a matching backend graph node and opens its WHY context. Money-trail focus changes graph emphasis; replay events highlight graph nodes and synchronize selected transaction/evidence context, while timeline events and the replay event selector can jump to a replay step. Transaction cards and finding-linked transaction hashes open the same selected-transaction inspector. The graph uses restrained institutional node/edge colors while preserving reported, intermediary, destination, and suspicious semantics. The dashboard and investigation shell now have responsive structural behavior for phone-width layouts, and the app publishes standalone web-manifest metadata using the same frontend. This is not an APK or hosted deployment claim. Browser verification must not be claimed without an available browser.

The investigation navigation also exposes an authorized Audit Log view backed by `GET /cases/{case_id}/audit`. It is case-scoped, shows actor/action/resource/timestamp context, and deliberately omits stored IP addresses from the investigator UI.

Evidence cards expose the persisted source, timestamp, finding reference, and supporting transaction hash when available, keeping the investigator-visible chain `finding → evidence → transaction` explicit.

The Evidence Center marks persisted evidence as `FACT` and selecting an item hydrates its linked transaction when that transaction is present in the same case. The AI Copilot is labeled `AI SUMMARY`, carries the current case context, and reminds investigators to verify conclusions against the evidence trail. Reports are labeled as structured output from the current investigation and preserve the existing fact/analysis/inference section types.

The shared API client keeps localhost as a development-only fallback. A production or installed-app build requires an explicit `NEXT_PUBLIC_API_URL`, preventing a phone from silently calling itself when the hosted HTTPS backend has not been configured.

The dashboard's New Case flow is the Wallet Intake surface. It uses the same case-creation API and backend wallet/chain validation as before, while presenting a compact institutional intake dialog with explicit `DEMO DATA` provenance for the deterministic Demo Network and touch-sized form actions. This does not claim live address existence checks for non-demo networks.

Settings is a read-only, authenticated account and environment surface reached from the Dashboard header. It deliberately avoids exposing tokens, provider credentials, or editable security settings; it shows the locally stored investigator profile, the application’s case-scoped security posture, provenance guidance, and the active institutional theme. Its redirect and logout behavior are code/build verified; browser verification remains unavailable.

Case rows, primary investigation controls, navigation items, transaction selection, and replay controls expose keyboard semantics and phone-sized targets. The replay control also wraps its progress and event selector at narrow widths to avoid horizontal overflow. This is static/code-level accessibility hardening; real keyboard, touch, and responsive browser validation are still unavailable in the current environment.
