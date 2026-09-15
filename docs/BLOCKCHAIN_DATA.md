# Blockchain data: Phase 2B

Ethereum Mainnet has an explicit `AlchemyEthereumProvider`; Demo Network still uses the existing deterministic `DemoProvider`. Other networks remain intake-only. A real-chain request never selects or falls back to DemoProvider.

## Configuration and interval

Set `ALCHEMY_API_KEY` in the backend environment only. The credential is an excluded, masked settings field and is used only with the fixed HTTPS Ethereum Mainnet Alchemy host. It must not be supplied to Next.js, Android, reports, logs, or source control. Existing production database, CORS, signing-key, and demo-account restrictions still apply. Configuration alone is not a connection test: capability initially reports `not_verified`.

Ethereum observations require an explicit historical `from_block`; `to_block` is optional. An omitted end is resolved once to the finalized block. An explicit end beyond finalized is rejected. Every page, transaction, receipt, and block must agree with the pinned interval and block hashes. The Ethereum form accepts these block numbers. Time-window and minimum-display-amount options remain Demo controls; Ethereum uses the block interval and exact amounts without that float filter.

## Supported records and exact accounting

Only external ETH and standard ERC-20 transfers are requested using `alchemy_getAssetTransfers`. Each candidate is checked against `eth_getTransactionByHash`, `eth_getTransactionReceipt`, and `eth_getBlockByNumber`. Successful native value is an integer wei string with 18 decimals. ERC-20 values come from three-topic `Transfer(address,address,uint256)` receipt logs, with the log index retained as event identity. Token decimals are obtained by `eth_call` to `decimals()` at the event block; missing/reverted/malformed metadata is never replaced with a guessed precision. Generic `ERC-20` labels do not assert verified token branding.

The existing Phase 2A chain-qualified asset and transfer identities remain authoritative. Numeric legacy amount fields are display projections only. Asset totals use integer strings; assets are never combined or converted to fiat. Records retain block number/hash, status, retrieval timestamp, provider, method provenance, token contract, and receipt log index.

No internal ETH, NFTs, bridges, DeFi/swap interpretation, other chains, or other providers are enabled. Structural routes do not prove continuity of the same funds, ownership, wrongdoing, current custody, or recoverability. Fraud-pattern generation and risk scoring remain disabled for this narrow Ethereum observation slice. No VASP identity is inferred or verified. External asset-action creation/status changes are disabled for Ethereum; readiness remains false. There is no government integration or continuous real-time monitoring.

## Bounds and coverage

Each fresh run permits at most 2 hops, 100 normalized transfers, and 200 provider requests including retries. Requests run sequentially. The observation run has a 10-second shared deadline; individual requests cannot exceed its remaining time. Up to two retries use exponential backoff for transient failures and rate limits, honoring numeric `Retry-After` within the deadline. Terminal authentication, timeout, and provider-limit errors stop further traversal.

`ProviderPage` carries records, continuation, exhaustion, partial coverage, safe provider errors, observation boundaries, requested range, retrieval time, and provenance. Run coverage includes page summaries, limits, request count, and the selected destination. A continuation token is run-local; stored page metadata is an audit record, not a promise that an expired token can resume a later run. Partial results are never described as exhaustive; exhaustion only applies to supported categories, queried addresses/direction, and the requested interval.

Observation states: `not_configured`, `not_verified` (configured but untested), `invalid_credentials`, `unavailable`, `connected_no_records`, `observed`, `partial`, `provider_limit`, and `metadata_unavailable`. Data origin is `observed` only when the current run contains reconciled records; empty or failed runs have origin `none`.

## Runs and artifacts

Every Ethereum attempt receives a fresh UUID. The current derived snapshot is replaced atomically, with the run lock held through publication. Expected provider failures publish a failed or partial current run; unexpected failures invalidate the prior snapshot. Old successful results cannot substitute for a failed attempt. Evidence and reports from prior runs are retained as archived artifacts and excluded from current-run responses; derived wallet, transaction, finding, risk, timeline, and flow rows are replaced. Current graph, evidence, recommendations, readiness, Copilot and report share capability, coverage, and the persisted destination selection. Demo snapshot reuse is unchanged.

No schema change is required: existing case summaries and event metadata store the new provenance and coverage. Existing migration head remains `0008_transfer_metadata`.

## Public validation fixtures

`backend/tests/fixtures/phase2b_alchemy.json` contains 11 sanitized read-only Mainnet responses captured on 2026-09-15. The public examples are test inputs, with no suspicious-owner labels:

- ETH address `0xef4396d9ff8107086d215a1c9f8866c54795d7c7`, documented blocks `0xb0eadc`–`0xb96042`: [Alchemy example](https://www.alchemy.com/docs/data/transfers-api/transfers-endpoints/alchemy-get-asset-transfers).
- ERC-20 transaction `0xe8c208398bd5ae8e4c237658580db56a2a94dfa0ca382c99b776fa6e7d31d5b4`, recipient `0x4e83362442b8d1bec281594cea3050c8eb01311c`, block 4,730,207: [Etherscan example](https://docs.etherscan.io/api-reference/endpoint/tokentx).

The captured receipt has two Transfer events. MKR supports historical decimals (18); the older contract returns empty metadata. Both-direction retrieval therefore preserves the supported MKR observation and reports metadata-unavailable partial coverage. Tests additionally construct explicit fault/multiple-event variants from these fixtures; those variants are not claimed as live responses. Automated tests remove operator credentials and use replay transports; they do not spend account quota.
