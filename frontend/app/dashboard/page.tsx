'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import {
  Search, Plus, Shield, Clock, CheckCircle,
  ChevronRight, Loader2, LogOut
} from 'lucide-react';

const statusColors: Record<string, string> = {
  new: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  investigating: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  review: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  completed: 'bg-green-500/10 text-green-400 border-green-500/20',
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

export default function DashboardPage() {
  const router = useRouter();
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
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
      setLoadError(err instanceof Error ? err.message : 'Unable to load cases.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const token = api.getToken();
    if (!token) {
      router.push('/');
      return;
    }
    void Promise.resolve().then(() => loadCases());
  }, [router, loadCases]);

  const handleLogout = () => {
    api.clearToken();
    localStorage.removeItem('cryptotrace_user');
    router.push('/');
  };

  return (
    <div className="min-h-screen bg-[#0a0e17]">
      {/* Top Bar */}
      <header className="min-h-14 border-b border-[#1e293b] bg-[#111827]/80 backdrop-blur-sm flex items-center px-4 sm:px-6 py-2 justify-between gap-3 sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
            <Shield className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-white text-sm tracking-tight">CryptoTrace AI</span>
          <span className="text-[10px] px-2 py-0.5 bg-cyan-500/10 text-cyan-400 rounded-full font-medium border border-cyan-500/20">
            {(user?.role || 'investigator').toUpperCase()}
          </span>
        </div>
        <div className="flex items-center gap-4">
          <span className="hidden sm:inline text-sm text-slate-400">{user?.full_name || 'Investigator'}</span>
          <button onClick={handleLogout} className="p-1.5 rounded-lg hover:bg-[#1e293b] transition-colors text-slate-400 hover:text-white">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {/* Dashboard Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white">Investigation Dashboard</h1>
            <p className="text-slate-400 text-sm mt-1">Manage and investigate fraud-linked cryptocurrency cases</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-blue-600 to-cyan-600 text-white
              rounded-lg font-medium text-sm hover:from-blue-500 hover:to-cyan-500 transition-all
              shadow-lg shadow-blue-500/20"
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
            <div key={stat.label} className="bg-[#111827] border border-[#1e293b] rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <stat.icon className={`w-5 h-5 text-${stat.color}-400`} />
              </div>
              <div className="text-2xl font-bold text-white">{stat.value}</div>
              <div className="text-xs text-slate-400 mt-1">{stat.label}</div>
            </div>
          ))}
        </div>

        {/* Cases List */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 text-blue-400 animate-spin" />
            <span className="ml-3 text-slate-400">Loading cases...</span>
          </div>
        ) : loadError ? (
          <div className="text-center py-20">
            <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto mb-4">
              <Shield className="w-8 h-8 text-red-400" />
            </div>
            <h3 className="text-white font-semibold mb-2">Unable to load cases</h3>
            <p className="text-red-300 text-sm mb-6">{loadError}</p>
            <button onClick={() => void loadCases()} className="px-6 py-2.5 bg-blue-600 text-white rounded-lg font-medium text-sm">
              Retry
            </button>
          </div>
        ) : cases.length === 0 ? (
          <div className="text-center py-20">
            <div className="w-16 h-16 rounded-2xl bg-[#111827] border border-[#1e293b] flex items-center justify-center mx-auto mb-4">
              <Shield className="w-8 h-8 text-slate-600" />
            </div>
            <h3 className="text-white font-semibold mb-2">No Cases Yet</h3>
            <p className="text-slate-400 text-sm mb-6">Create your first investigation case to get started</p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="px-6 py-2.5 bg-gradient-to-r from-blue-600 to-cyan-600 text-white rounded-lg font-medium text-sm"
            >
              Create First Case
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {cases.map((c) => (
              <div
                key={c.id}
                onClick={() => router.push(`/investigate/${c.id}`)}
                className="bg-[#111827] border border-[#1e293b] rounded-xl p-5 cursor-pointer
                  hover:border-blue-500/30 hover:bg-[#141c2b] transition-all duration-200 group"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-center gap-4 min-w-0">
                    <div className="w-10 h-10 rounded-lg bg-[#1e293b] flex items-center justify-center">
                      <Shield className="w-5 h-5 text-blue-400" />
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
                      <h3 className="text-white font-medium truncate">{c.title}</h3>
                      <p className="text-slate-500 text-xs mt-0.5 font-mono truncate">{c.reported_wallet}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4 pl-14 sm:pl-0">
                    <div className="text-left sm:text-right">
                      <div className="text-xs text-slate-500">
                        {new Date(c.created_at).toLocaleDateString()}
                      </div>
                      <div className="text-xs text-slate-600 mt-0.5">{c.blockchain}</div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-blue-400 transition-colors" />
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
            router.push(`/investigate/${c.id}`);
          }}
        />
      )}
    </div>
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
      setError(err instanceof Error ? err.message : 'Failed to create case');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-[#111827] border border-[#1e293b] rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto mx-0 sm:mx-4 p-5 sm:p-6 shadow-2xl animate-fade-in">
        <h2 className="text-lg font-bold text-white mb-1">Create New Case</h2>
        <p className="text-slate-500 text-sm mb-6">Enter the reported wallet address to begin investigation</p>

        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1">Case Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-4 py-2.5 bg-[#0a0e17] border border-[#2a3548] rounded-lg text-sm text-white
                focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1">
              Reported Wallet Address
              <span className="text-red-400 ml-1">*</span>
            </label>
            <input
              type="text"
              value={wallet}
              onChange={(e) => setWallet(e.target.value)}
              className="w-full px-4 py-2.5 bg-[#0a0e17] border border-[#2a3548] rounded-lg text-sm text-white font-mono
                focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30"
              placeholder="0x..."
              required
            />
            <p className="text-xs text-slate-600 mt-1">Use 0xReported001 for demo investigation</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-1">Blockchain</label>
              <select
                value={blockchain}
                onChange={(e) => setBlockchain(e.target.value)}
                className="w-full px-4 py-2.5 bg-[#0a0e17] border border-[#2a3548] rounded-lg text-sm text-white
                  focus:outline-none focus:border-blue-500"
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
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full px-4 py-2.5 bg-[#0a0e17] border border-[#2a3548] rounded-lg text-sm text-white
                  focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full px-4 py-2.5 bg-[#0a0e17] border border-[#2a3548] rounded-lg text-sm text-white
                focus:outline-none focus:border-blue-500 resize-none"
            />
          </div>

          {error && (
            <div className="px-4 py-2 bg-red-500/10 border border-red-500/20 rounded-lg">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 py-2.5 border border-[#2a3548] rounded-lg text-slate-400 text-sm hover:bg-[#1e293b] transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={loading}
              className="flex-1 py-2.5 bg-gradient-to-r from-blue-600 to-cyan-600 text-white rounded-lg text-sm font-medium
                disabled:opacity-50 shadow-lg shadow-blue-500/20">
              {loading ? 'Creating...' : 'Create Case'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
