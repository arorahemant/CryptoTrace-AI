'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  ExternalLink,
  Scale,
} from 'lucide-react';
import api from '@/lib/api';

interface PublicCaseFact {
  fact_id: string;
  label: string;
  value: string;
  source_locator: string;
}

interface PublicCaseRecord {
  case_id: string;
  title: string;
  case_label: string;
  source_authority: string;
  source_type: string;
  source_url: string;
  jurisdiction: string;
  publication_date: string;
  blockchain: string;
  network_note: string;
  asset: string;
  publicly_disclosed_wallets: string[];
  wallet_disclosure_note: string;
  disclosed_transaction_references: string[];
  transaction_disclosure_note: string;
  provenance: string;
  analysis_availability: string;
  analysis_note: string;
  facts: PublicCaseFact[];
  outcome_note: string;
}

interface ComparisonRow {
  element: string;
  real_case: string;
  cryptotrace: string;
  result: 'MATCH' | 'PARTIAL_MATCH' | 'NOT_OBSERVABLE' | 'NOT_COMPARABLE';
  why: string;
  evidence: string[];
  source: string;
}

interface ComparisonRecord {
  case: PublicCaseRecord;
  source: { authority: string; type: string; url: string };
  cryptotrace: {
    status: string;
    message: string;
    is_demo: boolean;
    wallets: string[];
    transaction_references: string[];
    findings: string[];
    recommendations: string[];
    attribution: Record<string, unknown> | null;
  };
  rows: ComparisonRow[];
  alignment: {
    label: string;
    comparable_elements: number;
    matched: number;
    partial: number;
    not_observable: number;
    not_comparable: number;
  };
  limitations: string;
}

const resultStyles: Record<ComparisonRow['result'], string> = {
  MATCH: 'border-[#a9cdb8] bg-[#edf8f1] text-[#28634c]',
  PARTIAL_MATCH: 'border-[#d9b49d] bg-[#fff4ed] text-[#734934]',
  NOT_OBSERVABLE: 'border-[#b4c8c7] bg-[#edf3f3] text-[#124343]',
  NOT_COMPARABLE: 'border-[#d3bdaa] bg-[#f5f0eb] text-[#58331f]',
};

const resultLabels: Record<ComparisonRow['result'], string> = {
  MATCH: 'MATCH',
  PARTIAL_MATCH: 'PARTIAL MATCH',
  NOT_OBSERVABLE: 'NOT OBSERVABLE',
  NOT_COMPARABLE: 'NOT COMPARABLE',
};

function displayList(items: string[], fallback: string) {
  return items.length > 0 ? items.join(', ') : fallback;
}

