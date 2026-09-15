"""Canonical transfer events. Integers/decimal strings are the source of truth.

Legacy numeric fields are display compatibility projections, never accounting
inputs. A transaction hash is not an event identity. Providers must supply a
stable event index (log index, trace address or output index), including 'native'
for a transaction's native transfer. No provider is enabled by this contract.
"""
from decimal import Decimal, localcontext
from typing import Iterable

FIELDS = ("transfer_id", "chain_id", "event_index", "asset_id", "amount_base_units",
          "token_decimals", "amount_exact", "amount_precision", "run_id",
          "block_number", "block_hash", "transaction_status", "log_index", "token_contract", "provenance")


def decimal_amount(units: str, decimals: int) -> str:
    digits = str(int(units)).zfill(decimals + 1)
    return (digits[:-decimals] + "." + digits[-decimals:]).rstrip("0").rstrip(".") if decimals else digits


def normalize_transfer(tx: dict, chain: str, *, legacy_demo: bool = False) -> dict:
    result = dict(tx)
    chain_id = str(tx.get("chain_id") or chain)
    if chain_id != chain:
        raise ValueError("Transfer chain does not match trace chain")
    decimals = tx.get("token_decimals")
    units = tx.get("amount_base_units")
    event = tx.get("event_index")
    asset_id = tx.get("asset_id")
    if legacy_demo and chain == "demo" and units is None:
        # Only the immutable, known ETH demo fixture may use this adapter.
        if tx.get("asset") != "ETH":
            raise ValueError("Non-fixture assets require explicit base units")
        decimals, event, asset_id = 18, "native", "demo:native"
        with localcontext() as ctx:
            ctx.prec = 120
            value = Decimal(str(tx["amount"])) * (10 ** decimals)
            if not value.is_finite() or value != value.to_integral_value():
                raise ValueError("Invalid fixture amount")
            units = str(int(value))
    if isinstance(decimals, bool) or not isinstance(decimals, int) or not 0 <= decimals <= 255:
        raise ValueError("Explicit token decimals required")
    if not isinstance(units, str) or not units.isascii() or not units.isdigit() or len(units) > 78:
        raise ValueError("Unsigned base-unit integer string required (maximum uint256)")
    if int(units) >= 2 ** 256:
        raise ValueError("Amount exceeds uint256")
    if event is None or not str(event) or not isinstance(asset_id, str) or not asset_id.startswith(chain_id + ":"):
        raise ValueError("Chain-qualified asset and stable event index required")
    import json
    # JSON tuple avoids delimiter collisions in chain/hash/event identifiers.
    identity = json.dumps([chain_id, tx["hash"], str(event)], separators=(",", ":"))
    exact = decimal_amount(units, decimals)
    result.update(transfer_id=identity, chain_id=chain_id, event_index=str(event),
                  asset_id=asset_id, amount_base_units=str(int(units)), token_decimals=decimals,
                  amount_exact=exact, amount_precision="exact", amount=float(exact))
    return result


def transfer_fields(tx: dict) -> dict:
    return {key: tx[key] for key in FIELDS if key in tx}


def record_fields(record) -> dict:
    """Legacy rows remain explicitly approximate; never manufacture precision."""
    stored = record.metadata_ or {}
    if stored.get("amount_precision") == "exact":
        return transfer_fields(stored)
    return {"amount_precision": "legacy_approximate", "transfer_id": f"legacy:{record.id}",
            "amount_exact": None, "amount_base_units": None, "token_decimals": None}


def asset_totals(transfers: Iterable[dict]) -> list[dict]:
    totals = {}
    for tx in transfers:
        if tx.get("amount_precision") != "exact":
            continue
        key = (tx["asset_id"], tx["token_decimals"])
        item = totals.setdefault(key, {"asset_id": key[0], "asset": tx.get("asset", ""),
                                      "token_decimals": key[1], "amount_base_units": "0"})
        item["amount_base_units"] = str(int(item["amount_base_units"]) + int(tx["amount_base_units"]))
    return [{**item, "amount_exact": decimal_amount(item["amount_base_units"], item["token_decimals"])}
            for _, item in sorted(totals.items())]


def format_totals(transfers: Iterable[dict]) -> str:
    return "; ".join(f"{t['amount_exact']} {t['asset']} [{t['asset_id']}]" for t in asset_totals(transfers)) or "exact totals unavailable"
