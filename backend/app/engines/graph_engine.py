"""
CryptoTrace AI - Graph Engine
Constructs investigation graphs using NetworkX and serializes them
for frontend visualization with React Flow.
"""
import logging
from typing import List, Dict, Any, Optional
import networkx as nx
from collections import deque
from app.core.transfers import transfer_fields
from app.services.destination_service import classify_candidates

logger = logging.getLogger(__name__)


class GraphEngine:
    """
    Builds and analyzes investigation graphs.
    Wallet = Node, Transaction = Edge.
    """

    def __init__(self):
        self.graph: Optional[nx.MultiDiGraph] = None

    def build_graph(
        self,
        transactions: List[Dict[str, Any]],
        wallets: Dict[str, Dict[str, Any]],
    ) -> nx.MultiDiGraph:
        """Build a directed graph from transactions and wallet metadata."""
        G = nx.MultiDiGraph()

        # Add wallet nodes
        for address, meta in wallets.items():
            G.add_node(
                address,
                label=meta.get("label", address[:10] + "..."),
                is_reported=meta.get("is_reported", False),
                is_intermediary=meta.get("is_intermediary", False),
                is_destination=meta.get("is_destination", False),
                is_suspicious=meta.get("is_suspicious", False),
                hop_distance=meta.get("hop_distance", 0),
                total_received=meta.get("total_received", 0),
                total_sent=meta.get("total_sent", 0),
                transaction_count=meta.get("transaction_count", 0),
                endpoint_kind=meta.get("endpoint_kind", "not_expanded"),
                expansion_state=meta.get("expansion_state", "legacy_unknown"),
                received_by_asset=meta.get("received_by_asset", []),
                sent_by_asset=meta.get("sent_by_asset", []),
            )

        # Add transaction edges
        for index, tx in enumerate(transactions):
            from_addr = tx["from_address"]
            to_addr = tx["to_address"]

            # Ensure nodes exist
            if from_addr not in G.nodes:
                G.add_node(from_addr, label=from_addr[:10] + "...")
            if to_addr not in G.nodes:
                G.add_node(to_addr, label=to_addr[:10] + "...")

            G.add_edge(
                from_addr,
                to_addr,
                key=tx.get("transfer_id", f"legacy:{index}:{tx.get('hash', '')}"),
                **transfer_fields(tx),
                hash=tx.get("hash", ""),
                amount=tx.get("amount", 0),
                asset=tx.get("asset", ""),
                timestamp=tx.get("timestamp"),
                is_suspicious=tx.get("is_suspicious", False),
                hop_number=tx.get("hop_number", 0),
            )

        self.graph = G
        return G

    def get_primary_path(self, source: str, destination: Optional[str] = None, max_hops: int = 10) -> List[str]:
        """Shortest directed route, lexicographic tie-break, O(V+E), hop bounded.

        This ranks structural review routes, not recovered/attributable value.
        It does not infer temporal continuity or ownership of fungible funds.
        """
        if not self.graph or source not in self.graph:
            return [source]
        if destination is None:
            candidates = classify_candidates(dict(self.graph.nodes(data=True)), {})
            destination = candidates[0]["address"] if candidates else None
        queue = deque([[source]])
        seen = {source}
        while queue:
            path = queue.popleft()
            if path[-1] == destination:
                return path
            if len(path) - 1 >= max_hops:
                continue
            for node in sorted(self.graph.successors(path[-1])):
                if node not in seen:
                    seen.add(node)
                    queue.append(path + [node])
        return [source]

    def get_intermediaries(self) -> List[Dict[str, Any]]:
        """
        Identify important intermediary wallets using graph analysis.
        Uses betweenness centrality and pass-through detection.
        """
        if not self.graph:
            return []

        intermediaries = []

        # Betweenness centrality
        try:
            centrality = nx.betweenness_centrality(self.graph)
        except Exception:
            centrality = {}

        for node in self.graph.nodes:
            data = self.graph.nodes[node]
            in_deg = self.graph.in_degree(node)
            out_deg = self.graph.out_degree(node)

            # Pass-through: has both incoming and outgoing
            is_passthrough = in_deg > 0 and out_deg > 0
            cent_score = centrality.get(node, 0)

            if is_passthrough and not data.get("is_reported", False):
                intermediaries.append({
                    "address": node,
                    "label": data.get("label", ""),
                    "centrality": round(cent_score, 4),
                    "in_degree": in_deg,
                    "out_degree": out_deg,
                    "is_high_centrality": cent_score > 0.1,
                    "reason": self._intermediary_reason(node, in_deg, out_deg, cent_score),
                })

        # Sort by centrality
        return sorted(intermediaries, key=lambda x: x["centrality"], reverse=True)

    def _intermediary_reason(self, address: str, in_deg: int, out_deg: int, centrality: float) -> str:
        reasons = []
        if centrality > 0.1:
            reasons.append("High betweenness centrality in the transaction network")
        if out_deg > 2:
            reasons.append(f"Distributes funds to {out_deg} downstream wallets")
        if in_deg > 2:
            reasons.append(f"Receives funds from {in_deg} upstream wallets")
        if in_deg > 0 and out_deg > 0:
            reasons.append("Pass-through wallet: receives and forwards funds")
        return ". ".join(reasons) if reasons else "Potential intermediary wallet"

    def serialize_for_frontend(
        self,
        primary_path: Optional[List[str]] = None,
        vasp_data: Optional[Dict[str, Dict]] = None,
        risk_data: Optional[Dict[str, Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Serialize the graph to a format compatible with React Flow.
        """
        if not self.graph:
            return {"nodes": [], "edges": [], "primary_path": []}

        nodes = []
        edges = []

        for node_id in self.graph.nodes:
            data = dict(self.graph.nodes[node_id])
            vasp = vasp_data.get(node_id, {}) if vasp_data else {}
            risk = risk_data.get(node_id, {}) if risk_data else {}

            nodes.append({
                "id": node_id,
                "endpoint_kind": data.get("endpoint_kind", "not_expanded"),
                "expansion_state": data.get("expansion_state", "legacy_unknown"),
                "received_by_asset": data.get("received_by_asset", []),
                "sent_by_asset": data.get("sent_by_asset", []),
                "address": node_id,
                "label": data.get("label", node_id[:10] + "..."),
                "is_reported": data.get("is_reported", False),
                "is_intermediary": data.get("is_intermediary", False),
                "is_destination": data.get("is_destination", False),
                "is_suspicious": data.get("is_suspicious", False),
                "hop_distance": data.get("hop_distance", 0),
                "total_received": data.get("total_received", 0),
                "total_sent": data.get("total_sent", 0),
                "risk_category": risk.get("risk_category", None),
                "risk_score": risk.get("risk_score", None),
                "risk_signals": risk.get("contributing_signals", []),
                "vasp_name": vasp.get("entity_name", None),
                "vasp_attribution_type": vasp.get("attribution_type", None),
                "vasp_confidence": vasp.get("confidence", None),
                "vasp_source": vasp.get("source", None),
                "vasp_supporting_evidence": vasp.get("supporting_evidence", None),
                "vasp_attribution_status": vasp.get("attribution_status", "unknown"),
                "vasp_provenance": vasp.get("provenance", "unknown"),
                "vasp_source_reference": vasp.get("source_reference", None),
                "vasp_reasoning": vasp.get("reasoning", None),
                "vasp_supporting_evidence_ids": vasp.get("supporting_evidence_ids", []),
                "vasp_supporting_transaction_hashes": vasp.get("supporting_transaction_hashes", []),
                "vasp_verified_at": vasp.get("verified_at", None),
            })

        for u, v, edge_id, data in self.graph.edges(keys=True, data=True):
            ts = data.get("timestamp")
            edges.append({
                "id": edge_id,
                **transfer_fields(data),
                "source": u,
                "target": v,
                "hash": data.get("hash", ""),
                "amount": data.get("amount", 0),
                "asset": data.get("asset", ""),
                "timestamp": ts.isoformat() if ts else None,
                "is_suspicious": data.get("is_suspicious", False),
                "hop_number": data.get("hop_number", 0),
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "primary_path": primary_path or [],
        }
