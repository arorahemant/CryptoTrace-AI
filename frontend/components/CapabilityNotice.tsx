import { capabilityLabel, type CapabilityState } from '@/lib/capabilities';

export function CapabilityNotice({ capability }: { capability?: CapabilityState }) {
  return <div role="status" className="rounded border border-[var(--ct-outline-variant)] bg-[var(--ct-surface-low)] px-3 py-2 text-xs leading-5 text-[var(--ct-ink-muted)]">
    <span className="font-semibold">{capabilityLabel(capability)}</span>
    {capability?.data_as_of && <span className="block">Data timestamp: {capability.data_as_of}</span>}
    {capability?.result_state === 'empty' && <span className="block">No matching records in this result. This does not establish that the wallet has no activity.</span>}
    {capability?.result_state === 'partial' && <span className="block">Limited coverage. Do not treat destinations or totals as exhaustive.</span>}
    {capability?.result_state === 'stale' && <span className="block">Historical result; freshness or processing metadata is unavailable.</span>}
    <span className="block">Case closure, verified ownership, recovery and external action are separate from processing status.</span>
  </div>;
}
