"""Fixed, read-only Alchemy connectivity checks for authenticated administrators."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.core.permissions import require_permission
from app.models.models import User
from app.providers.alchemy import AlchemyEthereumProvider, ProviderFailure, quantity


router = APIRouter(prefix="/diagnostics", tags=["Diagnostics"])

# Public burn address, one historical block, at most one result. Empty results
# are valid: this checks API access, not balances or investigation evidence.
_PUBLIC_ADDRESS = "0x000000000000000000000000000000000000dEaD"
_ERROR_MESSAGES = {
    "not_configured": "Alchemy credentials are not configured.",
    "invalid_credentials": "Alchemy rejected the credentials.",
    "provider_limit": "Alchemy request limit reached.",
    "timeout": "Alchemy request timed out.",
    "malformed_response": "Alchemy returned an invalid response.",
    "chain_mismatch": "Alchemy did not report Ethereum Mainnet (chain ID 1).",
    "unavailable": "Alchemy request could not be completed.",
}


class DiagnosticError(BaseModel):
    error_type: str
    message: str


class AlchemyDiagnostic(BaseModel):
    provider: Literal["Alchemy"] = "Alchemy"
    chain_id: int | None = None
    rpc_pass: bool = False
    asset_transfer_pass: bool = False
    errors: dict[str, DiagnosticError] = Field(default_factory=dict)


def _safe_error(exc: Exception) -> DiagnosticError:
    # Never serialize/log exception text, upstream bodies, or credential URLs.
    code = exc.code if isinstance(exc, ProviderFailure) else "unavailable"
    if code not in _ERROR_MESSAGES:
        code = "unavailable"
    return DiagnosticError(error_type=code, message=_ERROR_MESSAGES[code])


@router.get("/alchemy", response_model=AlchemyDiagnostic)
async def alchemy_diagnostic(
    response: Response,
    administrator: User = Depends(get_current_user),
) -> AlchemyDiagnostic:
    """HTTP 200 means the diagnostic ran; inspect both pass flags for success."""
    require_permission(administrator, "users.manage")
    # Public demo credentials must never grant access to production diagnostics.
    if administrator.is_demo_account:
        raise HTTPException(status_code=403, detail="A non-demo administrator is required")
    response.headers["Cache-Control"] = "no-store"
    result = AlchemyDiagnostic()
    provider = AlchemyEthereumProvider()
    provider.retries = 0
    provider.max_requests = 2
    try:
        async with provider:
            try:
                result.chain_id = quantity(await provider.rpc("eth_chainId", []))
                if result.chain_id != 1:
                    raise ProviderFailure("chain_mismatch")
                result.rpc_pass = True
            except Exception as exc:
                result.errors["rpc"] = _safe_error(exc)

            try:
                transfers = await provider.rpc("alchemy_getAssetTransfers", [{
                    "fromAddress": _PUBLIC_ADDRESS,
                    "fromBlock": "0x1",
                    "toBlock": "0x1",
                    "category": ["external"],
                    "excludeZeroValue": True,
                    "withMetadata": False,
                    "maxCount": "0x1",
                    "order": "asc",
                }])
                if not isinstance(transfers, dict) or not isinstance(transfers.get("transfers"), list):
                    raise ProviderFailure("malformed_response")
                result.asset_transfer_pass = True
            except Exception as exc:
                result.errors["asset_transfer"] = _safe_error(exc)
    except Exception as exc:
        # Session setup/cleanup failures also stay inside the sanitized boundary.
        result.rpc_pass = result.asset_transfer_pass = False
        result.errors = {step: _safe_error(exc) for step in ("rpc", "asset_transfer")}
    return result
