"""
CryptoTrace AI - Blockchain Provider Abstraction
Abstract interface that all blockchain data providers must implement.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime


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
