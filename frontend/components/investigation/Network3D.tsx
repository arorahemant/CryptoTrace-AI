'use client';

import { memo, useMemo, useRef, useState } from 'react';
import { layoutGraph, projectPoint, shortAddress, walletRole, boundaryLabel, type TrailGraph, type TrailSelection } from '@/lib/investigation';
import { displayAmount } from '@/lib/transfers';

interface Props {
  graph: TrailGraph;
  path: { wallets: Set<string>; transfers: Set<string> };
  isolate: boolean;
  selection: TrailSelection | null;
  focus: number;
  onWallet: (address: string) => void;
  onTransfer: (id: string) => void;
}

function Scene({ graph, path, isolate, selection, focus, onWallet, onTransfer }: Props) {
  const layout = useMemo(() => layoutGraph(graph), [graph]);
  const [camera, setCamera] = useState({ yaw: -0.28, pitch: 0.18, zoom: 0.72, x: 0, y: 0 });
  const [panMode, setPanMode] = useState(false);
  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  const focusNode = layout.find(item => item.node.address === selection?.wallets[0]);
  const graphCenter = Math.max(0, ...layout.map(item => item.x)) / 2;
  const [center, setCenter] = useState(() => ({ x: focus ? focusNode?.x ?? graphCenter : graphCenter, y: focus ? focusNode?.y ?? 0 : 0 }));
  const centerX = center.x, centerY = center.y;
  const points = layout.map(item => ({ ...item, projected: projectPoint({ x: item.x - centerX, y: item.y - centerY, z: item.z }, camera.yaw, camera.pitch, camera.zoom) }));
  const byAddress = new Map(points.map(point => [point.node.address, point]));
  const activate = (event: React.KeyboardEvent, action: () => void) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); action(); } };
  return <div className="trail-three">
    <div className="trail-camera" aria-label="3D camera controls">
      <button aria-pressed={!panMode} onClick={() => setPanMode(false)}>Rotate</button>
      <button aria-pressed={panMode} onClick={() => setPanMode(true)}>Pan</button>
      <button aria-label="Rotate network left" onClick={() => setCamera(c => ({ ...c, yaw: c.yaw - 0.2 }))}>↶</button>
      <button aria-label="Rotate network right" onClick={() => setCamera(c => ({ ...c, yaw: c.yaw + 0.2 }))}>↷</button>
      <button aria-label="Zoom in 3D network" onClick={() => setCamera(c => ({ ...c, zoom: Math.min(2, c.zoom * 1.2) }))}>+</button>
      <button aria-label="Zoom out 3D network" onClick={() => setCamera(c => ({ ...c, zoom: Math.max(0.1, c.zoom / 1.2) }))}>−</button>
      <button onClick={() => { setCamera({ yaw: -0.28, pitch: 0.18, zoom: 0.72, x: 0, y: 0 }); setCenter({ x: graphCenter, y: 0 }); }}>Reset camera</button>
    </div>
    <svg viewBox="0 0 1000 650" className="trail-three-scene" aria-label="3D projected investigation network. Drag to rotate; select Pan to move. Arrow keys rotate; Shift and arrows pan." tabIndex={0}
      onKeyDown={event => {
        if (event.target !== event.currentTarget || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
        event.preventDefault();
        const horizontal = event.key === 'ArrowLeft' ? -1 : event.key === 'ArrowRight' ? 1 : 0;
        const vertical = event.key === 'ArrowUp' ? -1 : event.key === 'ArrowDown' ? 1 : 0;
        setCamera(c => event.shiftKey ? { ...c, x: c.x + horizontal * 30, y: c.y + vertical * 30 } : { ...c, yaw: c.yaw + horizontal * 0.1, pitch: Math.max(-1.2, Math.min(1.2, c.pitch + vertical * 0.1)) });
      }}
      onPointerDown={event => { if ((event.target as Element).closest('[role="button"]')) return; drag.current = { x: event.clientX, y: event.clientY, moved: false }; event.currentTarget.setPointerCapture(event.pointerId); }}
      onPointerMove={event => {
        if (!drag.current) return;
        const dx = event.clientX - drag.current.x, dy = event.clientY - drag.current.y;
        drag.current = { x: event.clientX, y: event.clientY, moved: true };
        setCamera(c => panMode || event.shiftKey ? { ...c, x: c.x + dx, y: c.y + dy } : { ...c, yaw: c.yaw + dx * 0.006, pitch: Math.max(-1.2, Math.min(1.2, c.pitch + dy * 0.006)) });
      }}
      onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
      <defs><marker id="network-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke" /></marker></defs>
      <g transform={`translate(${500 + camera.x} ${325 + camera.y})`}>
        {graph.edges.map((edge, index) => {
          const source = byAddress.get(edge.source)?.projected, target = byAddress.get(edge.target)?.projected;
          if (!source || !target || (isolate && !path.transfers.has(edge.id))) return null;
          const selected = path.transfers.has(edge.id);
          const peers = graph.edges.filter(e => e.source === edge.source && e.target === edge.target);
          const bend = (peers.indexOf(edge) - (peers.length - 1) / 2) * 48;
          const mx = (source.x + target.x) / 2, my = (source.y + target.y) / 2 + bend;
          const d = edge.source === edge.target ? `M ${source.x - 12} ${source.y} C ${source.x - 100} ${source.y - 100}, ${source.x + 100} ${source.y - 100}, ${source.x + 12} ${source.y}` : `M ${source.x} ${source.y} Q ${mx} ${my} ${target.x} ${target.y}`;
          return <g key={edge.id} role="button" tabIndex={0} aria-label={`Inspect transfer ${displayAmount(edge)} ${edge.asset || ''}, ${edge.transfer_id || edge.id}`} onClick={() => onTransfer(edge.id)} onKeyDown={event => activate(event, () => onTransfer(edge.id))} className="trail-svg-edge">
            <title>{displayAmount(edge)} {edge.asset} · {edge.timestamp || 'Timestamp unavailable'} · {edge.transfer_id || edge.id}</title>
            <path d={d} stroke="transparent" strokeWidth="18" fill="none" />
            <path d={d} stroke={selected ? '#245b65' : '#a3adb4'} strokeWidth={selected ? 3 : 1.5} fill="none" markerEnd="url(#network-arrow)" />
            {(selection?.transfers.includes(edge.id) || selection?.transfers.includes(edge.transfer_id || '')) && <text x={mx} y={my - 8} textAnchor="middle" className="trail-svg-label">{displayAmount(edge)} {edge.asset}</text>}
            <text className="sr-only">Transfer {index + 1}</text>
          </g>;
        })}
        {points.sort((a, b) => b.projected.z - a.projected.z).map(({ node, projected: p }) => {
          if (isolate && !path.wallets.has(node.address)) return null;
          const limited = node.expansion_state !== 'expanded';
          return <g key={node.address} role="button" tabIndex={0} aria-label={`Inspect ${walletRole(node, graph.destination?.address)} ${node.address}. ${boundaryLabel(node)}`} onClick={() => onWallet(node.address)} onKeyDown={event => activate(event, () => onWallet(node.address))} transform={`translate(${p.x} ${p.y})`} className="trail-svg-node">
            <title>{node.address} · {walletRole(node, graph.destination?.address)} · {boundaryLabel(node)}</title>
            <circle r={node.is_reported ? 19 : 14} fill={node.is_reported ? '#245b65' : '#fff'} stroke={path.wallets.has(node.address) ? '#245b65' : '#73818c'} strokeWidth="3" strokeDasharray={limited ? '4 3' : undefined} />
            <text y="-29" textAnchor="middle" className="trail-svg-label">{walletRole(node, graph.destination?.address)}</text>
            <text y="35" textAnchor="middle" className="trail-svg-address">{shortAddress(node.address)}</text>
            {limited && <text y="50" textAnchor="middle" className="trail-svg-boundary">NOT EXPANDED</text>}
          </g>;
        })}
      </g>
    </svg>
    <p className="trail-camera-help">Drag to {panMode ? 'pan' : 'rotate'} · + / − zoom · Arrow keys rotate · Shift + arrows pan. Depth is layout only.</p>
  </div>;
}

export default memo(function Network3D(props: Props) { return <Scene key={props.focus} {...props} />; });
