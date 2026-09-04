"""Deterministic, case-scoped investigator recommendations."""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.asset_actions import _case_context
from app.services.attribution_service import normalize_attribution
from app.models.models import (
    AssetActionRequest,
    AssetActionType,
    Case,
    Evidence,
    PatternFinding,
    Transaction,
    VASPAttribution,
    Wallet,
)


_SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value or "")


def _evidence_for(
    evidence: list[Evidence],
    *,
    finding: PatternFinding | None = None,
    transaction_hashes: set[str] | None = None,
    wallet: str | None = None,
) -> list[Evidence]:
    hashes = transaction_hashes or set()
    matched = [
        item for item in evidence
        if (finding and item.finding_id == finding.id)
        or (item.transaction_hash and item.transaction_hash in hashes)
        or (wallet and item.wallet_address == wallet)
    ]
    return sorted(matched, key=lambda item: str(item.id))


def _recommendation(
    *,
    case: Case,
    kind: str,
    title: str,
    action: str,
    reason: str,
    priority: str,
    evidence: list[Evidence],
    transaction_hashes: list[str] | None = None,
    finding_ids: list[Any] | None = None,
    target_wallet: str | None = None,
    source: str,
) -> dict:
    return {
        "recommendation_id": f"{kind}:{case.id}",
        "case_id": case.id,
        "type": kind,
        "title": title,
        "action": action,
        "factual_reason": reason,
        "priority": priority,
        "evidence_ids": [item.id for item in evidence],
        "transaction_hashes": transaction_hashes or [],
        "finding_ids": finding_ids or [],
        "target_wallet": target_wallet,
        "deterministic_source": source,
        "created_at": case.created_at or datetime(1970, 1, 1, tzinfo=timezone.utc),
    }


