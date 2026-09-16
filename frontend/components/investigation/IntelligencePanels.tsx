'use client';

import { displayAmount } from '@/lib/transfers';
import { readable, shortAddress } from '@/lib/investigation';
import { intelligenceLabel, originLabel, copilotQuestions, type DestinationIntelligence, type CopilotAnswer, type RecordReference } from '@/lib/intelligence';

type Select = (record: RecordReference) => void;
function RecordLinks({ records, onSelect }: { records: RecordReference[]; onSelect: Select }) {
  return records.length ? <ul className="intelligence-records">{records.map(record => <li key={`${record.kind}:${record.id}`}><button onClick={() => onSelect(record)} title={record.id}><span>{record.kind}</span> {record.label}<small>{shortAddress(record.id)}{record.source ? ` · ${record.source}` : ''}</small></button></li>)}</ul> : <p>NOT AVAILABLE — no linked records.</p>;
}

export function DestinationIntelligencePanel({ data, onSelect }: { data?: DestinationIntelligence; onSelect: Select }) {
  if (!data) return <section className="intelligence-panel"><h3>Destination Intelligence</h3><p>NOT AVAILABLE — current run intelligence could not be loaded.</p></section>;
  const attr = data.attribution;
  return <section className="intelligence-panel" aria-label="Destination Intelligence" data-run-id={data.run_id || ''}>
    <header><h3>Destination Intelligence</h3><strong className="intelligence-status">{intelligenceLabel(attr.attribution_status)}</strong></header>
    <p className="intelligence-origin">{originLabel(data.data_origin)} · {data.coverage?.partial ? 'PARTIAL' : readable(data.coverage?.state || (data.data_origin === 'demo' ? 'demo' : 'unknown')).toUpperCase()}</p>
    <dl><dt>Candidate</dt><dd>{data.candidate ? <button className="intelligence-address" onClick={() => onSelect({ kind: 'wallet', id: data.candidate!.address, label: 'Destination candidate' })}>{data.candidate.address}</button> : 'UNKNOWN'}</dd>
      <dt>Network</dt><dd>{data.network === 'ethereum' ? 'Ethereum Mainnet' : data.network === 'demo' ? 'Demo Network' : data.network}</dd>
      <dt>Classification</dt><dd>{readable(data.candidate?.kind)}</dd><dt>Entity</dt><dd>{attr.entity_name || 'UNKNOWN'}</dd>
      <dt>Attribution basis</dt><dd>{attr.reasoning || 'NOT AVAILABLE'}</dd>
      <dt>Observation source</dt><dd>{data.observation_provider || 'UNKNOWN'}</dd>
      <dt>Attribution source</dt><dd>{attr.source_reference || attr.source || 'UNKNOWN'} · {readable(attr.provenance)}</dd>
      <dt>Verified at</dt><dd>{data.verified_at || 'NOT AVAILABLE'}</dd><dt>Freshness</dt><dd>{readable(data.freshness)}</dd>
      <dt>Observed at</dt><dd>{data.retrieved_at || 'NOT AVAILABLE'}</dd>
      <dt>External attribution</dt><dd>{readable(data.external_attribution_provider).toUpperCase()}</dd>
    </dl>
    <details><summary>Selection basis &amp; supporting path</summary><p>{readable(data.selection_basis)}</p><RecordLinks records={data.supporting_path.map((id, i) => ({ kind: 'wallet', id, label: `Path step ${i}: ${shortAddress(id)}` }))} onSelect={onSelect} /></details>
    <details><summary>Observed supporting transfers ({data.supporting_transfers.length})</summary><p>Observed connections do not independently verify an entity.</p><RecordLinks records={data.supporting_transfers.map(t => ({ kind: 'transfer', id: t.id, label: `${displayAmount(t)} ${t.asset || ''}`, source: data.observation_provider || 'UNKNOWN' }))} onSelect={onSelect} /></details>
    <details><summary>Evidence chain ({data.evidence.length} records)</summary>
      {data.findings.map(f => <section key={f.id} className="intelligence-chain"><RecordLinks records={[{ kind: 'finding', id: f.id, label: f.title }, ...f.transfer_ids.map(id => ({ kind: 'transfer' as const, id, label: 'Supporting transfer' })), ...f.evidence_ids.map(id => ({ kind: 'evidence' as const, id, label: 'Saved evidence' }))]} onSelect={onSelect} />{data.candidate && <button onClick={() => onSelect({ kind: 'wallet', id: data.candidate!.address, label: 'Destination candidate' })}>Destination candidate →</button>}</section>)}
      {!data.findings.length && <p>No finding recorded for this candidate.</p>}
      <RecordLinks records={data.evidence.map(e => ({ kind: 'evidence', id: e.id, label: e.title, source: e.source }))} onSelect={onSelect} />
    </details>
    <details><summary>Attribution references &amp; limitations</summary><p>{attr.supporting_evidence_ids.length} evidence references · {attr.supporting_transaction_hashes.length} transaction references in the attribution record.</p><RecordLinks records={data.evidence.filter(e => attr.supporting_evidence_ids.includes(e.id)).map(e => ({ kind: 'evidence', id: e.id, label: e.title }))} onSelect={onSelect} /><ul>{data.limitations.map((s, i) => <li key={i}>{readable(s)}</li>)}</ul></details>
  </section>;
}

