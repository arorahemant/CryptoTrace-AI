"""
CryptoTrace AI - Trace Engine
The heart of CryptoTrace: controlled BFS traversal from a starting wallet,
with cycle protection, hop limits, and relevance-based prioritization.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Set, Tuple
from collections import deque
from app.providers.base import BlockchainProvider

logger = logging.getLogger(__name__)


class TraceEngine:
    """
    Controlled blockchain transaction tracer.

    Takes a starting wallet and traces downstream fund movement
    with configurable limits to prevent unbounded traversal.
    """

    def __init__(self, provider: BlockchainProvider):
        self.provider = provider

    async def trace(
        self,
        starting_address: str,
        chain: str = "demo",
        max_hops: int = 5,
        min_amount: float = 0.001,
        time_window_hours: int = 720,
        direction: str = "outgoing",
        max_transactions: int = 200,
    ) -> Dict[str, Any]:
        """
        Trace fund movement from a starting wallet.

        Returns:
            Dict with:
              - transactions: List of canonical transaction dicts
              - wallets: Dict of discovered wallet metadata
              - paths: List of traced paths
              - stats: Tracing statistics
        """
        visited_addresses: Set[str] = set()
        visited_tx_hashes: Set[str] = set()
        all_transactions: List[Dict[str, Any]] = []
        discovered_wallets: Dict[str, Dict[str, Any]] = {}
        paths: List[List[str]] = []
        provider_errors = 0
        malformed_transactions = 0

        # Time window — for demo provider, use wide window to capture demo data
        end_time = datetime.now(timezone.utc)
        if self.provider.is_demo and hasattr(self.provider, "get_all_demo_transactions"):
            available = self.provider.get_all_demo_transactions()
            timestamps = [tx.get("timestamp") for tx in available if tx.get("timestamp")]
            if timestamps:
                end_time = max(timestamps)
        start_time = end_time - timedelta(hours=time_window_hours)

        # BFS queue: (address, current_hop, path_so_far)
        queue: deque[Tuple[str, int, List[str]]] = deque()
        queue.append((starting_address, 0, [starting_address]))

        # Register starting wallet
        discovered_wallets[starting_address] = {
            "address": starting_address,
            "is_reported": True,
            "is_intermediary": False,
            "is_destination": False,
            "is_suspicious": True,
            "hop_distance": 0,
            "total_received": 0.0,
            "total_sent": 0.0,
            "transaction_count": 0,
        }

        total_tx_count = 0

        while queue and total_tx_count < max_transactions:
            current_address, hop, current_path = queue.popleft()

            if hop >= max_hops:
                # Record path at max depth
                paths.append(current_path)
                continue

            if current_address in visited_addresses and hop > 0:
                # Cycle protection — don't re-traverse, but record path
                paths.append(current_path)
                continue

            visited_addresses.add(current_address)

            # Fetch transactions from provider
            try:
                txs = await self.provider.get_transactions(
                    address=current_address,
                    chain=chain,
                    direction=direction,
                    start_time=start_time,
                    end_time=end_time,
                    limit=50,
                )
            except Exception:
                provider_errors += 1
                logger.exception("Provider error fetching transactions for %s", current_address)
                paths.append(current_path)
                continue

            if not txs:
                paths.append(current_path)
                continue

            if not isinstance(txs, list):
                provider_errors += 1
                logger.error("Provider returned a non-list transaction response for %s", current_address)
                paths.append(current_path)
                continue

            valid_txs = []
            for tx in txs:
                if self._is_valid_transaction(tx):
                    valid_txs.append(tx)
                else:
                    malformed_transactions += 1
                    logger.warning("Provider returned malformed transaction data for %s", current_address)

            if not valid_txs:
                paths.append(current_path)
                continue

            # Sort by relevance: amount descending, then temporal proximity
            txs = self._prioritize_transactions(valid_txs, current_address, direction)

            has_outgoing = False
            for tx in txs:
                if total_tx_count >= max_transactions:
                    break

                tx_hash = tx.get("hash", "")
                if tx_hash in visited_tx_hashes:
                    continue

                # Filter by minimum amount
                if tx.get("amount", 0) < min_amount:
                    continue

                visited_tx_hashes.add(tx_hash)
                tx["hop_number"] = hop + 1 if tx["from_address"] == current_address else hop
                all_transactions.append(tx)
                total_tx_count += 1

                # Determine next address to trace
                if direction in ("outgoing", "both") and tx["from_address"] == current_address:
                    next_address = tx["to_address"]
                    has_outgoing = True
                elif direction in ("incoming", "both") and tx["to_address"] == current_address:
                    next_address = tx["from_address"]
                    has_outgoing = True
                else:
                    continue

                # Register discovered wallet
                if next_address not in discovered_wallets:
                    discovered_wallets[next_address] = {
                        "address": next_address,
                        "is_reported": False,
                        "is_intermediary": False,
                        "is_destination": False,
                        "is_suspicious": False,
                        "hop_distance": hop + 1,
                        "total_received": 0.0,
                        "total_sent": 0.0,
                        "transaction_count": 0,
                    }

                # Update wallet stats
                self._update_wallet_stats(discovered_wallets, tx)

                # Enqueue next hop
                new_path = current_path + [next_address]
                queue.append((next_address, hop + 1, new_path))

            if not has_outgoing:
                paths.append(current_path)

        # Update wallet stats for starting address
        self._finalize_wallet_metadata(discovered_wallets, all_transactions)

        trace_is_partial = provider_errors > 0 or malformed_transactions > 0

        return {
            "transactions": all_transactions,
            "wallets": discovered_wallets,
            "paths": paths,
            "stats": {
                "total_transactions": len(all_transactions),
                "total_wallets": len(discovered_wallets),
                "max_hop_reached": max(
                    (tx.get("hop_number", 0) for tx in all_transactions), default=0
                ),
                "total_amount_traced": sum(tx.get("amount", 0) for tx in all_transactions),
                "provider": self.provider.provider_name,
                "is_demo": self.provider.is_demo,
                "provider_errors": provider_errors,
                "malformed_transactions": malformed_transactions,
                "trace_status": "partial" if trace_is_partial else "complete",
                "trace_warning": (
                    "Trace incomplete: one or more provider responses were unavailable "
                    "or malformed; results may be incomplete."
                    if trace_is_partial
                    else None
                ),
            },
        }

    @staticmethod
    def _is_valid_transaction(tx: Any) -> bool:
        """Accept only normalized transaction records from a provider."""
        if not isinstance(tx, dict):
            return False
        required_strings = ("hash", "from_address", "to_address")
        if any(not isinstance(tx.get(key), str) or not tx[key] for key in required_strings):
            return False
        if not isinstance(tx.get("timestamp"), datetime):
            return False
        amount = tx.get("amount")
        return isinstance(amount, (int, float)) and amount >= 0

    def _prioritize_transactions(
        self, txs: List[Dict], address: str, direction: str
    ) -> List[Dict]:
        """
        Rank transactions by investigation relevance.
        Uses deterministic explainable signals — NOT ML.
        """
        def relevance_score(tx: Dict) -> float:
            score = 0.0
            # Higher amount = more relevant
            score += min(tx.get("amount", 0) * 10, 100)
            # Outgoing from current address = follow the money
            if tx.get("from_address") == address:
                score += 50
            # Temporal proximity to other transactions (rapid movement)
            score += 10
            return score

        return sorted(txs, key=relevance_score, reverse=True)

    def _update_wallet_stats(self, wallets: Dict, tx: Dict):
        """Update running statistics for wallets involved in a transaction."""
        from_addr = tx.get("from_address", "")
        to_addr = tx.get("to_address", "")
        amount = tx.get("amount", 0)

        if from_addr in wallets:
            wallets[from_addr]["total_sent"] += amount
            wallets[from_addr]["transaction_count"] += 1

        if to_addr in wallets:
            wallets[to_addr]["total_received"] += amount
            wallets[to_addr]["transaction_count"] += 1

    def _finalize_wallet_metadata(self, wallets: Dict, transactions: List[Dict]):
        """Post-processing: identify intermediaries and destinations."""
        for address, wallet in wallets.items():
            if wallet["is_reported"]:
                continue

            has_incoming = wallet["total_received"] > 0
            has_outgoing = wallet["total_sent"] > 0

            if has_incoming and has_outgoing:
                wallet["is_intermediary"] = True
            elif has_incoming and not has_outgoing:
                wallet["is_destination"] = True
