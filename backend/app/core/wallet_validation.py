"""Wallet format validation shared by investigator and reporter intake."""
import re

from app.models.models import Blockchain


ASSETS_BY_BLOCKCHAIN = {
    Blockchain.BITCOIN: ("BTC",),
    Blockchain.ETHEREUM: ("ETH", "USDT", "USDC"),
    Blockchain.TRON: ("TRX", "USDT"),
    Blockchain.POLYGON: ("POL", "USDT", "USDC"),
    Blockchain.BSC: ("BNB", "USDT", "USDC"),
    Blockchain.DEMO: ("ETH",),
}


def supported_assets(blockchain: Blockchain) -> tuple[str, ...]:
    return ASSETS_BY_BLOCKCHAIN.get(blockchain, ())


def normalize_asset(blockchain: Blockchain, asset: str | None) -> str | None:
    value = (asset or "").strip().upper()
    if not value:
        return supported_assets(blockchain)[0] if supported_assets(blockchain) else None
    return value if value in supported_assets(blockchain) else None


def analysis_capability(blockchain: Blockchain) -> tuple[str, str]:
    if blockchain == Blockchain.DEMO:
        return "analysis_available", "Analysis available for Demo Network using deterministic demonstration data."
    return "analysis_not_connected", f"Report accepted. Analysis provider not connected for {blockchain.value.title()}."


def validate_wallet_format(address: str, blockchain: Blockchain = Blockchain.DEMO) -> bool:
    """Validate format without claiming address ownership or on-chain existence."""
    if blockchain == Blockchain.DEMO:
        return re.fullmatch(r"0x[A-Za-z0-9]{8,253}", address) is not None
    if blockchain in (Blockchain.ETHEREUM, Blockchain.POLYGON, Blockchain.BSC):
        return re.fullmatch(r"0x[0-9a-fA-F]{40}", address) is not None
    if blockchain == Blockchain.BITCOIN:
        return re.fullmatch(
            r"(?:bc1[a-z0-9]{11,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})", address
        ) is not None
    if blockchain == Blockchain.TRON:
        return re.fullmatch(r"T[1-9A-HJ-NP-Za-km-z]{33}", address) is not None
    return False
