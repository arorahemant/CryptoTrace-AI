"""One deterministic destination policy; a frontier is not a proven endpoint."""
from sqlalchemy import select
from app.models.models import Wallet, VASPAttribution
from app.services.attribution_service import normalize_attribution


def classify_candidates(wallets: dict, attributions: dict) -> list[dict]:
    candidates = []
    for address, wallet in wallets.items():
        if wallet.get("is_reported"):
            continue
        attribution = attributions.get(address, {})
        status = attribution.get("attribution_status", "unknown")
        kind = wallet.get("endpoint_kind", "not_expanded")
        if status == "known_verified":
            kind = "identified_service_address"
        elif status == "likely_inferred":
            kind = "candidate_vasp"
        if kind not in {"identified_service_address", "candidate_vasp", "last_observed_wallet", "not_expanded"}:
            continue
        candidates.append({"address": address, "kind": kind,
                           "expansion_state": wallet.get("expansion_state", "legacy_unknown"),
                           "hop_distance": wallet.get("hop_distance") or 0,
                           "attribution_status": status})
    rank = {"identified_service_address": 0, "candidate_vasp": 1,
            "last_observed_wallet": 2, "not_expanded": 3}
    # Prefer supported services, then nearest observed endpoint, then frontier.
    # Ties use address, never incomparable asset values or database row order.
    return sorted(candidates, key=lambda c: (rank[c["kind"]], c["hop_distance"], c["address"]))


async def destination_context(db, case) -> dict:
    wallets = (await db.scalars(select(Wallet).where(Wallet.case_id == case.id))).all()
    rows = (await db.scalars(select(VASPAttribution).where(VASPAttribution.case_id == case.id)
                            .order_by(VASPAttribution.created_at.desc(), VASPAttribution.id))).all()
    attributions = {}
    for row in rows:
        attributions.setdefault(row.wallet_address, normalize_attribution(row))
    wallet_data = {w.address: {"is_reported": w.is_reported, "hop_distance": w.hop_distance,
                               **(w.metadata_ or {})} for w in wallets}
    candidates = classify_candidates(wallet_data, attributions)
    return {"selected": candidates[0] if candidates else None, "candidates": candidates,
            "policy": "supported-service_then_observed-endpoint_then_frontier; nearest-hop_then_address"}
