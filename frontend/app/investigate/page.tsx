'use client';

import './workspace.css';

import { Fragment, Suspense, useCallback, useMemo, useState, useEffect, useRef, type ReactNode } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import api, { ApiError } from '@/lib/api';
import { displayAmount, type ExactTransfer, type AssetTotal, type DestinationCandidate } from '@/lib/transfers';
import { CoverageStrip } from '@/components/investigation/CoverageStrip';
import { TrailWorkspace } from '@/components/investigation/TrailWorkspace';
import { WalletInspector, TransferInspector } from '@/components/investigation/RecordInspector';
import { shortAddress, type TrailSelection } from '@/lib/investigation';
import { capabilityLabel, hasAnalysis, type CapabilityState } from '@/lib/capabilities';
import { ReplayBar } from '@/components/investigation/ReplayBar';
import { SafeMarkdown } from '@/components/investigation/SafeMarkdown';
import {
  Shield, Search, Play,
  AlertTriangle, Eye, FileText, MessageSquare, ChevronLeft,
  Loader2,
  Bookmark, ArrowRight, ClipboardList, Send, XCircle
} from 'lucide-react';
import { ReactFlowProvider } from 'reactflow';

// ─── Types// ─── Types ────────────────────────────────────────────────────
interface GraphNodeData {
  endpoint_kind?: string;
  expansion_state?: string;
  received_by_asset?: AssetTotal[];
  sent_by_asset?: AssetTotal[];
  id?: string;
  address: string;
  label?: ReactNode;
  is_reported?: boolean;
  is_intermediary?: boolean;
  is_destination?: boolean;
  is_suspicious?: boolean;
  hop_distance?: number;
  total_received?: number;
  total_sent?: number;
  transaction_count?: number;
  vasp_name?: string | null;
  vasp_attribution_type?: string | null;
  vasp_confidence?: string | null;
  vasp_source?: string | null;
  vasp_supporting_evidence?: string | null;
  vasp_attribution_status?: string | null;
  vasp_provenance?: string | null;
  vasp_source_reference?: string | null;
  vasp_reasoning?: string | null;
  vasp_supporting_evidence_ids?: string[];
  vasp_supporting_transaction_hashes?: string[];
  risk_category?: string | null;
  risk_score?: number | null;
  risk_signals?: Array<{ signal_name?: string; description?: string; score_contribution?: number }>;
}

interface GraphEdgeData extends ExactTransfer {
  id: string;
  source: string;
  target: string;
  hash?: string;
  amount?: number;
  asset?: string;
  timestamp?: string | null;
  is_suspicious?: boolean;
  hop_number?: number;
}

interface GraphResponse { run_id?: string; destination?: DestinationCandidate | null; nodes: GraphNodeData[]; edges: GraphEdgeData[]; primary_path: string[]; }
interface FindingData {
  id?: string;
  pattern_type?: string;
  pattern_name: string;
  description: string;
  severity: string;
  confidence: number;
  trigger?: string;
  affected_wallets?: string[];
  supporting_transaction_ids?: string[];
  created_at?: string;
}
interface EvidenceData { transfer_id?: string; id: string; evidence_type?: string; title: string; description: string; reason?: string; transaction_hash?: string; wallet_address?: string; finding_id?: string; source?: string; created_at?: string; is_bookmarked?: boolean; }
interface ActionReadiness { transfer?: ExactTransfer; destination?: DestinationCandidate | null; case_id: string; ready: boolean; destination_wallet?: string | null; asset?: string | null; observed_amount?: number | null; last_movement_at?: string | null; attribution_status: string; attribution_confidence: string; attribution_entity?: string | null; attribution_provenance?: string; attribution_source_reference?: string | null; attribution_reasoning?: string | null; attribution_evidence_ids?: string[]; attribution_transaction_hashes?: string[]; supporting_transaction_hash?: string | null; supporting_finding_id?: string | null; evidence_count: number; evidence_ids: string[]; finding_ids: string[]; checks: Array<{ key: string; label: string; complete: boolean }>; }
interface ActionRequest { id: string; case_id: string; actor_id: string; target_wallet: string; action_type: string; status: string; evidence_ids: string[]; finding_ids: string[]; observed_asset?: string | null; observed_amount?: number | null; last_movement_at?: string | null; attribution_status: string; attribution_confidence: string; attribution_entity?: string | null; attribution_provenance?: string; attribution_source_reference?: string | null; attribution_reasoning?: string | null; supporting_reason?: string | null; created_at: string; updated_at: string; }
interface Recommendation { recommendation_id: string; case_id: string; type: string; title: string; action: string; factual_reason: string; priority: 'high' | 'medium' | 'low'; evidence_ids: string[]; transaction_hashes: string[]; finding_ids: string[]; target_wallet?: string | null; deterministic_source: string; created_at: string; }
interface TransactionData extends ExactTransfer {
  id?: string;
  hash: string;
  from_address: string;
  to_address: string;
  amount: number;
  asset: string;
  timestamp?: string | null;
  source?: string | null;
  status?: string | null;
  is_suspicious?: boolean;
  hop_number?: number;
}
interface TimelineEvent extends ExactTransfer { id?: string; title: string; description?: string; timestamp?: string; transaction_hash?: string; sequence_order?: number; }
interface AuditEvent { id: string; action: string; resource_type?: string | null; resource_id?: string | null; details?: Record<string, unknown> | null; actor: string; timestamp?: string | null; }
interface ReplayEvent extends ExactTransfer {
  event_id?: string;
  step: number;
  event_type: string;
  title: string;
  description?: string;
  timestamp?: string | null;
  from_address?: string | null;
  to_address?: string | null;
  amount?: number | null;
  asset?: string | null;
  transaction_hash?: string | null;
  highlight_nodes?: string[];
  highlight_edges?: string[];
  cumulative_amount?: number | null;
}
interface CaseAssignment {
  investigator_id: string;
  display_name?: string | null;
  role?: string | null;
  assigned_at?: string | null;
  last_activity_at?: string | null;
  history_available: boolean;
}
interface CaseDetail { capability: CapabilityState; lifecycle: 'open' | 'closed'; permissions: string[]; id: string; case_number: string; title: string; status: string; is_demo: boolean; reported_wallet: string; blockchain?: string; asset?: string | null; source_submission_reference?: string | null; analysis_status?: string; analysis_message?: string; assignment?: CaseAssignment; summary?: { risk_level?: string; total_wallets?: number; total_transactions?: number }; }
interface WhyData { wallet_address: string; reasons: string[]; findings?: FindingData[]; }
interface ReportSection { title: string; section_type: string; content: string; }
interface InvestigationData {
  case_id: string;
  case_number: string;
  status: string;
  is_demo: boolean;
  stats: Record<string, number | string | null>;
  graph: GraphResponse;
  primary_path: string[];
  intermediaries: GraphNodeData[];
  findings: FindingData[];
  risk: { overall: string; by_wallet: Record<string, { score?: number; category?: string }> };
  vasp_attributions: Record<string, { entity_name?: string; confidence?: string }>;
  fund_flow_summary: { origin_outflow_by_asset?: AssetTotal[]; max_hops?: number; paths_count?: number };
}

// ─── Node Colors ──────────────────────────────────────────────
function getNodeColor(node: GraphNodeData): string {
  if (node.is_reported) return '#ba1a1a';
  if (node.is_destination) return '#58331f';
  if (node.is_suspicious) return '#734934';
  if (node.is_intermediary) return '#396666';
  return '#526168';
}

function getRiskBadge(category: string | null): { bg: string; text: string } {
  const map: Record<string, { bg: string; text: string }> = {
    critical: { bg: 'bg-red-500/20 border-red-500/40', text: 'text-red-400' },
    high: { bg: 'bg-red-500/10 border-red-500/30', text: 'text-red-400' },
    medium: { bg: 'bg-amber-500/10 border-amber-500/30', text: 'text-amber-400' },
    low: { bg: 'bg-green-500/10 border-green-500/30', text: 'text-green-400' },
  };
  return map[category || 'unassessed'] || { bg: 'bg-white border-slate-300', text: 'text-slate-500' };
}

function attributionLabel(status?: string | null): string {
  if (status === 'known_verified' || status === 'known') return 'KNOWN / VERIFIED';
  if (status === 'likely_inferred' || status === 'likely') return 'LIKELY / INFERRED';
  return 'UNKNOWN';
}

const severityRank: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 };

function getStrongestFinding(findings: FindingData[]): FindingData | null {
  return [...findings].sort((left, right) => {
    const severityDifference = (severityRank[right.severity] || 0) - (severityRank[left.severity] || 0);
    return severityDifference || right.confidence - left.confidence;
  })[0] || null;
}

// ─── Main Page// ─── Main Page ────────────────────────────────────────────────
export default function InvestigatePage() {
  return (
    <Suspense fallback={<main id="main-content" className="ct-page-shell flex min-h-screen items-center justify-center">Loading investigation…</main>}>
      <ReactFlowProvider>
        <CaseRoute />
      </ReactFlowProvider>
    </Suspense>
  );
}

function CaseRoute() {
  const params = useSearchParams();
  return <InvestigateContent key={params.get('caseId') || ''} />;
}

function InvestigateContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const caseId = searchParams.get('caseId')?.trim() || '';

  // State
  const [caseData, setCaseData] = useState<CaseDetail | null>(null);
  const [investigation, setInvestigation] = useState<InvestigationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [actionError, setActionError] = useState('');
  const [investigating, setInvestigating] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedNode, setSelectedNode] = useState<GraphNodeData | null>(null);
  const [selectedTransaction, setSelectedTransaction] = useState<TransactionData | null>(null);
  const [showMoneyTrail, setShowMoneyTrail] = useState(false);

  const [selection, setSelection] = useState<TrailSelection | null>(null);
  const [selectedFinding, setSelectedFinding] = useState<FindingData | null>(null);
  const [recordFilter, setRecordFilter] = useState('');
  const [focusVersion, setFocusVersion] = useState(0);
  const attemptVersion = useRef(0);

  // Graph
  const nodes = useMemo(() => (investigation?.graph.nodes || []).map(data => ({ id: data.id || data.address, data })), [investigation?.graph]);
  const graphNodeData = useRef<Record<string, GraphNodeData>>({});

  // Panels
  const [whyData, setWhyData] = useState<WhyData | null>(null);
  const [loadingWhy, setLoadingWhy] = useState(false);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [findings, setFindings] = useState<FindingData[]>([]);
  const [evidence, setEvidence] = useState<EvidenceData[]>([]);
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceData | null>(null);
  const [transactions, setTransactions] = useState<TransactionData[]>([]);
  const [savingEvidence, setSavingEvidence] = useState(false);
  const [evidenceMessage, setEvidenceMessage] = useState('');
  const [actionReadiness, setActionReadiness] = useState<ActionReadiness | null>(null);
  const [actionRequests, setActionRequests] = useState<ActionRequest[]>([]);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState('');
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);

  // Replay
  const [replayEvents, setReplayEvents] = useState<ReplayEvent[]>([]);
  const [replayStep, setReplayStep] = useState(-1);
  const [replaying, setReplaying] = useState(false);
  const replayTimer = useRef<NodeJS.Timeout | null>(null);

  // AI
  const [aiMessages, setAiMessages] = useState<Array<{ role: string; content: string }>>([]);
  const [aiInput, setAiInput] = useState('');
  const [aiLoading, setAiLoading] = useState(false);

  // Report
  const [report, setReport] = useState<{ title: string; sections: ReportSection[] } | null>(null);
  const [generatingReport, setGeneratingReport] = useState(false);

  async function loadExistingReport() {
    try {
      setReport(await api.getReport(caseId));
    } catch (err) {
      // A report is optional until the investigator generates one. Do not
      // turn the normal 404 into a page-level loading failure.
      if (!(err instanceof Error && err.message === 'No report generated yet')) {
        console.error('Failed to load existing report', err);
      }
    }
  }

  async function loadCase() {
    try {
      const data = await api.getCase(caseId);
      setCaseData(data);
      await loadAuditLog();

      // If already investigated, load data
      if (hasAnalysis(data.capability) || data.capability.result_state === 'empty') {
        await loadInvestigationData(data);
        await loadActionData();
        await loadExistingReport();
      }
    } catch (err) {
      console.error('Failed to load case', err);
      setLoadError(err instanceof Error ? err.message : 'Unable to load this case.');
    } finally {
      setLoading(false);
    }
  };

  async function loadAuditLog() {
    try {
      const data = await api.getAuditLog(caseId);
      setAuditEvents(data.events || []);
    } catch (err) {
      console.error('Failed to load audit log', err);
      setActionError(err instanceof Error ? err.message : 'Unable to load the audit log.');
    }
  }

  async function loadActionData() {
    try {
      const [readinessData, requestsData, recommendationData] = await Promise.all([
        api.getActionReadiness(caseId),
        api.listActionRequests(caseId),
        api.getRecommendations(caseId),
      ]);
      setActionReadiness(readinessData);
      setActionRequests(requestsData || []);
      setRecommendations(recommendationData.recommendations || []);
    } catch (err) {
      console.error('Failed to load asset action data', err);
      setActionMessage(err instanceof Error ? err.message : 'Unable to load action readiness.');
    }
  }

  async function loadInvestigationData(caseRecord?: CaseDetail, investigationResult?: InvestigationData) {
    try {
      const [graphData, findingsData, evidenceData, timelineData, txData] = await Promise.all([
        api.getGraph(caseId),
        api.getFindings(caseId),
        api.getEvidence(caseId),
        api.getTimeline(caseId),
        api.getTransactions(caseId),
      ]);

      setFindings(findingsData.findings || []);
      setEvidence(evidenceData.evidence || []);
      setTimeline(timelineData.events || []);
      setTransactions(txData.transactions || []);

      // A refreshed case page still needs an investigation state object. Keep
      // the graph and primary path sourced from the API rather than relying on
      // the in-memory result from the previous visit.
      const currentCase = caseRecord || caseData;
      const currentInvestigation = investigationResult || investigation;
      setInvestigation((previous) => ({
        case_id: currentInvestigation?.case_id || previous?.case_id || caseId,
        case_number: currentInvestigation?.case_number || previous?.case_number || currentCase?.case_number || '',
        status: currentInvestigation?.status || previous?.status || currentCase?.status || 'investigating',
        is_demo: currentInvestigation?.is_demo ?? previous?.is_demo ?? currentCase?.is_demo ?? false,
        stats: currentInvestigation?.stats || previous?.stats || {},
        graph: graphData,
        primary_path: currentInvestigation?.primary_path || graphData.primary_path || [],
        intermediaries: currentInvestigation?.intermediaries || previous?.intermediaries || [],
        findings: findingsData.findings || [],
        risk: currentInvestigation?.risk || previous?.risk || {
          overall: currentCase?.blockchain === 'ethereum' ? 'unassessed' : currentCase?.summary?.risk_level || 'low',
          by_wallet: {},
        },
        vasp_attributions: currentInvestigation?.vasp_attributions || previous?.vasp_attributions || {},
        fund_flow_summary: currentInvestigation?.fund_flow_summary || previous?.fund_flow_summary || {},
      }));

      if (graphData.nodes?.length) {
        buildGraphVisualization(graphData);
      }
    } catch (err) {
      console.error('Failed to load investigation data', err);
      setLoadError(err instanceof Error ? err.message : 'Unable to load investigation data.');
    }
  };

  // ─── Load Case ────────────────────────────────────────────
  useEffect(() => {
    if (!caseId) return;
    const storedUser = localStorage.getItem('cryptotrace_user');
    if (storedUser) {
      try {
        if ((JSON.parse(storedUser) as { role?: string }).role === 'reporter') {
          router.replace('/reporter');
          return;
        }
      } catch {
        // The authenticated API remains the authority if cached UI state is invalid.
      }
    }
    void Promise.resolve().then(() => loadCase());
    // loadCase intentionally runs only when the route case changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, router]);

  // ─── Run Investigation ────────────────────────────────────
  const [fromBlock, setFromBlock] = useState('');
  const [toBlock, setToBlock] = useState('');
  const runInvestigation = async () => {
    const ethereum = caseData?.blockchain === 'ethereum';
    if (ethereum && (!/^\d+$/.test(fromBlock) || !Number.isSafeInteger(Number(fromBlock)) ||
      (toBlock !== '' && (!/^\d+$/.test(toBlock) || !Number.isSafeInteger(Number(toBlock)) || Number(toBlock) < Number(fromBlock))))) {
      setActionError('Enter a valid historical start block and an optional end block at or after it.');
      return;
    }
    if (investigating) return;
    attemptVersion.current += 1;
    setInvestigating(true);
    setActionError('');
    if (ethereum) {
      setSelection(null); setSelectedFinding(null); setSelectedNode(null); setSelectedTransaction(null);
      setSelectedEvidence(null); setWhyData(null); setAiMessages([]); setAiLoading(false);
      setReplayEvents([]); setReplayStep(-1); setReplaying(false); setRecordFilter('');
      setActiveTab('overview'); setEvidenceMessage(''); setActionMessage('');
      graphNodeData.current = {};
      setTransactions([]); setFindings([]); setEvidence([]);
      setReport(null); setInvestigation(null); setTimeline([]);
      setActionReadiness(null); setActionRequests([]); setRecommendations([]);
    }
    try {
      const result = await api.investigate(caseId, ethereum ? { from_block: Number(fromBlock), ...(toBlock ? { to_block: Number(toBlock) } : {}), max_hops: 2, min_amount: 0 } : undefined);
      setInvestigation(result);
      setCaseData((prev) => prev ? { ...prev, status: result.status, capability: result.capability } : prev);

      if (result.capability?.processing_state === 'failed') {
        setActionError('Provider attempt failed. No previous result is being reused. See capability and coverage.');
        return;
      }
      // Build graph from result
      if (result.graph) {
        buildGraphVisualization(result.graph);
      }

      // Load additional data
      await loadInvestigationData(undefined, result);
      await loadAuditLog();
      await loadActionData();
      setActiveTab('overview');
    } catch (err) {
      if (err instanceof ApiError && err.capability) setCaseData(prev => prev ? { ...prev, capability: err.capability! } : prev);
      console.error('Investigation failed', err);
      setActionError(err instanceof Error ? err.message : 'Unable to complete the investigation.');
    } finally {
      setInvestigating(false);
    }
  };

  // ─── Build Graph Visualization ────────────────────────────
  function buildGraphVisualization(graphData: GraphResponse) {
    graphNodeData.current = Object.fromEntries(graphData.nodes.map(node => [node.address, node]));
  }

  // ─── WHY?  // ─── WHY? ─────────────────────────────────────────────────
  const loadWhy = async (address: string) => {
    const version = attemptVersion.current;
    setLoadingWhy(true);
    setActionError('');
    try {
      const data = await api.getWhyExplanation(caseId, address);
      if (version === attemptVersion.current) setWhyData(data);
    } catch (err) {
      console.error('Failed to load WHY', err);
      setActionError(err instanceof Error ? err.message : 'Unable to load the WHY explanation.');
    } finally {
      setLoadingWhy(false);
    }
  };

  // ─── Replay ───────────────────────────────────────────────
  const loadReplay = async (): Promise<ReplayEvent[]> => {
    if (replayEvents.length > 0) return replayEvents;
    const version = attemptVersion.current;
    const data = await api.getReplay(caseId);
    if (version !== attemptVersion.current) return [];
    const events = data.events || [];
    setReplayEvents(events);
    return events;
  };

  const startReplay = async () => {
    setActionError('');
    try {
      const events = await loadReplay();
      if (events.length === 0) return;
      setReplayStep((current) => current >= events.length - 1 ? 0 : Math.max(0, current));
      setReplaying(true);
    } catch (err) {
      console.error('Failed to load replay', err);
      setActionError(err instanceof Error ? err.message : 'Unable to load replay events.');
    }
  };

  const moveReplayStep = (delta: number) => {
    if (replayEvents.length === 0) return;
    setReplaying(false);
    setReplayStep((current) => {
      const start = current < 0 ? (delta < 0 ? replayEvents.length - 1 : 0) : current;
      return Math.min(replayEvents.length - 1, Math.max(0, start + (current < 0 ? 0 : delta)));
    });
  };

  useEffect(() => {
    if (replaying && replayStep >= 0 && replayStep < replayEvents.length) {
      replayTimer.current = setTimeout(() => {
        setReplayStep(prev => {
          if (prev >= replayEvents.length - 1) {
            setReplaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 1500);
    }
    return () => { if (replayTimer.current) clearTimeout(replayTimer.current); };
  }, [replaying, replayStep, replayEvents.length]);

  useEffect(() => {
    const event = replayStep >= 0 ? replayEvents[replayStep] : undefined;
    // Keep the right-side inspector    // Keep the right-side inspector and evidence context synchronized with the
    // event currently shown in the replay bar.
    if (event) {
      const transaction = event.transaction_hash
        ? transactions.find(item => event.transfer_id ? item.transfer_id === event.transfer_id : item.hash === event.transaction_hash) || null
        : null;
      const supportingEvidence = event.transaction_hash
        ? evidence.find(item => item.transaction_hash === event.transaction_hash) || null
        : null;
      const selectedReplayNode = event.highlight_nodes?.[0]
        ? graphNodeData.current[event.highlight_nodes[0]]
        : undefined;
      void Promise.resolve().then(() => {
        setSelectedTransaction(transaction);
        setSelection({ wallets: event.highlight_nodes || [], transfers: event.transfer_id ? [event.transfer_id] : event.highlight_edges || [], label: 'Replay event' });
        setSelectedEvidence(supportingEvidence);
        if (selectedReplayNode) setSelectedNode(selectedReplayNode);
      });
    }
  }, [replayStep, replayEvents, transactions, evidence]);

  // ─── AI Query ─────────────────────────────────────────────
  const askAI = async (question?: string) => {
    if (aiLoading || investigating || !caseData?.permissions.includes('case.write') || caseData.lifecycle === 'closed') return;
    const version = attemptVersion.current;
    const q = question || aiInput.trim();
    if (!q) return;

    setAiMessages(prev => [...prev, { role: 'user', content: q }]);
    setAiInput('');
    setAiLoading(true);

    try {
      const data = await api.askAI(caseId, q);
      if (version === attemptVersion.current) setAiMessages(prev => [...prev, { role: 'assistant', content: data.answer }]);
    } catch (err) {
      console.error('AI Copilot request failed', err);
      if (version === attemptVersion.current) setAiMessages(prev => [...prev, { role: 'assistant', content: 'AI Copilot is unavailable right now. Review the case evidence and try again.' }]);
    } finally {
      if (version === attemptVersion.current) setAiLoading(false);
    }
  };

  const saveTransactionEvidence = async (transaction: TransactionData) => {
    if (!transaction?.hash || savingEvidence || investigating) return;
    const version = attemptVersion.current;
    setSavingEvidence(true);
    setEvidenceMessage('');
    try {
      const saved = await api.saveEvidence(caseId, {
        evidence_type: 'transaction',
        title: `Transaction ${transaction.hash.slice(0, 14)}…`,
        description: `Observed ${displayAmount(transaction)} ${transaction.asset || ''} movement from ${transaction.from_address} to ${transaction.to_address}.`,
        reason: 'Selected by investigator as supporting evidence for the traced money trail.',
        transaction_hash: transaction.hash,
        transfer_id: transaction.transfer_id,
        wallet_address: transaction.to_address,
        source: 'investigator',
      });
      if (version !== attemptVersion.current) return;
      const refreshed = await api.getEvidence(caseId);
      if (version !== attemptVersion.current) return;
      setEvidence(refreshed.evidence || []);
      setSelectedEvidence(saved);
      setEvidenceMessage('Evidence saved to this case.');
    } catch (err) {
      setEvidenceMessage(err instanceof Error ? err.message : 'Unable to save evidence.');
    } finally {
      setSavingEvidence(false);
    }
  };

  const createActionRequest = async (actionType: 'freeze_request' | 'preservation_request') => {
    if (!actionReadiness?.destination_wallet || actionReadiness.evidence_ids.length === 0 || actionLoading) return;
    setActionLoading(true);
    setActionMessage('');
    try {
      await api.createActionRequest(caseId, {
        target_wallet: actionReadiness.destination_wallet,
        action_type: actionType,
        evidence_ids: actionReadiness.evidence_ids,
        finding_ids: actionReadiness.finding_ids,
      });
      await loadActionData();
      await loadAuditLog();
      setActionMessage('Request created as DRAFT from existing case evidence.');
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : 'Unable to create the request.');
    } finally {
      setActionLoading(false);
    }
  };

  const updateActionRequest = async (requestId: string, nextStatus: string, prepare = false) => {
    if (actionLoading) return;
    setActionLoading(true);
    setActionMessage('');
    try {
      if (prepare) await api.prepareActionRequest(caseId, requestId);
      else await api.updateActionRequestStatus(caseId, requestId, nextStatus);
      await loadActionData();
      await loadAuditLog();
      setActionMessage('Operational status recorded in CryptoTrace. External action is not independently verified.');
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : 'Unable to update request status.');
    } finally {
      setActionLoading(false);
    }
  };

  const selectEvidence = (item: EvidenceData) => {
    setSelectedEvidence(item);
    const matches = transactions.filter(candidate => item.transfer_id ? candidate.transfer_id === item.transfer_id : candidate.hash === item.transaction_hash);
    if (matches.length === 1) {
      const transaction = matches[0];
      setSelectedTransaction(transaction); setSelectedNode(null);
      setSelection({ wallets: [transaction.from_address, transaction.to_address], transfers: [transaction.transfer_id || transaction.id || ''], label: 'Evidence transfer' });
    } else if (item.wallet_address) {
      setSelection({ wallets: [item.wallet_address], transfers: [], label: 'Evidence wallet' });
    }
  };

  // ─── Report  // ─── Report ───────────────────────────────────────────────
  const generateReport = async () => {
    if (investigating) return;
    const version = attemptVersion.current;
    setGeneratingReport(true);
    setActionError('');
    try {
      const data = await api.generateReport(caseId);
      if (version !== attemptVersion.current) return;
      setReport(data);
      setActiveTab('report');
    } catch (err) {
      console.error('Failed to generate report', err);
      setActionError(err instanceof Error ? err.message : 'Unable to generate the report.');
    } finally {
      setGeneratingReport(false);
    }
  };

  // ─── Node Click ───────────────────────────────────────────
  const selectTransfer = useCallback((id: string) => {
    const transaction = transactions.find(item => item.transfer_id === id || item.id === id);
    if (!transaction) { setActionError('This transfer record is unavailable in the current run.'); return; }
    setSelectedTransaction(transaction); setSelectedNode(null); setSelectedFinding(null);
    setSelection({ wallets: [transaction.from_address, transaction.to_address], transfers: [transaction.transfer_id || id], label: 'Selected transfer' });
    setActiveTab('transactions');
  }, [transactions]);

  const selectWallet = useCallback((address: string) => {
    const wallet = graphNodeData.current[address];
    if (!wallet) return;
    setSelectedNode(wallet); setSelectedTransaction(null); setSelectedFinding(null); setWhyData(null);
    setSelection({ wallets: [address], transfers: [], label: 'Selected wallet' });
    setActiveTab('overview');
  }, []);

  const selectFinding = (finding: FindingData) => {
    setSelectedFinding(finding); setSelectedNode(null); setSelectedTransaction(null);
    setSelection({ wallets: finding.affected_wallets || [], transfers: transactions.filter(t => finding.supporting_transaction_ids?.includes(t.hash)).map(t => t.transfer_id || t.id || ''), label: finding.pattern_name });
    setActiveTab('findings');
  };

  const selectTransactionByHash = (hash: string) => {
    const matches = transactions.filter(item => item.hash === hash);
    if (matches.length > 1) {
      setActiveTab('transactions');
      setActionError('This transaction contains multiple transfer events. Select the required event from the transaction list.');
      return;
    }
    const transaction = matches[0];
    if (!transaction) {
      setActionError('The supporting transaction is not available in this case.');
      return;
    }
    selectTransfer(transaction.transfer_id || transaction.id || '');
  };

  const selectWalletByAddress = (address: string) => selectWallet(address);

  const jumpToReplayEvent = async (timelineEvent: TimelineEvent) => {
    setActionError('');
    try {
      const events = await loadReplay();
      const index = events.findIndex(event =>
        (timelineEvent.id && event.event_id === timelineEvent.id)
        || (timelineEvent.transfer_id ? event.transfer_id === timelineEvent.transfer_id : timelineEvent.transaction_hash && event.transaction_hash === timelineEvent.transaction_hash)
        || (!timelineEvent.transaction_hash && timelineEvent.timestamp && event.timestamp === timelineEvent.timestamp),
      );
      if (index >= 0) {
        setReplayStep(index);
        setReplaying(false);
      }
    } catch (err) {
      console.error('Failed to jump to replay event', err);
      setActionError(err instanceof Error ? err.message : 'Unable to open this replay event.');
    }
  };

  if (!caseId) {
    return (
      <div className="min-h-screen bg-[var(--ct-surface)] flex items-center justify-center px-6">
        <div className="max-w-md text-center">
          <Shield className="w-10 h-10 text-red-400 mx-auto mb-4" />
          <h1 className="text-lg font-semibold text-white mb-2">Case unavailable</h1>
          <p className="text-sm text-red-300 mb-6">No case was selected. Return to the dashboard and choose a case.</p>
          <button onClick={() => router.push('/dashboard')} className="px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium">
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--ct-surface)] flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
      </div>
    );
  }

  if (loadError || !caseData) {
    return (
      <div className="min-h-screen bg-[var(--ct-surface)] flex items-center justify-center px-6">
        <div className="max-w-md text-center">
          <Shield className="w-10 h-10 text-red-400 mx-auto mb-4" />
          <h1 className="text-lg font-semibold text-white mb-2">Case unavailable</h1>
          <p className="text-sm text-red-300 mb-6">{loadError || 'This case could not be loaded.'}</p>
          <button onClick={() => router.push('/dashboard')} className="px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium">
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const hasInvestigation = hasAnalysis(caseData?.capability) && nodes.length > 0;
  const canMutate = !!caseData?.permissions?.includes('case.write') && caseData.lifecycle !== 'closed';
  const riskBadge = getRiskBadge(investigation?.risk?.overall || caseData?.summary?.risk_level || 'low');
  const analysisAvailable = caseData?.capability?.can_investigate ?? caseData?.capability?.provider_state === 'available';
  const traceHopCount = transactions.reduce((maxHop, transaction) => Math.max(maxHop, transaction.hop_number ?? 0), 0);
  const suspiciousTransactionCount = transactions.filter((transaction) => transaction.is_suspicious).length;
  const linkedEvidenceCount = evidence.filter((item) => item.transaction_hash || item.finding_id).length;
  const riskCategory = (investigation?.risk?.overall || caseData?.summary?.risk_level || 'PENDING').toUpperCase();
  const strongestFinding = getStrongestFinding(findings);
  const primaryPath = investigation?.primary_path || investigation?.graph?.primary_path || [];
  const destinationNode = nodes.find((node) => node.id === investigation?.graph?.destination?.address)?.data;
  return (
    <main id="main-content" className="ct-investigation-shell flex h-screen flex-col overflow-hidden bg-[var(--ct-surface)]">
      <h1 className="sr-only">Investigation for case {caseData.case_number}</h1>
      {/* ─── Top Bar ────────────────────────────────────────── */}
      <header className="ct-investigation-header h-12 border-b border-[var(--ct-outline-variant)] bg-white/96 backdrop-blur-sm flex items-center px-4 justify-between shrink-0">
        <div className="flex items-center gap-3">
          <button type="button" onClick={() => router.push('/dashboard')} aria-label="Back to case dashboard" className="ct-icon-button flex items-center justify-center">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <div className="ct-brand-mark h-7 w-7 rounded-md">
            <Shield className="w-3.5 h-3.5 text-white" />
          </div>
          <span className="ct-investigation-header-brand text-sm font-bold text-white">CryptoTrace AI</span>
          <span className="ct-investigation-header-separator text-slate-600">|</span>
          <span className="ct-mobile-case-label hidden text-[10px] font-bold uppercase tracking-wide text-[var(--ct-outline)]">Case</span>
          <span className="font-mono text-xs text-slate-400">{caseData?.case_number}</span>
          <span className="hidden max-w-48 truncate text-xs text-slate-400 md:inline" title={caseData.title}>{caseData.title}</span>
          <span className={`ct-investigation-header-risk text-[10px] px-2 py-0.5 rounded-full font-medium border ${riskBadge.bg} ${riskBadge.text}`}>
            {(investigation?.risk?.overall || caseData?.summary?.risk_level || 'PENDING').toUpperCase()} RISK
          </span>
          {caseData?.is_demo && (
            <span className="ct-investigation-header-demo text-[10px] px-2 py-0.5 bg-amber-500/10 text-amber-400 rounded-full border border-amber-500/20">
              DEMO DATA
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!hasInvestigation ? (
            <button
              onClick={runInvestigation}
              disabled={!canMutate || investigating || !analysisAvailable}
              className="ct-button-primary flex items-center gap-1.5 px-4 py-1.5 text-xs disabled:opacity-50"
            >
              {investigating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />}
              {investigating ? 'Investigating…' : 'Run investigation'}
            </button>
          ) : <span className="hidden text-[10px] font-medium text-[var(--ct-ink-muted)] sm:inline">Evidence-linked workspace</span>}
        </div>
      </header>

      {actionError && (
        <div role="alert" className="flex items-center justify-between gap-3 border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-200 shrink-0">
          <span>{actionError}</span>
          <button onClick={() => setActionError('')} aria-label="Dismiss error" className="text-red-300 hover:text-white">
            <XCircle className="w-4 h-4" />
          </button>
        </div>
      )}

      <div className="investigation-context">
        <CoverageStrip capability={caseData.capability} />
        <section className="case-brief" aria-label="Case summary">
          <div><span>Case status</span><strong>{caseData.lifecycle === 'closed' ? 'Closed' : caseData.status.replaceAll('_', ' ')}</strong><small>{!canMutate ? 'Read-only' : 'Investigator workspace'}</small></div>
          <div><span>Network / risk</span><strong>{caseData.blockchain === 'ethereum' ? 'Ethereum Mainnet' : caseData.blockchain === 'demo' ? 'Demo Network' : caseData.blockchain}</strong><small>{riskCategory} RISK</small></div>
          <button onClick={() => selectWallet(caseData.reported_wallet)} disabled={!hasInvestigation}><span>Reported wallet</span><strong className="font-mono" title={caseData.reported_wallet}>{shortAddress(caseData.reported_wallet)}</strong><small>Investigation origin</small></button>
          <button onClick={() => investigation?.graph.destination && selectWallet(investigation.graph.destination.address)} disabled={!investigation?.graph.destination}><span>Destination candidate</span><strong className="font-mono" title={investigation?.graph.destination?.address}>{investigation?.graph.destination ? shortAddress(investigation.graph.destination.address) : 'Not established'}</strong><small>{destinationNode?.vasp_name ? `${destinationNode.vasp_name} · ${attributionLabel(destinationNode.vasp_attribution_status)}` : 'Attribution unknown'}</small></button>
          <button onClick={() => setActiveTab('findings')}><span>Key findings</span><strong>{findings.length}</strong><small>{caseData.blockchain === 'ethereum' ? 'Risk interpretation unavailable' : strongestFinding?.pattern_name || 'None recorded'}</small></button>
          <button onClick={() => setActiveTab('recommendations')}><span>Next action</span><strong>{recommendations.length ? 'Review recommendation' : 'Review coverage'}</strong><small>{recommendations[0]?.title || 'Check observation boundaries'}</small></button>
        </section>
        <details className="observation-controls">
          <summary>{caseData.blockchain === 'ethereum' ? 'Observation interval & case controls' : 'Case controls'}</summary>
          {caseData.blockchain === 'ethereum' && <div className="observation-form">
            <label>Historical start block<input aria-label="Historical start block" inputMode="numeric" value={fromBlock} onChange={e => setFromBlock(e.target.value)} placeholder="Required" /></label>
            <label>End block<input aria-label="Historical end block" inputMode="numeric" value={toBlock} onChange={e => setToBlock(e.target.value)} placeholder="Latest finalized" /></label>
            <button onClick={runInvestigation} disabled={!canMutate || investigating || !analysisAvailable}>{investigating ? 'Observing…' : 'Run Ethereum observation'}</button>
            <small>Up to 2 hops / 100 transfers. External ETH and standard ERC-20. A new attempt replaces this run.</small>
          </div>}
          {canMutate && <button className="case-close" onClick={async () => {
            if (!window.confirm('Close this case? Processing results do not establish recovery or external action.')) return;
            try { await api.closeCase(caseId); await loadCase(); } catch (err) { setActionError(err instanceof Error ? err.message : 'Unable to close case'); }
          }}>Close case</button>}
        </details>
      </div>

      {/* ─── Main Content      {/* ─── Main Content ──────────────────────────────────── */}
      <div className="ct-investigation-main flex flex-1 overflow-hidden">
        {/* ─── Left Panel ──────────────────────────────────── */}
        <div className="ct-investigation-nav w-56 border-r border-[var(--ct-outline-variant)] bg-white flex flex-col shrink-0 overflow-y-auto">
          <nav className="hidden p-3 md:block" aria-label="Case workspace">
            <div className="mb-1.5 text-[9px] font-semibold uppercase tracking-widest text-slate-500">Workspace</div>
            <button type="button" onClick={() => router.push('/dashboard')} className="mb-0.5 flex min-h-10 w-full items-center gap-2 rounded px-3 py-2 text-xs text-[var(--ct-ink-muted)] hover:bg-[var(--ct-surface-high)]"><ChevronLeft className="h-3.5 w-3.5" /><span>Dashboard / cases</span></button>
            {[
              { id: 'overview', icon: Eye, label: 'Investigation' },
              { id: 'recommendations', icon: ClipboardList, label: 'Next actions', count: recommendations.length },
              { id: 'action', icon: Shield, label: 'Action readiness', count: actionRequests.length },
              { id: 'evidence', icon: Bookmark, label: 'Evidence', count: evidence.length },
              { id: 'report', icon: FileText, label: 'Reports' },
              { id: 'ai', icon: MessageSquare, label: 'Copilot' },
            ].map((tab) => (
              <button key={tab.id} type="button" onClick={() => setActiveTab(tab.id)} aria-pressed={activeTab === tab.id} className={`mb-0.5 flex min-h-10 w-full items-center gap-2 rounded px-3 py-2 text-xs ${activeTab === tab.id ? 'border border-[#8aa9a9] bg-[var(--ct-primary-container)] text-[var(--ct-primary)]' : 'text-[var(--ct-ink-muted)] hover:bg-[var(--ct-surface-high)] hover:text-[var(--ct-ink)]'}`}><tab.icon className="h-3.5 w-3.5" /><span className="flex-1 text-left">{tab.label}</span>{'count' in tab && tab.count != null && tab.count > 0 && <span className="rounded-full bg-[var(--ct-surface-high)] px-1.5 py-0.5 text-[10px]">{tab.count}</span>}</button>
            ))}
            <details className="mt-1 border-t border-[var(--ct-outline-variant)] pt-2">
              <summary className="flex min-h-10 cursor-pointer items-center rounded px-3 py-2 text-xs font-semibold text-[var(--ct-ink-muted)] hover:bg-[var(--ct-surface-high)]">More tools</summary>
              <div className="mt-1 space-y-0.5 pl-2">
                {[{ id: 'findings', label: 'All findings' }, { id: 'wallets', label: 'Wallets' }, { id: 'transactions', label: 'Transactions' }, { id: 'timeline', label: 'Replay' }, { id: 'audit', label: 'Audit' }].map((tab) => <button key={tab.id} type="button" onClick={() => setActiveTab(tab.id)} className="flex min-h-10 w-full items-center rounded px-3 text-left text-[11px] text-[var(--ct-ink-muted)] hover:bg-[var(--ct-surface-high)]">{tab.label}</button>)}
                <button type="button" onClick={() => router.push('/settings')} className="flex min-h-10 w-full items-center rounded px-3 text-left text-[11px] text-[var(--ct-ink-muted)] hover:bg-[var(--ct-surface-high)]">Settings</button>
              </div>
            </details>
          </nav>

          <div className="ct-mobile-investigation-nav p-2 md:hidden" aria-label="Investigation tools">
            <div className="grid grid-cols-4 gap-1">
              <button type="button" onClick={() => router.push('/dashboard')} className="flex min-h-12 flex-col items-center justify-center gap-1 rounded px-1 text-[9px] font-semibold text-[var(--ct-ink-muted)]"><ChevronLeft className="h-4 w-4" /><span>Home</span></button>
              {[
                { id: 'overview', label: 'Investigation', icon: Eye },
                { id: 'action', label: 'Readiness', icon: Shield },
                { id: 'evidence', label: 'Evidence', icon: Bookmark },
              ].map((tab) => (
                <button key={tab.id} type="button" onClick={() => setActiveTab(tab.id)} aria-pressed={activeTab === tab.id} className={`flex min-h-12 flex-col items-center justify-center gap-1 rounded px-1 text-[9px] font-semibold ${activeTab === tab.id ? 'bg-[var(--ct-primary-container)] text-[var(--ct-primary)]' : 'text-[var(--ct-ink-muted)]'}`}>
                  <tab.icon className="h-4 w-4" /><span>{tab.label}</span>
                </button>
              ))}
              <label className="flex min-h-12 flex-col items-center justify-center gap-1 rounded px-1 text-[9px] font-semibold text-[var(--ct-ink-muted)]"><span>More</span><select value={['recommendations', 'findings', 'wallets', 'transactions', 'timeline', 'ai', 'report', 'audit'].includes(activeTab) ? activeTab : ''} onChange={(event) => event.target.value && setActiveTab(event.target.value)} aria-label="Open more investigation tools" className="w-full bg-transparent text-center text-[9px] outline-none"><option value="">Tools</option><option value="recommendations">Next actions</option><option value="findings">Findings / WHY</option><option value="wallets">Wallets</option><option value="transactions">Transactions</option><option value="timeline">Replay</option><option value="ai">Copilot</option><option value="report">Report</option><option value="audit">Audit</option></select></label>
            </div>
          </div>
        </div>

        {/* ─── Center: Graph ───────────────────────────────── */}
        <div className="ct-investigation-graph flex-1 flex flex-col relative">
          {!hasInvestigation ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <div className="w-20 h-20 rounded-2xl bg-[var(--ct-surface-high)] border border-[var(--ct-outline-variant)] flex items-center justify-center mx-auto mb-4">
                  <Search className="w-10 h-10 text-slate-600" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">{investigating ? 'Observing the selected interval' : caseData.capability.processing_state === 'failed' ? 'Observation attempt failed' : caseData.capability.result_state === 'empty' ? 'No records observed' : 'Ready to investigate'}</h3>
                <p className="text-slate-400 text-sm mb-1">Wallet: <span className="font-mono text-blue-400">{caseData?.reported_wallet}</span></p>
                <p className="text-slate-500 text-xs mb-6">{caseData.blockchain === 'demo' ? 'Run demonstration analysis on synthetic transactions.' : caseData.capability.result_state === 'empty' ? 'No matching records in this interval. This does not mean no wallet activity.' : 'Choose a historical interval in Observation controls above.'}</p>
                <button
                  onClick={runInvestigation}
                  disabled={!canMutate || investigating || !analysisAvailable}
                  className="ct-button-primary px-8 py-3 text-sm disabled:opacity-50"
                >
                  {investigating ? (
                    <span className="flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Running investigation…</span>
                  ) : (
                    <span className="flex items-center gap-2"><Search className="w-4 h-4" /> Run investigation</span>
                  )}
                </button>
              </div>
            </div>
          ) : (
            <TrailWorkspace key={caseData.capability.run_id || caseId} graph={investigation!.graph} selection={selection} onWallet={selectWallet} onTransfer={selectTransfer} focusVersion={focusVersion} isolateRequested={showMoneyTrail} />
          )}

          {/* ─── Replay Bar ──────────────────────────────── */}
          {replayEvents.length > 0 && replayStep >= 0 && (
            <ReplayBar
              events={replayEvents}
              step={replayStep}
              playing={replaying}
              onStepBackward={() => moveReplayStep(-1)}
              onTogglePlaying={() => setReplaying((current) => !current)}
              onStepForward={() => moveReplayStep(1)}
              onJumpToStep={(step) => { setReplayStep(step); setReplaying(false); }}
            />
          )}
        </div>

        {/* ─── Right Panel ─────────────────────────────────── */}
        <div aria-label="Investigation inspector" className="ct-investigation-inspector w-80 border-l border-[var(--ct-outline-variant)] bg-white overflow-y-auto shrink-0">
          <div className="inspector-location"><strong>{activeTab === 'ai' ? 'Investigation Copilot' : activeTab === 'overview' ? 'Case / selected wallet' : activeTab.replaceAll('_', ' ')}</strong><span title={caseData.capability.run_id || undefined}>Run {caseData.capability.run_id?.slice(0, 8) || 'not started'}</span></div>
          {recordFilter && ['transactions', 'evidence'].includes(activeTab) && <div className="trail-notice">Wallet: {shortAddress(recordFilter)} <button onClick={() => setRecordFilter('')}>Clear filter</button></div>}
          {replayStep >= 0 && replayEvents[replayStep] && (
            <div className="p-3 border-b border-cyan-500/20 bg-cyan-500/5">
              <div className="text-[10px] uppercase tracking-widest text-cyan-400 font-medium mb-1">Replay context</div>
              <div className="text-xs text-white font-medium truncate">{replayEvents[replayStep].title}</div>
              <div className="text-[10px] text-slate-500 mt-1">{replayEvents[replayStep].timestamp ? new Date(replayEvents[replayStep].timestamp).toLocaleString() : 'Timestamp unavailable'}</div>
              {selectedTransaction && <div className="text-[10px] text-blue-300 font-mono truncate mt-1">TX {selectedTransaction.hash}</div>}
              {selectedEvidence && <div className="text-[10px] text-amber-300 truncate mt-1">Evidence: {selectedEvidence.title}</div>}
            </div>
          )}
          {activeTab === 'overview' && hasInvestigation && !selectedNode && (
            <div className="space-y-3 p-4 animate-fade-in">
              <div className="flex items-start justify-between gap-3">
                <div><h3 className="text-sm font-bold text-white">Investigation summary</h3><p className="mt-0.5 text-[10px] text-slate-500">Decision-ready case context</p></div>
                <span className={`rounded border px-2 py-1 text-[9px] font-bold ${riskBadge.bg} ${riskBadge.text}`}>{riskCategory} RISK</span>
              </div>

              <section className="rounded-lg border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-3" aria-labelledby="what-we-found-heading">
                <div className="flex items-center justify-between gap-2">
                  <div><div id="what-we-found-heading" className="text-[9px] font-bold uppercase tracking-widest text-slate-500">What we found</div><div className="mt-1 text-xs font-semibold text-white">{strongestFinding?.pattern_name || 'No suspicious pattern recorded'}</div></div>
                  <button type="button" onClick={() => setActiveTab('findings')} className="min-h-10 rounded border border-[var(--ct-outline-variant)] px-2 text-[10px] font-semibold text-[var(--ct-primary)]">All findings</button>
                </div>
                <div className="mt-2 text-[9px] font-bold uppercase tracking-wide text-slate-500">Why it matters</div>
                {strongestFinding ? <p className="mt-1 text-[11px] leading-relaxed text-slate-400">{strongestFinding.description}</p> : <p className="mt-1 text-[11px] text-slate-400">No finding requires explanation yet.</p>}
                {strongestFinding?.affected_wallets?.[0] && (
                  <button type="button" onClick={() => selectWalletByAddress(strongestFinding.affected_wallets![0])} className="mt-2 flex min-h-10 w-full items-center justify-center gap-2 rounded border border-amber-500/30 bg-amber-500/10 px-3 text-[10px] font-bold text-amber-400">
                    <AlertTriangle className="h-3.5 w-3.5" /> Explain WHY this was flagged
                  </button>
                )}
              </section>

              <section className="rounded-lg border border-[var(--ct-outline-variant)] bg-white p-3" aria-labelledby="money-trail-heading">
                <div className="flex items-center justify-between gap-2"><div><div id="money-trail-heading" className="text-[9px] font-bold uppercase tracking-widest text-slate-500">Money trail</div><div className="mt-1 text-[10px] text-slate-400">Origin to likely destination</div></div><button type="button" onClick={() => { setShowMoneyTrail(true); setFocusVersion(v => v + 1); }} className="min-h-10 rounded border border-[#8aa9a9] px-2 text-[10px] font-semibold text-[var(--ct-primary)]">Focus graph</button></div>
                {primaryPath.length > 0 ? (
                  <ol className="mt-2 space-y-1.5">
                    {primaryPath.slice(0, 6).map((address, index) => {
                      const node = nodes.find((item) => item.data.address === address)?.data;
                      const movement = index > 0 ? transactions.find((transaction) => transaction.from_address === primaryPath[index - 1] && transaction.to_address === address) : undefined;
                      const role = node?.is_reported ? 'Reported wallet' : node?.is_destination ? (node.vasp_name ? 'Attributed destination (review required)' : 'Last wallet observed') : node?.endpoint_kind === 'not_expanded' ? `Not expanded (${node.expansion_state})` : `Hop ${node?.hop_distance ?? index}`;
                      return <li key={address} className="grid grid-cols-[1rem_1fr] gap-1.5 text-[10px]"><span className="font-mono text-[var(--ct-primary)]">{index === 0 ? '●' : '↓'}</span><button type="button" onClick={() => selectWalletByAddress(address)} className="min-w-0 text-left"><span className="flex items-center justify-between gap-2 font-semibold text-slate-300"><span>{role}</span>{movement && <span className="shrink-0 font-mono text-[9px] text-[var(--ct-primary)]">{displayAmount(movement)} {movement.asset}</span>}</span><span className="block truncate font-mono text-slate-500">{address}</span></button></li>;
                    })}
                  </ol>
                ) : <p className="mt-2 text-[10px] text-slate-500">No primary money trail is available.</p>}
              </section>

              <section className="grid grid-cols-2 gap-2" aria-label="Case outcome context">
                <div className="rounded-lg border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-2.5"><div className="text-[9px] uppercase tracking-wide text-slate-500">Status</div><div className="mt-1 text-xs font-semibold capitalize text-white">{caseData.status.replaceAll('_', ' ')}</div></div>
                <div className="rounded-lg border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-2.5"><div className="text-[9px] uppercase tracking-wide text-slate-500">Destination attribution</div><div className="mt-1 truncate text-xs font-semibold text-white">{destinationNode?.vasp_name || 'No attribution available'}</div><div className="mt-0.5 text-[9px] font-semibold text-slate-500">{attributionLabel(destinationNode?.vasp_attribution_status || destinationNode?.vasp_confidence)}</div></div>
              </section>

              <section className="copilot-entry"><h3>Investigation Copilot</h3><p>Evidence-grounded explanations</p><button onClick={() => setActiveTab('ai')}>Explain the money trail →</button><button onClick={() => setActiveTab('ai')}>What should I review next? →</button></section>
              <details className="rounded-lg border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-3">
                <summary className="cursor-pointer text-[10px] font-semibold text-slate-400">Case assignment</summary>
                <div className="mt-2 text-xs font-semibold text-white">{caseData.assignment?.display_name || 'Assignment unavailable'}</div>
                {caseData.assignment?.role && <div className="mt-0.5 text-[10px] capitalize text-slate-500">{caseData.assignment.role.replaceAll('_', ' ')}</div>}
              </details>
            </div>
          )}

          {activeTab === 'overview' && selectedNode && !investigating && <>
            <WalletInspector wallet={selectedNode} network={caseData.blockchain === 'ethereum' ? 'Ethereum Mainnet' : caseData.blockchain || 'Unknown'}
              onClose={() => { setSelectedNode(null); setSelection(null); }}
              onTransfers={() => { setRecordFilter(selectedNode.address); setActiveTab('transactions'); }}
              onEvidence={() => { setRecordFilter(selectedNode.address); setActiveTab('evidence'); }}
              onWhy={() => void loadWhy(selectedNode.address)}
              onFocus={() => { setShowMoneyTrail(true); setFocusVersion(v => v + 1); }} />
            {loadingWhy && <p role="status" className="p-4 text-xs">Loading explanation…</p>}
            {whyData?.wallet_address === selectedNode.address && <section className="record-inspector"><h3>Why this wallet?</h3>
              {caseData.blockchain === 'ethereum' && <p className="trail-notice">Observed connection only. Risk interpretation is unavailable for Ethereum.</p>}
              <ul className="inspect-reasons">{whyData.reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul>
              {whyData.findings?.map(finding => <button key={finding.id} className="finding-link" onClick={() => selectFinding(finding)}>{finding.pattern_name} →</button>)}
            </section>}
          </>}

          {activeTab === 'recommendations' && (
            <div className="space-y-3 p-4 animate-fade-in">
              <div className="flex items-start justify-between gap-3">
                <div><h3 className="text-sm font-bold text-white">Recommended next actions</h3><p className="mt-0.5 text-[10px] text-slate-500">Deterministic actions derived from this investigation’s evidence.</p></div>
                <span className="rounded border border-[var(--ct-outline-variant)] px-2 py-1 text-[9px] font-bold text-[var(--ct-primary)]">{recommendations.length} PRIORITIZED</span>
              </div>
              <div className="rounded-lg border border-blue-500/20 bg-blue-500/5 p-3 text-[10px] leading-relaxed text-slate-400">Recommendations are not generated by the Copilot. Each item below is linked to persisted findings, transactions, evidence, or readiness signals.</div>
              {recommendations.length === 0 ? <p className="rounded-lg border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-3 text-xs text-slate-500">No evidence-grounded next action is currently eligible.</p> : recommendations.slice(0, 3).map((item) => {
                const linkedEvidence = evidence.find((entry) => item.evidence_ids.includes(entry.id));
                const linkedTransaction = transactions.find((entry) => item.transaction_hashes.includes(entry.hash));
                const review = () => {
                  if (linkedEvidence) { selectEvidence(linkedEvidence); setActiveTab('evidence'); }
                  else if (linkedTransaction) { selectTransfer(linkedTransaction.transfer_id || linkedTransaction.id || ''); }
                  else if (item.type === 'prepare_asset_action_request' || item.type === 'preserve_supporting_evidence') setActiveTab('action');
                  else setActiveTab('findings');
                };
                return <details key={item.recommendation_id} className="rounded-lg border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-3" open={item.priority === 'high'}>
                  <summary className="cursor-pointer list-none"><div className="flex items-start justify-between gap-2"><div><div className="text-[9px] font-bold uppercase tracking-widest text-slate-500">Recommended next action</div><div className="mt-1 text-xs font-semibold text-white">{item.title}</div></div><span className={`rounded border px-1.5 py-0.5 text-[9px] font-bold uppercase ${item.priority === 'high' ? 'border-red-500/30 text-red-300' : item.priority === 'medium' ? 'border-amber-500/30 text-amber-300' : 'border-slate-500/30 text-slate-400'}`}>{item.priority}</span></div></summary>
                  <div className="mt-3 space-y-2 text-[10px]"><div><div className="font-bold uppercase tracking-wide text-slate-500">Action</div><div className="mt-1 text-slate-300">{item.action}</div></div><div><div className="font-bold uppercase tracking-wide text-slate-500">Why this?</div><div className="mt-1 leading-relaxed text-slate-400">{item.factual_reason}</div></div><div><div className="font-bold uppercase tracking-wide text-slate-500">Supporting evidence</div><div className="mt-1 font-mono text-slate-500">{linkedEvidence?.title || linkedTransaction?.hash || `${item.evidence_ids.length} evidence reference(s)`}</div></div><button type="button" onClick={review} className="min-h-10 rounded border border-[var(--ct-primary)] px-3 text-[10px] font-semibold text-[var(--ct-primary)]">Review supporting record</button></div>
                </details>;
              })}
            </div>
          )}

          {activeTab === 'action' && (
            <div className="space-y-3 p-4 animate-fade-in">
              <div className="flex items-start justify-between gap-3">
                <div><h3 className="text-sm font-bold text-white">Action readiness</h3><p className="mt-0.5 text-[10px] text-slate-500">Investigation readiness for an external preservation/freeze request.</p></div>
                <span className={`rounded border px-2 py-1 text-[9px] font-bold ${actionReadiness?.ready ? 'border-green-500/30 bg-green-500/10 text-green-400' : 'border-amber-500/30 bg-amber-500/10 text-amber-400'}`}>{actionReadiness?.ready ? 'READY' : 'INCOMPLETE'}</span>
              </div>
              <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-[10px] leading-relaxed text-slate-400">This is operational readiness recorded from the current investigation. CryptoTrace does not execute or independently verify a blockchain freeze or external action.</div>
              {caseData.blockchain === 'ethereum' && <p className="trail-notice">Action requests are unavailable for Ethereum. Review and preserve the observed evidence.</p>}
              {actionReadiness ? (
                <>
                  <section className="rounded-lg border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-3" aria-label="Freeze readiness facts">
                    <div className="grid grid-cols-2 gap-2 text-[10px]">
                      <div><div className="uppercase tracking-wide text-slate-500">Destination</div><div className="mt-1 break-all font-mono text-white">{actionReadiness.destination_wallet || 'UNKNOWN'}</div></div>
                      <div><div className="uppercase tracking-wide text-slate-500">Attribution</div><div className="mt-1 font-semibold text-white">{attributionLabel(actionReadiness.attribution_status)}</div><div className="mt-1 text-slate-400">{actionReadiness.attribution_entity || 'No attribution available'}</div><div className="mt-0.5 text-[9px] text-slate-500">{actionReadiness.attribution_source_reference || actionReadiness.attribution_provenance || 'Source unavailable'} · {actionReadiness.attribution_status === 'known_verified' ? 'Verified' : actionReadiness.attribution_status === 'likely_inferred' ? 'Not independently verified' : 'Unknown'}</div></div>
                      <div><div className="uppercase tracking-wide text-slate-500">Observed movement</div><div className="mt-1 text-white">{actionReadiness.observed_amount != null ? `${displayAmount({ ...actionReadiness.transfer, amount: actionReadiness.observed_amount })} ${actionReadiness.asset || 'asset'}` : 'NOT AVAILABLE'}</div></div>
                      <div><div className="uppercase tracking-wide text-slate-500">Last movement</div><div className="mt-1 text-white">{actionReadiness.last_movement_at ? new Date(actionReadiness.last_movement_at).toLocaleString() : 'NOT AVAILABLE'}</div></div>
                    </div>
                  </section>
                  <section className="rounded-lg border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-3" aria-labelledby="readiness-checklist-heading">
                    <div id="readiness-checklist-heading" className="text-[9px] font-bold uppercase tracking-widest text-slate-500">Readiness checklist</div>
                    <div className="mt-2 space-y-1.5">{actionReadiness.checks.map((check) => <div key={check.key} className="flex items-start gap-2 text-[10px]"><span className={check.complete ? 'text-green-400' : 'text-amber-400'}>{check.complete ? '✓' : '○'}</span><span className={check.complete ? 'text-slate-300' : 'text-slate-500'}>{check.label}</span></div>)}</div>
                  </section>
                  {caseData.blockchain === 'demo' && <div className="grid gap-2 sm:grid-cols-2">
                    <button type="button" onClick={() => void createActionRequest('preservation_request')} disabled={!canMutate || !actionReadiness.evidence_ids.length || actionLoading} className="min-h-11 rounded border border-[var(--ct-primary)] px-3 text-[10px] font-bold text-[var(--ct-primary)] disabled:cursor-not-allowed disabled:opacity-40">{actionLoading ? 'Preparing…' : 'RECORD PRESERVATION REQUEST'}</button>
                    <button type="button" onClick={() => void createActionRequest('freeze_request')} disabled={!canMutate || !actionReadiness.evidence_ids.length || actionLoading} className="min-h-11 rounded bg-[var(--ct-primary)] px-3 text-[10px] font-bold text-[#ffffff] disabled:cursor-not-allowed disabled:opacity-40">RECORD FREEZE REQUEST</button>
                  </div>}
                  {actionReadiness.evidence_ids.length === 0 && <p className="text-[10px] text-amber-400">No supporting evidence is available for a request.</p>}
                </>
              ) : <p className="text-xs text-slate-500">Run the investigation first to derive readiness from case data.</p>}
              {actionMessage && <p role="status" className="rounded border border-[var(--ct-outline-variant)] bg-white p-2 text-[10px] text-[var(--ct-primary)]">{actionMessage}</p>}
              {actionRequests.length > 0 && <section className="space-y-2" aria-labelledby="request-status-heading"><div id="request-status-heading" className="text-[9px] font-bold uppercase tracking-widest text-slate-500">Request status</div>{actionRequests.map((item) => <div key={item.id} className="rounded-lg border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-3"><div className="flex items-start justify-between gap-2"><div><div className="text-[10px] font-semibold text-white">{item.action_type === 'freeze_request' ? 'Freeze request' : 'Preservation request'}</div><div className="mt-1 break-all font-mono text-[9px] text-slate-500">{item.target_wallet}</div></div><span className="rounded border border-[var(--ct-outline-variant)] px-1.5 py-0.5 text-[9px] font-bold uppercase text-slate-300">{item.status.replaceAll('_', ' ')}</span></div><div className="mt-2 grid grid-cols-2 gap-2 text-[10px] text-slate-500"><div>Attribution<div className="font-semibold text-slate-300">{attributionLabel(item.attribution_status)}{item.attribution_entity ? ` · ${item.attribution_entity}` : ''}</div></div><div>Source<div className="font-semibold text-slate-300">{item.attribution_source_reference || item.attribution_provenance || 'Unknown'}</div></div></div><div className="mt-2 text-[10px] text-slate-500">{item.evidence_ids.length} evidence reference{item.evidence_ids.length === 1 ? '' : 's'} · Local request record; external submission is separate</div>{item.status === 'draft' && <button type="button" onClick={() => void updateActionRequest(item.id, 'prepared', true)} disabled={!canMutate || actionLoading} className="mt-2 min-h-10 rounded border border-[var(--ct-primary)] px-3 text-[10px] font-semibold text-[var(--ct-primary)]">Prepare request</button>}{item.status === 'prepared' && <button type="button" onClick={() => void updateActionRequest(item.id, 'submitted')} disabled={!canMutate || actionLoading} className="mt-2 min-h-10 rounded border border-[var(--ct-primary)] px-3 text-[10px] font-semibold text-[var(--ct-primary)]">Record submitted</button>}{item.status === 'submitted' && <div className="mt-2 flex flex-wrap gap-2"><button type="button" onClick={() => void updateActionRequest(item.id, 'acknowledged')} disabled={!canMutate || actionLoading} className="min-h-10 rounded border border-[var(--ct-primary)] px-3 text-[10px] font-semibold text-[var(--ct-primary)]">Record acknowledged</button><button type="button" onClick={() => void updateActionRequest(item.id, 'more_information_required')} disabled={!canMutate || actionLoading} className="min-h-10 rounded border border-amber-500/30 px-3 text-[10px] font-semibold text-amber-400">More information required</button><button type="button" onClick={() => void updateActionRequest(item.id, 'declined')} disabled={!canMutate || actionLoading} className="min-h-10 rounded border border-red-500/30 px-3 text-[10px] font-semibold text-red-400">Record declined</button></div>}{item.status === 'acknowledged' && <button type="button" onClick={() => void updateActionRequest(item.id, 'actioned')} disabled={!canMutate || actionLoading} className="mt-2 min-h-10 rounded border border-[var(--ct-primary)] px-3 text-[10px] font-semibold text-[var(--ct-primary)]">Record actioned</button>}<p className="mt-2 text-[9px] leading-relaxed text-slate-500">Operational status recorded in CryptoTrace. External action not independently verified.</p></div>)}</section>}
            </div>
          )}

          {activeTab === 'transactions' && selectedTransaction && !investigating && <TransferInspector
            transfer={selectedTransaction} network={caseData.blockchain || ''} capability={caseData.capability}
            canSave={canMutate} saving={savingEvidence} message={evidenceMessage}
            onSave={() => void saveTransactionEvidence(selectedTransaction)}
            onClose={() => { setSelectedTransaction(null); setSelection(null); }}
            onWallet={selectWallet} onFocus={() => { setShowMoneyTrail(true); setFocusVersion(v => v + 1); }} />}

          {/* Findings Tab */}
          {activeTab === 'findings' && (
            <div className="p-4 space-y-3 animate-fade-in">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-bold text-white">Findings &amp; Risk Analysis</h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">Deterministic analysis from this investigation</p>
                </div>
                <span className={`text-[10px] px-2 py-1 rounded border font-medium ${riskBadge.bg} ${riskBadge.text}`}>
                  {(investigation?.risk?.overall || caseData?.summary?.risk_level || 'PENDING').toUpperCase()} PRIORITY
                </span>
              </div>
              <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3" aria-label="Investigation risk summary">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[9px] uppercase tracking-widest text-slate-500">Investigation priority</div>
                    <div className="mt-1 text-sm font-semibold text-white">{riskCategory}</div>
                  </div>
                  <div className="text-right text-[10px] text-slate-500">
                    <div>{findings.length} finding{findings.length === 1 ? '' : 's'}</div>
                    <div>{evidence.length} evidence record{evidence.length === 1 ? '' : 's'}</div>
                  </div>
                </div>
                <p className="mt-2 text-[10px] leading-relaxed text-slate-400">Risk prioritizes investigator review. Wallet-level scores and contributing signals are available in the Wallet Inspector.</p>
              </div>
              {findings.length === 0 ? (
                <p className="text-xs text-slate-500">{caseData.blockchain === 'ethereum' ? 'Risk interpretation is not available for Ethereum. Observed transfers are not fraud findings.' : 'No findings recorded in this run.'}</p>
              ) : findings.map((f, i) => (
                <details key={f.id || `${f.pattern_name}-${i}`} open={selectedFinding?.id === f.id && !!selectedFinding} className="bg-[var(--ct-surface)] border border-[var(--ct-outline-variant)] rounded-lg p-3">
                  <summary onClick={event => { event.preventDefault(); if (selectedFinding === f) setSelectedFinding(null); else selectFinding(f); }} className="mb-3 flex cursor-pointer items-center gap-2">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                    <span className="text-xs font-medium text-white">{f.pattern_name}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium border ml-auto
                      ${f.severity === 'high' || f.severity === 'critical' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20'}`}>
                      {f.severity?.toUpperCase()}
                    </span>
                  </summary>
                  <div className="space-y-3">
                    <div>
                      <div className="text-[9px] font-semibold uppercase tracking-widest text-slate-500">What happened</div>
                      <p className="mt-1 text-[11px] leading-relaxed text-slate-300">{f.description}</p>
                    </div>
                    <div>
                      <div className="text-[9px] font-semibold uppercase tracking-widest text-slate-500">Why it matters</div>
                      <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
                        {f.trigger || `Deterministic analysis classified this pattern as ${f.severity} severity with ${(f.confidence * 100).toFixed(0)}% confidence.`}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-[10px]">
                      <span className="px-1.5 py-0.5 rounded border border-blue-500/20 bg-blue-500/10 text-blue-400">ANALYSIS</span>
                      <span className="text-slate-600">Confidence {(f.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  {(f.affected_wallets ?? []).length > 0 && (
                    <div className="mt-2 border-t border-[var(--ct-outline-variant)] pt-2">
                      <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-1">Next · explain a flagged wallet</div>
                      <div className="flex flex-wrap gap-1.5">
                        {(f.affected_wallets ?? []).slice(0, 4).map((address) => (
                          <button
                            key={address}
                            type="button"
                            onClick={() => selectWalletByAddress(address)}
                            aria-label={`Explain why wallet ${address} was flagged`}
                            className="min-h-10 rounded border border-amber-500/30 px-2 py-1 font-mono text-[10px] text-amber-400 hover:border-amber-500/50 hover:bg-amber-500/10"
                          >
                            Explain {address.slice(0, 12)}…
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {(f.supporting_transaction_ids ?? []).length > 0 && (
                    <div className="mt-2 border-t border-[var(--ct-outline-variant)] pt-2">
                      <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-1">Transactions supporting this finding</div>
                      <div className="flex flex-wrap gap-1.5">
                        {(f.supporting_transaction_ids ?? []).slice(0, 4).map((hash) => (
                          <button
                            key={hash}
                            type="button"
                            onClick={() => selectTransactionByHash(hash)}
                            className="min-h-10 rounded border border-[var(--ct-outline-variant)] px-2 py-1 font-mono text-[10px] text-[var(--ct-primary)] hover:border-[#8aa9a9] hover:text-[var(--accent-cyan)]"
                          >
                            View TX {hash.slice(0, 12)}…
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="inspect-actions">
                    <button onClick={() => { setRecordFilter(''); setActiveTab('evidence'); const linked = evidence.find(e => e.finding_id === f.id); if (linked) selectEvidence(linked); }}>View evidence ({evidence.filter(e => e.finding_id === f.id).length})</button>
                    <button onClick={() => setActiveTab('recommendations')}>Review next action</button>
                  </div>
                </details>
              ))}
            </div>
          )}

          {/* Evidence Tab */}
          {activeTab === 'evidence' && (
            <div className="p-4 space-y-3 animate-fade-in">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-bold text-white">Evidence Center</h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">Observed records linked to findings and transactions</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[9px] uppercase tracking-wide text-slate-500">{evidence.length} records</span>
                  {caseData?.is_demo && <span className="rounded border border-amber-500/20 bg-amber-500/10 px-1.5 py-0.5 text-[9px] font-medium text-amber-400">DEMO DATA</span>}
                  <Bookmark aria-hidden="true" className="w-4 h-4 text-slate-500" />
                </div>
              </div>
              <div className="rounded-lg border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[9px] uppercase tracking-widest text-slate-500">Evidence chain</div>
                    <div className="mt-1 text-xs font-medium text-white">Finding → reason → transaction</div>
                  </div>
                  <div className="text-right text-[10px] text-slate-500">
                    <div>{linkedEvidenceCount} linked</div>
                    <div>Evidence records</div>
                  </div>
                </div>
                <p className="mt-2 text-[10px] leading-relaxed text-slate-400">Select a record to inspect its persisted source, timestamp, and case-linked transaction context.</p>
              </div>
              {selectedEvidence && (
                <div className="bg-cyan-500/5 border border-cyan-500/20 rounded-lg p-3">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <div className="text-[10px] uppercase tracking-widest text-cyan-400 font-medium">Selected evidence</div>
                    <span className="text-[9px] px-1.5 py-0.5 rounded border border-blue-500/20 bg-blue-500/10 text-blue-400">EVIDENCE RECORD</span>
                  </div>
                  <div className="text-xs text-white font-medium">{selectedEvidence.title}</div>
                  {selectedEvidence.transaction_hash && <div className="text-[10px] text-slate-500 font-mono break-all mt-1">{selectedEvidence.transaction_hash}</div>}
                  {selectedEvidence.finding_id && <div className="text-[10px] text-slate-400 font-mono break-all mt-1">Finding {selectedEvidence.finding_id}</div>}
                  {selectedEvidence.transaction_hash && transactions.some(transaction => transaction.hash === selectedEvidence.transaction_hash) && (
                    <button
                      type="button"
                      onClick={() => selectTransactionByHash(selectedEvidence.transaction_hash as string)}
                      className="mt-2 min-h-10 rounded border border-cyan-500/30 px-3 py-1.5 text-[10px] font-medium text-cyan-400 hover:bg-cyan-500/10"
                    >
                      VIEW LINKED TRANSACTION
                    </button>
                  )}
                  {selectedEvidence.reason && <div className="text-[10px] text-cyan-400 mt-1">{selectedEvidence.reason}</div>}
                  <div className="mt-1 text-[10px] text-slate-500">
                    Source: {selectedEvidence.source || 'unknown'}{selectedEvidence.created_at ? ` · ${new Date(selectedEvidence.created_at).toLocaleString()}` : ''}
                  </div>
                </div>
              )}
              {evidence.length === 0 ? (
                <p className="rounded-lg border border-dashed border-[var(--ct-outline-variant)] px-3 py-4 text-xs text-[var(--ct-ink-muted)]">No evidence yet. Run investigation first.</p>
              ) : evidence.filter(e => !recordFilter || e.wallet_address === recordFilter || transactions.some(t => t.hash === e.transaction_hash && (t.from_address === recordFilter || t.to_address === recordFilter))).map((e, i) => (
                <button type="button" key={e.id || i} onClick={() => selectEvidence(e)} aria-pressed={selectedEvidence?.id === e.id} className={`w-full text-left bg-[var(--ct-surface)] border rounded-lg p-3 ${selectedEvidence?.id === e.id ? 'border-[#8aa9a9]' : 'border-[var(--ct-outline-variant)]'}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <Bookmark className="w-3 h-3 text-blue-400" />
                    <span className="text-xs font-medium text-white">{e.title}</span>
                    <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded border border-blue-500/20 bg-blue-500/10 text-blue-400">EVIDENCE RECORD</span>
                  </div>
                  <p className="text-[11px] text-slate-400 leading-relaxed">{e.description}</p>
                  {e.reason && <p className="text-[10px] text-cyan-400 mt-1">{e.reason}</p>}
                  {e.transaction_hash && <p className="mt-1 break-all font-mono text-[10px] text-slate-500">TX {e.transaction_hash}</p>}
                  {e.finding_id && <p className="mt-1 break-all font-mono text-[10px] text-slate-500">Finding {e.finding_id}</p>}
                  <div className="mt-1 text-[10px] text-slate-500">
                    {e.source || 'unknown source'}{e.created_at ? ` · ${new Date(e.created_at).toLocaleString()}` : ''}
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* Timeline Tab */}
          {activeTab === 'timeline' && (
            <div className="p-4 animate-fade-in">
              <div className="mb-3 flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-bold text-white">Investigation Timeline</h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">Chronological events from the current case</p>
                </div>
                <button type="button" onClick={startReplay} className="ct-button-primary flex min-h-10 items-center gap-1.5 px-3 text-[10px]"><Play className="h-3 w-3" /> Replay</button>
              </div>
              {timeline.length === 0 ? (
                <p className="rounded-lg border border-dashed border-[var(--ct-outline-variant)] px-3 py-4 text-xs text-[var(--ct-ink-muted)]">No timeline events are available yet. Run the investigation first.</p>
              ) : (
                <div className="space-y-0">
                {timeline.map((e, i) => (
                  <button type="button" key={i} onClick={() => jumpToReplayEvent(e)} className={`min-h-10 w-full text-left flex gap-3 group rounded-lg ${replayEvents[replayStep]?.transaction_hash && replayEvents[replayStep]?.transaction_hash === e.transaction_hash ? 'bg-blue-500/5' : ''}`}>
                    <div className="flex flex-col items-center">
                      <div className="w-2.5 h-2.5 rounded-full bg-[var(--ct-primary)] border-2 border-white z-10" />
                      {i < timeline.length - 1 && <div className="w-0.5 flex-1 bg-[var(--ct-outline-variant)]" />}
                    </div>
                    <div className="pb-4 flex-1">
                      <div className="text-[10px] text-slate-500 font-mono mb-0.5">
                        {e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : ''}
                      </div>
                      <div className="text-xs text-white font-medium">{e.title}</div>
                      {e.description && <p className="text-[10px] text-slate-500 mt-0.5">{e.description}</p>}
                    </div>
                  </button>
                ))}
                </div>
              )}
            </div>
          )}

          {/* Audit Log Tab */}
          {activeTab === 'audit' && (
            <div className="p-4 animate-fade-in">
              <div className="flex items-start justify-between gap-3 mb-3">
                <div>
                  <h3 className="text-sm font-bold text-white">Audit Log</h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">Case-scoped investigator activity</p>
                </div>
                <ClipboardList className="w-4 h-4 text-slate-500" />
              </div>
              {auditEvents.length === 0 ? (
                <p className="text-xs text-slate-500">No audit events recorded for this case.</p>
              ) : (
                <div className="space-y-2">
                  {auditEvents.map((event) => (
                    <div key={event.id} className="bg-[var(--ct-surface)] border border-[var(--ct-outline-variant)] rounded-lg p-3">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-xs font-medium text-white">
                          {event.action.replaceAll('_', ' ').toUpperCase()}
                        </span>
                        <span className="text-[10px] text-slate-500 whitespace-nowrap">
                          {event.timestamp ? new Date(event.timestamp).toLocaleString() : 'Timestamp unavailable'}
                        </span>
                      </div>
                      <div className="mt-1 text-[10px] text-slate-400">
                        {event.actor} · {event.resource_type || 'case'}
                        {event.resource_id ? ` · ${event.resource_id.slice(0, 12)}…` : ''}
                      </div>
                      {event.details && Object.keys(event.details).length > 0 && (
                        <details className="mt-2 rounded border border-[var(--ct-outline-variant)] bg-white p-2 text-[10px] text-[var(--ct-ink-muted)]">
                          <summary className="min-h-8 cursor-pointer select-none py-1 font-medium text-[var(--ct-primary)]">
                            View event details
                          </summary>
                          <dl className="mt-2 grid grid-cols-[minmax(5rem,auto)_1fr] gap-x-3 gap-y-1 border-t border-[var(--ct-outline-variant)] pt-2">
                            {Object.entries(event.details).map(([key, value]) => (
                              <Fragment key={key}>
                                <dt className="font-medium text-[var(--ct-ink)]">{key.replaceAll('_', ' ')}</dt>
                                <dd className="min-w-0 break-words font-mono">
                                  {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                                </dd>
                              </Fragment>
                            ))}
                          </dl>
                          <details className="mt-2 border-t border-[var(--ct-outline-variant)] pt-2">
                            <summary className="min-h-8 cursor-pointer select-none py-1">Raw JSON</summary>
                            <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-all rounded bg-[var(--ct-surface)] p-2 font-mono">
                              {JSON.stringify(event.details, null, 2)}
                            </pre>
                          </details>
                        </details>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Transactions Tab */}
          {activeTab === 'transactions' && (
            <div className="p-4 space-y-3 animate-fade-in">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-bold text-white">Transaction Trace</h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">Source → movement → destination, ordered by traced hop</p>
                </div>
                <span className="shrink-0 rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[9px] font-medium text-amber-400">
                  {capabilityLabel(caseData?.capability)}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2" aria-label="Transaction trace summary">
                <div className="rounded-lg border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-2">
                  <div className="text-sm font-semibold text-white">{transactions.length}</div>
                  <div className="text-[9px] uppercase tracking-wide text-slate-500">Transfers</div>
                </div>
                <div className="rounded-lg border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-2">
                  <div className="text-sm font-semibold text-white">{traceHopCount}</div>
                  <div className="text-[9px] uppercase tracking-wide text-slate-500">Hops covered</div>
                </div>
                <div className="rounded-lg border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-2">
                  <div className="text-sm font-semibold text-white">{suspiciousTransactionCount}</div>
                  <div className="text-[9px] uppercase tracking-wide text-slate-500">Flagged transfers</div>
                </div>
              </div>
              <div className="space-y-2">
                {transactions.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-[var(--ct-outline-variant)] px-3 py-4 text-xs text-[var(--ct-ink-muted)]">No traced transactions are available for this case.</p>
                ) : transactions.filter(t => !recordFilter || t.from_address === recordFilter || t.to_address === recordFilter).map((t, i) => (
                  <div
                    key={t.id || t.hash || i}
                    role="button"
                    tabIndex={0}
                    aria-pressed={selectedTransaction?.transfer_id === t.transfer_id && selectedTransaction?.id === t.id}
                    aria-label={`Select transaction ${t.hash}`}
                    onClick={() => { selectTransfer(t.transfer_id || t.id || ''); }}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        selectTransfer(t.transfer_id || t.id || '');
                      }
                    }}
                    className={`bg-[var(--ct-surface)] border rounded-lg p-2.5 cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ct-primary)]
                      ${selectedTransaction?.transfer_id === t.transfer_id && selectedTransaction?.id === t.id ? 'border-[#8aa9a9]' : 'border-[var(--ct-outline-variant)] hover:border-[#8aa9a9]'}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="min-w-0 break-all font-mono text-[10px] text-blue-400">TX {t.hash?.slice(0, 20)}...</span>
                      <div className="ml-2 flex shrink-0 items-center gap-1.5">
                        {t.is_suspicious && <span className="rounded border border-red-500/30 bg-red-500/10 px-1.5 py-0.5 text-[9px] font-medium text-red-400">FLAGGED</span>}
                        <span className="text-[10px] text-slate-500">Hop {t.hop_number ?? '—'}</span>
                      </div>
                    </div>
                    <div className="mt-2 grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-start gap-2">
                      <div className="min-w-0">
                        <div className="text-[9px] uppercase tracking-widest text-slate-500">Source</div>
                        <div className="mt-1 break-all font-mono text-[10px] text-slate-400">{t.from_address}</div>
                      </div>
                      <ArrowRight aria-hidden="true" className="mt-4 h-3.5 w-3.5 shrink-0 text-blue-400" />
                      <div className="min-w-0 text-right">
                        <div className="text-[9px] uppercase tracking-widest text-slate-500">Destination</div>
                        <div className="mt-1 break-all font-mono text-[10px] text-slate-400">{t.to_address}</div>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-t border-[var(--ct-outline-variant)] pt-2">
                      <span className="text-xs font-semibold text-white font-mono">{displayAmount(t)} {t.asset}</span>
                      <span className="text-[10px] text-slate-500">
                        {t.timestamp ? new Date(t.timestamp).toLocaleString() : 'Timestamp unavailable'}
                        {t.source ? ` · ${t.source}` : ''}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={(event) => { event.stopPropagation(); void saveTransactionEvidence(t); }}
                      disabled={!canMutate || savingEvidence}
                      className="mt-2 inline-flex min-h-10 items-center gap-1.5 text-[10px] text-blue-400 hover:text-blue-300 disabled:opacity-50"
                    >
                      <Bookmark className="w-3 h-3" /> {savingEvidence ? 'Saving…' : 'SAVE EVIDENCE'}
                    </button>
                  </div>
                ))}
                {evidenceMessage && <p className="text-[10px] text-cyan-400 mt-2">{evidenceMessage}</p>}
              </div>
            </div>
          )}

          {/* AI Tab */}
          {activeTab === 'ai' && (
            <div className="flex flex-col h-full animate-fade-in">
              <div className="p-4 border-b border-[var(--ct-outline-variant)]">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-bold text-white">AI Investigation Copilot</h3>
                    <p className="text-[10px] text-slate-500 mt-0.5">Grounded in this case&apos;s findings, flow, and evidence</p>
                  </div>
                  <span className="text-[9px] px-1.5 py-0.5 rounded border border-purple-500/20 bg-purple-500/10 text-purple-400">STRUCTURED EXPLANATION</span>
                </div>
                {caseData?.is_demo && <p className="mt-2 text-[10px] text-amber-400">DEMO DATA context · verify conclusions against the evidence trail.</p>}
                <div className="mt-3 grid grid-cols-3 gap-2" aria-label="Copilot grounding context">
                  <div className="rounded border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-2">
                    <div className="text-sm font-semibold text-white">{transactions.length}</div>
                    <div className="text-[9px] uppercase tracking-wide text-slate-500">Transfers</div>
                  </div>
                  <div className="rounded border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-2">
                    <div className="text-sm font-semibold text-white">{findings.length}</div>
                    <div className="text-[9px] uppercase tracking-wide text-slate-500">Findings</div>
                  </div>
                  <div className="rounded border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-2">
                    <div className="text-sm font-semibold text-white">{evidence.length}</div>
                    <div className="text-[9px] uppercase tracking-wide text-slate-500">Evidence</div>
                  </div>
                </div>
              </div>

              {/* Suggested Questions */}
              {!hasInvestigation ? (
                <div className="m-4 rounded-lg border border-dashed border-[var(--ct-outline-variant)] px-3 py-4 text-xs text-[var(--ct-ink-muted)]">
                  Run the investigation first so Copilot can use this case&apos;s trace, findings, and evidence.
                </div>
              ) : aiMessages.length === 0 && (
                <div className="p-4">
                  <div className="rounded-lg border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-3 text-xs leading-relaxed text-[var(--ct-ink-muted)]">
                    Review a case question. Answers use persisted findings, transfers, and evidence; no new blockchain facts are inferred.
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2" aria-label="Example questions">
                    {[
                      'Why was this wallet flagged?',
                      'Explain the money trail.',
                      'Why is this the leading destination?',
                      'What evidence supports this finding?',
                      'What should I review next?',
                      'What information is missing?',
                    ].map((q) => (
                      <button type="button" key={q} disabled={!canMutate || aiLoading || investigating} onClick={() => askAI(q)}
                        className="min-h-10 rounded-full border border-[#8aa9a9] bg-white px-3 py-1.5 text-left text-[10px] font-medium text-[#124343] hover:bg-[#f4f4ef]">
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {aiMessages.map((msg, i) => (
                  <div key={i} className={`${msg.role === 'user' ? 'text-right' : ''}`}>
                    <div className={`inline-block max-w-[90%] px-3 py-2 rounded-lg text-xs leading-relaxed
                      ${msg.role === 'user'
                        ? 'bg-blue-600/20 text-blue-200 border border-blue-500/20'
                        : 'bg-[var(--ct-surface)] text-[var(--ct-ink-muted)] border border-[var(--ct-outline-variant)]'
                      }`}
                    >
                      {msg.role === 'assistant'
                        ? <SafeMarkdown content={msg.content} />
                        : <div className="whitespace-pre-wrap">{msg.content}</div>}
                    </div>
                  </div>
                ))}
                {aiLoading && (
                  <div role="status" aria-live="polite" className="flex items-center gap-2 text-slate-500">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span className="text-xs">Analyzing case data...</span>
                  </div>
                )}
              </div>

              {/* Input */}
              <div className="p-3 border-t border-[var(--ct-outline-variant)]">
                <div className="flex gap-2">
                  <input
                    value={aiInput}
                    onChange={(e) => setAiInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && askAI()}
                    aria-label="Ask the investigation copilot"
                    disabled={!canMutate || !hasInvestigation || aiLoading}
                    maxLength={1000}
                    placeholder="Ask about the investigation..."
                    className="flex-1 px-3 py-2 bg-[var(--ct-surface)] border border-[var(--ct-outline-variant)] rounded-lg text-xs text-[var(--ct-ink)]
                      focus:outline-none focus:border-blue-500 placeholder:text-slate-600 disabled:cursor-not-allowed disabled:opacity-50"
                  />
                  <button type="button" onClick={() => askAI()} disabled={!canMutate || !hasInvestigation || aiLoading} aria-label="Send question to investigation copilot" className="min-h-10 min-w-10 flex items-center justify-center p-2 bg-blue-600 rounded-lg text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50">
                    <Send className="w-3 h-3" />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Report Tab */}
          {activeTab === 'report' && (
            <div className="p-4 animate-fade-in">
              <div className="flex items-start justify-between gap-3 mb-3">
                <div>
                  <h3 className="text-sm font-bold text-white">Forensic Report</h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">Structured output from the current investigation</p>
                </div>
                {caseData?.is_demo && <span className="text-[9px] px-1.5 py-0.5 rounded border border-amber-500/20 bg-amber-500/10 text-amber-400">DEMO DATA</span>}
              </div>
              {!report ? (
                <div className="text-center py-8">
                  <FileText className="w-10 h-10 text-slate-600 mx-auto mb-3" />
                  <p className="text-xs text-slate-500 mb-1">No report generated yet</p>
                  <p className="text-[10px] text-slate-600 mb-4">{hasInvestigation ? 'Generate a report after reviewing the case evidence.' : 'Run the investigation before generating a report.'}</p>
                  {hasInvestigation && (
                    <button type="button" onClick={generateReport} disabled={!canMutate || generatingReport}
                      className="min-h-10 px-4 py-2 bg-green-600/20 text-green-400 border border-green-500/30 rounded-lg text-xs font-medium hover:bg-green-600/30 disabled:opacity-50">
                      {generatingReport ? 'Generating...' : 'Generate Report'}
                    </button>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="rounded-lg border border-[var(--ct-outline-variant)] bg-[var(--ct-surface)] p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-[9px] uppercase tracking-widest text-slate-500">Forensic report · {caseData?.case_number}</div>
                        <div className="mt-1 text-sm font-semibold text-white">{report.title}</div>
                      </div>
                      <span className="shrink-0 text-[9px] uppercase tracking-wide text-slate-500">{report.sections?.length || 0} sections</span>
                    </div>
                    <p className="mt-2 text-[10px] leading-relaxed text-slate-400">Structured from this investigation&apos;s facts, deterministic analysis, and labeled inferences.</p>
                  </div>
                  {report.sections?.map((s, i: number) => (
                    <section key={`${s.section_type}-${s.title}-${i}`} className="bg-[var(--ct-surface)] border border-[var(--ct-outline-variant)] rounded-lg p-3">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium border
                          ${s.section_type === 'fact' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                            : s.section_type === 'analysis' ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20'
                            : s.section_type === 'inference' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                            : 'bg-purple-500/10 text-purple-400 border-purple-500/20'}`}>
                          {s.section_type?.toUpperCase()}
                        </span>
                        <span className="text-xs font-medium text-white">{s.title}</span>
                      </div>
                      <pre className="text-[11px] text-slate-400 whitespace-pre-wrap font-sans leading-relaxed">{s.content}</pre>
                    </section>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Wallets Tab */}
          {activeTab === 'wallets' && (
            <div className="p-4 animate-fade-in">
              <h3 className="text-sm font-bold text-white mb-3">Discovered Wallets</h3>
              <div className="space-y-2">
                {nodes.map((n, i) => {
                  const d = n.data;
                  return (
                    <button
                      key={i}
                      onClick={() => selectWallet(d.address)}
                      className="w-full text-left bg-[var(--ct-surface)] border border-[var(--ct-outline-variant)] rounded-lg p-3 hover:border-[#8aa9a9] transition-colors"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: getNodeColor(d) }} />
                        <span className="text-xs text-white font-medium">{d.label || d.address?.slice(0, 16) + '...'}</span>
                        {d.is_reported && <span className="text-[9px] text-red-400 font-medium">REPORTED</span>}
                        {d.is_destination && <span className="text-[9px] text-purple-400 font-medium">DEST</span>}
                      </div>
                      <div className="text-[10px] font-mono text-slate-500">{d.address}</div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