export function CopilotPanel({ answer, question, input, loading, disabled, contextLabel, onInput, onAsk, onSelect }: { answer: CopilotAnswer | null; question: string; input: string; loading: boolean; disabled: boolean; contextLabel: string; onInput: (s: string) => void; onAsk: (q?: string) => void; onSelect: Select }) {
  return <section className="intelligence-panel copilot-panel" aria-label="Investigation Copilot">
    <header><h3>Investigation Copilot</h3><span>Structured explanation</span></header>
    <p>Current selection: {contextLabel}</p>
    <div className="copilot-questions">{copilotQuestions.map(q => <button key={q} disabled={disabled || loading} onClick={() => onAsk(q)}>{q}</button>)}</div>
    <form onSubmit={event => { event.preventDefault(); onAsk(); }}><label htmlFor="copilot-question">Ask about this case</label><div><input id="copilot-question" value={input} onChange={e => onInput(e.target.value)} placeholder="Ask a question…" minLength={5} maxLength={1000} disabled={disabled || loading} /><button disabled={disabled || loading || input.trim().length < 5}>Send</button></div></form>
    <div aria-live="polite" aria-busy={loading}>
      {loading && <p role="status">Reading current case records…</p>}
      {!loading && answer && <article><h4>{question}</h4><p className="intelligence-origin">{originLabel(answer.data_origin)} · Attribution {intelligenceLabel(answer.attribution_status)}{answer.coverage?.partial ? ' · PARTIAL' : ''}</p>
        <h4>Answer</h4>{answer.sections?.length ? answer.sections.map((s, i) => <section key={i}><h4>{s.title}</h4><ul>{s.items.map((item, j) => <li key={j}>{item}</li>)}</ul></section>) : <p>{answer.answer}</p>}
        <details><summary>Key evidence ({(answer.supporting_records || []).filter(r => r.kind === 'evidence').length})</summary><RecordLinks records={(answer.supporting_records || []).filter(r => r.kind === 'evidence')} onSelect={onSelect} /></details>
        <details><summary>Supporting transfers ({(answer.supporting_records || []).filter(r => r.kind === 'transfer').length})</summary><RecordLinks records={(answer.supporting_records || []).filter(r => r.kind === 'transfer')} onSelect={onSelect} /></details>
        {(answer.supporting_records || []).some(r => r.kind === 'wallet' || r.kind === 'finding') && <details><summary>Wallets &amp; findings</summary><RecordLinks records={(answer.supporting_records || []).filter(r => r.kind === 'wallet' || r.kind === 'finding')} onSelect={onSelect} /></details>}
        <h4>Next review step</h4><p>{answer.next_review_step || 'NOT AVAILABLE — review saved evidence and coverage.'}</p>
        <details><summary>Sources &amp; limitations</summary><p>Run: {answer.run_id || 'NOT AVAILABLE'}</p><p>{answer.sources.join(' · ') || 'NOT AVAILABLE'}</p><ul>{answer.limitations.map((l, i) => <li key={i}>{readable(l)}</li>)}</ul></details>
      </article>}
      {!answer && !loading && <p>Answers use saved case/run records. No hidden blockchain or external intelligence searches.</p>}
    </div>
  </section>;
}

export function ActionReadinessSummary({ ready, evidenceCount, transferCount, candidate, attribution, isDemo, dataOrigin, onEvidence, onAudit }: { ready: boolean; evidenceCount: number; transferCount: number; candidate?: string | null; attribution: string; isDemo: boolean; dataOrigin: string; onEvidence: () => void; onAudit: () => void }) {
  return <section className="intelligence-panel" aria-label="Action package readiness"><h3>Action readiness</h3><p>{originLabel(dataOrigin)} · {isDemo ? 'local request preparation' : 'external action unavailable'}</p>
    <dl><dt>Evidence preserved</dt><dd>{evidenceCount ? `${evidenceCount} records` : 'NOT AVAILABLE'}</dd><dt>Supporting transfers</dt><dd>{transferCount}</dd><dt>Destination candidate</dt><dd>{candidate ? 'IDENTIFIED' : 'UNKNOWN'}</dd><dt>Attribution review</dt><dd>{attribution === 'known_verified' ? 'VERIFIED RECORD' : 'REQUIRED'}</dd><dt>Request package</dt><dd>{ready && isDemo ? 'READY FOR LOCAL PREPARATION' : 'NOT READY'}</dd></dl>
    <div className="copilot-questions"><button onClick={onEvidence}>View evidence</button><button onClick={onAudit}>View audit</button></div><p>Preparation records a local request. External submission and freezing are not performed or independently verified.</p>
  </section>;
}
