"""CryptoTrace AI - Providers Package"""
from app.providers.base import BlockchainProvider
from app.providers.demo import DemoProvider


def get_provider(provider_name: str = "demo") -> BlockchainProvider:
    """Factory to get the appropriate blockchain provider."""
    providers = {
        "demo": DemoProvider,
    }
    provider_class = providers.get(provider_name, DemoProvider)
    return provider_class()


__all__ = ["BlockchainProvider", "DemoProvider", "get_provider"]
