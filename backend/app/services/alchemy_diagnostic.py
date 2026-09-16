"""Shared fixed Alchemy checks and the allowlisted startup health summary."""
import asyncio
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from app.providers.alchemy import AlchemyEthereumProvider, ProviderFailure, quantity


STARTUP_TIMEOUT_SECONDS = 12

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


async def run_alchemy_diagnostic() -> AlchemyDiagnostic:
    """At most two upstream requests; no retries, persistence, or demo fallback."""
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


def empty_startup_summary(enabled: bool) -> dict:
    """Null pass flags mean no completed check, not success or provider failure."""
    return {"provider": "Alchemy", "chain_id": None, "rpc_pass": None,
            "asset_transfer_pass": None, "error_code": "pending" if enabled else "disabled",
            "checked_at": None}


async def startup_alchemy_summary() -> dict:
    """Return only public status fields, even if setup fails unexpectedly."""
    summary = empty_startup_summary(True)
    summary.update(rpc_pass=False, asset_transfer_pass=False)
    try:
        async with asyncio.timeout(STARTUP_TIMEOUT_SECONDS):
            result = await run_alchemy_diagnostic()
        code = next((error.error_type for error in result.errors.values()), None)
        summary.update(chain_id=result.chain_id, rpc_pass=result.rpc_pass,
                       asset_transfer_pass=result.asset_transfer_pass,
                       error_code=code if code is None or code in _ERROR_MESSAGES else "unavailable")
    except TimeoutError:
        summary["error_code"] = "timeout"
    except Exception as exc:
        summary["error_code"] = _safe_error(exc).error_type
    summary["checked_at"] = datetime.now(timezone.utc).isoformat()
    return summary
