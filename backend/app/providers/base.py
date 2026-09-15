"""
CryptoTrace AI - Blockchain Provider Abstraction
Abstract interface that all blockchain data providers must implement.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class ProviderPage:
    """One bounded observation; an empty page is not necessarily exhaustion."""
    records: list[dict] = field(default_factory=list)
    continuation: str | None = None
    exhausted: bool = False
    partial_coverage: bool = False
    errors: list[dict] = field(default_factory=list)
    observation_boundaries: dict = field(default_factory=dict)
    requested_block_range: dict = field(default_factory=dict)
    retrieved_at: str | None = None
    provenance: dict = field(default_factory=dict)


class BlockchainProvider(ABC):
    """Abstract blockchain data provider interface."""

    @abstractmethod
    async def validate_address(self, address: str, chain: str) -> bool:
        """Validate that an address is properly formatted for the given chain."""
        pass

    @abstractmethod
    async def get_network(self, address: str) -> Optional[str]:
        """Identify the blockchain network for an address."""
        pass

    @abstractmethod
    async def get_transactions(
        self,
        address: str,
        chain: str,
        direction: str = "both",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch transactions for an address.
        Returns normalized canonical transaction dicts.
        """
        pass

    @abstractmethod
    async def get_transaction(self, tx_hash: str, chain: str) -> Optional[Dict[str, Any]]:
        """Fetch a single transaction by hash."""
        pass

    @abstractmethod
    async def get_balance(self, address: str, chain: str) -> float:
        """Get current balance of an address."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider."""
        pass

    @property
    @abstractmethod
    def is_demo(self) -> bool:
        """Whether this provider returns demo data."""
        pass
