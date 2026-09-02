"""
CryptoTrace AI - Pattern Engine
Detects suspicious transaction patterns using deterministic, explainable rules.
NOT ML — these are configurable heuristic detectors.
"""
import logging
from datetime import timedelta
from typing import List, Dict, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class PatternEngine:
    """
    Detects five core suspicious patterns:
    1. Rapid Movement
    2. Fund Splitting
    3. Fund Consolidation
    4. Layering (multi-hop chains)
    5. Repeated Suspicious Connections
    """

    def __init__(
        self,
        rapid_threshold_minutes: int = 30,
        split_threshold: int = 3,
        consolidation_threshold: int = 3,
        layering_min_hops: int = 3,
    ):
        self.rapid_threshold = timedelta(minutes=rapid_threshold_minutes)
        self.split_threshold = split_threshold
        self.consolidation_threshold = consolidation_threshold
        self.layering_min_hops = layering_min_hops

    def detect_all(
        self,
        transactions: List[Dict[str, Any]],
        wallets: Dict[str, Dict[str, Any]],
        paths: List[List[str]],
    ) -> List[Dict[str, Any]]:
        """Run all pattern detectors and return combined findings."""
        findings = []

        findings.extend(self.detect_rapid_movement(transactions, wallets))
        findings.extend(self.detect_fund_splitting(transactions, wallets))
        findings.extend(self.detect_fund_consolidation(transactions, wallets))
        findings.extend(self.detect_layering(transactions, paths))
        findings.extend(self.detect_repeated_connections(transactions))

        return findings

    def detect_rapid_movement(
        self,
        transactions: List[Dict[str, Any]],
        wallets: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Detect cases where funds are received and moved onward unusually quickly.
        """
        findings = []
        # Group transactions by wallet
        incoming_by_wallet: Dict[str, List[Dict]] = defaultdict(list)
        outgoing_by_wallet: Dict[str, List[Dict]] = defaultdict(list)

        for tx in transactions:
            incoming_by_wallet[tx["to_address"]].append(tx)
            outgoing_by_wallet[tx["from_address"]].append(tx)

        for address in wallets:
            incoming = incoming_by_wallet.get(address, [])
            outgoing = outgoing_by_wallet.get(address, [])

            for inc_tx in incoming:
                for out_tx in outgoing:
                    inc_time = inc_tx.get("timestamp")
                    out_time = out_tx.get("timestamp")
                    if not inc_time or not out_time:
                        continue

                    time_diff = out_time - inc_time
                    if timedelta(0) <= time_diff <= self.rapid_threshold:
                        minutes = time_diff.total_seconds() / 60

                        findings.append({
                            "pattern_type": "rapid_movement",
                            "pattern_name": "Rapid Fund Movement",
                            "description": (
                                f"Funds were transferred onward from {address[:12]}... "
                                f"within {minutes:.0f} minutes of receipt. "
                                f"Received {inc_tx['amount']:.4f} {inc_tx.get('asset', 'ETH')}, "
                                f"sent {out_tx['amount']:.4f} {out_tx.get('asset', 'ETH')}."
                            ),
                            "severity": "high" if minutes < 10 else "medium",
                            "confidence": min(0.9, 0.5 + (1 - minutes / 30) * 0.4),
                            "trigger": f"Time between receipt and transfer: {minutes:.0f} minutes",
                            "affected_wallets": [address],
                            "supporting_transaction_ids": [inc_tx["hash"], out_tx["hash"]],
                            "metadata": {
                                "receipt_tx": inc_tx["hash"],
                                "onward_tx": out_tx["hash"],
                                "time_difference_minutes": round(minutes, 1),
                                "amount_received": inc_tx["amount"],
                                "amount_sent": out_tx["amount"],
                            },
                        })

        return findings

    def detect_fund_splitting(
        self,
        transactions: List[Dict[str, Any]],
        wallets: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Detect one-to-many fund distribution."""
        findings = []
        outgoing_by_wallet: Dict[str, List[Dict]] = defaultdict(list)

        for tx in transactions:
            outgoing_by_wallet[tx["from_address"]].append(tx)

        for address, out_txs in outgoing_by_wallet.items():
            destinations = set(tx["to_address"] for tx in out_txs)
            if len(destinations) >= self.split_threshold:
                total_amount = sum(tx["amount"] for tx in out_txs)
                findings.append({
                    "pattern_type": "fund_splitting",
                    "pattern_name": "Fund Splitting Detected",
                    "description": (
                        f"Wallet {address[:12]}... distributed funds to "
                        f"{len(destinations)} different wallets "
                        f"(total: {total_amount:.4f} ETH). "
                        f"This may indicate an attempt to obscure the money trail."
                    ),
                    "severity": "high" if len(destinations) >= 5 else "medium",
                    "confidence": min(0.85, 0.4 + len(destinations) * 0.1),
                    "trigger": f"Funds sent to {len(destinations)} distinct wallets",
                    "affected_wallets": [address] + list(destinations),
                    "supporting_transaction_ids": [tx["hash"] for tx in out_txs],
                    "metadata": {
                        "source_wallet": address,
                        "destination_count": len(destinations),
                        "destinations": list(destinations),
                        "total_amount": total_amount,
                    },
                })

        return findings

    def detect_fund_consolidation(
        self,
        transactions: List[Dict[str, Any]],
        wallets: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Detect many-to-one fund collection."""
        findings = []
        incoming_by_wallet: Dict[str, List[Dict]] = defaultdict(list)

        for tx in transactions:
            incoming_by_wallet[tx["to_address"]].append(tx)

        for address, inc_txs in incoming_by_wallet.items():
            sources = set(tx["from_address"] for tx in inc_txs)
            if len(sources) >= self.consolidation_threshold:
                total_amount = sum(tx["amount"] for tx in inc_txs)
                findings.append({
                    "pattern_type": "fund_consolidation",
                    "pattern_name": "Fund Consolidation Detected",
                    "description": (
                        f"Wallet {address[:12]}... received funds from "
                        f"{len(sources)} different wallets "
                        f"(total: {total_amount:.4f} ETH). "
                        f"This may indicate consolidation of distributed funds."
                    ),
                    "severity": "high" if len(sources) >= 5 else "medium",
                    "confidence": min(0.85, 0.4 + len(sources) * 0.1),
                    "trigger": f"Funds received from {len(sources)} distinct wallets",
                    "affected_wallets": list(sources) + [address],
                    "supporting_transaction_ids": [tx["hash"] for tx in inc_txs],
                    "metadata": {
                        "receiving_wallet": address,
                        "source_count": len(sources),
                        "sources": list(sources),
                        "total_amount": total_amount,
                    },
                })

        return findings

    def detect_layering(
        self,
        transactions: List[Dict[str, Any]],
        paths: List[List[str]],
    ) -> List[Dict[str, Any]]:
        """Detect multi-hop chains that may indicate layered movement."""
        findings = []

        for path in paths:
            if len(path) >= self.layering_min_hops:
                # Find transactions along this path
                path_txs = []
                for i in range(len(path) - 1):
                    for tx in transactions:
                        if tx["from_address"] == path[i] and tx["to_address"] == path[i + 1]:
                            path_txs.append(tx)
                            break

                if path_txs:
                    findings.append({
                        "pattern_type": "layering",
                        "pattern_name": "Multi-Hop Fund Movement",
                        "description": (
                            f"Funds traversed {len(path) - 1} hops through "
                            f"{len(path)} wallets. "
                            f"This multi-hop movement may indicate layered fund "
                            f"transfer and requires further investigation."
                        ),
                        "severity": "high" if len(path) >= 5 else "medium",
                        "confidence": min(0.8, 0.3 + len(path) * 0.1),
                        "trigger": f"{len(path) - 1}-hop chain detected",
                        "affected_wallets": path,
                        "supporting_transaction_ids": [tx["hash"] for tx in path_txs],
                        "metadata": {
                            "path": path,
                            "hop_count": len(path) - 1,
                            "path_transactions": [tx["hash"] for tx in path_txs],
                        },
                    })

        # Deduplicate by affected wallets tuple
        seen = set()
        unique_findings = []
        for f in findings:
            key = tuple(sorted(f["affected_wallets"]))
            if key not in seen:
                seen.add(key)
                unique_findings.append(f)

        return unique_findings

    def detect_repeated_connections(
        self,
        transactions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Detect repeated transactions between the same wallet pairs."""
        findings = []
        pair_txs: Dict[tuple, List[Dict]] = defaultdict(list)

        for tx in transactions:
            pair = (tx["from_address"], tx["to_address"])
            pair_txs[pair].append(tx)

        for (from_addr, to_addr), txs in pair_txs.items():
            if len(txs) >= 2:
                total_amount = sum(tx["amount"] for tx in txs)
                findings.append({
                    "pattern_type": "repeated_connections",
                    "pattern_name": "Repeated Wallet Connections",
                    "description": (
                        f"Detected {len(txs)} transactions between "
                        f"{from_addr[:12]}... and {to_addr[:12]}... "
                        f"(total: {total_amount:.4f} ETH). "
                        f"Repeated connections may indicate a persistent relationship."
                    ),
                    "severity": "medium",
                    "confidence": min(0.7, 0.3 + len(txs) * 0.1),
                    "trigger": f"{len(txs)} transactions between same wallets",
                    "affected_wallets": [from_addr, to_addr],
                    "supporting_transaction_ids": [tx["hash"] for tx in txs],
                    "metadata": {
                        "from_wallet": from_addr,
                        "to_wallet": to_addr,
                        "transaction_count": len(txs),
                        "total_amount": total_amount,
                    },
                })

        return findings
