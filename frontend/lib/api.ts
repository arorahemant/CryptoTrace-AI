/**
 * CryptoTrace AI - API Client
 * Centralized API communication layer.
 * All API keys and secrets stay on the backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface ApiOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

class ApiClient {
  private token: string | null = null;

  setToken(token: string) {
    this.token = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('cryptotrace_token', token);
    }
  }

  getToken(): string | null {
    if (this.token) return this.token;
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('cryptotrace_token');
    }
    return this.token;
  }

  clearToken() {
    this.token = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('cryptotrace_token');
    }
  }

  private async request(endpoint: string, options: ApiOptions = {}) {
    const { method = 'GET', body, headers = {} } = options;

    const token = this.getToken();
    const requestHeaders: Record<string, string> = {
      'Content-Type': 'application/json',
      ...headers,
    };

    if (token) {
      requestHeaders['Authorization'] = `Bearer ${token}`;
    }

    const config: RequestInit = {
      method,
      headers: requestHeaders,
    };

    if (body && method !== 'GET') {
      config.body = JSON.stringify(body);
    }

    const response = await fetch(`${API_BASE}${endpoint}`, config);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || `API Error: ${response.status}`);
    }

    return response.json();
  }

  // ─── Auth ──────────────────────────────────────────────
  async login(username: string, password: string) {
    const data = await this.request('/auth/login', {
      method: 'POST',
      body: { username, password },
    });
    this.setToken(data.access_token);
    return data;
  }

  async register(data: { email: string; username: string; password: string; full_name: string }) {
    return this.request('/auth/register', { method: 'POST', body: data });
  }

  // ─── Cases ─────────────────────────────────────────────
  async createCase(data: {
    title: string;
    reported_wallet: string;
    blockchain?: string;
    description?: string;
    reported_amount?: number;
  }) {
    return this.request('/cases', { method: 'POST', body: data });
  }

  async listCases() {
    return this.request('/cases');
  }

  async getCase(caseId: string) {
    return this.request(`/cases/${caseId}`);
  }

  // ─── Investigation ────────────────────────────────────
  async investigate(caseId: string, options?: {
    max_hops?: number;
    min_amount?: number;
    direction?: string;
  }) {
    return this.request(`/cases/${caseId}/investigate`, {
      method: 'POST',
      body: options || {},
    });
  }

  async getGraph(caseId: string) {
    return this.request(`/cases/${caseId}/graph`);
  }

  async getWallets(caseId: string) {
    return this.request(`/cases/${caseId}/wallets`);
  }

  async getTransactions(caseId: string) {
    return this.request(`/cases/${caseId}/transactions`);
  }

  async getFindings(caseId: string) {
    return this.request(`/cases/${caseId}/findings`);
  }

  async getEvidence(caseId: string) {
    return this.request(`/cases/${caseId}/evidence`);
  }

  async saveEvidence(caseId: string, data: {
    evidence_type?: string;
    title: string;
    description: string;
    reason?: string;
    transaction_hash?: string;
    wallet_address?: string;
    finding_id?: string;
    source?: string;
  }) {
    return this.request(`/cases/${caseId}/evidence`, { method: 'POST', body: data });
  }

  async getTimeline(caseId: string) {
    return this.request(`/cases/${caseId}/timeline`);
  }

  async getFundFlow(caseId: string) {
    return this.request(`/cases/${caseId}/fund-flow`);
  }

  // ─── WHY? ─────────────────────────────────────────────
  async getWhyExplanation(caseId: string, walletAddress: string) {
    return this.request(`/cases/${caseId}/why/${walletAddress}`);
  }

  // ─── Replay ───────────────────────────────────────────
  async getReplay(caseId: string) {
    return this.request(`/cases/${caseId}/replay`, { method: 'POST' });
  }

  // ─── AI ───────────────────────────────────────────────
  async askAI(caseId: string, question: string) {
    return this.request(`/cases/${caseId}/ai/query`, {
      method: 'POST',
      body: { question },
    });
  }

  // ─── Report ───────────────────────────────────────────
  async generateReport(caseId: string) {
    return this.request(`/cases/${caseId}/report`, { method: 'POST' });
  }

  async getReport(caseId: string) {
    return this.request(`/cases/${caseId}/report`);
  }
}

export const api = new ApiClient();
export default api;
