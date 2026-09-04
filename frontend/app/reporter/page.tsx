'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CheckCircle2, FileSearch, Loader2, LogOut, Send, ShieldCheck } from 'lucide-react';
import api from '@/lib/api';

interface ReporterUser {
  full_name: string;
  role: string;
}

interface ReporterSubmission {
  id: string;
  reference_number: string;
  title: string;
  reported_wallet: string;
  blockchain: string;
  status: string;
  status_label: string;
  submitted_at: string;
  last_status_update: string;
  next_step: string;
  assigned_investigator?: { display_name: string; role_title: string } | null;
}

const statusStyle: Record<string, string> = {
  report_received: 'border-[#b4c8c7] bg-[#edf3f3] text-[#124343]',
  under_investigation: 'border-[#d9b49d] bg-[#fff4ed] text-[#734934]',
  further_review_required: 'border-[#d3bdaa] bg-[#f5f0eb] text-[#58331f]',
  investigation_completed: 'border-[#a9cdb8] bg-[#edf8f1] text-[#28634c]',
};

export default function ReporterPage() {
  const router = useRouter();
  const [user] = useState<ReporterUser | null>(() => {
    if (typeof window === 'undefined') return null;
    const stored = localStorage.getItem('cryptotrace_user');
    if (!stored) return null;
    try { return JSON.parse(stored) as ReporterUser; } catch { return null; }
  });
  const [submissions, setSubmissions] = useState<ReporterSubmission[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [createdReference, setCreatedReference] = useState('');
  const [title, setTitle] = useState('Suspicious wallet report');
  const [wallet, setWallet] = useState('0xReported001');
  const [blockchain, setBlockchain] = useState('demo');
  const [description, setDescription] = useState('');

  const loadSubmissions = useCallback(async () => {
    try {
      const data = await api.listReporterSubmissions();
      setSubmissions(data);
      setError('');
    } catch (requestError) {
      console.error('Reporter submissions could not be loaded', requestError);
      setError('Your reports could not be loaded. Check your connection and try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
    if (!api.getToken()) {
      router.replace('/');
      return;
    }
    if (user?.role !== 'reporter') {
      router.replace('/dashboard');
      return;
    }
    void Promise.resolve().then(loadSubmissions);
  }, [loadSubmissions, router, user?.role]);

  const handleLogout = () => {
    api.clearToken();
    localStorage.removeItem('cryptotrace_user');
    router.push('/');
  };

  const submitReport = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    setCreatedReference('');
    try {
      const submission = await api.createReporterSubmission({
        title,
        reported_wallet: wallet,
        blockchain,
        description: description || undefined,
      });
      setSubmissions((current) => [submission, ...current]);
      setCreatedReference(submission.reference_number);
      setDescription('');
    } catch (requestError) {
      console.error('Reporter submission failed', requestError);
      setError('The report could not be submitted. Check the wallet details and try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main id="main-content" className="ct-page">
      <header className="ct-topbar sticky top-0 z-50 flex min-h-16 items-center justify-between gap-3 px-4 py-2 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <div className="ct-brand-mark h-9 w-9 rounded-lg"><FileSearch className="h-4 w-4" aria-hidden="true" /></div>
          <div className="min-w-0">
            <div className="truncate text-sm font-bold text-[var(--ct-ink)]">CryptoTrace AI</div>
            <div className="text-[10px] text-[var(--ct-ink-muted)]">Reporter view</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden text-sm text-[var(--ct-ink-muted)] sm:inline">{user?.full_name || 'Reporter'}</span>
          <button type="button" onClick={handleLogout} aria-label="Sign out" className="ct-icon-button flex items-center justify-center"><LogOut className="h-4 w-4" /></button>
        </div>
      </header>

      <div className="ct-reporter-content mx-auto max-w-4xl px-4 py-6 sm:px-6 sm:py-10">
        <section className="ct-reporter-intro mb-7">
          <p className="ct-eyebrow mb-2">Your report</p>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--ct-ink)] sm:text-3xl">Report one wallet. Track your submission.</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--ct-ink-muted)]">Submit a suspicious wallet and keep the reference ID. This view shows only safe status information for reports owned by your account.</p>
        </section>

        {error && <div role="alert" className="ct-error-panel mb-5 px-4 py-3 text-sm">{error}</div>}
        {createdReference && (
          <div role="status" className="mb-5 flex items-start gap-3 rounded-lg border border-[#a9cdb8] bg-[var(--ct-success-surface)] p-4 text-sm text-[var(--ct-ink)]">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[var(--risk-low)]" />
            <div><strong>Submission received.</strong><div className="mt-1 font-mono text-xs">Reference ID: {createdReference}</div></div>
          </div>
        )}

        <section id="report-wallet" className="ct-reporter-form ct-card p-5 sm:p-6" aria-labelledby="report-wallet-heading">
          <div className="mb-5 flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--ct-surface-high)] text-[var(--ct-primary)]"><Send className="h-4 w-4" /></div>
            <div><h2 id="report-wallet-heading" className="font-bold text-[var(--ct-ink)]">Report a suspicious wallet</h2><p className="mt-1 text-xs leading-5 text-[var(--ct-ink-muted)]">Wallet format is validated. Submission does not claim ownership, guilt, or a confirmed fraud finding.</p></div>
          </div>
          <form onSubmit={submitReport} className="grid gap-4 sm:grid-cols-2">
            <label className="sm:col-span-2"><span className="mb-1.5 block text-sm font-semibold text-[var(--ct-ink)]">Report title</span><input className="ct-field px-3 text-sm" value={title} onChange={(event) => setTitle(event.target.value)} required minLength={3} /></label>
            <label className="sm:col-span-2"><span className="mb-1.5 block text-sm font-semibold text-[var(--ct-ink)]">Reported wallet</span><input className="ct-field px-3 font-mono text-sm" value={wallet} onChange={(event) => setWallet(event.target.value)} required minLength={10} /></label>
            <label><span className="mb-1.5 block text-sm font-semibold text-[var(--ct-ink)]">Blockchain</span><select className="ct-field px-3 text-sm" value={blockchain} onChange={(event) => setBlockchain(event.target.value)}><option value="demo">Demo Network</option><option value="ethereum">Ethereum</option><option value="bitcoin">Bitcoin</option><option value="polygon">Polygon</option><option value="bsc">BNB Smart Chain</option></select></label>
            <div className="flex items-end"><span className="w-full rounded-lg border border-[#d9c3af] bg-[var(--ct-warning-surface)] p-3 text-xs leading-5 text-[var(--ct-ink-muted)]">Demo Network uses deterministic demonstration data.</span></div>
            <label className="sm:col-span-2"><span className="mb-1.5 block text-sm font-semibold text-[var(--ct-ink)]">What happened? <span className="font-normal text-[var(--ct-ink-muted)]">(optional)</span></span><textarea className="ct-field min-h-24 resize-y px-3 py-2.5 text-sm" value={description} onChange={(event) => setDescription(event.target.value)} maxLength={2000} placeholder="Add context that may help an investigator review the report." aria-describedby="description-counter" /><div id="description-counter" className="mt-1.5 text-right text-xs text-[var(--ct-ink-muted)]" aria-live="polite">{description.length} / 2,000 characters</div></label>
            <div className="sm:col-span-2"><button type="submit" disabled={submitting} className="ct-button-primary flex w-full items-center justify-center gap-2 px-4 py-2.5 text-sm disabled:opacity-50 sm:w-auto">{submitting ? <><Loader2 className="h-4 w-4 animate-spin" />Submitting…</> : 'Submit report'}</button></div>
          </form>
        </section>

        <section id="report-status" className="ct-reporter-status mt-8" aria-labelledby="submitted-reports-heading">
          <div className="mb-3 flex items-end justify-between gap-3"><div><p className="ct-eyebrow mb-1">Status</p><h2 id="submitted-reports-heading" className="text-lg font-bold text-[var(--ct-ink)]">Your submitted reports</h2></div><span className="text-xs text-[var(--ct-ink-muted)]">{submissions.length} total</span></div>
          {loading ? (
            <div role="status" className="ct-state-panel flex items-center justify-center py-10 text-sm text-[var(--ct-ink-muted)]"><Loader2 className="mr-2 h-4 w-4 animate-spin" />Loading reports…</div>
          ) : submissions.length === 0 ? (
            <div className="ct-state-panel px-5 py-10 text-center"><ShieldCheck className="mx-auto h-6 w-6 text-[var(--ct-ink-muted)]" /><p className="mt-3 text-sm font-semibold text-[var(--ct-ink)]">No reports submitted</p><p className="mt-1 text-xs text-[var(--ct-ink-muted)]">Your first submission will appear here with its reference ID.</p></div>
          ) : (
            <div className="space-y-3">
              {submissions.map((submission) => (
                <article key={submission.id} className="ct-card p-4 sm:p-5">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0"><div className="font-mono text-[10px] text-[var(--ct-outline)]">{submission.reference_number}</div><h3 className="mt-1 font-semibold text-[var(--ct-ink)]">{submission.title}</h3><p className="mt-1 break-all font-mono text-xs text-[var(--ct-ink-muted)]">{submission.reported_wallet}</p></div>
                    <span className={`ct-status-chip self-start ${statusStyle[submission.status] || statusStyle.report_received}`}>{submission.status_label}</span>
                  </div>
                  <div className="mt-4 grid gap-3 border-t border-[var(--ct-outline-variant)] pt-4 sm:grid-cols-2">
                    <div><div className="text-[10px] font-semibold uppercase tracking-wide text-[var(--ct-outline)]">What happens next</div><p className="mt-1 text-xs leading-5 text-[var(--ct-ink-muted)]">{submission.next_step}</p></div>
                    <div><div className="text-[10px] font-semibold uppercase tracking-wide text-[var(--ct-outline)]">Accountability</div>{submission.assigned_investigator ? <div className="mt-1"><div className="text-sm font-semibold text-[var(--ct-ink)]">{submission.assigned_investigator.display_name}</div><div className="text-xs text-[var(--ct-ink-muted)]">{submission.assigned_investigator.role_title}</div></div> : <p className="mt-1 text-xs leading-5 text-[var(--ct-ink-muted)]">Approved investigator details are not available for display.</p>}</div>
                  </div>
                  <div className="mt-3 text-[10px] text-[var(--ct-outline)]">Submitted {new Date(submission.submitted_at).toLocaleString()} · Last status update {new Date(submission.last_status_update).toLocaleString()}</div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
