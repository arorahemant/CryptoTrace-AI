"""Wallet format validation shared by investigator and reporter intake."""
import re

from app.models.models import Blockchain


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
    return False
