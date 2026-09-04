/**
 * CryptoTrace AI - API Client
 * Centralized API communication layer.
 * All API keys and secrets stay on the backend.
 */

const configuredApiBase = process.env.NEXT_PUBLIC_API_URL?.trim();
// Localhost is useful only for `next dev`. A production build must receive an
// explicit hosted HTTPS endpoint so an installed phone app never targets the
// phone itself by accident.
const API_BASE = configuredApiBase || (
  process.env.NODE_ENV === 'development' ? 'http://localhost:8000/api/v1' : ''
);

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

    if (!API_BASE) {
      throw new Error('API endpoint is not configured. Set NEXT_PUBLIC_API_URL before starting the production app.');
    }

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

  async registerReporter(data: { email: string; username: string; password: string; full_name: string }) {
    return this.request('/auth/reporter/register', { method: 'POST', body: data });
  }

  async updatePublicInvestigatorProfile(data: {
    display_name: string;
    role_title: string;
    is_reporter_visible: boolean;
  }) {
    return this.request('/auth/me/public-profile', { method: 'PUT', body: data });
  }

  async getPublicInvestigatorProfile() {
    return this.request('/auth/me/public-profile');
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

  // ─── Reporter intake and limited status ────────────────────
  async createReporterSubmission(data: {
    title: string;
    reported_wallet: string;
    blockchain: string;
    asset: string;
    description?: string;
  }) {
    return this.request('/reporter/submissions', { method: 'POST', body: data });
  }

  async listReporterSubmissions() {
    return this.request('/reporter/submissions');
  }

  async getReporterSubmission(submissionId: string) {
    return this.request(`/reporter/submissions/${submissionId}`);
  }

  async listReporterSubmissionsForReview() {
    return this.request('/reporter/submissions/review');
  }

  async getReporterSubmissionForReview(submissionId: string) {
    return this.request(`/reporter/submissions/${submissionId}/review`);
  }

  async acceptReporterSubmission(submissionId: string) {
    return this.request(`/reporter/submissions/${submissionId}/accept`, { method: 'POST' });
  }

  async assignReporterSubmission(submissionId: string) {
    return this.request(`/reporter/submissions/${submissionId}/assign`, { method: 'POST' });
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

  async getActionReadiness(caseId: string) {
    return this.request(`/cases/${caseId}/action-readiness`);
  }

  async listActionRequests(caseId: string) {
    return this.request(`/cases/${caseId}/action-requests`);
  }

  async createActionRequest(caseId: string, data: {
    target_wallet: string;
    action_type: 'freeze_request' | 'preservation_request';
    evidence_ids: string[];
    finding_ids?: string[];
  }) {
    return this.request(`/cases/${caseId}/action-requests`, { method: 'POST', body: data });
  }

  async getActionRequest(caseId: string, requestId: string) {
    return this.request(`/cases/${caseId}/action-requests/${requestId}`);
  }

  async prepareActionRequest(caseId: string, requestId: string) {
    return this.request(`/cases/${caseId}/action-requests/${requestId}/prepare`, { method: 'POST' });
  }

  async updateActionRequestStatus(caseId: string, requestId: string, status: string) {
    return this.request(`/cases/${caseId}/action-requests/${requestId}/status`, { method: 'PATCH', body: { status } });
  }

  async getRecommendations(caseId: string) {
    return this.request(`/cases/${caseId}/recommendations`);
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

  async getAuditLog(caseId: string, options?: { limit?: number; offset?: number }) {
    const params = new URLSearchParams();
    if (options?.limit != null) params.set('limit', String(options.limit));
    if (options?.offset != null) params.set('offset', String(options.offset));
    const query = params.toString();
    return this.request(`/cases/${caseId}/audit${query ? `?${query}` : ''}`);
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

  // ─── Public case validation ─────────────────────────────────────────────
  async listPublicCases() {
    return this.request('/public-cases');
  }

  async getPublicCaseComparison(caseId: string) {
    return this.request(`/public-cases/${encodeURIComponent(caseId)}/comparison`);
  }
}

export const api = new ApiClient();
export default api;
