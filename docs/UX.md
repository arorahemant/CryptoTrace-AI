# UX

The approved visual direction is institutional forensic software: warm ivory/stone surfaces, graphite text, deep teal primary actions, restrained semantic colors, compact rectangular cards, and monospace data for wallet/transaction identifiers. The current frontend has begun this migration through shared theme tokens and preserves the functional state/API model while visual work continues.

Investigation, WHY, replay, report, and timeline-jump failures surface a visible dismissible error banner; API messages remain safe and do not expose internal details.

The Next.js workspace presents case scope/risk at the top, navigation and filters on the left, React Flow graph in the center, and wallet/finding/evidence/AI/report details on the right. Primary actions call real APIs. React Flow provides zoom/pan and node/edge selection; wallet search selects a matching backend graph node and opens its WHY context. Money-trail focus changes graph emphasis; replay events highlight graph nodes and synchronize selected transaction/evidence context, while timeline events can jump to a replay step. The dashboard and investigation shell now have responsive structural behavior for phone-width layouts, and the app publishes standalone web-manifest metadata using the same frontend. This is not an APK or hosted deployment claim. Browser verification must not be claimed without an available browser.

The investigation navigation also exposes an authorized Audit Log view backed by `GET /cases/{case_id}/audit`. It is case-scoped, shows actor/action/resource/timestamp context, and deliberately omits stored IP addresses from the investigator UI.

Evidence cards expose the persisted source, timestamp, finding reference, and supporting transaction hash when available, keeping the investigator-visible chain `finding → evidence → transaction` explicit.

The shared API client keeps localhost as a development-only fallback. A production or installed-app build requires an explicit `NEXT_PUBLIC_API_URL`, preventing a phone from silently calling itself when the hosted HTTPS backend has not been configured.