async def build_recommendations(db: AsyncSession, case: Case) -> list[dict]:
    """Derive stable recommendations from persisted investigation facts only."""
    wallets = (await db.scalars(select(Wallet).where(Wallet.case_id == case.id))).all()
    transactions = (await db.scalars(select(Transaction).where(Transaction.case_id == case.id))).all()
    findings = (await db.scalars(select(PatternFinding).where(PatternFinding.case_id == case.id))).all()
    evidence = (await db.scalars(select(Evidence).where(Evidence.case_id == case.id))).all()
    attributions = (await db.scalars(
        select(VASPAttribution)
        .where(VASPAttribution.case_id == case.id)
        .order_by(VASPAttribution.created_at.desc(), VASPAttribution.id)
    )).all()
    requests = (await db.scalars(select(AssetActionRequest).where(AssetActionRequest.case_id == case.id))).all()

    recommendations: list[dict] = []
    destination = next((wallet for wallet in wallets if wallet.is_destination), None)
    intermediary = max(
        (wallet for wallet in wallets if wallet.is_intermediary),
        key=lambda wallet: (wallet.total_received or 0, wallet.address),
        default=None,
    )
    if intermediary and (intermediary.total_received or 0) > 0:
        supporting_txs = sorted(
            (tx for tx in transactions if tx.to_address == intermediary.address),
            key=lambda tx: (-tx.amount, tx.timestamp, tx.hash),
        )
        tx_hashes = [tx.hash for tx in supporting_txs[:1]]
        linked = _evidence_for(evidence, transaction_hashes=set(tx_hashes), wallet=intermediary.address)
        if tx_hashes and linked:
            amount = supporting_txs[0].amount
            recommendations.append(_recommendation(
                case=case,
                kind="review_highest_value_intermediary",
                title="Review highest-value intermediary",
                action="Review intermediary wallet",
                reason=f"{intermediary.address} received the highest observed intermediary transfer of {amount:g} {supporting_txs[0].asset} in the traced case.",
                priority="high",
                evidence=linked,
                transaction_hashes=tx_hashes,
                target_wallet=intermediary.address,
                source="wallet.total_received + transaction.amount + linked evidence",
            ))

    strongest = max(
        findings,
        key=lambda item: (_SEVERITY_RANK.get(_enum_value(item.severity), 0), item.confidence or 0, str(item.id)),
        default=None,
    )
    if strongest and (
        _SEVERITY_RANK.get(_enum_value(strongest.severity), 0) >= 3
        or (strongest.confidence or 0) >= 0.7
    ):
        tx_hashes = list(strongest.supporting_transaction_ids or [])
        linked = _evidence_for(evidence, finding=strongest, transaction_hashes=set(tx_hashes))
        if linked or tx_hashes:
            recommendations.append(_recommendation(
                case=case,
                kind="inspect_strongest_finding",
                title="Inspect strongest finding",
                action="Inspect strongest finding transaction",
                reason=f"{strongest.pattern_name} is the strongest deterministic finding with {_enum_value(strongest.severity).upper()} severity and {strongest.confidence:.0%} confidence.",
                priority="high",
                evidence=linked,
                transaction_hashes=tx_hashes,
                finding_ids=[strongest.id],
                target_wallet=(strongest.affected_wallets or [None])[0],
                source="finding.severity + finding.confidence + finding references",
            ))

    destination_attribution = next(
        (item for item in attributions if destination and item.wallet_address == destination.address),
        None,
    )
    destination_attribution_data = normalize_attribution(destination_attribution) if destination_attribution else normalize_attribution({})
    if destination and destination_attribution_data["attribution_status"] in {"likely_inferred", "unknown"}:
        linked = _evidence_for(evidence, wallet=destination.address)
        if linked:
            recommendations.append(_recommendation(
                case=case,
                kind="review_destination_attribution",
                title="Review destination attribution" if destination_attribution_data["attribution_status"] == "likely_inferred" else "Investigate destination attribution",
                action="Review likely destination attribution" if destination_attribution_data["attribution_status"] == "likely_inferred" else "Investigate destination attribution",
                reason=(
                    f"The destination {destination.address} has LIKELY / INFERRED attribution to {destination_attribution_data['entity_name']}; investigator verification is required."
                    if destination_attribution_data["attribution_status"] == "likely_inferred"
                    else f"No sufficiently supported attribution is currently available for destination {destination.address}."
                ),
                priority="medium",
                evidence=linked,
                target_wallet=destination.address,
                source="destination wallet + VASP attribution confidence + linked evidence",
            ))

    context = await _case_context(db, case)
    relevant_evidence = _evidence_for(
        evidence,
        transaction_hashes={context["supporting_transaction_hash"]} if context["supporting_transaction_hash"] else set(),
        finding=next((item for item in findings if item.id == context["supporting_finding_id"]), None),
        wallet=context["destination_wallet"],
    )
    if destination and relevant_evidence:
        has_preservation_request = any(
            item.action_type == AssetActionType.PRESERVATION_REQUEST
            and item.target_wallet == destination.address
            and set(item.evidence_ids or []) == {str(ref.id) for ref in relevant_evidence}
            for item in requests
        )
        if not has_preservation_request:
            recommendations.append(_recommendation(
                case=case,
                kind="preserve_supporting_evidence",
                title="Preserve supporting evidence",
                action="Preserve supporting evidence",
                reason=f"{len(relevant_evidence)} evidence record(s) support the identified destination and have not yet been associated with a matching preservation request.",
                priority="medium",
                evidence=relevant_evidence,
                transaction_hashes=[context["supporting_transaction_hash"]] if context["supporting_transaction_hash"] else [],
                finding_ids=context["finding_ids"],
                target_wallet=destination.address,
                source="action-readiness evidence references + existing preservation requests",
            ))

    if context["ready"] and destination:
        has_action_request = any(item.target_wallet == destination.address for item in requests)
        if not has_action_request:
            recommendations.append(_recommendation(
                case=case,
                kind="prepare_asset_action_request",
                title="Prepare asset-action request",
                action="Prepare preservation or freeze-readiness request",
                reason="All deterministic Freeze Readiness checks are complete for the identified destination, and no matching asset-action request exists.",
                priority="high",
                evidence=relevant_evidence,
                transaction_hashes=[context["supporting_transaction_hash"]] if context["supporting_transaction_hash"] else [],
                finding_ids=context["finding_ids"],
                target_wallet=destination.address,
                source="action-readiness checks + existing asset-action requests",
            ))

    priority_order = {"high": 0, "medium": 1, "low": 2}
    type_order = {
        "review_highest_value_intermediary": 0,
        "inspect_strongest_finding": 1,
        "prepare_asset_action_request": 2,
        "review_destination_attribution": 3,
        "preserve_supporting_evidence": 4,
    }
    return sorted(recommendations, key=lambda item: (priority_order[item["priority"]], type_order[item["type"]], item["recommendation_id"]))[:5]
