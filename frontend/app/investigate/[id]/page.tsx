'use client';

import { useState, useEffect, useRef, type CSSProperties, type ReactNode } from 'react';
import { useParams, useRouter } from 'next/navigation';
import api from '@/lib/api';
import { ReplayBar } from '@/components/investigation/ReplayBar';
import {
  Shield, Search, Play,
  AlertTriangle, Eye, FileText, MessageSquare, ChevronLeft,
  Loader2, Crosshair,
  Bookmark, ArrowRight, Activity, ClipboardList, Send, XCircle
} from 'lucide-react';
import ReactFlow, {
  Background, Controls, MiniMap,
  Node, Edge, MarkerType, useNodesState, useEdgesState,
  Position, ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';

// ─── Types ────────────────────────────────────────────────────
interface GraphNodeData {
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
  risk_category?: string | null;
  risk_score?: number | null;
  risk_signals?: Array<{ signal_name?: string; description?: string; score_contribution?: number }>;
}

interface GraphEdgeData {
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

interface GraphResponse { nodes: GraphNodeData[]; edges: GraphEdgeData[]; primary_path: string[]; }
interface FindingData {
  id?: string;
  pattern_name: string;
  description: string;
  severity: string;
  confidence: number;
  supporting_transaction_ids?: string[];
  created_at?: string;
}
interface EvidenceData { id: string; evidence_type?: string; title: string; description: string; reason?: string; transaction_hash?: string; wallet_address?: string; finding_id?: string; source?: string; created_at?: string; is_bookmarked?: boolean; }
interface TransactionData {
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
interface TimelineEvent { id?: string; title: string; description?: string; timestamp?: string; transaction_hash?: string; sequence_order?: number; }
interface AuditEvent { id: string; action: string; resource_type?: string | null; resource_id?: string | null; details?: Record<string, unknown> | null; actor: string; timestamp?: string | null; }
interface ReplayEvent {
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
  cumulative_amount?: number;
}
interface CaseDetail { id: string; case_number: string; status: string; is_demo: boolean; reported_wallet: string; blockchain?: string; summary?: { risk_level?: string; total_wallets?: number; total_transactions?: number }; }
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
  fund_flow_summary: Record<string, unknown>;
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
  return map[category || 'low'] || map.low;
}

// ─── Main Page ────────────────────────────────────────────────
export default function InvestigatePage() {
  return (
    <ReactFlowProvider>
      <InvestigateContent />
    </ReactFlowProvider>
  );
}

function InvestigateContent() {
  const params = useParams();
  const router = useRouter();
  const caseId = params.id as string;

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
  const [graphSearch, setGraphSearch] = useState('');
  const [graphSearchMessage, setGraphSearchMessage] = useState('');

  // Graph
  const [nodes, setNodes, onNodesChange] = useNodesState<GraphNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<GraphEdgeData>([]);
  const baseNodeStyles = useRef<Record<string, CSSProperties>>({});
  const baseEdgeStyles = useRef<Record<string, CSSProperties>>({});
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
      if (data.status === 'investigating' || data.status === 'review' || data.status === 'completed') {
        await loadInvestigationData(data);
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
          overall: currentCase?.summary?.risk_level || 'low',
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
    void Promise.resolve().then(() => loadCase());
    // loadCase intentionally runs only when the route case changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  // ─── Run Investigation ────────────────────────────────────
  const runInvestigation = async () => {
    setInvestigating(true);
    setActionError('');
    try {
      const result = await api.investigate(caseId);
      setInvestigation(result);
      setCaseData((prev) => prev ? { ...prev, status: 'investigating' } : prev);

      // Build graph from result
      if (result.graph) {
        buildGraphVisualization(result.graph);
      }

      // Load additional data
      await loadInvestigationData(undefined, result);
      await loadAuditLog();
      setActiveTab('overview');
    } catch (err) {
      console.error('Investigation failed', err);
      setActionError(err instanceof Error ? err.message : 'Unable to complete the investigation.');
    } finally {
      setInvestigating(false);
    }
  };

  // ─── Build Graph Visualization ────────────────────────────
  function buildGraphVisualization(graphData: GraphResponse) {
    const primaryPath = graphData.primary_path || [];
    const pathSet = new Set(primaryPath);

    // Layout: arrange by hop distance in columns
    const hopGroups: Record<number, GraphNodeData[]> = {};
    graphData.nodes.forEach((n: GraphNodeData) => {
      const hop = n.hop_distance || 0;
      if (!hopGroups[hop]) hopGroups[hop] = [];
      hopGroups[hop].push(n);
    });

    const flowNodes: Node<GraphNodeData>[] = graphData.nodes.map((n: GraphNodeData) => {
      const hop = n.hop_distance || 0;
      const groupIndex = hopGroups[hop]?.indexOf(n) || 0;
      const groupSize = hopGroups[hop]?.length || 1;

      const onPrimary = pathSet.has(n.address);
      const color = getNodeColor(n);

      return {
        id: n.id || n.address,
        position: {
          x: hop * 260 + 80,
          y: (groupIndex - (groupSize - 1) / 2) * 140 + 300,
        },
        data: {
          label: (
            <div className="text-center">
              <div className="text-[10px] font-mono text-white/80 mb-0.5">
                {n.label || n.address?.slice(0, 14) + '...'}
              </div>
              <div className="text-[9px] text-white/50 font-mono">
                {n.address?.slice(0, 10)}...
              </div>
              {n.vasp_name && (
                <div className="text-[9px] text-purple-300 mt-0.5 font-medium">
                  {n.vasp_name}
                </div>
              )}
              {n.is_reported && <div className="text-[8px] text-red-300 mt-0.5">⚠ REPORTED</div>}
              {n.is_destination && <div className="text-[8px] text-purple-300 mt-0.5">◆ DESTINATION</div>}
            </div>
          ),
          ...n,
        },
        style: {
          background: `${color}20`,
          border: `2px solid ${color}`,
          borderRadius: '4px',
          padding: '10px 14px',
          minWidth: '150px',
          boxShadow: onPrimary ? '0 2px 4px rgba(26, 28, 25, 0.12)' : 'none',
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      };
    });

    const flowEdges: Edge<GraphEdgeData>[] = graphData.edges.map((e: GraphEdgeData) => {
      const onPrimary = pathSet.has(e.source) && pathSet.has(e.target);
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        data: e,
        label: `${e.amount?.toFixed(3)} ${e.asset || 'ETH'}`,
        labelStyle: { fill: '#526168', fontSize: 10, fontFamily: 'monospace' },
        labelBgStyle: { fill: '#fafaf5', fillOpacity: 0.95 },
        style: {
          stroke: onPrimary ? '#124343' : '#c0c8c7',
          strokeWidth: onPrimary ? 2.5 : 1.5,
        },
        animated: onPrimary,
        markerEnd: { type: MarkerType.ArrowClosed, color: onPrimary ? '#124343' : '#c0c8c7' },
      };
    });

    baseNodeStyles.current = Object.fromEntries(
      flowNodes.map((node) => [node.id, { ...(node.style || {}) }]),
    );
    baseEdgeStyles.current = Object.fromEntries(
      flowEdges.map((edge) => [edge.id, { ...(edge.style || {}) }]),
    );
    graphNodeData.current = Object.fromEntries(
      graphData.nodes.map((node) => [node.id || node.address, node]),
    );
    setNodes(flowNodes);
    setEdges(flowEdges);
  }

  // ─── WHY? ─────────────────────────────────────────────────
  const loadWhy = async (address: string) => {
    setLoadingWhy(true);
    setActionError('');
    try {
      const data = await api.getWhyExplanation(caseId, address);
      setWhyData(data);
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
    const data = await api.getReplay(caseId);
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

  // Replay and money-trail styling are projections of the same backend graph.
  // Rebuild from the baseline styles so the previous replay step cannot leave
  // stale node or edge highlights behind.
  useEffect(() => {
    const event = replayStep >= 0 ? replayEvents[replayStep] : undefined;
    const highlightNodes = new Set(event?.highlight_nodes || []);
    const highlightEdges = new Set(event?.highlight_edges || []);
    const primaryPath = new Set(investigation?.graph?.primary_path || []);

    setNodes(nds => nds.map(n => ({
      ...n,
      style: {
        ...baseNodeStyles.current[n.id],
        opacity: showMoneyTrail && !primaryPath.has(n.id) ? 0.45 : 1,
        border: highlightNodes.has(n.id) ? '2px solid #124343' : baseNodeStyles.current[n.id]?.border,
        boxShadow: highlightNodes.has(n.id)
          ? '0 2px 6px rgba(18, 67, 67, 0.28)'
          : baseNodeStyles.current[n.id]?.boxShadow,
      },
    })));

    setEdges(currentEdges => currentEdges.map(edge => {
      const edgeData = edge.data;
      const onPrimary = primaryPath.has(edge.source) && primaryPath.has(edge.target);
      const isCurrent = Boolean(
        highlightEdges.has(edge.id)
        || (event?.transaction_hash && edgeData?.hash === event.transaction_hash),
      );
      return {
        ...edge,
        animated: showMoneyTrail ? onPrimary : isCurrent,
        style: {
          ...baseEdgeStyles.current[edge.id],
          stroke: isCurrent
            ? '#124343'
            : showMoneyTrail
              ? (onPrimary ? '#396666' : '#c0c8c7')
              : (onPrimary ? '#124343' : '#c0c8c7'),
          strokeWidth: isCurrent ? 3.5 : (showMoneyTrail && onPrimary ? 3 : (onPrimary ? 2.5 : 1.5)),
        },
      };
    }));

    // Keep the right-side inspector and evidence context synchronized with the
    // event currently shown in the replay bar.
    if (event) {
      const transaction = event.transaction_hash
        ? transactions.find(item => item.hash === event.transaction_hash) || null
        : null;
      const supportingEvidence = event.transaction_hash
        ? evidence.find(item => item.transaction_hash === event.transaction_hash) || null
        : null;
      const selectedReplayNode = event.highlight_nodes?.[0]
        ? graphNodeData.current[event.highlight_nodes[0]]
        : undefined;
      void Promise.resolve().then(() => {
        setSelectedTransaction(transaction);
        setSelectedEvidence(supportingEvidence);
        if (selectedReplayNode) setSelectedNode(selectedReplayNode);
      });
    }
  }, [replayStep, replayEvents, transactions, evidence, showMoneyTrail, investigation, setNodes, setEdges]);

  // ─── AI Query ─────────────────────────────────────────────
  const askAI = async (question?: string) => {
    const q = question || aiInput.trim();
    if (!q) return;

    setAiMessages(prev => [...prev, { role: 'user', content: q }]);
    setAiInput('');
    setAiLoading(true);

    try {
      const data = await api.askAI(caseId, q);
      setAiMessages(prev => [...prev, { role: 'assistant', content: data.answer }]);
    } catch {
      setAiMessages(prev => [...prev, { role: 'assistant', content: 'Failed to get response. Please try again.' }]);
    } finally {
      setAiLoading(false);
    }
  };

  const saveTransactionEvidence = async (transaction: TransactionData) => {
    if (!transaction?.hash || savingEvidence) return;
    setSavingEvidence(true);
    setEvidenceMessage('');
    try {
      const saved = await api.saveEvidence(caseId, {
        evidence_type: 'transaction',
        title: `Transaction ${transaction.hash.slice(0, 14)}…`,
        description: `Observed ${transaction.amount?.toFixed?.(4) || transaction.amount} ${transaction.asset || 'ETH'} movement from ${transaction.from_address} to ${transaction.to_address}.`,
        reason: 'Selected by investigator as supporting evidence for the traced money trail.',
        transaction_hash: transaction.hash,
        wallet_address: transaction.to_address,
        source: 'investigator',
      });
      const refreshed = await api.getEvidence(caseId);
      setEvidence(refreshed.evidence || []);
      setSelectedEvidence(saved);
      setEvidenceMessage('Evidence saved to this case.');
    } catch (err) {
      setEvidenceMessage(err instanceof Error ? err.message : 'Unable to save evidence.');
    } finally {
      setSavingEvidence(false);
    }
  };

  const selectEvidence = (item: EvidenceData) => {
    setSelectedEvidence(item);
    if (item.transaction_hash) {
      const transaction = transactions.find(candidate => candidate.hash === item.transaction_hash);
      if (transaction) setSelectedTransaction(transaction);
    }
  };

  // ─── Report ───────────────────────────────────────────────
  const generateReport = async () => {
    setGeneratingReport(true);
    setActionError('');
    try {
      const data = await api.generateReport(caseId);
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
  const onNodeClick = (_: React.MouseEvent, node: Node<GraphNodeData>) => {
    setSelectedNode(node.data);
    setActiveTab('overview');
    void loadWhy(node.data.address);
  };

  const onEdgeClick = (_: React.MouseEvent, edge: Edge<GraphEdgeData>) => {
    const transaction = transactions.find(item => item.hash === edge.data?.hash || item.hash === edge.id);
    if (transaction) {
      setSelectedTransaction(transaction);
      setActiveTab('transactions');
    }
  };

  const selectTransactionByHash = (hash: string) => {
    const transaction = transactions.find(item => item.hash === hash);
    if (!transaction) {
      setActionError('The supporting transaction is not available in this case.');
      return;
    }
    setSelectedTransaction(transaction);
    setActiveTab('transactions');
  };

  const searchGraph = () => {
    const query = graphSearch.trim().toLowerCase();
    if (!query) return;

    const match = nodes.find(node => {
      const address = node.data.address?.toLowerCase() || '';
      const label = typeof node.data.label === 'string' ? node.data.label.toLowerCase() : '';
      return address.includes(query) || label.includes(query);
    });

    if (!match) {
      setGraphSearchMessage('No matching wallet in this investigation.');
      return;
    }

    setGraphSearchMessage('');
    setSelectedNode(match.data);
    setActiveTab('overview');
    void loadWhy(match.data.address);
  };

  const jumpToReplayEvent = async (timelineEvent: TimelineEvent) => {
    setActionError('');
    try {
      const events = await loadReplay();
      const index = events.findIndex(event =>
        (timelineEvent.id && event.event_id === timelineEvent.id)
        || (timelineEvent.transaction_hash && event.transaction_hash === timelineEvent.transaction_hash)
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

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0e17] flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
      </div>
    );
  }

  if (loadError || !caseData) {
    return (
      <div className="min-h-screen bg-[#0a0e17] flex items-center justify-center px-6">
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

  const hasInvestigation = nodes.length > 0;
  const riskBadge = getRiskBadge(investigation?.risk?.overall || caseData?.summary?.risk_level || 'low');

  return (
    <div className="ct-investigation-shell h-screen bg-[#0a0e17] flex flex-col overflow-hidden">
      {/* ─── Top Bar ────────────────────────────────────────── */}
      <header className="ct-investigation-header h-12 border-b border-[#1e293b] bg-[#111827]/90 backdrop-blur-sm flex items-center px-4 justify-between shrink-0">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push('/dashboard')} className="p-1 rounded hover:bg-[#1e293b] text-slate-400 hover:text-white">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <div className="w-6 h-6 rounded bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
            <Shield className="w-3.5 h-3.5 text-white" />
          </div>
          <span className="font-bold text-white text-sm">CryptoTrace AI</span>
          <span className="text-slate-600">|</span>
          <span className="font-mono text-xs text-slate-400">{caseData?.case_number}</span>
          <span className="max-w-32 truncate font-mono text-[10px] text-blue-300" title={caseData?.reported_wallet}>{caseData?.reported_wallet}</span>
          <span className="text-[10px] uppercase text-slate-500">{caseData?.blockchain || 'network unknown'}</span>
          <span className="text-[10px] uppercase text-slate-400">{caseData?.status}</span>
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium border ${riskBadge.bg} ${riskBadge.text}`}>
            {(investigation?.risk?.overall || caseData?.summary?.risk_level || 'PENDING').toUpperCase()} RISK
          </span>
          {caseData?.is_demo && (
            <span className="text-[10px] px-2 py-0.5 bg-amber-500/10 text-amber-400 rounded-full border border-amber-500/20">
              DEMO DATA
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!hasInvestigation ? (
            <button
              onClick={runInvestigation}
              disabled={investigating}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-gradient-to-r from-blue-600 to-cyan-600 text-white rounded-lg text-xs font-medium
                hover:from-blue-500 hover:to-cyan-500 disabled:opacity-50 shadow-lg shadow-blue-500/20"
            >
              {investigating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />}
              {investigating ? 'Investigating...' : 'INVESTIGATE'}
            </button>
          ) : (
            <>
              <button onClick={startReplay}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1e293b] text-cyan-400 rounded-lg text-xs font-medium hover:bg-[#2a3548] border border-[#2a3548]">
                <Play className="w-3 h-3" /> REPLAY
              </button>
              <button onClick={() => setActiveTab('ai')}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1e293b] text-purple-400 rounded-lg text-xs font-medium hover:bg-[#2a3548] border border-[#2a3548]">
                <MessageSquare className="w-3 h-3" /> ASK AI
              </button>
              <button onClick={generateReport} disabled={generatingReport}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1e293b] text-green-400 rounded-lg text-xs font-medium hover:bg-[#2a3548] border border-[#2a3548]">
                {generatingReport ? <Loader2 className="w-3 h-3 animate-spin" /> : <FileText className="w-3 h-3" />}
                REPORT
              </button>
            </>
          )}
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

      {/* ─── Main Content ──────────────────────────────────── */}
      <div className="ct-investigation-main flex flex-1 overflow-hidden">
        {/* ─── Left Panel ──────────────────────────────────── */}
        <div className="ct-investigation-nav w-56 border-r border-[#1e293b] bg-[#111827]/50 flex flex-col shrink-0 overflow-y-auto">
          <div className="p-3">
            <div className="text-[10px] uppercase tracking-widest text-slate-500 font-medium mb-2">Navigation</div>
            {[
              { id: 'overview', icon: Eye, label: 'Overview' },
              { id: 'wallets', icon: Shield, label: 'Wallets', count: caseData?.summary?.total_wallets },
              { id: 'transactions', icon: ArrowRight, label: 'Transactions', count: caseData?.summary?.total_transactions },
              { id: 'findings', icon: AlertTriangle, label: 'Findings', count: findings.length },
              { id: 'evidence', icon: Bookmark, label: 'Evidence', count: evidence.length },
              { id: 'timeline', icon: Activity, label: 'Timeline', count: timeline.length },
              { id: 'audit', icon: ClipboardList, label: 'Audit Log', count: auditEvents.length },
              { id: 'ai', icon: MessageSquare, label: 'AI Copilot' },
              { id: 'report', icon: FileText, label: 'Report' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs mb-0.5 transition-all
                  ${activeTab === tab.id ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' : 'text-slate-400 hover:bg-[#1e293b] hover:text-white'}`}
              >
                <tab.icon className="w-3.5 h-3.5" />
                <span className="flex-1 text-left">{tab.label}</span>
                {tab.count != null && tab.count > 0 && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-[#1e293b] rounded-full text-slate-500">{tab.count}</span>
                )}
              </button>
            ))}
          </div>

          {/* Money Trail Button */}
          {hasInvestigation && (
            <div className="p-3 mt-auto border-t border-[#1e293b]">
              <button
                onClick={() => setShowMoneyTrail(!showMoneyTrail)}
                className={`w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-xs font-bold transition-all
                  ${showMoneyTrail
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/30'
                    : 'bg-blue-500/10 text-blue-400 border border-blue-500/30 hover:bg-blue-500/20'
                  }`}
              >
                <Crosshair className="w-3.5 h-3.5" />
                FOCUS MONEY TRAIL
              </button>
            </div>
          )}
        </div>

        {/* ─── Center: Graph ───────────────────────────────── */}
        <div className="ct-investigation-graph flex-1 flex flex-col relative">
          {!hasInvestigation ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <div className="w-20 h-20 rounded-2xl bg-[#111827] border border-[#1e293b] flex items-center justify-center mx-auto mb-4">
                  <Search className="w-10 h-10 text-slate-600" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">Ready to Investigate</h3>
                <p className="text-slate-400 text-sm mb-1">Wallet: <span className="font-mono text-blue-400">{caseData?.reported_wallet}</span></p>
                <p className="text-slate-500 text-xs mb-6">Click INVESTIGATE to trace blockchain transactions</p>
                <button
                  onClick={runInvestigation}
                  disabled={investigating}
                  className="px-8 py-3 bg-gradient-to-r from-blue-600 to-cyan-600 text-white rounded-xl font-medium text-sm
                    shadow-xl shadow-blue-500/30 hover:from-blue-500 hover:to-cyan-500 disabled:opacity-50"
                >
                  {investigating ? (
                    <span className="flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Running Investigation...</span>
                  ) : (
                    <span className="flex items-center gap-2"><Search className="w-4 h-4" /> INVESTIGATE</span>
                  )}
                </button>
              </div>
            </div>
          ) : (
            <div className="flex-1 relative" style={{ height: '100%' }}>
              <div className="absolute top-3 right-3 z-10 hidden sm:block rounded border border-[#2a3548] bg-[#111827]/95 px-3 py-2 shadow-xl">
                <div className="text-[10px] uppercase tracking-widest text-slate-500 font-medium">Transaction flow topology</div>
                <div className="mt-1 text-[10px] text-slate-400 font-mono">{nodes.length} wallets · {edges.length} transfers</div>
              </div>
              <form
                onSubmit={(event) => { event.preventDefault(); searchGraph(); }}
                className="absolute top-3 left-3 z-10 flex items-center gap-1 rounded-lg border border-[#2a3548] bg-[#111827]/95 p-1 shadow-xl"
              >
                <Search className="ml-2 h-3.5 w-3.5 text-slate-500" />
                <input
                  value={graphSearch}
                  onChange={(event) => { setGraphSearch(event.target.value); setGraphSearchMessage(''); }}
                  placeholder="Search wallet"
                  aria-label="Search wallet in graph"
                  className="w-36 bg-transparent px-2 py-1.5 text-[11px] text-white outline-none placeholder:text-slate-600"
                />
                <button type="submit" className="rounded-md bg-blue-500/15 px-2 py-1.5 text-[10px] font-medium text-blue-300 hover:bg-blue-500/25">
                  FIND
                </button>
              </form>
              {graphSearchMessage && (
                <div className="absolute left-3 top-14 z-10 rounded-md border border-amber-500/20 bg-[#111827]/95 px-2.5 py-1.5 text-[10px] text-amber-300 shadow-lg">
                  {graphSearchMessage}
                </div>
              )}
              {investigation?.stats?.trace_status === 'partial' && (
                <div className="absolute left-3 top-24 z-10 max-w-sm rounded-md border border-amber-500/30 bg-amber-950/80 px-3 py-2 text-[10px] text-amber-200 shadow-lg">
                  <div className="font-bold uppercase tracking-wide">Trace incomplete</div>
                  <div className="mt-0.5">{investigation.stats.trace_warning || 'Provider data was incomplete; results may be incomplete.'}</div>
                </div>
              )}
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                onEdgeClick={onEdgeClick}
                fitView
                fitViewOptions={{ padding: 0.3 }}
                minZoom={0.3}
                maxZoom={2}
                attributionPosition="bottom-left"
              >
                <Background color="#dfe4e2" gap={40} size={1} />
                <Controls position="bottom-right" />
                <MiniMap
                  position="bottom-left"
                  nodeColor={(n) => getNodeColor(n.data)}
                  maskColor="#fafaf5cc"
                />
              </ReactFlow>
            </div>
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
        <div className="ct-investigation-inspector w-80 border-l border-[#1e293b] bg-[#111827]/50 overflow-y-auto shrink-0">
          {replayStep >= 0 && replayEvents[replayStep] && (
            <div className="p-3 border-b border-cyan-500/20 bg-cyan-500/5">
              <div className="text-[10px] uppercase tracking-widest text-cyan-400 font-medium mb-1">Replay context</div>
              <div className="text-xs text-white font-medium truncate">{replayEvents[replayStep].title}</div>
              <div className="text-[10px] text-slate-500 mt-1">{replayEvents[replayStep].timestamp ? new Date(replayEvents[replayStep].timestamp).toLocaleString() : 'Timestamp unavailable'}</div>
              {selectedTransaction && <div className="text-[10px] text-blue-300 font-mono truncate mt-1">TX {selectedTransaction.hash}</div>}
              {selectedEvidence && <div className="text-[10px] text-amber-300 truncate mt-1">Evidence: {selectedEvidence.title}</div>}
            </div>
          )}
          {activeTab === 'overview' && hasInvestigation && (
            <div className="p-4 space-y-4 animate-fade-in">
              <h3 className="text-sm font-bold text-white">Investigation Summary</h3>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: 'Wallets', value: caseData?.summary?.total_wallets || nodes.length },
                  { label: 'Transactions', value: caseData?.summary?.total_transactions || edges.length },
                  { label: 'Findings', value: findings.length },
                  { label: 'Evidence', value: evidence.length },
                ].map(s => (
                  <div key={s.label} className="bg-[#0a0e17] rounded-lg p-3 border border-[#1e293b]">
                    <div className="text-lg font-bold text-white">{s.value}</div>
                    <div className="text-[10px] text-slate-500">{s.label}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'overview' && selectedNode && (
            <div className="p-4 space-y-3 border-t border-[#1e293b] animate-slide-in">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-white">Wallet Inspector</h3>
                <button onClick={() => setSelectedNode(null)} className="text-slate-500 hover:text-white">
                  <XCircle className="w-4 h-4" />
                </button>
              </div>
              <div className="bg-[#0a0e17] rounded-lg p-3 border border-[#1e293b]">
                <div className="text-[10px] text-slate-500 mb-1">Address</div>
                <div className="text-xs font-mono text-blue-400 break-all">{selectedNode.address}</div>
              </div>
              {selectedNode.label && (
                <div className="bg-[#0a0e17] rounded-lg p-3 border border-[#1e293b]">
                  <div className="text-[10px] text-slate-500 mb-1">Label</div>
                  <div className="text-xs text-white">{selectedNode.label}</div>
                </div>
              )}
              {(selectedNode.risk_category || selectedNode.risk_score != null) && (
                <div className="bg-[#0a0e17] rounded-lg p-3 border border-red-500/20">
                  <div className="text-[10px] uppercase tracking-widest text-red-300 font-medium mb-1">Risk assessment</div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-white">{selectedNode.risk_category?.toUpperCase() || 'UNASSESSED'}</span>
                    {selectedNode.risk_score != null && <span className="text-xs text-red-300 font-mono">{selectedNode.risk_score}/100</span>}
                  </div>
                  {(selectedNode.risk_signals ?? []).slice(0, 3).map((signal, i) => (
                    <div key={i} className="text-[10px] text-slate-400 mt-1">{signal.signal_name || 'Signal'}{signal.score_contribution != null ? ` (+${signal.score_contribution})` : ''}</div>
                  ))}
                </div>
              )}
              {selectedNode.vasp_name && (
                <div className="bg-[#0a0e17] rounded-lg p-3 border border-purple-500/20">
                  <div className="text-[10px] uppercase tracking-widest text-purple-300 font-medium mb-1">Attribution</div>
                  <div className="text-xs text-white">{selectedNode.vasp_name}</div>
                  <div className="text-[10px] text-slate-400 mt-1">
                    {(selectedNode.vasp_confidence || 'unknown').toUpperCase()} · {selectedNode.vasp_attribution_type || 'unclassified'}
                  </div>
                  {selectedNode.vasp_source && <div className="text-[10px] text-slate-500 mt-1">Source: {selectedNode.vasp_source}</div>}
                  {selectedNode.vasp_supporting_evidence && <p className="text-[10px] text-slate-400 mt-1">{selectedNode.vasp_supporting_evidence}</p>}
                </div>
              )}
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-[#0a0e17] rounded-lg p-2 border border-[#1e293b]">
                  <div className="text-[10px] text-slate-500">Received</div>
                  <div className="text-xs text-green-400 font-mono">{selectedNode.total_received?.toFixed(4)}</div>
                </div>
                <div className="bg-[#0a0e17] rounded-lg p-2 border border-[#1e293b]">
                  <div className="text-[10px] text-slate-500">Sent</div>
                  <div className="text-xs text-red-400 font-mono">{selectedNode.total_sent?.toFixed(4)}</div>
                </div>
              </div>

              {/* WHY? Button */}
              <button
                onClick={() => selectedNode?.address && loadWhy(selectedNode.address)}
                disabled={loadingWhy}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-amber-500/10 text-amber-400
                  border border-amber-500/30 rounded-lg text-xs font-bold hover:bg-amber-500/20 transition-all"
              >
                {loadingWhy ? <Loader2 className="w-3 h-3 animate-spin" /> : <AlertTriangle className="w-3.5 h-3.5" />}
                WHY WAS THIS FLAGGED?
              </button>

              {/* WHY? Result */}
              {whyData && whyData.wallet_address === selectedNode.address && (
                <div className="space-y-2 animate-fade-in">
                  <div className="text-[10px] uppercase tracking-widest text-amber-400 font-medium">Reasons</div>
                  {whyData.reasons?.map((r: string, i: number) => (
                    <div key={i} className="bg-amber-500/5 border border-amber-500/10 rounded-lg p-2.5">
                      <p className="text-xs text-slate-300">{r}</p>
                    </div>
                  ))}
                  {(whyData.findings ?? []).length > 0 && (
                    <>
                      <div className="text-[10px] uppercase tracking-widest text-slate-500 font-medium mt-3">Supporting Findings</div>
                      {(whyData.findings ?? []).map((f, i: number) => (
                        <div key={i} className="bg-[#0a0e17] border border-[#1e293b] rounded-lg p-2.5">
                          <div className="flex items-center gap-2 mb-1">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium border
                              ${f.severity === 'high' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20'}`}>
                              {f.severity?.toUpperCase()}
                            </span>
                            <span className="text-[10px] text-slate-400">{f.pattern_name}</span>
                          </div>
                          <p className="text-[11px] text-slate-300">{f.description}</p>
                        </div>
                      ))}
                    </>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === 'transactions' && selectedTransaction && (
            <div className="p-4 border-b border-[#1e293b] animate-fade-in">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-bold text-white">Selected Transaction</h3>
                <button onClick={() => setSelectedTransaction(null)} className="text-slate-500 hover:text-white"><XCircle className="w-4 h-4" /></button>
              </div>
              <div className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-3 space-y-1.5">
                <div className="text-[10px] text-blue-300 font-mono break-all">{selectedTransaction.hash}</div>
                <div className="text-xs text-white font-mono">{selectedTransaction.amount.toFixed(4)} {selectedTransaction.asset}</div>
                <div className="text-[10px] text-slate-400 break-all">{selectedTransaction.from_address} → {selectedTransaction.to_address}</div>
                <button onClick={() => saveTransactionEvidence(selectedTransaction)} disabled={savingEvidence} className="mt-1 inline-flex items-center gap-1.5 text-[10px] text-cyan-400 hover:text-cyan-300 disabled:opacity-50"><Bookmark className="w-3 h-3" /> SAVE EVIDENCE</button>
              </div>
            </div>
          )}

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
              {findings.length === 0 ? (
                <p className="text-xs text-slate-500">No findings yet. Run investigation first.</p>
              ) : findings.map((f, i) => (
                <div key={i} className="bg-[#0a0e17] border border-[#1e293b] rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                    <span className="text-xs font-medium text-white">{f.pattern_name}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium border ml-auto
                      ${f.severity === 'high' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20'}`}>
                      {f.severity?.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 leading-relaxed">{f.description}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px]">
                    <span className="px-1.5 py-0.5 rounded border border-blue-500/20 bg-blue-500/10 text-blue-400">DETERMINISTIC ANALYSIS</span>
                    <span className="text-slate-600">Confidence: {(f.confidence * 100).toFixed(0)}%</span>
                  </div>
                  {(f.supporting_transaction_ids ?? []).length > 0 && (
                    <div className="mt-2 border-t border-[#1e293b] pt-2">
                      <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-1">Supporting transactions</div>
                      <div className="flex flex-wrap gap-1.5">
                        {(f.supporting_transaction_ids ?? []).slice(0, 4).map((hash) => (
                          <button
                            key={hash}
                            type="button"
                            onClick={() => selectTransactionByHash(hash)}
                            className="rounded border border-[#2a3548] px-2 py-1 font-mono text-[10px] text-blue-400 hover:border-blue-500/40 hover:text-blue-300"
                          >
                            TX {hash.slice(0, 12)}…
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
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
                <Bookmark className="w-4 h-4 text-slate-500" />
              </div>
              {selectedEvidence && (
                <div className="bg-cyan-500/5 border border-cyan-500/20 rounded-lg p-3">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <div className="text-[10px] uppercase tracking-widest text-cyan-400 font-medium">Selected evidence</div>
                    <span className="text-[9px] px-1.5 py-0.5 rounded border border-blue-500/20 bg-blue-500/10 text-blue-400">FACT</span>
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
                <p className="text-xs text-slate-500">No evidence yet. Run investigation first.</p>
              ) : evidence.map((e, i) => (
                <button key={e.id || i} onClick={() => selectEvidence(e)} aria-pressed={selectedEvidence?.id === e.id} className={`w-full text-left bg-[#0a0e17] border rounded-lg p-3 ${selectedEvidence?.id === e.id ? 'border-cyan-500/40' : 'border-[#1e293b]'}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <Bookmark className="w-3 h-3 text-blue-400" />
                    <span className="text-xs font-medium text-white">{e.title}</span>
                    <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded border border-blue-500/20 bg-blue-500/10 text-blue-400">FACT</span>
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
              <h3 className="text-sm font-bold text-white mb-3">Investigation Timeline</h3>
              <div className="space-y-0">
                {timeline.map((e, i) => (
                  <button key={i} onClick={() => jumpToReplayEvent(e)} className={`w-full text-left flex gap-3 group rounded-lg ${replayEvents[replayStep]?.transaction_hash && replayEvents[replayStep]?.transaction_hash === e.transaction_hash ? 'bg-blue-500/5' : ''}`}>
                    <div className="flex flex-col items-center">
                      <div className="w-2.5 h-2.5 rounded-full bg-blue-500 border-2 border-[#111827] z-10" />
                      {i < timeline.length - 1 && <div className="w-0.5 flex-1 bg-[#1e293b]" />}
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
                    <div key={event.id} className="bg-[#0a0e17] border border-[#1e293b] rounded-lg p-3">
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
                        <div className="mt-1.5 break-words font-mono text-[10px] text-slate-500">
                          {JSON.stringify(event.details)}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Transactions Tab */}
          {activeTab === 'transactions' && (
            <div className="p-4 animate-fade-in">
              <h3 className="text-sm font-bold text-white mb-3">Transactions</h3>
              <div className="space-y-2">
                {transactions.map((t, i) => (
                  <div
                    key={t.id || t.hash || i}
                    role="button"
                    tabIndex={0}
                    aria-pressed={selectedTransaction?.hash === t.hash}
                    aria-label={`Select transaction ${t.hash}`}
                    onClick={() => { setSelectedTransaction(t); setActiveTab('transactions'); }}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        setSelectedTransaction(t);
                        setActiveTab('transactions');
                      }
                    }}
                    className={`bg-[#0a0e17] border rounded-lg p-2.5 cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500
                      ${selectedTransaction?.hash === t.hash ? 'border-blue-500/50' : 'border-[#1e293b] hover:border-blue-500/30'}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] font-mono text-blue-400">{t.hash?.slice(0, 20)}...</span>
                      <span className="text-[10px] text-slate-500">Hop {t.hop_number}</span>
                    </div>
                    <div className="text-[10px] text-slate-400">
                      {t.from_address?.slice(0, 12)}... → {t.to_address?.slice(0, 12)}...
                    </div>
                    <div className="text-xs text-white font-mono mt-0.5">{t.amount?.toFixed(4)} {t.asset}</div>
                    <div className="mt-1 text-[10px] text-slate-500">
                      {t.timestamp ? new Date(t.timestamp).toLocaleString() : 'Timestamp unavailable'}
                      {t.source ? ` · ${t.source}` : ''}
                    </div>
                    <button
                      onClick={(event) => { event.stopPropagation(); void saveTransactionEvidence(t); }}
                      disabled={savingEvidence}
                      className="mt-2 inline-flex items-center gap-1.5 text-[10px] text-blue-400 hover:text-blue-300 disabled:opacity-50"
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
              <div className="p-4 border-b border-[#1e293b]">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-bold text-white">AI Investigation Copilot</h3>
                    <p className="text-[10px] text-slate-500 mt-0.5">Grounded in this case&apos;s findings, flow, and evidence</p>
                  </div>
                  <span className="text-[9px] px-1.5 py-0.5 rounded border border-purple-500/20 bg-purple-500/10 text-purple-400">AI SUMMARY</span>
                </div>
                {caseData?.is_demo && <p className="mt-2 text-[10px] text-amber-400">DEMO DATA context · verify conclusions against the evidence trail.</p>}
              </div>

              {/* Suggested Questions */}
              {aiMessages.length === 0 && (
                <div className="p-4 space-y-2">
                  {[
                    'Where did the money go?',
                    'What suspicious patterns were detected?',
                    'Which wallets are intermediaries?',
                    'Summarize the investigation.',
                  ].map((q) => (
                    <button key={q} onClick={() => askAI(q)}
                      className="w-full min-h-10 text-left px-3 py-2 bg-[#0a0e17] border border-[#1e293b] rounded-lg text-xs text-slate-400 hover:text-white hover:border-blue-500/30 transition-colors">
                      {q}
                    </button>
                  ))}
                </div>
              )}

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {aiMessages.map((msg, i) => (
                  <div key={i} className={`${msg.role === 'user' ? 'text-right' : ''}`}>
                    <div className={`inline-block max-w-[90%] px-3 py-2 rounded-lg text-xs leading-relaxed
                      ${msg.role === 'user'
                        ? 'bg-blue-600/20 text-blue-200 border border-blue-500/20'
                        : 'bg-[#0a0e17] text-slate-300 border border-[#1e293b]'
                      }`}
                    >
                      <div className="whitespace-pre-wrap">{msg.content}</div>
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
              <div className="p-3 border-t border-[#1e293b]">
                <div className="flex gap-2">
                  <input
                    value={aiInput}
                    onChange={(e) => setAiInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && askAI()}
                    aria-label="Ask the investigation copilot"
                    placeholder="Ask about the investigation..."
                    className="flex-1 px-3 py-2 bg-[#0a0e17] border border-[#2a3548] rounded-lg text-xs text-white
                      focus:outline-none focus:border-blue-500 placeholder:text-slate-600"
                  />
                  <button type="button" onClick={() => askAI()} aria-label="Send question to investigation copilot" className="min-h-10 min-w-10 flex items-center justify-center p-2 bg-blue-600 rounded-lg text-white hover:bg-blue-500">
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
                  <p className="text-[10px] text-slate-600 mb-4">Generate a report after reviewing the case evidence.</p>
                  <button onClick={generateReport} disabled={generatingReport}
                    className="px-4 py-2 bg-green-600/20 text-green-400 border border-green-500/30 rounded-lg text-xs font-medium hover:bg-green-600/30">
                    {generatingReport ? 'Generating...' : 'Generate Report'}
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="text-xs text-slate-400 mb-2">{report.title}</div>
                  {report.sections?.map((s, i: number) => (
                    <div key={i} className="bg-[#0a0e17] border border-[#1e293b] rounded-lg p-3">
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
                    </div>
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
                      onClick={() => { setSelectedNode(d); setActiveTab('overview'); loadWhy(d.address); }}
                      className="w-full text-left bg-[#0a0e17] border border-[#1e293b] rounded-lg p-3 hover:border-blue-500/30 transition-colors"
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
    </div>
  );
}
