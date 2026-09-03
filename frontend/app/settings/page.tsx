'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  CheckCircle2,
  Database,
  LockKeyhole,
  LogOut,
  Palette,
  Settings as SettingsIcon,
  Shield,
} from 'lucide-react';
import api from '@/lib/api';

interface UserProfile {
  full_name?: string;
  username?: string;
  role?: string;
}

export default function SettingsPage() {
  const router = useRouter();
  const [user] = useState<UserProfile | null>(() => {
    if (typeof window === 'undefined') return null;
    const stored = localStorage.getItem('cryptotrace_user');
    if (!stored) return null;
    try {
      return JSON.parse(stored) as UserProfile;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    if (!api.getToken()) {
      router.replace('/');
      return;
    }

  }, [router]);

  const handleLogout = () => {
    api.clearToken();
    localStorage.removeItem('cryptotrace_user');
    router.push('/');
  };

  return (
    <main className="ct-page">
      <header className="ct-topbar sticky top-0 z-50 flex min-h-16 items-center justify-between gap-3 px-4 py-2 sm:px-6">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={() => router.push('/dashboard')}
            aria-label="Back to case dashboard"
            className="ct-icon-button flex items-center justify-center"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="ct-brand-mark h-9 w-9 rounded-lg">
            <Shield className="w-4 h-4 text-white" />
          </div>
          <span className="truncate text-sm font-bold tracking-tight text-[var(--ct-ink)]">CryptoTrace AI</span>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          aria-label="Sign out"
          className="ct-icon-button flex items-center justify-center"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </header>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-10">
        <div className="mb-8">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-slate-500 font-medium mb-3">
            <span>Workspace</span>
            <span>›</span>
            <span className="text-blue-400">Settings</span>
          </div>
          <div className="flex items-start gap-3">
            <SettingsIcon className="mt-1 h-6 w-6 text-[var(--ct-primary)]" />
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-[var(--ct-ink)] sm:text-3xl">Account &amp; workspace</h1>
              <p className="mt-1 text-sm text-[var(--ct-ink-muted)]">Review your persisted account identity, access safeguards, and data provenance guidance.</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <section className="ct-card p-5">
            <div className="mb-5 flex items-center gap-2 border-b border-[var(--ct-outline-variant)] pb-3">
              <Shield className="h-4 w-4 text-[var(--ct-primary)]" />
              <h2 className="text-sm font-semibold text-[var(--ct-ink)]">Authenticated account</h2>
            </div>
            <dl className="space-y-4">
              <div>
                <dt className="text-[10px] uppercase tracking-widest text-slate-500">Full name</dt>
                <dd className="mt-1 text-sm text-[var(--ct-ink)]">{user?.full_name || 'Name unavailable'}</dd>
              </div>
              <div>
                <dt className="text-[10px] uppercase tracking-widest text-slate-500">Username</dt>
                <dd className="text-sm text-white font-mono mt-1">{user?.username || '—'}</dd>
              </div>
              <div>
                <dt className="text-[10px] uppercase tracking-widest text-slate-500">Role</dt>
                <dd className="mt-1 text-sm text-[var(--ct-ink)]">{user?.role ? user.role.replaceAll('_', ' ').toUpperCase() : 'Unavailable'}</dd>
              </div>
            </dl>
          </section>

          <section className="ct-card p-5">
            <div className="mb-5 flex items-center gap-2 border-b border-[var(--ct-outline-variant)] pb-3">
              <LockKeyhole className="w-4 h-4 text-green-400" />
              <h2 className="text-sm font-semibold text-[var(--ct-ink)]">Security &amp; access</h2>
            </div>
            <div className="space-y-3">
              {[
                'Authenticated session is active',
                'Case access is checked per request',
                'Provider credentials remain server-side',
              ].map((item) => (
                <div key={item} className="flex items-start gap-2 text-xs text-[var(--ct-ink-muted)]">
                  <CheckCircle2 className="w-4 h-4 text-green-400 shrink-0" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-slate-500 mt-5">Never share access tokens or investigation records outside the authorized case workflow.</p>
          </section>

          <section className="ct-card p-5">
            <div className="mb-5 flex items-center gap-2 border-b border-[var(--ct-outline-variant)] pb-3">
              <Database className="w-4 h-4 text-amber-400" />
              <h2 className="text-sm font-semibold text-[var(--ct-ink)]">Data &amp; environment</h2>
            </div>
            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-400">Synthetic case provenance</span>
                <span className="text-amber-400 font-medium">DEMO DATA</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-400">Analysis labels</span>
                <span className="text-blue-400 font-medium">FACT · ANALYSIS · INFERENCE</span>
              </div>
              <p className="text-[10px] text-slate-500 pt-2">Check each case badge before treating a result as observed blockchain data. Unknown attribution remains unknown.</p>
            </div>
          </section>

          <section className="ct-card p-5">
            <div className="mb-5 flex items-center gap-2 border-b border-[var(--ct-outline-variant)] pb-3">
              <Palette className="h-4 w-4 text-[var(--accent-purple)]" />
              <h2 className="text-sm font-semibold text-[var(--ct-ink)]">Visual language</h2>
            </div>
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm text-[var(--ct-ink)]">Institutional forensic theme</div>
                <div className="text-[10px] text-slate-500 mt-1">Warm neutral surfaces, graphite text, restrained semantic colors</div>
              </div>
              <span className="text-[10px] px-2 py-1 rounded border border-blue-500/20 bg-blue-500/10 text-blue-400">ACTIVE</span>
            </div>
          </section>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={() => router.push('/dashboard')}
            className="ct-button-secondary px-4 text-sm"
          >
            Return to cases
          </button>
        </div>
      </div>
    </main>
  );
}
