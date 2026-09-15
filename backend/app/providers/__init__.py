"""CryptoTrace AI - Providers Package"""
from app.providers.base import BlockchainProvider
from app.providers.demo import DemoProvider
from app.providers.alchemy import AlchemyEthereumProvider


def get_provider(provider_name: str = "demo") -> BlockchainProvider:
    """Factory to get the appropriate blockchain provider."""
    providers = {
        "demo": DemoProvider,
        "ethereum": AlchemyEthereumProvider,
        "alchemy_ethereum": AlchemyEthereumProvider,
    }
    if provider_name not in providers:
        raise ValueError("Blockchain provider is not connected")
    provider_class = providers[provider_name]
    return provider_class()


__all__ = ["BlockchainProvider", "DemoProvider", "get_provider"]
