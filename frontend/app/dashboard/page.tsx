'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import {
  Search, Plus, Shield, Clock, CheckCircle,
  ChevronRight, Inbox, Loader2, LogOut, Settings as SettingsIcon
} from 'lucide-react';

const statusColors: Record<string, string> = {
  new: 'bg-[#edf3f3] text-[#124343] border-[#b4c8c7]',
  investigating: 'bg-[#fff4ed] text-[#734934] border-[#d9b49d]',
  review: 'bg-[#f5f0eb] text-[#58331f] border-[#d3bdaa]',
  completed: 'bg-[#edf8f1] text-[#28634c] border-[#a9cdb8]',
};

const statIconColors: Record<string, string> = {
  blue: 'text-blue-400',
  amber: 'text-amber-400',
  purple: 'text-purple-400',
  green: 'text-green-400',
};

interface CaseRecord {
  id: string;
  case_number: string;
  title: string;
  reported_wallet: string;
  blockchain: string;
  status: string;
  is_demo: boolean;
  created_at: string;
}

interface UserRecord { full_name: string; username: string; role: string; }
interface ReporterReviewRecord {
  id: string;
  reference_number: string;
  title: string;
  reported_wallet: string;
  blockchain: string;
  submitted_at: string;
}

export default function DashboardPage() {
  const router = useRouter();
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [reporterSubmissions, setReporterSubmissions] = useState<ReporterReviewRecord[]>([]);
  const [assigningSubmission, setAssigningSubmission] = useState('');
  const [user] = useState<UserRecord | null>(() => {
    if (typeof window === 'undefined') return null;
    const stored = localStorage.getItem('cryptotrace_user');
    if (!stored) return null;
    try { return JSON.parse(stored) as UserRecord; } catch { return null; }
  });

  const loadCases = useCallback(async () => {
    try {
      const data = await api.listCases();
      setCases(data.cases || []);
      setLoadError('');
    } catch (err) {
      console.error('Failed to load cases', err);
      setLoadError('Cases could not be loaded. Check your connection and try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadReporterSubmissions = useCallback(async () => {
    try {
      const data = await api.listReporterSubmissionsForReview();
      setReporterSubmissions(data.submissions || []);
    } catch (err) {
      console.error('Reporter submissions could not be loaded', err);
    }
  }, []);

  useEffect(() => {
    const token = api.getToken();
    if (!token) {
      router.push('/');
      return;
    }
    if (user?.role === 'reporter') {
      router.replace('/reporter');
      return;
    }
    void Promise.resolve().then(() => loadCases());
    void Promise.resolve().then(() => loadReporterSubmissions());
  }, [router, loadCases, loadReporterSubmissions, user?.role]);

  const assignSubmission = async (submissionId: string) => {
    setAssigningSubmission(submissionId);
    try {
      const assigned = await api.assignReporterSubmission(submissionId);
      setReporterSubmissions((current) => current.filter((item) => item.id !== submissionId));
      router.push(`/investigate?caseId=${encodeURIComponent(assigned.case_id)}`);
    } catch (err) {
      console.error('Reporter submission assignment failed', err);
      setLoadError('The reported wallet could not be assigned. Refresh the queue and try again.');
    } finally {
      setAssigningSubmission('');
    }
  };

  const handleLogout = () => {
    api.clearToken();
    localStorage.removeItem('cryptotrace_user');
    router.push('/');
  };

  return (
    <main id="main-content" className="ct-page ct-dashboard-page">
      {/* Top Bar */}
      <header className="ct-topbar sticky top-0 z-50 flex min-h-16 items-center justify-between gap-3 px-4 py-2 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="ct-brand-mark h-9 w-9 rounded-lg">
            <Shield className="w-4 h-4 text-white" />
          </div>
          <span className="text-sm font-bold tracking-tight text-[var(--ct-ink)]">CryptoTrace AI</span>
          <span className="ct-status-chip hidden bg-[#edf3f3] text-[var(--ct-primary)] sm:inline-flex">
            {(user?.role || 'investigator').toUpperCase()}
          </span>
        </div>
        <div className="flex items-center gap-4">
          <span className="hidden text-sm text-[var(--ct-ink-muted)] sm:inline">{user?.full_name || 'Investigator'}</span>
          <button onClick={() => router.push('/settings')} aria-label="Open settings" className="ct-icon-button flex items-center justify-center">
            <SettingsIcon className="w-4 h-4" />
          </button>
          <button onClick={handleLogout} aria-label="Sign out" className="ct-icon-button flex items-center justify-center">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {/* Dashboard Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <p className="ct-eyebrow mb-1">Investigation workspace</p>
            <h1 className="text-2xl font-bold tracking-tight text-[var(--ct-ink)]">Your cases</h1>
            <p className="mt-1 text-sm text-[var(--ct-ink-muted)]">Open an active case or start with one reported wallet.</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="ct-button-primary flex items-center gap-2 px-4 py-2.5 text-sm"
          >
            <Plus className="w-4 h-4" />
            New Case
          </button>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Total Cases', value: cases.length, icon: Shield, color: 'blue' },
            { label: 'Investigating', value: cases.filter(c => c.status === 'investigating').length, icon: Search, color: 'amber' },
            { label: 'Review', value: cases.filter(c => c.status === 'review').length, icon: Clock, color: 'purple' },
            { label: 'Completed', value: cases.filter(c => c.status === 'completed').length, icon: CheckCircle, color: 'green' },
          ].map((stat) => (
            <div key={stat.label} className="ct-card p-4">
              <div className="flex items-center justify-between mb-2">
                <stat.icon className={`w-5 h-5 ${statIconColors[stat.color] || statIconColors.blue}`} />
              </div>
              <div className="text-2xl font-bold text-[var(--ct-ink)]">{stat.value}</div>
              <div className="mt-1 text-xs text-[var(--ct-ink-muted)]">{stat.label}</div>
            </div>
          ))}
        </div>

        {reporterSubmissions.length > 0 && (
          <section className="mb-8" aria-labelledby="reporter-queue-heading">
            <div className="mb-3 flex items-end justify-between gap-3">
              <div>
                <p className="ct-eyebrow mb-1">Reporter intake</p>
                <h2 id="reporter-queue-heading" className="text-lg font-bold text-[var(--ct-ink)]">Reports awaiting assignment</h2>
              </div>
              <span className="ct-status-chip bg-[var(--ct-warning-surface)] text-[var(--risk-medium)]">{reporterSubmissions.length} waiting</span>
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              {reporterSubmissions.map((submission) => (
                <article key={submission.id} className="ct-card p-4">
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--ct-surface-high)] text-[var(--ct-primary)]"><Inbox className="h-4 w-4" /></div>
                    <div className="min-w-0 flex-1">
                      <div className="font-mono text-[10px] text-[var(--ct-outline)]">{submission.reference_number}</div>
                      <h3 className="mt-1 truncate text-sm font-semibold text-[var(--ct-ink)]">{submission.title}</h3>
                      <p className="mt-1 truncate font-mono text-[10px] text-[var(--ct-ink-muted)]">{submission.reported_wallet}</p>
                      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                        <span className="text-[10px] text-[var(--ct-outline)]">Submitted {new Date(submission.submitted_at).toLocaleString()}</span>
                        <button type="button" onClick={() => void assignSubmission(submission.id)} disabled={assigningSubmission === submission.id} className="ct-button-primary px-3 py-1.5 text-xs disabled:opacity-50">
                          {assigningSubmission === submission.id ? 'Assigning…' : 'Assign to me'}
                        </button>
                      </div>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        {/* Cases List */}
        {loading ? (
          <div role="status" className="ct-state-panel flex items-center justify-center py-16">
            <Loader2 className="h-5 w-5 animate-spin text-[var(--ct-primary)]" />
            <span className="ml-3 text-sm text-[var(--ct-ink-muted)]">Loading your cases…</span>
          </div>
        ) : loadError ? (
          <div className="ct-state-panel px-5 py-14 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg border border-[#e8aaa5] bg-[var(--ct-danger-surface)]">
              <Shield className="h-5 w-5 text-[var(--risk-high)]" />
            </div>
            <h3 className="mb-2 font-semibold text-[var(--ct-ink)]">Cases are temporarily unavailable</h3>
            <p className="mb-6 text-sm text-[var(--ct-ink-muted)]">{loadError}</p>
            <button onClick={() => void loadCases()} className="ct-button-primary px-6 py-2.5 text-sm">
              Retry
            </button>
          </div>
        ) : cases.length === 0 ? (
          <div className="ct-state-panel px-5 py-14 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg border border-[var(--ct-outline-variant)] bg-white">
              <Shield className="h-5 w-5 text-[var(--ct-ink-muted)]" />
            </div>
            <h3 className="mb-2 font-semibold text-[var(--ct-ink)]">No cases yet</h3>
            <p className="mb-6 text-sm text-[var(--ct-ink-muted)]">Create a case to begin tracing a reported wallet.</p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="ct-button-primary px-6 py-2.5 text-sm"
            >
              Create First Case
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {cases.map((c) => (
              <div
                key={c.id}
                role="button"
                tabIndex={0}
                aria-label={`Open case ${c.case_number}: ${c.title}`}
                onClick={() => router.push(`/investigate?caseId=${encodeURIComponent(c.id)}`)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    router.push(`/investigate?caseId=${encodeURIComponent(c.id)}`);
                  }
                }}
                className="ct-card ct-card-interactive group cursor-pointer p-5 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ct-primary)]"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-center gap-4 min-w-0">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--ct-surface-high)]">
                      <Shield className="h-5 w-5 text-[var(--ct-primary)]" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 sm:gap-3 mb-1">
                        <span className="font-mono text-xs text-slate-500">{c.case_number}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium border ${statusColors[c.status] || statusColors.new}`}>
                          {c.status?.toUpperCase()}
                        </span>
                        {c.is_demo && (
                          <span className="text-[10px] px-2 py-0.5 bg-amber-500/10 text-amber-400 rounded-full border border-amber-500/20">
                            DEMO DATA
                          </span>
                        )}
                      </div>
                      <h3 className="truncate font-medium text-[var(--ct-ink)]">{c.title}</h3>
                      <p className="mt-0.5 truncate font-mono text-xs text-[var(--ct-ink-muted)]">{c.reported_wallet}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4 pl-14 sm:pl-0">
                    <div className="text-left sm:text-right">
                      <div className="text-xs text-slate-500">
                        {new Date(c.created_at).toLocaleDateString()}
                      </div>
                      <div className="text-xs text-slate-600 mt-0.5">{c.blockchain}</div>
                    </div>
                    <ChevronRight className="h-4 w-4 text-[var(--ct-outline)] group-hover:text-[var(--ct-primary)]" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Case Modal */}
      {showCreateModal && (
        <CreateCaseModal
          onClose={() => setShowCreateModal(false)}
          onCreated={(c: CaseRecord) => {
            setCases([c, ...cases]);
            setShowCreateModal(false);
            router.push(`/investigate?caseId=${encodeURIComponent(c.id)}`);
          }}
        />
      )}
    </main>
  );
}

function CreateCaseModal({ onClose, onCreated }: { onClose: () => void; onCreated: (c: CaseRecord) => void }) {
  const [title, setTitle] = useState('Suspicious Wallet Investigation');
  const [wallet, setWallet] = useState('0xReported001');
  const [blockchain, setBlockchain] = useState('demo');
  const [amount, setAmount] = useState('12500');
  const [description, setDescription] = useState('Investigation of suspected fraud-linked wallet reported by victim.');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const data = await api.createCase({
        title,
        reported_wallet: wallet,
        blockchain,
        description,
        reported_amount: parseFloat(amount) || undefined,
      });
      onCreated(data);
    } catch (err: unknown) {
      console.error('Case creation failed', err);
      setError('The case could not be created. Check the wallet details and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ct-modal-backdrop fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="wallet-intake-title"
        aria-describedby="wallet-intake-description"
        className="ct-card mx-0 max-h-[90dvh] w-full max-w-lg overflow-y-auto p-5 shadow-[var(--ct-shadow-md)] animate-fade-in sm:mx-4 sm:p-6"
      >
        <div className="flex items-start justify-between gap-4 mb-1">
          <div>
            <div className="ct-eyebrow mb-1">Wallet intake</div>
            <h2 id="wallet-intake-title" className="text-lg font-bold text-[var(--ct-ink)]">Create a case</h2>
          </div>
          {blockchain === 'demo' && (
            <span className="shrink-0 text-[10px] px-2 py-1 bg-amber-500/10 text-amber-400 rounded border border-amber-500/20 font-medium">
              DEMO DATA
            </span>
          )}
        </div>
        <p id="wallet-intake-description" className="mb-6 text-sm leading-6 text-[var(--ct-ink-muted)]">Start with one reported wallet. CryptoTrace validates the address and keeps the investigation within this case.</p>

        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label htmlFor="wallet-intake-title-input" className="block text-sm font-medium text-slate-400 mb-1">Case Title</label>
            <input
              id="wallet-intake-title-input"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="ct-field px-4 py-2.5 text-sm"
              required
            />
          </div>

          <div>
            <label htmlFor="wallet-intake-wallet-input" className="block text-sm font-medium text-slate-400 mb-1">
              Reported Wallet Address
              <span className="text-red-400 ml-1">*</span>
            </label>
            <input
              id="wallet-intake-wallet-input"
              type="text"
              value={wallet}
              onChange={(e) => setWallet(e.target.value)}
              className="ct-field px-4 py-2.5 font-mono text-sm"
              placeholder="0x..."
              required
            />
            <p className="text-xs text-slate-600 mt-1">Demo Network accepts the deterministic demo wallet shown above. Other networks require a valid address for that chain.</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="wallet-intake-blockchain-input" className="block text-sm font-medium text-slate-400 mb-1">Blockchain</label>
              <select
                id="wallet-intake-blockchain-input"
                value={blockchain}
                onChange={(e) => setBlockchain(e.target.value)}
                className="ct-field px-4 py-2.5 text-sm"
              >
                <option value="demo">Demo Network</option>
                <option value="ethereum">Ethereum</option>
                <option value="bitcoin">Bitcoin</option>
                <option value="polygon">Polygon</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-1">Reported Amount (₹)</label>
              <input
                id="wallet-intake-amount-input"
                aria-label="Reported amount in INR"
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="ct-field px-4 py-2.5 text-sm"
              />
            </div>
          </div>

          <div>
            <label htmlFor="wallet-intake-description-input" className="block text-sm font-medium text-slate-400 mb-1">Description</label>
            <textarea
              id="wallet-intake-description-input"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="ct-field resize-none px-4 py-2.5 text-sm"
            />
          </div>

          {error && (
            <div role="alert" className="ct-error-panel px-4 py-3">
              <p className="text-sm">{error}</p>
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="ct-button-secondary flex-1 px-4 py-2.5 text-sm">
              Cancel
            </button>
            <button type="submit" disabled={loading}
              className="ct-button-primary flex-1 px-4 py-2.5 text-sm disabled:opacity-50">
              {loading ? 'Creating…' : 'Create case'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
