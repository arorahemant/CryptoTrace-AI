# Public Ethereum high-activity validation

This is a benign public observation example, not a fraud allegation or a claim
about the identity, ownership or conduct of any address or counterparty.

## Example and selection

- **Network:** Ethereum Mainnet, Alchemy only.
- **Address:** `0xd152f549545093347a162dce210e7293f1452150`.
- **Public context:** the [Disperse application repository](https://github.com/omniaprotocol/disperse.app)
  documents this contract on chain 1. This source helps choose an example;
  it does not create a verified VASP attribution in CryptoTrace.
- **Inclusive interval:** blocks **20,000,047–20,000,355**, approximately
  **2024-06-01 22:46:11–23:47:59 UTC**.
- **Direction:** outgoing. Maximum hops 2. The existing minimum amount field
  is not used to filter authoritative Ethereum event values.

Initial live probes confirmed many observable counterparties. Receipt batches
make this interval useful within the existing request budget. The final example
was selected after a live, authenticated end-to-end validation succeeded.

## Captured observation

Captured on **2026-09-15 UTC**, through normal case intake, capability,
investigation, graph, transfers, findings, evidence, recommendations and report APIs:

| Measurement | Observed result |
| --- | --- |
| Transfer events | 62 distinct standard ERC-20 receipt events |
| Ethereum transactions | 4 distinct transaction hashes |
| Graph addresses | 62: starting contract and 61 counterparties |
| Origin pagination | 25 + 25 + 12 records; final origin page exhausted |
| Provider requests | 29 |
| Evidence records | 62 |
| Findings | 0 |
| Recommendations | 1 review recommendation |
| Coverage | PARTIAL: timeout during further counterparty expansion |

The whole provider observation retains the existing 10-second deadline,
100-transfer maximum, 200-request maximum, 2-hop maximum, 2 retries and serial
requests. Measured API elapsed time was 10.172 seconds including application
overhead. Exhausting the origin's pages does **not** mean all counterparty
activity or the two-hop graph is exhausted. The persisted destination is an
unknown last-observed wallet, not a verified service or recovery endpoint.

These are event/address counts, not 62 separate transactions. No external ETH
transfers were returned in this interval. The provider still supports external
ETH and standard ERC-20 only; internal ETH, NFTs, bridges and swap interpretation
remain excluded. Relationships do not establish common ownership or prove that
the same funds continued through a path. Risk scoring is not enabled for these
observations; activity volume does not manufacture a finding.

## Reproduce in the existing UI

1. Sign in as an authorized investigator and create a case with a neutral title
   such as **Public Ethereum validation**. Choose **Ethereum**, then enter the
   address above. Keep this separate from Demo Network cases.
2. Open the investigation, verify the Ethereum/Alchemy capability, and enter
   start block **20000047**, end block **20000355**. The existing Ethereum UI
   submits an outgoing trace with maximum hops **2**.
3. Run the investigation. Read the current run's coverage; slower responses,
   account limits or upstream changes may produce fewer observations.
4. In **2D TRAIL**, use zoom/pan and select a wallet or individual transfer.
   Open the inspector; exact decimal strings, raw units and receipt log identity
   remain available. Select a transfer in the list if overview labels overlap.
5. Switch to **3D NETWORK**. The view uses the same persisted graph and selection.
   Focus and isolate the selected path, then reset the camera/show all transfers.
6. Review evidence, the review recommendation and the report. All use the same
   run and coverage. Reporter access remains restricted by existing RBAC.

Large graphs are initially fitted to the viewport. Individual labels require
zoom or path focus; the overview does not silently discard or aggregate events.
Coverage details expose the stopping reason and provider request count.

## Opt-in live capture and offline regressions

With the backend Python environment and backend-only `ALCHEMY_API_KEY` configured:

```powershell
cd backend
.venv/Scripts/python.exe -B validate_high_activity.py --live --capture <new-output-path.json>
```

The tool creates a disposable local database, authenticates a local investigator,
and calls the normal application APIs with the real Alchemy provider. Local demo
authentication is enabled only for this isolated database; explicit Ethereum
intake still selects Alchemy. The database is removed afterward. Existing output
files are refused. Captures contain public successful RPC results, fixed failure
codes and application observations; no credential, endpoint or auth token is
stored. This consumes a bounded live observation's quota, so normal regressions
replay the checked-in capture instead.

`backend/tests/fixtures/high_activity_alchemy.json` is a captured-response test
fixture, **never runtime frontend data**. Strict replay rejects uncaptured RPCs
rather than inventing empty responses. Fault-injection tests alter copies only.
Regressions cover pagination, exact event identities, duplicates, bounded partial
results, all 62 nodes/events, inspector values and synchronized path selection.

No new dependency, backend provider behavior or Demo dataset is introduced.
Live browser visual, pointer and touch testing was unavailable; source review,
server-rendered component tests, projection bounds, TypeScript and build checks
provide the available UI validation. A browser review remains recommended before
demonstrating the dense overview on different screen sizes.
