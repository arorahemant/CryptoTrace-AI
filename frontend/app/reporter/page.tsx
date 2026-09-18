'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, Check, CheckCircle2, Copy, FileSearch, Loader2, LogOut, RefreshCw, Send } from 'lucide-react';
import api, { ApiError } from '@/lib/api';
import type { CapabilityState, NetworkCapability } from '@/lib/capabilities';
import { networkOptions, reporterStatus, walletError, reporterError, formatReportDate } from '@/lib/reporter-ui';
import './reporter.css';

interface ReporterUser { full_name: string; role: string }
interface ReporterSubmission {
  capability: CapabilityState;
  id: string;
  reference_number: string;
  title: string;
  reported_wallet: string;
  blockchain: string;
  asset: string;
  status: string;
  submitted_at: string;
  last_status_update?: string;
  assigned_investigator?: { display_name: string; role_title: string } | null;
}

function Reference({ value }: { value: string }) {
  const [copyState, setCopyState] = useState('');
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopyState('Reference ID copied.');
    } catch {
      setCopyState('Copy is unavailable. Press and hold the reference ID to select and copy it.');
    }
  }
  return <div className="rp-reference">
    <p className="rp-label">Reference ID</p>
    <div className="rp-reference-row"><strong>{value}</strong><button type="button" className="ct-button-secondary" onClick={copy} aria-label={`Copy reference ID ${value}`}><Copy size={18} aria-hidden="true" />Copy</button></div>
    <p className="rp-help" role="status">{copyState || 'Save this ID. Use it to find this report in your account.'}</p>
  </div>;
}

function NetworkNotice({ capability, demo }: { capability?: CapabilityState; demo: boolean }) {
  if (demo || capability?.data_origin === 'demo') return <p className="rp-notice"><strong>DEMO DATA</strong> · This network uses demonstration data, not real wallet activity.</p>;
  if (!capability) return <p className="rp-notice">Network availability could not be checked. You can still submit a report.</p>;
  if (capability.provider_state === 'not_connected') return <p className="rp-notice">Reports are accepted for this network. Wallet activity analysis is currently unavailable.</p>;
  return null;
}

function ReportCard({ report }: { report: ReporterSubmission }) {
  const status = reporterStatus(report.status);
  const submitted = formatReportDate(report.submitted_at);
  const updated = formatReportDate(report.last_status_update);
  return <article className="ct-card rp-report" aria-label={`Report ${report.reference_number}`}>
    <Reference value={report.reference_number} />
    <h3>{report.title}</h3>
    <p className="rp-help">{networkOptions.find(n => n.value === report.blockchain)?.label || 'Reported network'} · {report.asset}</p>
    <p className="rp-wallet">{report.reported_wallet}</p>
    <NetworkNotice capability={report.capability} demo={report.blockchain === 'demo'} />
    <ol className="rp-journey" aria-label="Report status journey">
      <li aria-current={report.status === 'report_received' ? 'step' : undefined}>
        <span className="rp-step"><Check size={18} aria-hidden="true" /></span>
        <div><p className="rp-label">Report received{report.status === 'report_received' && <span className="rp-current">Current status</span>}</p>
          {submitted && <p className="rp-help"><time dateTime={report.submitted_at}>{submitted}</time></p>}
          {report.status === 'report_received' && <p>{status.description}</p>}
        </div>
      </li>
      {report.status !== 'report_received' && <li aria-current="step"><span className="rp-step rp-step-current" aria-hidden="true" /><div><p className="rp-label">{status.label}<span className="rp-current">Current status</span></p><p>{status.description}</p></div></li>}
    </ol>
    <p className="rp-help rp-updated">{updated ? <>Last update <time dateTime={report.last_status_update}>{updated}</time></> : 'Last update time is unavailable.'}</p>
    {report.assigned_investigator && <div className="rp-contact"><p className="rp-label">Assigned investigator</p><p>{report.assigned_investigator.display_name}</p><p className="rp-help">{report.assigned_investigator.role_title}</p></div>}
  </article>;
}

