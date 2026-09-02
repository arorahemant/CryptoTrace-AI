'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('investigator');
  const [password, setPassword] = useState('investigate123');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const data = await api.login(username, password);
      if (typeof window !== 'undefined') {
        localStorage.setItem('cryptotrace_user', JSON.stringify(data.user));
      }
      router.push('/dashboard');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="ct-login-page min-h-screen flex items-center justify-center bg-[#0a0e17] relative overflow-hidden px-4 py-8 sm:px-8">
      {/* Background grid effect */}
      <div className="absolute inset-0 opacity-5">
        <div className="absolute inset-0" style={{
          backgroundImage: `
            linear-gradient(rgba(59,130,246,0.3) 1px, transparent 1px),
            linear-gradient(90deg, rgba(59,130,246,0.3) 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px',
        }} />
      </div>

      {/* Gradient orbs */}
      <div className="hidden" aria-hidden="true" />
      <div className="hidden" aria-hidden="true" />

      <div className="relative z-10 w-full max-w-md">
        {/* Logo / Brand */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded bg-[#124343] flex items-center justify-center">
              <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">CryptoTrace AI</h1>
            </div>
          </div>
          <p className="text-slate-400 text-sm font-medium tracking-wide uppercase">
            Blockchain Fraud Investigation Platform
          </p>
          <p className="text-slate-500 text-xs mt-1">One Wallet. Complete Investigation.</p>
        </div>

        {/* Login Card */}
        <div className="bg-[#111827] border border-[#1e293b] rounded p-6 sm:p-8 shadow-2xl shadow-black/40">
          <h2 className="text-lg font-semibold text-white mb-1">Investigator Login</h2>
          <p className="text-slate-500 text-sm mb-6">Enter your credentials to access the platform</p>

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label htmlFor="investigator-id" className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">Investigator ID</label>
              <input
                id="investigator-id"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-4 py-2.5 bg-[#0a0e17] border border-[#2a3548] rounded-lg text-slate-200 text-sm
                  focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30
                  placeholder:text-slate-600 transition-colors"
                placeholder="Enter username"
                autoComplete="username"
                required
              />
            </div>

            <div>
              <label htmlFor="authorization-key" className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">Authorization Key</label>
              <input
                id="authorization-key"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2.5 bg-[#0a0e17] border border-[#2a3548] rounded-lg text-slate-200 text-sm
                  focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30
                  placeholder:text-slate-600 transition-colors"
                placeholder="Enter password"
                autoComplete="current-password"
                required
              />
            </div>

            {error && (
              <div role="alert" className="px-4 py-2.5 bg-red-500/10 border border-red-500/20 rounded-lg">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full min-h-11 py-2.5 bg-gradient-to-r from-blue-600 to-cyan-600 text-white font-medium rounded
                hover:from-blue-500 hover:to-cyan-500 transition-all duration-200
                disabled:opacity-50 disabled:cursor-not-allowed
                shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Authenticating...
                </span>
              ) : (
                'Sign In'
              )}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-[#1e293b]">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span>Demo credentials pre-filled • SIH26183</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-6">
          <p className="text-slate-600 text-xs">
            SIH26183 • Blockchain & Cybersecurity
          </p>
        </div>
      </div>
    </main>
  );
}
