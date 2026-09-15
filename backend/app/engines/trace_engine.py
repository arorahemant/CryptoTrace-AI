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
from app.core.transfers import normalize_transfer, asset_totals
from decimal import Decimal

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
        from_block: int | None = None,
        to_block: int | None = None,
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
        if not 1 <= max_hops <= 20 or not 1 <= max_transactions <= 10000:
            raise ValueError("Trace bounds must be positive and bounded")
        if direction not in {"incoming", "outgoing", "both"}:
            raise ValueError("Invalid trace direction")
        if not Decimal(str(min_amount)).is_finite() or min_amount < 0:
            raise ValueError("Invalid minimum amount")
        from app.providers.alchemy import AlchemyEthereumProvider
        if isinstance(self.provider, AlchemyEthereumProvider):
            if chain != "ethereum":
                raise ValueError("Alchemy supports Ethereum Mainnet only")
            from app.engines.ethereum_trace import trace_ethereum
            return await trace_ethereum(self.provider, starting_address, max_hops=max_hops,
                max_transactions=max_transactions, direction=direction,
                from_block=from_block, to_block=to_block)
        if chain != "demo":
            raise ValueError("Real chains require an explicit supported provider")
        visited_addresses: Set[str] = set()
        visited_transfer_ids: Set[str] = set()
        event_records = {}
        asset_decimals = {}
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
            "expansion_state": "pending",
        }

        total_tx_count = 0

        while queue and total_tx_count < max_transactions:
            current_address, hop, current_path = queue.popleft()

            if current_address in visited_addresses:
                paths.append(current_path)
                continue

            if hop >= max_hops:
                discovered_wallets[current_address]["expansion_state"] = "hop_limit"
                # Record path at max depth
                paths.append(current_path)
                continue

            if current_address in visited_addresses and hop > 0:
                # Cycle protection — don't re-traverse, but record path
                paths.append(current_path)
                continue

            visited_addresses.add(current_address)
            discovered_wallets[current_address]["expansion_state"] = "expanded"

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
                discovered_wallets[current_address]["expansion_state"] = "provider_error"
                logger.exception("Provider error fetching transactions for %s", current_address)
                paths.append(current_path)
                continue

            if not txs:
                paths.append(current_path)
                continue

            if not isinstance(txs, list):
                provider_errors += 1
                discovered_wallets[current_address]["expansion_state"] = "provider_error"
                logger.error("Provider returned a non-list transaction response for %s", current_address)
                paths.append(current_path)
                continue

            if len(txs) >= 50:
                discovered_wallets[current_address]["expansion_state"] = "provider_limit"
            valid_txs = []
            for tx in txs:
                if self._is_valid_transaction(tx):
                    try:
                        valid_txs.append(normalize_transfer(tx, chain, legacy_demo=self.provider.is_demo))
                    except (ValueError, KeyError, TypeError):
                        malformed_transactions += 1
                        discovered_wallets[current_address]["expansion_state"] = "malformed_response"
                else:
                    malformed_transactions += 1
                    discovered_wallets[current_address]["expansion_state"] = "malformed_response"
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

                tx_hash = tx["transfer_id"]
                signature = (tx["from_address"], tx["to_address"], tx["asset_id"], tx["amount_base_units"], tx["token_decimals"])
                if (tx_hash in event_records and event_records[tx_hash] != signature) or (
                    tx["asset_id"] in asset_decimals and asset_decimals[tx["asset_id"]] != tx["token_decimals"]):
                    malformed_transactions += 1
                    discovered_wallets[current_address]["expansion_state"] = "malformed_response"
                    continue
                event_records[tx_hash] = signature
                asset_decimals[tx["asset_id"]] = tx["token_decimals"]
                if tx_hash in visited_transfer_ids:
                    continue

                # Filter by minimum amount
                if Decimal(tx["amount_exact"]) < Decimal(str(min_amount)):
                    discovered_wallets[current_address]["expansion_state"] = "amount_filter"
                    continue

                if not ((direction in ("outgoing", "both") and tx["from_address"] == current_address)
                        or (direction in ("incoming", "both") and tx["to_address"] == current_address)):
                    malformed_transactions += 1
                    continue
                visited_transfer_ids.add(tx_hash)
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
            "expansion_state": "pending",
                    }

                # Update wallet stats
                self._update_wallet_stats(discovered_wallets, tx)

                # Enqueue next hop
                new_path = current_path + [next_address]
                queue.append((next_address, hop + 1, new_path))

            if not has_outgoing:
                paths.append(current_path)

        for address, wallet in discovered_wallets.items():
            if wallet["expansion_state"] == "pending":
                wallet["expansion_state"] = "transaction_limit"
        if total_tx_count >= max_transactions:
            discovered_wallets[current_address]["expansion_state"] = "transaction_limit"

        # Update wallet stats for starting address
        self._finalize_wallet_metadata(discovered_wallets, all_transactions)

        trace_is_partial = provider_errors > 0 or malformed_transactions > 0 or any(w["expansion_state"] != "expanded" for w in discovered_wallets.values())
        # A bounded result is not an exhaustive blockchain history.

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
                "total_amount_traced": None,  # deprecated: volume is not unique traced funds
                "transfer_volume_by_asset": asset_totals(all_transactions),
                "origin_outflow_by_asset": asset_totals(tx for tx in all_transactions if tx["from_address"] == starting_address),
                "provider": self.provider.provider_name,
                "is_demo": self.provider.is_demo,
                "provider_errors": provider_errors,
                "malformed_transactions": malformed_transactions,
                "trace_status": "partial" if trace_is_partial else "complete",
                "trace_warning": (
                    "Trace incomplete: a transaction limit was reached or provider responses were unavailable "
                    "or malformed, or a hop/filter limit was reached; results may be incomplete."
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
        return "amount_base_units" in tx or (isinstance(amount, (int, float)) and amount >= 0)

    def _prioritize_transactions(
        self, txs: List[Dict], address: str, direction: str
    ) -> List[Dict]:
        """
        Rank transactions by investigation relevance.
        Uses deterministic explainable signals — NOT ML.
        """
        # Asset-neutral, reproducible ordering; no implicit FX comparison.
        return sorted(txs, key=lambda tx: (tx["timestamp"], tx["transfer_id"]))

    def _update_wallet_stats(self, wallets: Dict, tx: Dict):
        """Update running statistics for wallets involved in a transaction."""
        from_addr = tx.get("from_address", "")
        to_addr = tx.get("to_address", "")
        if from_addr in wallets:
            wallets[from_addr]["transaction_count"] += 1
        if to_addr in wallets:
            wallets[to_addr]["transaction_count"] += 1

    def _finalize_wallet_metadata(self, wallets: Dict, transactions: List[Dict]):
        for address, wallet in wallets.items():
            incoming = [tx for tx in transactions if tx["to_address"] == address]
            outgoing = [tx for tx in transactions if tx["from_address"] == address]
            wallet["received_by_asset"] = asset_totals(incoming)
            wallet["sent_by_asset"] = asset_totals(outgoing)
            # Legacy single-asset projections; exact arrays are authoritative.
            wallet["total_received"] = float(wallet["received_by_asset"][0]["amount_exact"]) if len(wallet["received_by_asset"]) == 1 else 0
            wallet["total_sent"] = float(wallet["sent_by_asset"][0]["amount_exact"]) if len(wallet["sent_by_asset"]) == 1 else 0
            wallet["is_intermediary"] = bool(incoming and outgoing and not wallet["is_reported"])
            wallet["endpoint_kind"] = ("not_expanded" if wallet["expansion_state"] != "expanded"
                                       else "last_observed_wallet" if incoming and not outgoing else "intermediary")
            wallet["is_destination"] = wallet["endpoint_kind"] == "last_observed_wallet"
