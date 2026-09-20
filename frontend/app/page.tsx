'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, ArrowRight, FileSearch, Loader2, ShieldCheck } from 'lucide-react';
import api from '@/lib/api';

type EntryPath = 'investigator' | 'reporter';

// Existing repository seed accounts only; never production credentials.
const demoCredentials = {
  investigator: { username: 'investigator', password: 'investigate123' },
  reporter: { username: 'reporter', password: 'report123' },
};

function PathLogin({ path, demoAvailable }: { path: EntryPath; demoAvailable: boolean }) {
  const router = useRouter();
  const prefillDemoCredentials = demoAvailable;
  const [username, setUsername] = useState(prefillDemoCredentials ? demoCredentials[path].username : '');
  const [password, setPassword] = useState(prefillDemoCredentials ? demoCredentials[path].password : '');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const pending = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const reporter = path === 'reporter';

  async function handleLogin(event: React.FormEvent) {
    event.preventDefault();
    if (pending.current) return;
    pending.current = true;
    setLoading(true);
    setError('');
    try {
      const data = await api.login(username, password);
      // Keep navigation within the selected path. The existing API still authenticates
      // accounts and the backend remains authoritative for all permissions.
      const matchesPath = reporter ? data.user.role === 'reporter' : ['investigator', 'supervisor', 'admin'].includes(data.user.role);
      if (!mounted.current || !matchesPath) {
        api.clearToken();
        localStorage.removeItem('cryptotrace_user');
        if (mounted.current) setError(`This account cannot open the ${reporter ? 'reporter' : 'investigator'} path. Use the matching account or return to the entry screen.`);
        return;
      }
      localStorage.setItem('cryptotrace_user', JSON.stringify(data.user));
      router.push(reporter ? '/reporter' : '/dashboard');
    } catch {
      if (mounted.current) setError('Sign-in unsuccessful. Check your username, password, and connection, then try again.');
    } finally {
      pending.current = false;
      if (mounted.current) setLoading(false);
    }
  }

  return <section aria-labelledby="sign-in-heading" className="mx-auto w-full max-w-lg">
    <p className="ct-eyebrow mb-3">{reporter ? 'Reporter' : 'Investigator / staff'}</p>
    <h1 id="sign-in-heading" className="text-3xl font-bold tracking-tight">{reporter ? 'Reporter sign in' : 'Investigator sign in'}</h1>
    <p className="mt-3 leading-6 text-[var(--ct-ink-muted)]">{reporter ? 'Sign in to report a suspicious wallet and track your reports.' : 'Sign in with your authorized staff account to open the investigation workspace.'}</p>
    {demoAvailable && <div className="mt-6 rounded-lg border border-[#d9c3af] bg-[var(--ct-warning-surface)] p-4">
      <p className="text-sm font-bold text-[var(--risk-medium)]">DEMO {reporter ? 'REPORTER' : 'INVESTIGATOR'} ACCOUNT</p>
      <p className="mt-2 text-sm leading-6 text-[var(--ct-ink-muted)]">The existing demo credentials are prefilled. Demonstration data must not be treated as real wallet activity.</p>
    </div>}
    <form onSubmit={handleLogin} className="mt-7 space-y-5">
      <fieldset disabled={loading} className="space-y-5">
        <legend className="sr-only">{reporter ? 'Reporter' : 'Investigator'} credentials</legend>
        <div><label htmlFor="username" className="mb-2 block font-semibold">Username</label><input id="username" className="ct-field min-h-12 px-4 text-base" value={username} onChange={event => setUsername(event.target.value)} autoComplete="username" autoCapitalize="none" spellCheck={false} required /></div>
        <div><label htmlFor="password" className="mb-2 block font-semibold">Password</label><input id="password" className="ct-field min-h-12 px-4 text-base" type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="current-password" required /></div>
      </fieldset>
      {error && <p role="alert" className="ct-error-panel p-4 text-sm leading-6">{error}</p>}
      <button type="submit" disabled={loading} className="ct-button-primary flex min-h-14 w-full items-center justify-center gap-3 px-4 py-3 disabled:opacity-60">
        {loading ? <><Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" /><span role="status">Signing in…</span></> : <>{reporter ? 'Open reporter workspace' : 'Open investigator workspace'}<ArrowRight className="h-5 w-5" aria-hidden="true" /></>}
      </button>
    </form>
    {!loading && <a href="#" className="mt-5 inline-flex min-h-12 items-center gap-2 text-sm font-semibold text-[var(--ct-primary)]"><ArrowLeft className="h-4 w-4" aria-hidden="true" />Back to entry</a>}
  </section>;
}

export default function LoginPage() {
  const [path, setPath] = useState<EntryPath | null>(null);
  const [demoAvailability, setDemoAvailability] = useState<{ staff: boolean; reporter: boolean } | null>(null);
  useEffect(() => {
    function readPath() {
      const hash = window.location.hash;
      setPath(hash === '#reporter' ? 'reporter' : hash === '#investigator' ? 'investigator' : null);
    }
    readPath();
    window.addEventListener('hashchange', readPath);
    return () => window.removeEventListener('hashchange', readPath);
  }, []);
  useEffect(() => {
    api.capabilities()
      .then(data => setDemoAvailability({ staff: data.demo_login_available, reporter: data.reporter_demo_login_available }))
      .catch(() => setDemoAvailability({ staff: false, reporter: false }));
  }, []);

  return <main id="main-content" className="ct-page flex min-h-dvh items-center px-4 py-[max(24px,env(safe-area-inset-top),env(safe-area-inset-bottom))] sm:px-8">
    <div className="ct-card mx-auto w-full max-w-3xl p-6 sm:p-10">
      <div className="mb-9 flex items-center gap-3"><div className="ct-brand-mark h-11 w-11 rounded-lg"><FileSearch className="h-5 w-5" aria-hidden="true" /></div><div><p className="text-lg font-bold text-[var(--ct-primary)]">CryptoTrace AI</p><p className="text-sm text-[var(--ct-ink-muted)]">SIH26183</p></div></div>
      {!path ? <section aria-labelledby="entry-heading">
        <p className="ct-eyebrow mb-3">Choose your path</p><h1 id="entry-heading" className="text-3xl font-bold tracking-tight sm:text-4xl">Welcome to CryptoTrace AI</h1><p className="mt-3 leading-6 text-[var(--ct-ink-muted)]">Choose how you want to use CryptoTrace.</p>
        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          <a href="#investigator" className="ct-card ct-card-interactive flex flex-col items-start gap-4 p-6 text-[var(--ct-primary)]"><ShieldCheck className="h-7 w-7" aria-hidden="true" /><span className="text-lg font-bold">INVESTIGATOR</span><span className="text-sm leading-6 text-[var(--ct-ink-muted)]">Sign in to the investigator / staff workspace.</span><span className="mt-auto flex min-h-11 items-center gap-2 font-semibold">Investigator login<ArrowRight className="h-5 w-5" aria-hidden="true" /></span></a>
          <Link href="/reporter" className="ct-button-primary flex flex-col items-start gap-4 rounded-lg p-6"><FileSearch className="h-7 w-7" aria-hidden="true" /><span className="text-lg font-bold">REPORTER</span><span className="text-sm font-normal leading-6">Report a suspicious wallet and track your report.</span><span className="mt-auto flex min-h-11 items-center gap-2 font-semibold">Report Suspicious Wallet<ArrowRight className="h-5 w-5" aria-hidden="true" /></span></Link>
        </div>
      </section> : demoAvailability === null ? <p role="status" className="flex items-center gap-3 py-8"><Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />Preparing sign in…</p>
        : path === 'reporter' ? <PathLogin path="reporter" demoAvailable={demoAvailability.reporter} />
          : <PathLogin path="investigator" demoAvailable={demoAvailability.staff} />}
    </div>
  </main>;
}
