"""
CryptoTrace AI - Demo Data Provider
Provides a realistic, pre-built investigation scenario for prototype demonstrations.
ALL DATA IS CLEARLY LABELED AS DEMO DATA.

Scenario: A victim reports wallet. Funds flow through intermediaries,
get split, pass through a mixer-like pattern, and reach an exchange.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from app.providers.base import BlockchainProvider

# ─── Demo Wallet Addresses (clearly fake, plausible format) ────────────────
DEMO_WALLETS = {
    "0xReported001": {
        "label": "Reported Wallet (Victim)",
        "is_reported": True,
        "is_suspicious": True,
    },
    "0xIntermed002": {
        "label": "Intermediary A",
        "is_intermediary": True,
        "is_suspicious": True,
    },
    "0xIntermed003": {
        "label": "Intermediary B",
        "is_intermediary": True,
        "is_suspicious": True,
    },
    "0xSplitDst004": {
        "label": "Split Destination 1",
        "is_intermediary": True,
    },
    "0xSplitDst005": {
        "label": "Split Destination 2",
        "is_intermediary": True,
    },
    "0xSplitDst006": {
        "label": "Split Destination 3",
        "is_intermediary": True,
        "is_suspicious": True,
    },
    "0xCollect007": {
        "label": "Consolidation Wallet",
        "is_intermediary": True,
        "is_suspicious": True,
    },
    "0xLayer008": {
        "label": "Layering Wallet",
        "is_intermediary": True,
        "is_suspicious": True,
    },
    "0xExchang009": {
        "label": "Suspected Exchange Deposit",
        "is_destination": True,
    },
    "0xUnrelat010": {
        "label": "Unrelated Wallet",
    },
}

# ─── Demo Timeline Base ─────────────────────────────────────────────────────
_BASE_TIME = datetime(2025, 8, 15, 10, 30, 0, tzinfo=timezone.utc)


def _t(minutes: int) -> datetime:
    return _BASE_TIME + timedelta(minutes=minutes)


# ─── Demo Transactions ──────────────────────────────────────────────────────
DEMO_TRANSACTIONS: List[Dict[str, Any]] = [
    # Hop 0: Victim sends to Reported Wallet (initial fraud deposit)
    {
        "hash": "0xdemo_tx_001_reported_receives",
        "blockchain": "demo",
        "block_number": 18500001,
        "timestamp": _t(0),
        "from_address": "0xVictim000",
        "to_address": "0xReported001",
        "asset": "ETH",
        "amount": 5.0,
        "amount_usd": 12500.00,
        "fee": 0.002,
        "status": "confirmed",
        "source": "demo",
        "hop_number": 0,
    },
    # Hop 1: Reported → Intermediary A (rapid movement - 3 min)
    {
        "hash": "0xdemo_tx_002_rapid_move",
        "blockchain": "demo",
        "block_number": 18500005,
        "timestamp": _t(3),
        "from_address": "0xReported001",
        "to_address": "0xIntermed002",
        "asset": "ETH",
        "amount": 4.95,
        "amount_usd": 12375.00,
        "fee": 0.003,
        "status": "confirmed",
        "source": "demo",
        "hop_number": 1,
    },
    # Hop 2: Intermediary A → Intermediary B (another rapid move - 5 min)
    {
        "hash": "0xdemo_tx_003_layer",
        "blockchain": "demo",
        "block_number": 18500012,
        "timestamp": _t(8),
        "from_address": "0xIntermed002",
        "to_address": "0xIntermed003",
        "asset": "ETH",
        "amount": 4.90,
        "amount_usd": 12250.00,
        "fee": 0.002,
        "status": "confirmed",
        "source": "demo",
        "hop_number": 2,
    },
    # Hop 3a: Intermediary B → Split Destination 1 (fund splitting)
    {
        "hash": "0xdemo_tx_004_split1",
        "blockchain": "demo",
        "block_number": 18500020,
        "timestamp": _t(15),
        "from_address": "0xIntermed003",
        "to_address": "0xSplitDst004",
        "asset": "ETH",
        "amount": 1.5,
        "amount_usd": 3750.00,
        "fee": 0.002,
        "status": "confirmed",
        "source": "demo",
        "hop_number": 3,
    },
    # Hop 3b: Intermediary B → Split Destination 2
    {
        "hash": "0xdemo_tx_005_split2",
        "blockchain": "demo",
        "block_number": 18500021,
        "timestamp": _t(16),
        "from_address": "0xIntermed003",
        "to_address": "0xSplitDst005",
        "asset": "ETH",
        "amount": 1.5,
        "amount_usd": 3750.00,
        "fee": 0.002,
        "status": "confirmed",
        "source": "demo",
        "hop_number": 3,
    },
    # Hop 3c: Intermediary B → Split Destination 3
    {
        "hash": "0xdemo_tx_006_split3",
        "blockchain": "demo",
        "block_number": 18500022,
        "timestamp": _t(17),
        "from_address": "0xIntermed003",
        "to_address": "0xSplitDst006",
        "asset": "ETH",
        "amount": 1.8,
        "amount_usd": 4500.00,
        "fee": 0.002,
        "status": "confirmed",
        "source": "demo",
        "hop_number": 3,
    },
    # Hop 4a: Split Dest 1 → Consolidation (fund consolidation begins)
    {
        "hash": "0xdemo_tx_007_consol1",
        "blockchain": "demo",
        "block_number": 18500035,
        "timestamp": _t(45),
        "from_address": "0xSplitDst004",
        "to_address": "0xCollect007",
        "asset": "ETH",
        "amount": 1.45,
        "amount_usd": 3625.00,
        "fee": 0.002,
        "status": "confirmed",
        "source": "demo",
        "hop_number": 4,
    },
    # Hop 4b: Split Dest 2 → Consolidation
    {
        "hash": "0xdemo_tx_008_consol2",
        "blockchain": "demo",
        "block_number": 18500036,
        "timestamp": _t(47),
        "from_address": "0xSplitDst005",
        "to_address": "0xCollect007",
        "asset": "ETH",
        "amount": 1.45,
        "amount_usd": 3625.00,
        "fee": 0.002,
        "status": "confirmed",
        "source": "demo",
        "hop_number": 4,
    },
    # Hop 4c: Split Dest 3 → Layering wallet
    {
        "hash": "0xdemo_tx_009_layer2",
        "blockchain": "demo",
        "block_number": 18500040,
        "timestamp": _t(52),
        "from_address": "0xSplitDst006",
        "to_address": "0xLayer008",
        "asset": "ETH",
        "amount": 1.75,
        "amount_usd": 4375.00,
        "fee": 0.002,
        "status": "confirmed",
        "source": "demo",
        "hop_number": 4,
    },
    # Hop 5a: Consolidation → Exchange
    {
        "hash": "0xdemo_tx_010_to_exchange",
        "blockchain": "demo",
        "block_number": 18500055,
        "timestamp": _t(90),
        "from_address": "0xCollect007",
        "to_address": "0xExchang009",
        "asset": "ETH",
        "amount": 2.85,
        "amount_usd": 7125.00,
        "fee": 0.003,
        "status": "confirmed",
        "source": "demo",
        "hop_number": 5,
    },
    # Hop 5b: Layering → Exchange
    {
        "hash": "0xdemo_tx_011_to_exchange2",
        "blockchain": "demo",
        "block_number": 18500060,
        "timestamp": _t(95),
        "from_address": "0xLayer008",
        "to_address": "0xExchang009",
        "asset": "ETH",
        "amount": 1.70,
        "amount_usd": 4250.00,
        "fee": 0.002,
        "status": "confirmed",
        "source": "demo",
        "hop_number": 5,
    },
    # Noise: unrelated transaction to Intermediary A
    {
        "hash": "0xdemo_tx_012_noise",
        "blockchain": "demo",
        "block_number": 18500070,
        "timestamp": _t(120),
        "from_address": "0xUnrelat010",
        "to_address": "0xIntermed002",
        "asset": "ETH",
        "amount": 0.1,
        "amount_usd": 250.00,
        "fee": 0.001,
        "status": "confirmed",
        "source": "demo",
        "hop_number": None,
    },
]

# ─── Demo VASP Attribution ──────────────────────────────────────────────────
DEMO_VASP_ATTRIBUTIONS = {
    "0xExchang009": {
        "entity_name": "DemoExchange (Simulated)",
        "entity_type": "cryptocurrency_exchange",
        "attribution_type": "inferred",
        "confidence": "likely",
        "source": "demo_intelligence",
        "provenance": "demo_intelligence",
        "source_reference": "CryptoTrace Demo Intelligence",
        "reasoning": "Observed destination relationship in the deterministic investigation dataset.",
        "supporting_evidence": "DEMO DATA: This attribution is simulated for demonstration. In production, this would come from verified address intelligence sources.",
    },
}


class DemoProvider(BlockchainProvider):
    """
    Demo blockchain data provider.
    Provides pre-built investigation scenario for prototype demonstrations.
    ALL DATA IS CLEARLY LABELED AS DEMO DATA.
    """

    @property
    def provider_name(self) -> str:
        return "demo"

    @property
    def is_demo(self) -> bool:
        return True

    async def validate_address(self, address: str, chain: str) -> bool:
        """In demo mode, accept known demo addresses or ETH-format addresses."""
        if address in DEMO_WALLETS:
            return True
        # Accept any 0x-prefixed hex string of appropriate length
        if address.startswith("0x") and len(address) >= 10:
            return True
        return False

    async def get_network(self, address: str) -> Optional[str]:
        if address in DEMO_WALLETS or address.startswith("0x"):
            return "demo"
        return None

    async def get_transactions(
        self,
        address: str,
        chain: str = "demo",
        direction: str = "both",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return demo transactions involving the given address."""
        results = []
        for tx in DEMO_TRANSACTIONS:
            matches = False
            if direction in ("outgoing", "both") and tx["from_address"] == address:
                matches = True
            if direction in ("incoming", "both") and tx["to_address"] == address:
                matches = True

            if matches:
                if start_time and tx["timestamp"] < start_time:
                    continue
                if end_time and tx["timestamp"] > end_time:
                    continue
                results.append(tx.copy())

            if len(results) >= limit:
                break

        return results

    async def get_transaction(self, tx_hash: str, chain: str) -> Optional[Dict[str, Any]]:
        for tx in DEMO_TRANSACTIONS:
            if tx["hash"] == tx_hash:
                return tx.copy()
        return None

    async def get_balance(self, address: str, chain: str) -> float:
        received = sum(
            tx["amount"] for tx in DEMO_TRANSACTIONS if tx["to_address"] == address
        )
        sent = sum(
            tx["amount"] for tx in DEMO_TRANSACTIONS if tx["from_address"] == address
        )
        return round(received - sent, 6)

    def get_all_demo_transactions(self) -> List[Dict[str, Any]]:
        """Return all demo transactions (for seeding)."""
        return [tx.copy() for tx in DEMO_TRANSACTIONS]

    def get_demo_wallets(self) -> Dict[str, Dict[str, Any]]:
        """Return demo wallet metadata."""
        return {k: v.copy() for k, v in DEMO_WALLETS.items()}

    def get_demo_vasp(self, address: str) -> Optional[Dict[str, Any]]:
        """Return VASP attribution for a demo address."""
        return DEMO_VASP_ATTRIBUTIONS.get(address)
