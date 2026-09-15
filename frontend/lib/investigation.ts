import type { ExactTransfer, AssetTotal, DestinationCandidate } from './transfers';

export interface TrailWallet {
  id?: string;
  address: string;
  is_reported?: boolean;
  is_destination?: boolean;
  hop_distance?: number;
  expansion_state?: string;
  endpoint_kind?: string;
  transaction_count?: number;
  received_by_asset?: AssetTotal[];
  sent_by_asset?: AssetTotal[];
  vasp_name?: string | null;
  vasp_attribution_status?: string | null;
}
export interface TrailTransfer extends ExactTransfer {
  id: string;
  source: string;
  target: string;
  hash?: string;
  amount?: number;
  asset?: string;
  timestamp?: string | null;
}
export interface TrailGraph {
  run_id?: string;
  nodes: TrailWallet[];
  edges: TrailTransfer[];
  primary_path: string[];
  destination?: DestinationCandidate | null;
}
export type TrailSelection = { wallets: string[]; transfers: string[]; label: string };
export const shortAddress = (address: string) => address.length > 20 ? `${address.slice(0, 8)}…${address.slice(-6)}` : address;
export const readable = (value?: string | null) => value ? value.replaceAll('_', ' ') : 'Unknown';
export function walletRole(wallet: TrailWallet, destination?: string) {
  if (wallet.is_reported) return 'Reported wallet';
  if (wallet.address === destination) return wallet.vasp_name ? 'Candidate service' : 'Destination candidate';
  return `Hop ${wallet.hop_distance ?? '?'} · Wallet`;
}
export function boundaryLabel(wallet: TrailWallet) {
  if (wallet.expansion_state === 'expanded') return 'Expanded';
  if (!wallet.expansion_state) return 'Expansion unknown';
  return `Not expanded · ${readable(wallet.expansion_state)}`;
}

// Visual path only: directed shortest connection through observed edges. This
// does not attribute ownership or establish that the same funds were forwarded.
export function selectedPath(graph: TrailGraph, selection: TrailSelection | null) {
  const wallets = new Set<string>();
  const transfers = new Set<string>();
  const origin = graph.nodes.find(node => node.is_reported)?.address;
  const incoming = new Map<string, TrailTransfer>();
  const outgoing = new Map<string, TrailTransfer[]>();
  for (const edge of graph.edges) outgoing.set(edge.source, [...(outgoing.get(edge.source) || []), edge]);
  const visited = new Set(origin ? [origin] : []);
  const queue = origin ? [origin] : [];
  for (let i = 0; i < queue.length; i++) {
    for (const edge of outgoing.get(queue[i]) || []) {
      if (visited.has(edge.target)) continue;
      visited.add(edge.target); incoming.set(edge.target, edge); queue.push(edge.target);
    }
  }
  const connect = (address: string) => {
    wallets.add(address);
    let edge = incoming.get(address);
    while (edge) {
      transfers.add(edge.id); wallets.add(edge.source); edge = incoming.get(edge.source);
    }
  };
  if (selection) {
    const selectedEdges = graph.edges.filter(edge => selection.transfers.includes(edge.id) || selection.transfers.includes(edge.transfer_id || ''));
    // An explicit event must not also highlight another event with the same
    // endpoints simply because it happened to be the BFS predecessor.
    selection.wallets.filter(address => !selectedEdges.some(edge => edge.target === address)).forEach(connect);
    for (const id of selection.transfers) {
      const edge = graph.edges.find(item => item.id === id || item.transfer_id === id);
      if (edge) { connect(edge.source); wallets.add(edge.target); transfers.add(edge.id); }
    }
  } else {
    graph.primary_path.forEach(address => wallets.add(address));
    for (let i = 1; i < graph.primary_path.length; i++) {
      graph.edges.filter(edge => edge.source === graph.primary_path[i - 1] && edge.target === graph.primary_path[i]).forEach(edge => transfers.add(edge.id));
    }
  }
  return { wallets, transfers };
}

export function layoutGraph(graph: TrailGraph) {
  const groups = new Map<number, TrailWallet[]>();
  graph.nodes.forEach(node => { const hop = node.hop_distance ?? 0; groups.set(hop, [...(groups.get(hop) || []), node]); });
  return graph.nodes.map(node => {
    const hop = node.hop_distance ?? 0;
    const group = groups.get(hop)!;
    const index = group.indexOf(node);
    return { node, x: hop * 340, y: (index - (group.length - 1) / 2) * 170, z: (index % 3 - 1) * 95 };
  });
}

export function projectPoint(point: { x: number; y: number; z: number }, yaw: number, pitch: number, zoom: number) {
  const x = point.x * Math.cos(yaw) + point.z * Math.sin(yaw);
  const depth = -point.x * Math.sin(yaw) + point.z * Math.cos(yaw);
  const y = point.y * Math.cos(pitch) - depth * Math.sin(pitch);
  const z = point.y * Math.sin(pitch) + depth * Math.cos(pitch);
  const scale = 1400 / Math.max(350, 1400 + z) * zoom;
  return { x: x * scale, y: y * scale, z, scale };
}
