import type { CapabilityState } from '@/lib/capabilities';
import { readable } from '@/lib/investigation';

export function CoverageStrip({ capability }: { capability: CapabilityState }) {
  const coverage = capability.coverage;
  const state = capability.processing_state === 'failed' ? 'ATTEMPT FAILED' : coverage?.partial ? 'PARTIAL' : readable(capability.observation_state || capability.result_state).toUpperCase();
  return <details className={`coverage-strip ${coverage?.partial || capability.processing_state === 'failed' ? 'coverage-limited' : ''}`}>
    <summary><span className="coverage-badge">{capability.data_origin === 'demo' ? 'DEMO DATA' : capability.data_origin === 'observed' ? 'PROVIDER-OBSERVED DATA' : 'NO OBSERVED DATA'}</span><strong>{state}</strong><span>{capability.provider || 'Provider not connected'}</span><span className="coverage-detail-label">Coverage &amp; limitations</span></summary>
    <div className="coverage-details">
      <dl><dt>Run</dt><dd className="font-mono">{capability.run_id || 'Not started'}</dd><dt>Observed interval</dt><dd>{coverage?.observation_boundaries?.from_block ?? 'Unavailable'} → {coverage?.observation_boundaries?.to_block ?? 'Unavailable'}</dd><dt>Retrieved</dt><dd>{coverage?.retrieved_at || capability.processed_at || 'Unavailable'}</dd><dt>Interval exhausted</dt><dd>{coverage?.exhausted == null ? 'Unknown' : coverage.exhausted ? 'Yes, within observation boundaries' : 'No'}</dd></dl>
      <ul>{capability.limitations.map((limit, i) => <li key={i}>{limit}</li>)}</ul>
      <p>Observed activity does not establish ownership, fraud, verified service attribution, or recovery. No continuous monitoring or external action.</p>
    </div>
  </details>;
}
