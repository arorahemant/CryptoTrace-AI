'use client';

import { memo, useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import ReactFlow, { Background, Controls, Handle, Position, MarkerType, BaseEdge, EdgeLabelRenderer, useReactFlow, type NodeProps, type EdgeProps } from 'reactflow';
import { displayAmount } from '@/lib/transfers';
import { boundaryLabel, layoutGraph, selectedPath, shortAddress, walletRole, type TrailGraph, type TrailSelection, type TrailWallet, type TrailTransfer } from '@/lib/investigation';
import 'reactflow/dist/style.css';

const Network3D = dynamic(() => import('./Network3D'), { ssr: false, loading: () => <p role="status" className="p-4">Loading network view…</p> });
const WalletNode = memo(function WalletNode({ data }: NodeProps<{ wallet: TrailWallet; destination?: string; select: (address: string) => void }>) {
  return <div className="trail-wallet-card">
    <Handle type="target" position={Position.Left} />
    <button className="nodrag nopan" onClick={event => { event.stopPropagation(); data.select(data.wallet.address); }} aria-label={`Inspect wallet ${data.wallet.address}`}><strong>{walletRole(data.wallet, data.destination)}</strong></button>
    <span className="font-mono">{shortAddress(data.wallet.address)}</span>
    <small>{boundaryLabel(data.wallet)}</small>
    {data.wallet.vasp_name && <small>{data.wallet.vasp_name} · {data.wallet.vasp_attribution_status === 'known_verified' ? 'VERIFIED' : 'INFERRED / REVIEW'}</small>}
    <Handle type="source" position={Position.Right} />
  </div>;
});
function TransferEdge({ id, sourceX, sourceY, targetX, targetY, data, markerEnd, style }: EdgeProps<{ transfer: TrailTransfer; offset: number; select: (id: string) => void }>) {
  const middleX = (sourceX + targetX) / 2, middleY = (sourceY + targetY) / 2 + (data?.offset || 0);
  const d = `M${sourceX},${sourceY} Q${middleX},${middleY} ${targetX},${targetY}`;
  return <><BaseEdge id={id} path={d} markerEnd={markerEnd} style={style} interactionWidth={22} />
    <EdgeLabelRenderer><button className="trail-transfer-label nodrag nopan" style={{ transform: `translate(-50%, -50%) translate(${middleX}px,${(sourceY + targetY) / 2 + (data?.offset || 0) / 2}px)` }} onClick={() => data?.select(id)} aria-label={`Inspect transfer ${data ? displayAmount(data.transfer) : ''} ${data?.transfer.asset || ''}, ${id}`}>
      <strong>{data ? displayAmount(data.transfer) : 'Unavailable'} {data?.transfer.asset}</strong>
      <span>{data?.transfer.timestamp ? new Date(data.transfer.timestamp).toLocaleString() : 'Timestamp unavailable'}</span>
    </button></EdgeLabelRenderer></>;
}
const nodeTypes = { wallet: WalletNode };
const edgeTypes = { transfer: TransferEdge };

export const TrailWorkspace = memo(function TrailWorkspace({ graph, selection, onWallet, onTransfer, focusVersion, isolateRequested }: {
  graph: TrailGraph; selection: TrailSelection | null; onWallet: (address: string) => void; onTransfer: (id: string) => void;
  focusVersion: number; isolateRequested: boolean;
}) {
  const [view, setView] = useState<'2d' | '3d'>('2d');
  const [isolation, setIsolation] = useState({ version: focusVersion, value: false });
  const isolate = isolation.version === focusVersion ? isolation.value : isolateRequested;
  const setIsolate = (value: boolean) => setIsolation({ version: focusVersion, value });
  const [query, setQuery] = useState('');
  const [message, setMessage] = useState('');
  const [focus, setFocus] = useState(0);
  const flow = useReactFlow();
  const path = useMemo(() => selectedPath(graph, selection), [graph, selection]);
  const layout = useMemo(() => layoutGraph(graph), [graph]);
  const nodes = useMemo(() => layout.map(({ node, x, y }) => ({
    id: node.address, type: 'wallet', position: { x, y }, data: { wallet: node, destination: graph.destination?.address, select: onWallet },
    hidden: isolate && !path.wallets.has(node.address),
    className: `${path.wallets.has(node.address) ? 'trail-node-active' : ''} ${node.expansion_state !== 'expanded' ? 'trail-node-boundary' : ''}`,
    ariaLabel: `${walletRole(node, graph.destination?.address)} ${node.address}. ${boundaryLabel(node)}`,
  })), [layout, graph.destination, isolate, path, onWallet]);
  const edges = useMemo(() => graph.edges.map(edge => {
    const peers = graph.edges.filter(e => e.source === edge.source && e.target === edge.target);
    return { id: edge.id, source: edge.source, target: edge.target, type: 'transfer',
      data: { transfer: edge, offset: (peers.indexOf(edge) - (peers.length - 1) / 2) * 100, select: onTransfer },
      hidden: isolate && !path.transfers.has(edge.id),
      style: { stroke: path.transfers.has(edge.id) ? '#245b65' : '#a3adb4', strokeWidth: path.transfers.has(edge.id) ? 2.5 : 1.5 },
      markerEnd: { type: MarkerType.ArrowClosed, color: path.transfers.has(edge.id) ? '#245b65' : '#a3adb4' },
    };
  }), [graph.edges, path, isolate, onTransfer]);
  const focusSelection = () => {
    setFocus(value => value + 1);
    void flow.fitView({ nodes: nodes.filter(node => path.wallets.has(node.id)), padding: 0.3, duration: 0 });
  };
  useEffect(() => {
    if (!focusVersion) return;
    void flow.fitView({ nodes: nodes.filter(node => path.wallets.has(node.id)), padding: 0.3, duration: 0 });
    // A focus command is explicit; selection alone must not reset the camera.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusVersion]);
  return <section className="trail-workspace" aria-label="Investigation trail" data-run-id={graph.run_id || 'unavailable'}>
    <div className="trail-toolbar">
      <div className="trail-view-toggle" role="group" aria-label="Graph view">
        <button aria-pressed={view === '2d'} onClick={() => setView('2d')}>2D TRAIL</button>
        <button aria-pressed={view === '3d'} onClick={() => setView('3d')}>3D NETWORK</button>
      </div>
      <form onSubmit={event => { event.preventDefault(); const match = graph.nodes.find(node => node.address.toLowerCase().includes(query.trim().toLowerCase())); if (query.trim() && match) { onWallet(match.address); setMessage(''); } else setMessage('No matching wallet in this run.'); }}>
        <input aria-label="Search wallet in graph" placeholder="Find a wallet" value={query} onChange={event => setQuery(event.target.value)} /><button type="submit">Find</button>
      </form>
    </div>
    <div className="trail-toolbar trail-tools">
      <button aria-pressed={isolate} onClick={() => setIsolate(true)} disabled={!path.wallets.size}>Show selected path</button>
      <button aria-pressed={!isolate} onClick={() => setIsolate(false)}>Show all transfers</button>
      <button onClick={focusSelection} disabled={!path.wallets.size}>Focus selection</button>
      <span>{graph.nodes.length} wallets · {graph.edges.length} transfers</span>
    </div>
    {message && <p role="status" className="trail-notice">{message}</p>}
    <div className="trail-selection-label" aria-live="polite">{selection?.label || 'Candidate route'} · Observed connections; shared ownership and fund continuity are not established.</div>
    {graph.primary_path.length > 0 && <ol className="trail-route" aria-label="Candidate destination route">
      {graph.primary_path.map((address, index) => {
        const wallet = graph.nodes.find(node => node.address === address);
        if (!wallet) return null;
        return <li key={address}>{index > 0 && <span aria-hidden="true">→</span>}<button onClick={() => onWallet(address)} aria-pressed={selection?.wallets.includes(address) || false}><strong>{walletRole(wallet, graph.destination?.address)}</strong><small>{shortAddress(address)}</small></button></li>;
      })}
    </ol>}
    <div className="trail-canvas">
      {view === '2d' ? <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} onNodeClick={(_, node) => onWallet(node.id)} onEdgeClick={(_, edge) => onTransfer(edge.id)} nodesDraggable={false} nodesConnectable={false} deleteKeyCode={null} fitView fitViewOptions={{ padding: 0.25, minZoom: 0.02 }} minZoom={0.02} maxZoom={1.5} aria-label="2D money trail">
        <Background color="#dce1e5" gap={28} size={1} /><Controls showInteractive={false} />
      </ReactFlow> : <Network3D graph={graph} path={path} selection={selection} isolate={isolate} focus={focus + focusVersion} onWallet={onWallet} onTransfer={onTransfer} />}
    </div>
    <div className="trail-legend" aria-label="Graph legend"><span>● Reported wallet</span><span>○ Intermediary / candidate</span><span>━ Selected path</span><span>┄ Not expanded / limited</span><span>Click a wallet or transfer to inspect</span></div>
  </section>;
});
