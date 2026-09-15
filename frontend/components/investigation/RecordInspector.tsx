import type { ReactNode } from 'react';
import type { CapabilityState } from '@/lib/capabilities';
import { displayAmount, type ExactTransfer } from '@/lib/transfers';
import { boundaryLabel, readable, type TrailWallet } from '@/lib/investigation';

export function Fact({ label, children }: { label: string; children: ReactNode }) {
  return <div className="inspect-fact"><dt>{label}</dt><dd>{children ?? 'Unavailable'}</dd></div>;
}
export function WalletInspector({ wallet, network, onClose, onTransfers, onEvidence, onWhy, onFocus }: {
  wallet: TrailWallet; network: string; onClose: () => void; onTransfers: () => void; onEvidence: () => void; onWhy: () => void; onFocus: () => void;
}) {
  return <section className="record-inspector" aria-labelledby="wallet-inspector-title">
    <div className="inspect-heading"><h2 id="wallet-inspector-title">Wallet inspector</h2><button onClick={onClose} aria-label="Close wallet inspector">×</button></div>
    <dl><Fact label="Address"><span className="font-mono">{wallet.address}</span></Fact>
      <div className="inspect-grid"><Fact label="Network">{network}</Fact><Fact label="Hop distance">{wallet.hop_distance ?? 'Unknown'}</Fact><Fact label="Expansion">{boundaryLabel(wallet)}</Fact><Fact label="Transfer count">{wallet.transaction_count ?? 'Unavailable'}</Fact></div>
      <Fact label="Destination classification">{readable(wallet.endpoint_kind)}</Fact>
      <Fact label="Attribution status">{wallet.vasp_attribution_status === 'known_verified' ? 'VERIFIED' : wallet.vasp_attribution_status === 'likely_inferred' ? 'INFERRED / LIKELY — review required' : 'UNKNOWN'}{wallet.vasp_name ? ` · ${wallet.vasp_name}` : ''}</Fact>
      {[['Received', wallet.received_by_asset], ['Sent', wallet.sent_by_asset]].map(([label, totals]) => <Fact key={String(label)} label={String(label)}>{Array.isArray(totals) && totals.length ? totals.map(total => <div key={total.asset_id}><strong>{total.amount_exact} {total.asset}</strong><small className="inspect-asset">{total.asset_id}</small></div>) : 'Unavailable'}</Fact>)}
    </dl>
    <div className="inspect-actions"><button onClick={onTransfers}>View transfers</button><button onClick={onEvidence}>View evidence</button><button onClick={onWhy}>Why this wallet?</button><button onClick={onFocus}>Focus graph</button></div>
  </section>;
}
export interface InspectorTransfer extends ExactTransfer {
  hash: string; from_address: string; to_address: string; amount?: number; asset: string; timestamp?: string | null; source?: string | null; status?: string | null;
}
export function TransferInspector({ transfer, network, capability, canSave, saving, message, onSave, onClose, onWallet, onFocus }: {
  transfer: InspectorTransfer; network: string; capability: CapabilityState; canSave: boolean; saving: boolean; message: string;
  onSave: () => void; onClose: () => void; onWallet: (address: string) => void; onFocus: () => void;
}) {
  return <section className="record-inspector" aria-labelledby="transfer-inspector-title">
    <div className="inspect-heading"><h2 id="transfer-inspector-title">Transfer inspector</h2><button onClick={onClose} aria-label="Close transfer inspector">×</button></div>
    <div className="inspect-amount"><strong>{displayAmount(transfer)}</strong><span>{transfer.asset}</span></div>
    <dl>
      <Fact label="Asset identity">{transfer.asset_id || 'Unknown'}</Fact>
      <div className="inspect-grid"><Fact label="Base units">{transfer.amount_base_units}</Fact><Fact label="Decimals">{transfer.token_decimals}</Fact></div>
      <Fact label="From"><button className="inspect-address" onClick={() => onWallet(transfer.from_address)}>{transfer.from_address}</button></Fact>
      <Fact label="To"><button className="inspect-address" onClick={() => onWallet(transfer.to_address)}>{transfer.to_address}</button></Fact>
      <div className="inspect-grid"><Fact label="Block">{transfer.block_number}</Fact><Fact label="Transaction status">{transfer.transaction_status || transfer.status || 'Unknown'}</Fact></div>
      <Fact label="Timestamp">{transfer.timestamp ? `${new Date(transfer.timestamp).toISOString()} (UTC)` : 'Unavailable'}</Fact>
      <Fact label="Transaction hash"><span className="font-mono">{transfer.hash}</span></Fact>
      <Fact label="Event / log identity">{transfer.event_index ?? transfer.log_index ?? 'Unavailable'}</Fact>
      <Fact label="Transfer identity">{transfer.transfer_id || 'Legacy record'}</Fact>
      <Fact label="Block hash">{transfer.block_hash || 'Unavailable'}</Fact>
      <Fact label="Provider / source">{String(transfer.provenance?.provider || transfer.source || capability.provider || 'Unknown')}</Fact>
      <Fact label="Coverage">{capability.data_origin === 'demo' ? 'DEMO DATA' : 'PROVIDER-OBSERVED DATA'} · {capability.coverage?.partial ? 'PARTIAL' : readable(capability.observation_state || capability.result_state).toUpperCase()}{transfer.token_decimals == null ? ' · METADATA UNAVAILABLE' : ''}</Fact>
    </dl>
    <div className="inspect-actions">
      {network === 'ethereum' && /^0x[0-9a-fA-F]{64}$/.test(transfer.hash) && <a href={`https://etherscan.io/tx/${transfer.hash}`} target="_blank" rel="noopener noreferrer">View transaction ↗</a>}
      {canSave && <button onClick={onSave} disabled={saving}>{saving ? 'Saving…' : 'Add evidence'}</button>}
      <button onClick={onFocus}>Focus transfer</button>
    </div>
    {message && <p role="status" className="trail-notice">{message}</p>}
  </section>;
}
