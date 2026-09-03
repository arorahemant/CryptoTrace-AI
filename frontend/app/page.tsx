'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, CheckCircle2, FileSearch, Route, ShieldCheck } from 'lucide-react';
import api from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('investigator');
  const [password, setPassword] = useState('investigate123');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [demoRole, setDemoRole] = useState<'investigator' | 'reporter'>('investigator');

  const selectDemoRole = (role: 'investigator' | 'reporter') => {
    setDemoRole(role);
    setUsername(role);
    setPassword(role === 'investigator' ? 'investigate123' : 'report123');
    setError('');
  };

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      const data = await api.login(username, password);
      if (typeof window !== 'undefined') {
        localStorage.setItem('cryptotrace_user', JSON.stringify(data.user));
      }
      router.push(data.user.role === 'reporter' ? '/reporter' : '/dashboard');
    } catch {
      setError('Sign-in unsuccessful. Check your username and password, then try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="ct-page ct-login-page flex items-center px-4 py-6 sm:px-8 sm:py-10">
      <div className="mx-auto grid w-full max-w-6xl overflow-hidden rounded-xl border border-[var(--ct-outline-variant)] bg-white shadow-[var(--ct-shadow-md)] lg:grid-cols-[1.12fr_0.88fr]">
        <section className="flex flex-col justify-between bg-[var(--ct-surface-low)] p-6 sm:p-10 lg:p-12" aria-labelledby="product-heading">
          <div>
            <div className="mb-10 flex items-center gap-3">
              <div className="ct-brand-mark h-11 w-11 rounded-lg">
                <FileSearch className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <div className="text-base font-bold tracking-tight text-[var(--ct-ink)]">CryptoTrace AI</div>
                <div className="text-xs font-medium text-[var(--ct-ink-muted)]">SIH26183</div>
              </div>
            </div>

            <p className="ct-eyebrow mb-3">Blockchain fraud investigation platform</p>
            <h1 id="product-heading" className="max-w-xl text-3xl font-bold leading-tight tracking-[-0.025em] text-[var(--ct-ink)] sm:text-4xl">
              One reported wallet. A complete, evidence-linked money trail.
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-[var(--ct-ink-muted)]">
              Trace how funds moved, understand why activity was flagged, and preserve the transactions supporting each finding.
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3" aria-label="Platform capabilities">
              {[
                { icon: Route, label: 'Follow the money', detail: 'Map wallet-to-wallet movement.' },
                { icon: ShieldCheck, label: 'Explain findings', detail: 'Connect analysis to evidence.' },
                { icon: CheckCircle2, label: 'Keep case scope', detail: 'Work within authorized cases.' },
              ].map(({ icon: Icon, label, detail }) => (
                <div key={label} className="rounded-lg border border-[var(--ct-outline-variant)] bg-white/75 p-3.5">
                  <Icon className="mb-2 h-4 w-4 text-[var(--ct-primary)]" aria-hidden="true" />
                  <div className="text-sm font-semibold text-[var(--ct-ink)]">{label}</div>
                  <div className="mt-1 text-xs leading-5 text-[var(--ct-ink-muted)]">{detail}</div>
                </div>
              ))}
            </div>
          </div>

          <p className="mt-10 border-t border-[var(--ct-outline-variant)] pt-5 text-xs leading-5 text-[var(--ct-ink-muted)]">
            Analysis is derived from available blockchain records and deterministic case data. Conclusions remain subject to investigator review.
          </p>
        </section>

        <section className="flex items-center p-6 sm:p-10 lg:p-12" aria-labelledby="sign-in-heading">
          <div className="w-full">
            <p className="ct-eyebrow mb-2">Secure workspace</p>
            <h2 id="sign-in-heading" className="text-2xl font-bold tracking-tight text-[var(--ct-ink)]">Sign in to continue</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--ct-ink-muted)]">Use your authorized CryptoTrace account to open your case workspace.</p>

            <form onSubmit={handleLogin} className="mt-8 space-y-5">
              <div>
                <label htmlFor="username" className="mb-2 block text-sm font-semibold text-[var(--ct-ink)]">Username</label>
                <input id="username" type="text" value={username} onChange={(event) => setUsername(event.target.value)} className="ct-field px-4 text-sm" placeholder="Your username" autoComplete="username" required />
              </div>

              <div>
                <label htmlFor="password" className="mb-2 block text-sm font-semibold text-[var(--ct-ink)]">Password</label>
                <input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="ct-field px-4 text-sm" placeholder="Your password" autoComplete="current-password" required />
              </div>

              {error && <div role="alert" className="ct-error-panel px-4 py-3"><p className="text-sm">{error}</p></div>}

              <button type="submit" disabled={loading} className="ct-button-primary flex w-full items-center justify-center gap-2 px-4 py-2.5 text-sm disabled:cursor-not-allowed disabled:opacity-50">
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" aria-hidden="true"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                    Signing in…
                  </span>
                ) : <><span>Open workspace</span><ArrowRight className="h-4 w-4" aria-hidden="true" /></>}
              </button>
            </form>

            <div className="mt-7 rounded-lg border border-[#d9c3af] bg-[var(--ct-warning-surface)] p-4">
              <div className="flex items-start gap-3">
                <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-[var(--risk-medium)]" aria-hidden="true" />
                <div>
                  <div className="text-xs font-bold uppercase tracking-wide text-[var(--risk-medium)]">Demonstration workspace</div>
                  <p className="mt-1 text-xs leading-5 text-[var(--ct-ink-muted)]">Choose a role to preview its authorized workflow. Resulting data is demonstration data and must not be treated as a live-chain result.</p>
                  <div className="mt-3 grid grid-cols-2 gap-2" aria-label="Demo role">
                    {(['investigator', 'reporter'] as const).map((role) => (
                      <button
                        key={role}
                        type="button"
                        aria-pressed={demoRole === role}
                        onClick={() => selectDemoRole(role)}
                        className={`min-h-10 rounded-md border px-2 text-xs font-semibold capitalize ${demoRole === role ? 'border-[var(--ct-primary)] bg-white text-[var(--ct-primary)]' : 'border-[#d9c3af] bg-transparent text-[var(--ct-ink-muted)] hover:bg-white/70'}`}
                      >
                        {role} demo
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