export default function CaseComparisonPage() {
  const router = useRouter();
  const [publicCases, setPublicCases] = useState<PublicCaseRecord[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState('');
  const [comparison, setComparison] = useState<ComparisonRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    const storedUser = typeof window !== 'undefined' ? localStorage.getItem('cryptotrace_user') : null;
    let role = '';
    if (storedUser) {
      try {
        role = (JSON.parse(storedUser) as { role?: string }).role || '';
      } catch {
        role = '';
      }
    }
    if (!api.getToken()) {
      router.replace('/');
      return () => { cancelled = true; };
    }
    if (role === 'reporter') {
      router.replace('/reporter');
      return () => { cancelled = true; };
    }

    const load = async () => {
      try {
        const available = await api.listPublicCases() as PublicCaseRecord[];
        if (cancelled) return;
        setPublicCases(available);
        const first = available[0];
        if (!first) {
          setLoading(false);
          return;
        }
        setSelectedCaseId(first.case_id);
        const result = await api.getPublicCaseComparison(first.case_id) as ComparisonRecord;
        if (!cancelled) setComparison(result);
      } catch (err) {
        console.error('Public case comparison could not be loaded', err);
        if (!cancelled) setError('The public case reference could not be loaded. Check the investigator connection and retry.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => { cancelled = true; };
  }, [router]);

  const selectCase = async (caseId: string) => {
    setSelectedCaseId(caseId);
    setComparisonLoading(true);
    setError('');
    try {
      const result = await api.getPublicCaseComparison(caseId) as ComparisonRecord;
      setComparison(result);
    } catch (err) {
      console.error('Public case comparison could not be loaded', err);
      setError('The selected comparison could not be loaded.');
    } finally {
      setComparisonLoading(false);
    }
  };

  const caseRecord = comparison?.case;
  const aligned = comparison ? comparison.alignment.matched + comparison.alignment.partial : 0;

  return (
    <main id="main-content" className="ct-page min-h-screen bg-[var(--ct-background)]">
      <header className="ct-topbar sticky top-0 z-50 flex min-h-16 items-center justify-between gap-3 px-4 py-2 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <div className="ct-brand-mark flex h-9 w-9 shrink-0 items-center justify-center rounded-lg">
            <Scale className="h-4 w-4 text-white" />
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-bold tracking-tight text-[var(--ct-ink)]">CryptoTrace AI</div>
            <div className="hidden text-[10px] text-[var(--ct-ink-muted)] sm:block">Investigator case validation</div>
          </div>
        </div>
        <button type="button" onClick={() => router.push('/dashboard')} className="ct-button-secondary flex min-h-10 items-center gap-2 px-3 text-xs">
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to cases
        </button>
      </header>

      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="ct-eyebrow mb-1">More tools · case validation</p>
            <h1 className="text-2xl font-bold tracking-tight text-[var(--ct-ink)] sm:text-3xl">REAL CASE vs CRYPTOTRACE</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--ct-ink-muted)]">Compare publicly documented case findings with CryptoTrace&apos;s independent analytical results.</p>
          </div>
          {publicCases.length > 0 && (
            <label className="flex w-full max-w-sm flex-col gap-1.5 text-xs text-[var(--ct-ink-muted)]">
              <span className="ct-label">Public case reference</span>
              <select value={selectedCaseId} onChange={(event) => void selectCase(event.target.value)} className="ct-input min-h-11 w-full text-sm">
                {publicCases.map((item) => <option key={item.case_id} value={item.case_id}>{item.title}</option>)}
              </select>
            </label>
          )}
        </div>

        {loading ? (
          <div role="status" className="ct-state-panel px-5 py-16 text-center text-sm text-[var(--ct-ink-muted)]">Loading public case reference…</div>
        ) : error ? (
          <div role="alert" className="ct-state-panel px-5 py-12 text-center">
            <AlertTriangle className="mx-auto mb-3 h-6 w-6 text-[var(--risk-high)]" />
            <p className="text-sm text-[var(--ct-ink)]">{error}</p>
            <button type="button" onClick={() => window.location.reload()} className="ct-button-primary mt-5 px-4 py-2 text-xs">Retry</button>
          </div>
        ) : comparisonLoading || !comparison || !caseRecord ? (
          <div role="status" className="ct-state-panel px-5 py-16 text-center text-sm text-[var(--ct-ink-muted)]">Loading comparison…</div>
        ) : (
          <>
            <section className="ct-card mb-5 border-l-4 border-[var(--ct-primary)] p-4 sm:p-5" aria-labelledby="reference-banner-heading">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="ct-status-chip bg-[var(--ct-warning-surface)] text-[var(--risk-medium)]">{caseRecord.case_label}</span>
                    <span className="ct-status-chip bg-[var(--ct-surface-high)] text-[var(--ct-primary)]">{caseRecord.provenance}</span>
                  </div>
                  <h2 id="reference-banner-heading" className="mt-3 text-base font-bold text-[var(--ct-ink)]">{caseRecord.title}</h2>
                  <p className="mt-1 text-xs text-[var(--ct-ink-muted)]">NOT A CRYPTOTRACE-GENERATED INVESTIGATION</p>
                </div>
                  <div className="text-left text-xs sm:text-right">
                  <div className="ct-label">Source authority</div>
                  <div className="mt-1 font-semibold text-[var(--ct-ink)]">{comparison.source.authority}</div>
                  <div className="mt-1 text-[10px] text-[var(--ct-ink-muted)]">{comparison.source.type}</div>
                  <a href={comparison.source.url} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-[var(--ct-primary)] underline underline-offset-2">
                    Official source <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            </section>

            <section className="mb-5 grid gap-4 lg:grid-cols-2" aria-label="Real case and CryptoTrace comparison">
              <article className="ct-card p-4 sm:p-5">
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <p className="ct-eyebrow mb-1">Source record</p>
                    <h2 className="text-lg font-bold text-[var(--ct-ink)]">REAL CASE RECORD</h2>
                  </div>
                  <BookOpen className="h-5 w-5 text-[var(--ct-primary)]" />
                </div>
                <div className="grid gap-3 text-xs sm:grid-cols-2">
                  <div><div className="ct-label">Jurisdiction</div><div className="mt-1 text-[var(--ct-ink)]">{caseRecord.jurisdiction}</div></div>
                  <div><div className="ct-label">Reference date</div><div className="mt-1 text-[var(--ct-ink)]">{caseRecord.publication_date}</div></div>
                  <div><div className="ct-label">Network</div><div className="mt-1 text-[var(--ct-ink)]">{caseRecord.blockchain}</div><div className="mt-1 text-[10px] text-[var(--ct-ink-muted)]">{caseRecord.network_note}</div></div>
                  <div><div className="ct-label">Asset</div><div className="mt-1 text-[var(--ct-ink)]">{caseRecord.asset}</div></div>
                  <div><div className="ct-label">Public data</div><div className="mt-1 text-[var(--ct-ink)]">{caseRecord.publicly_disclosed_wallets.length > 0 ? 'PUBLICLY DISCLOSED' : 'NOT PUBLICLY DISCLOSED'}</div></div>
                  <div><div className="ct-label">Analysis availability</div><div className="mt-1 text-[var(--ct-ink)]">{caseRecord.analysis_availability}</div><div className="mt-1 text-[10px] text-[var(--ct-ink-muted)]">{caseRecord.analysis_note}</div></div>
                </div>
                <div className="mt-4 border-t border-[var(--ct-outline-variant)] pt-4">
                  <div className="ct-label">Publicly disclosed wallet</div>
                  <div className="mt-1 break-words font-mono text-xs text-[var(--ct-ink)]">{displayList(caseRecord.publicly_disclosed_wallets, caseRecord.wallet_disclosure_note)}</div>
                  <div className="mt-1 text-[10px] text-[var(--ct-ink-muted)]">Address identified in the public case record only when explicitly disclosed.</div>
                </div>
                <div className="mt-4 border-t border-[var(--ct-outline-variant)] pt-4">
                  <div className="ct-label">Transaction references</div>
                  <div className="mt-1 break-words font-mono text-xs text-[var(--ct-ink)]">{displayList(caseRecord.disclosed_transaction_references, caseRecord.transaction_disclosure_note)}</div>
                </div>
                <div className="mt-4 space-y-3 border-t border-[var(--ct-outline-variant)] pt-4">
                  {caseRecord.facts.map((fact) => <div key={fact.fact_id}><div className="ct-label">{fact.label}</div><p className="mt-1 text-xs leading-5 text-[var(--ct-ink-muted)]">{fact.value}</p><p className="mt-1 text-[10px] text-[var(--ct-outline)]">{fact.source_locator}</p></div>)}
                </div>
                <p className="mt-4 rounded border border-[var(--ct-outline-variant)] bg-[var(--ct-surface-high)] p-3 text-[10px] leading-5 text-[var(--ct-ink-muted)]">{caseRecord.outcome_note}</p>
              </article>

              <article className="ct-card p-4 sm:p-5">
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <p className="ct-eyebrow mb-1">Independent output</p>
                    <h2 className="text-lg font-bold text-[var(--ct-ink)]">CRYPTOTRACE ANALYSIS</h2>
                  </div>
                  <span className="ct-status-chip bg-[var(--ct-surface-high)] text-[var(--ct-primary)]">{comparison.cryptotrace.status}</span>
                </div>
                <div className="rounded border border-[var(--ct-outline-variant)] bg-[var(--ct-surface-high)] p-4">
                  <p className="text-sm font-semibold text-[var(--ct-ink)]">No independent analysis claimed</p>
                  <p className="mt-2 text-xs leading-5 text-[var(--ct-ink-muted)]">{comparison.cryptotrace.message}</p>
                </div>
                <div className="mt-4 grid gap-3 text-xs sm:grid-cols-2">
                  <div><div className="ct-label">Wallets analyzed</div><div className="mt-1 text-[var(--ct-ink)]">{displayList(comparison.cryptotrace.wallets, 'NONE')}</div></div>
                  <div><div className="ct-label">Transactions analyzed</div><div className="mt-1 text-[var(--ct-ink)]">{displayList(comparison.cryptotrace.transaction_references, 'NONE')}</div></div>
                  <div><div className="ct-label">Findings</div><div className="mt-1 text-[var(--ct-ink)]">{displayList(comparison.cryptotrace.findings, 'NONE')}</div></div>
                  <div><div className="ct-label">Attribution</div><div className="mt-1 text-[var(--ct-ink)]">NOT AVAILABLE</div></div>
                </div>
                <div className="mt-5 flex items-start gap-2 border-t border-[var(--ct-outline-variant)] pt-4 text-[10px] leading-5 text-[var(--ct-ink-muted)]">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--risk-medium)]" />
                  <span>CryptoTrace does not run DemoProvider against this public case or manufacture a match from undisclosed data.</span>
                </div>
              </article>
            </section>

            <section className="ct-card mb-5 p-4 sm:p-5" aria-labelledby="comparison-heading">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="ct-eyebrow mb-1">Element-by-element review</p>
                  <h2 id="comparison-heading" className="text-lg font-bold text-[var(--ct-ink)]">COMPARISON</h2>
                </div>
                <div className="rounded border border-[var(--ct-outline-variant)] bg-[var(--ct-surface-high)] px-4 py-3 text-left sm:text-right">
                  <div className="ct-label">Analytical alignment</div>
                  <div className="mt-1 text-xl font-bold text-[var(--ct-ink)]">{aligned} / {comparison.alignment.comparable_elements}</div>
                  <div className="mt-1 text-[10px] text-[var(--ct-ink-muted)]">{comparison.alignment.label}</div>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                {(['MATCH', 'PARTIAL_MATCH', 'NOT_OBSERVABLE', 'NOT_COMPARABLE'] as ComparisonRow['result'][]).map((result) => {
                  const count = result === 'MATCH' ? comparison.alignment.matched : result === 'PARTIAL_MATCH' ? comparison.alignment.partial : result === 'NOT_OBSERVABLE' ? comparison.alignment.not_observable : comparison.alignment.not_comparable;
                  return <div key={result} className={`rounded border px-3 py-2 text-center text-[10px] font-bold ${resultStyles[result]}`}><div>{resultLabels[result]}</div><div className="mt-1 text-base">{count}</div></div>;
                })}
              </div>
              <div className="mt-4 overflow-x-auto rounded border border-[var(--ct-outline-variant)]">
                <table className="min-w-[760px] w-full border-collapse text-left text-xs">
                  <thead className="bg-[var(--ct-surface-high)] text-[10px] uppercase tracking-wide text-[var(--ct-ink-muted)]">
                    <tr><th className="p-3 font-semibold">Investigation element</th><th className="p-3 font-semibold">Real case</th><th className="p-3 font-semibold">CryptoTrace</th><th className="p-3 font-semibold">Result</th></tr>
                  </thead>
                  <tbody>
                    {comparison.rows.map((row) => <tr key={row.element} className="border-t border-[var(--ct-outline-variant)] align-top"><td className="p-3 font-semibold text-[var(--ct-ink)]">{row.element}</td><td className="p-3 leading-5 text-[var(--ct-ink-muted)]">{row.real_case}</td><td className="p-3 leading-5 text-[var(--ct-ink-muted)]">{row.cryptotrace}</td><td className="p-3"><span className={`inline-flex whitespace-nowrap rounded border px-2 py-1 text-[9px] font-bold ${resultStyles[row.result]}`}>{resultLabels[row.result]}</span></td></tr>)}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="grid gap-4 lg:grid-cols-2">
              <article className="ct-card p-4 sm:p-5">
                <div className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-[var(--ct-primary)]" /><h2 className="text-sm font-bold text-[var(--ct-ink)]">WHY THE RESULTS ARE LIMITED</h2></div>
                <div className="mt-4 space-y-3">{comparison.rows.map((row) => <div key={`${row.element}-reason`} className="border-l-2 border-[var(--ct-outline-variant)] pl-3"><div className="text-xs font-semibold text-[var(--ct-ink)]">{row.element} · {resultLabels[row.result]}</div><p className="mt-1 text-xs leading-5 text-[var(--ct-ink-muted)]">{row.why}</p><p className="mt-1 text-[10px] text-[var(--ct-outline)]">Source: {row.source} · Evidence: {displayList(row.evidence, 'NOT AVAILABLE')}</p></div>)}</div>
              </article>
              <article className="ct-card p-4 sm:p-5">
                <div className="flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-[var(--risk-medium)]" /><h2 className="text-sm font-bold text-[var(--ct-ink)]">LIMITATIONS</h2></div>
                <p className="mt-4 text-xs leading-6 text-[var(--ct-ink-muted)]">{comparison.limitations}</p>
                <p className="mt-4 border-t border-[var(--ct-outline-variant)] pt-4 text-xs font-semibold leading-5 text-[var(--ct-ink)]">This is a comparable-element assessment, not an accuracy benchmark, legal certification, or claim of reproducing the original investigation.</p>
              </article>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