export default function ReporterPage() {
  const router = useRouter();
  const [user] = useState<ReporterUser | null>(() => {
    if (typeof window === 'undefined') return null;
    const stored = localStorage.getItem('cryptotrace_user');
    if (!stored) return null;
    try { return JSON.parse(stored) as ReporterUser; } catch { return null; }
  });
  const [view, setView] = useState('home');
  const [ready, setReady] = useState(false);
  const [submissions, setSubmissions] = useState<ReporterSubmission[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [capabilities, setCapabilities] = useState<NetworkCapability[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<{ title?: string; wallet?: string }>({});
  const [created, setCreated] = useState<ReporterSubmission | null>(null);
  const [title, setTitle] = useState('Suspicious wallet report');
  const [wallet, setWallet] = useState('0xReported001');
  const [blockchain, setBlockchain] = useState('demo');
  const [asset, setAsset] = useState('ETH');
  const [description, setDescription] = useState('');
  const [referenceQuery, setReferenceQuery] = useState('');
  const submitLock = useRef(false);
  const loadVersion = useRef(0);
  const heading = useRef<HTMLHeadingElement>(null);
  const titleInput = useRef<HTMLInputElement>(null);
  const walletInput = useRef<HTMLTextAreaElement>(null);
  const selectedNetwork = networkOptions.find(option => option.value === blockchain) || networkOptions[0];

  const loadSubmissions = useCallback(async () => {
    const version = ++loadVersion.current;
    setLoading(true);
    setLoadError('');
    try {
      const data = await api.listReporterSubmissions();
      if (version === loadVersion.current) setSubmissions(data);
    } catch (requestError) {
      if (version === loadVersion.current) setLoadError(reporterError(requestError instanceof ApiError ? requestError.status : undefined, 'load'));
    } finally {
      if (version === loadVersion.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
    if (!api.getToken() || user?.role !== 'reporter') { router.replace('/#reporter'); return; }
    void Promise.resolve().then(() => { setReady(true); return loadSubmissions(); });
    api.capabilities().then(data => setCapabilities(data.networks)).catch(() => setCapabilities([]));
  }, [loadSubmissions, router, user?.role]);

  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, [view]);

  function navigate(next: string) {
    if (submitLock.current) return;
    setView(next);
    if (next === 'track') void loadSubmissions();
  }

  const handleLogout = () => {
    api.clearToken();
    localStorage.removeItem('cryptotrace_user');
    router.push('/');
  };

  const submitReport = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submitLock.current || created) return;
    const validation = { title: title.trim().length < 3 ? 'Add a title with at least 3 characters.' : undefined, wallet: walletError(wallet, blockchain) };
    setFieldErrors(validation);
    setError('');
    if (validation.title || validation.wallet) {
      (validation.title ? titleInput.current : walletInput.current)?.focus();
      return;
    }
    submitLock.current = true;
    setSubmitting(true);
    try {
      const submission = await api.createReporterSubmission({ title: title.trim(), reported_wallet: wallet.trim(), blockchain, asset, description: description.trim() || undefined });
      ++loadVersion.current;
      setLoading(false);
      setSubmissions(current => [submission, ...current.filter(item => item.id !== submission.id)]);
      setCreated(submission);
      setView('success');
      setDescription('');
    } catch (requestError) {
      setError(reporterError(requestError instanceof ApiError ? requestError.status : undefined, 'submit'));
    } finally {
      submitLock.current = false;
      setSubmitting(false);
    }
  };

  function startReport() {
    if (created) { setCreated(null); setWallet(''); setTitle('Suspicious wallet report'); setError(''); setFieldErrors({}); }
    navigate('report');
  }

  const matchingReports = submissions.filter(report => report.reference_number.toLowerCase().includes(referenceQuery.trim().toLowerCase()));

  if (!ready) return <main id="main-content" className="ct-page rp-page"><div className="rp-state" role="status"><Loader2 className="rp-spinner" size={26} aria-hidden="true" /><p>Opening reporter access…</p></div></main>;

  return <main id="main-content" className="ct-page rp-page">
    <header className="rp-header">
      <button type="button" className="rp-brand" onClick={() => navigate('home')} disabled={submitting} aria-label="CryptoTrace AI reporter home"><span className="ct-brand-mark"><FileSearch size={22} aria-hidden="true" /></span><span>CryptoTrace AI<small>Wallet reporting</small></span></button>
      <button type="button" className="ct-icon-button" onClick={handleLogout} disabled={submitting} aria-label="Sign out"><LogOut size={20} aria-hidden="true" /></button>
    </header>
    <div className="rp-shell">
      <nav className="rp-nav" aria-label="Reporter navigation">
        <button type="button" aria-current={view === 'report' || view === 'success' ? 'page' : undefined} onClick={startReport} disabled={submitting}><Send size={18} aria-hidden="true" />Report</button>
        <button type="button" aria-current={view === 'track' ? 'page' : undefined} onClick={() => { setReferenceQuery(''); navigate('track'); }} disabled={submitting}><FileSearch size={18} aria-hidden="true" />Track</button>
      </nav>

      {view === 'home' && <section className="rp-home">
        <p className="rp-eyebrow">A clear first step</p>
        <h1 ref={heading} tabIndex={-1}>Suspicious wallet?<br />Start with a report.</h1>
        <p className="rp-lead">Share a wallet address and what happened. Receive a reference ID to follow your report’s status.</p>
        <div className="rp-actions"><button type="button" className="ct-button-primary" onClick={startReport}>Report Suspicious Wallet<ArrowRight size={20} aria-hidden="true" /></button><button type="button" className="ct-button-secondary" onClick={() => navigate('track')}>Track My Report</button></div>
        <p className="rp-help">Your reports and their status are available in your account.</p>
        <ol className="rp-overview" aria-label="How reporting works"><li><span>1</span>Report a wallet</li><li><span>2</span>Save your reference ID</li><li><span>3</span>Track your report</li></ol>
      </section>}

      {view === 'report' && <section aria-labelledby="report-heading">
        <div className="rp-section-heading"><p className="rp-eyebrow">New report</p><h1 id="report-heading" ref={heading} tabIndex={-1}>Report a suspicious wallet</h1><p>Share the details below. You’ll receive a reference ID after submitting.</p></div>
        <form onSubmit={submitReport} noValidate className="ct-card rp-form" aria-busy={submitting}>
          <fieldset disabled={submitting}>
            <legend className="sr-only">Wallet report details</legend>
            <label htmlFor="report-title">Report title <span>Required</span></label>
            <input id="report-title" ref={titleInput} className="ct-field" value={title} onChange={e => { setTitle(e.target.value); setFieldErrors(current => ({ ...current, title: undefined })); }} required minLength={3} maxLength={255} aria-invalid={!!fieldErrors.title} aria-describedby={fieldErrors.title ? 'title-error' : undefined} />
            {fieldErrors.title && <p id="title-error" className="rp-field-error">{fieldErrors.title}</p>}
            <div className="rp-field-pair"><div><label htmlFor="report-network">Blockchain network <span>Required</span></label><select id="report-network" className="ct-field" value={blockchain} onChange={e => { const next = networkOptions.find(option => option.value === e.target.value)!; setBlockchain(next.value); setAsset(next.assets[0].value); setFieldErrors(current => ({ ...current, wallet: undefined })); }} aria-describedby="network-help">{networkOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div>
              <div><label htmlFor="report-asset">Currency <span>Required</span></label><select id="report-asset" className="ct-field" value={asset} onChange={e => setAsset(e.target.value)}>{selectedNetwork.assets.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div></div>
            <p id="network-help" className="rp-help">Choose the network used for the wallet or transaction.</p>
            <label htmlFor="report-wallet">Wallet address <span>Required</span></label>
            <textarea id="report-wallet" ref={walletInput} className="ct-field rp-address-input" rows={3} value={wallet} onChange={e => { setWallet(e.target.value); setFieldErrors(current => ({ ...current, wallet: undefined })); }} required maxLength={255} spellCheck={false} autoCapitalize="none" autoCorrect="off" aria-invalid={!!fieldErrors.wallet} aria-describedby={`wallet-help${fieldErrors.wallet ? ' wallet-error' : ''}`} placeholder="Paste the complete wallet address" />
            <p id="wallet-help" className="rp-help">{selectedNetwork.hint}</p>
            {fieldErrors.wallet && <p id="wallet-error" className="rp-field-error">{fieldErrors.wallet}</p>}
            <NetworkNotice capability={capabilities.find(n => n.blockchain === blockchain)?.capability} demo={blockchain === 'demo'} />
            <label htmlFor="report-description">What happened? <span>Optional</span></label>
            <textarea id="report-description" className="ct-field" rows={4} value={description} onChange={e => setDescription(e.target.value)} maxLength={2000} placeholder="Describe why this wallet seems suspicious." aria-describedby="description-help description-counter" />
            <p id="description-help" className="rp-help">Never include passwords, private keys, or recovery phrases.</p><p id="description-counter" className="rp-counter">{description.length.toLocaleString()} / 2,000 characters</p>
          </fieldset>
          {error && <div role="alert" className="ct-error-panel rp-error"><p>{error}</p><button type="button" className="ct-button-secondary" onClick={() => navigate('track')}>Check my reports</button></div>}
          <button type="submit" className="ct-button-primary rp-submit" disabled={submitting}>{submitting ? <><Loader2 className="rp-spinner" size={20} aria-hidden="true" />Submitting report…</> : <>Submit Report<ArrowRight size={20} aria-hidden="true" /></>}</button>
          <p className="rp-help rp-submit-note" role="status">{submitting ? 'Please keep this screen open while your report is sent.' : 'Submitting a report does not confirm fraud or guarantee recovery of funds.'}</p>
        </form>
      </section>}

      {view === 'success' && created && <section className="ct-card rp-success">
        <CheckCircle2 className="rp-success-icon" size={44} aria-hidden="true" /><p className="rp-eyebrow">Submission successful</p><h1 ref={heading} tabIndex={-1}>Your report is received.</h1><p>Keep your reference ID somewhere safe so you can find this report again.</p>
        {created.blockchain === 'demo' && <NetworkNotice capability={created.capability} demo />}
        <Reference value={created.reference_number} />
        <div className="rp-actions"><button type="button" className="ct-button-primary" onClick={() => { setReferenceQuery(created.reference_number); navigate('track'); }}>Track Report<ArrowRight size={20} aria-hidden="true" /></button><button type="button" className="ct-button-secondary" onClick={startReport}>Report another wallet</button></div>
      </section>}

      {view === 'track' && <section aria-labelledby="track-heading">
        <div className="rp-section-heading"><p className="rp-eyebrow">Your reports</p><h1 id="track-heading" ref={heading} tabIndex={-1}>Track my report</h1><p>Check the latest available status of reports submitted from your account.</p></div>
        <div className="rp-track-tools"><label htmlFor="reference-search">Find by reference ID</label><input id="reference-search" className="ct-field" type="search" value={referenceQuery} onChange={e => setReferenceQuery(e.target.value)} autoCapitalize="characters" spellCheck={false} placeholder="Enter your reference ID" /><button type="button" className="ct-button-secondary" disabled={loading} onClick={() => void loadSubmissions()}><RefreshCw size={18} aria-hidden="true" />Refresh status</button></div>
        {loadError ? <div role="alert" className="ct-error-panel rp-error"><h2>Reports are unavailable</h2><p>{loadError}</p><button type="button" className="ct-button-secondary" onClick={() => void loadSubmissions()}>Try again</button></div>
          : loading ? <div className="rp-state" role="status"><Loader2 className="rp-spinner" size={26} aria-hidden="true" /><h2>Checking your reports…</h2><p>This may take a moment.</p></div>
          : submissions.length === 0 ? <div className="ct-state-panel rp-state"><FileSearch size={32} aria-hidden="true" /><h2>No reports yet</h2><p>Your reports will appear here after you submit a wallet.</p><button type="button" className="ct-button-primary" onClick={startReport}>Report Suspicious Wallet</button></div>
          : matchingReports.length === 0 ? <div className="ct-state-panel rp-state" role="status"><FileSearch size={32} aria-hidden="true" /><h2>Report not found</h2><p>Check the reference ID and make sure you’re using the account that submitted the report.</p><button type="button" className="ct-button-secondary" onClick={() => setReferenceQuery('')}>Show all my reports</button></div>
          : <div className="rp-reports"><p className="rp-help" role="status">{matchingReports.length} {matchingReports.length === 1 ? 'report' : 'reports'}{referenceQuery.trim() ? ' matching this reference' : ' in your account'}</p>{matchingReports.map(report => <ReportCard key={report.id} report={report} />)}</div>}
      </section>}
    </div>
  </main>;
}
