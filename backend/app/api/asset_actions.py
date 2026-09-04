"""Case-scoped external asset-action readiness and request workflow."""
import hashlib
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cases import _get_authorized_case, _get_user
from app.core.audit import record_audit_event
from app.core.database import get_db
from app.models.models import (
    AssetActionRequest, AssetActionStatus, AssetActionType, Case, Evidence,
    PatternFinding, Transaction, User, VASPAttribution, Wallet,
)
from app.schemas.schemas import (
    AssetActionReadiness, AssetActionRequestCreate, AssetActionRequestResponse,
    AssetActionStatusSchema, AssetActionStatusUpdate,
)
from app.services.attribution_service import normalize_attribution

router = APIRouter(prefix="/cases", tags=["Asset Action Readiness"])

_TRANSITIONS = {
    AssetActionStatus.DRAFT: {AssetActionStatus.PREPARED},
    AssetActionStatus.PREPARED: {AssetActionStatus.SUBMITTED},
    AssetActionStatus.SUBMITTED: {
        AssetActionStatus.ACKNOWLEDGED,
        AssetActionStatus.DECLINED,
        AssetActionStatus.MORE_INFORMATION_REQUIRED,
    },
    AssetActionStatus.ACKNOWLEDGED: {AssetActionStatus.ACTIONED},
    AssetActionStatus.ACTIONED: set(),
    AssetActionStatus.DECLINED: set(),
    AssetActionStatus.MORE_INFORMATION_REQUIRED: set(),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _case_context(db: AsyncSession, case: Case) -> dict:
    wallet_result = await db.execute(
        select(Wallet)
        .where(Wallet.case_id == case.id, Wallet.is_destination.is_(True))
        .order_by(Wallet.total_received.desc(), Wallet.address)
    )
    destination = wallet_result.scalars().first()
    transactions = []
    attribution = None
    findings = []
    evidence = []
    if destination:
        tx_result = await db.execute(
            select(Transaction)
            .where(
                Transaction.case_id == case.id,
                Transaction.to_address == destination.address,
            )
            .order_by(Transaction.timestamp.desc())
        )
        transactions = tx_result.scalars().all()
        attribution = await db.scalar(
            select(VASPAttribution)
            .where(
                VASPAttribution.case_id == case.id,
                VASPAttribution.wallet_address == destination.address,
            )
            .order_by(VASPAttribution.created_at.desc())
        )
    findings = (await db.scalars(select(PatternFinding).where(PatternFinding.case_id == case.id))).all()
    evidence = (await db.scalars(select(Evidence).where(Evidence.case_id == case.id))).all()
    latest = transactions[0] if transactions else None
    supporting_finding = next(
        (
            item for item in findings
            if destination and (
                destination.address in (item.affected_wallets or [])
                or (latest and latest.hash in (item.supporting_transaction_ids or []))
            )
        ),
        None,
    )
    relevant_evidence = [
        item for item in evidence
        if (
            (destination and item.wallet_address == destination.address)
            or (latest and item.transaction_hash == latest.hash)
            or (supporting_finding and item.finding_id == supporting_finding.id)
        )
    ]
    normalized_attribution = normalize_attribution(attribution) if attribution else normalize_attribution({})
    has_attribution = normalized_attribution["attribution_status"] != "unknown"
    checks = [
        {"key": "destination_identified", "label": "Destination identified", "complete": destination is not None},
        {"key": "supporting_transaction", "label": "Supporting transaction identified", "complete": latest is not None},
        {"key": "supporting_finding", "label": "Supporting finding exists", "complete": supporting_finding is not None},
        {"key": "evidence_available", "label": "Evidence available", "complete": bool(relevant_evidence)},
        {"key": "asset_amount_available", "label": "Observed asset and amount available", "complete": bool(latest and latest.asset and latest.amount is not None)},
        {"key": "attribution_available", "label": "Attribution available", "complete": has_attribution},
    ]
    return {
        "case_id": case.id,
        "ready": all(item["complete"] for item in checks),
        "destination_wallet": destination.address if destination else None,
        "asset": latest.asset if latest else None,
        "observed_amount": latest.amount if latest else None,
        "last_movement_at": latest.timestamp if latest else None,
        "attribution_status": normalized_attribution["attribution_status"],
        "attribution_confidence": normalized_attribution["confidence"],
        "attribution_entity": normalized_attribution["entity_name"],
        "attribution_provenance": normalized_attribution["provenance"],
        "attribution_source_reference": normalized_attribution["source_reference"],
        "attribution_reasoning": normalized_attribution["reasoning"],
        "attribution_evidence_ids": normalized_attribution["supporting_evidence_ids"],
        "attribution_transaction_hashes": normalized_attribution["supporting_transaction_hashes"],
        "supporting_transaction_hash": latest.hash if latest else None,
        "supporting_finding_id": supporting_finding.id if supporting_finding else None,
        "evidence_count": len(relevant_evidence),
        "evidence_ids": [item.id for item in relevant_evidence],
        "finding_ids": [supporting_finding.id] if supporting_finding else [],
        "checks": checks,
        "supporting_reason": supporting_finding.description if supporting_finding else None,
    }


def _serialize(request: AssetActionRequest) -> dict:
    return {
        "id": request.id,
        "case_id": request.case_id,
        "actor_id": request.actor_id,
        "target_wallet": request.target_wallet,
        "action_type": request.action_type.value if hasattr(request.action_type, "value") else request.action_type,
        "status": request.status.value if hasattr(request.status, "value") else request.status,
        "evidence_ids": request.evidence_ids or [],
        "finding_ids": request.finding_ids or [],
        "observed_asset": request.observed_asset,
        "observed_amount": request.observed_amount,
        "last_movement_at": request.last_movement_at,
        "attribution_status": request.attribution_status,
        "attribution_confidence": request.attribution_confidence,
        "attribution_entity": request.attribution_entity,
        "attribution_provenance": request.attribution_provenance,
        "attribution_source_reference": request.attribution_source_reference,
        "attribution_reasoning": request.attribution_reasoning,
        "supporting_reason": request.supporting_reason,
        "created_at": request.created_at,
        "updated_at": request.updated_at,
    }


async def _get_request(case_id: str, request_id: str, db: AsyncSession, user: User) -> AssetActionRequest:
    case = await _get_authorized_case(case_id, db, user)
    try:
        request_uuid = uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Asset action request not found")
    item = await db.scalar(
        select(AssetActionRequest).where(
            AssetActionRequest.id == request_uuid,
            AssetActionRequest.case_id == case.id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Asset action request not found")
    return item


@router.get("/{case_id}/action-readiness", response_model=AssetActionReadiness)
async def get_action_readiness(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_get_user),
):
    case = await _get_authorized_case(case_id, db, current_user)
    return await _case_context(db, case)


@router.get("/{case_id}/action-requests", response_model=list[AssetActionRequestResponse])
async def list_action_requests(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_get_user),
):
    case = await _get_authorized_case(case_id, db, current_user)
    items = (await db.scalars(
        select(AssetActionRequest)
        .where(AssetActionRequest.case_id == case.id)
        .order_by(AssetActionRequest.created_at.desc())
    )).all()
    return [_serialize(item) for item in items]


@router.post("/{case_id}/action-requests", response_model=AssetActionRequestResponse)
async def create_action_request(
    case_id: str,
    request: AssetActionRequestCreate,
    request_context: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_get_user),
):
    case = await _get_authorized_case(case_id, db, current_user)
    target = await db.scalar(select(Wallet).where(Wallet.case_id == case.id, Wallet.address == request.target_wallet.strip()))
    if not target or not target.is_destination:
        raise HTTPException(status_code=422, detail="Target wallet must be an identified destination in this case")
    evidence_uuid_ids = list(dict.fromkeys(request.evidence_ids))
    finding_uuid_ids = list(dict.fromkeys(request.finding_ids))
    evidence_items = (await db.scalars(select(Evidence).where(Evidence.case_id == case.id, Evidence.id.in_(evidence_uuid_ids)))).all()
    finding_items = (await db.scalars(select(PatternFinding).where(PatternFinding.case_id == case.id, PatternFinding.id.in_(finding_uuid_ids)))).all()
    if len(evidence_items) != len(evidence_uuid_ids):
        raise HTTPException(status_code=422, detail="All evidence references must belong to this case")
    if len(finding_items) != len(finding_uuid_ids):
        raise HTTPException(status_code=422, detail="All finding references must belong to this case")

    context = await _case_context(db, case)
    fingerprint_data = {
        "case_id": str(case.id),
        "target_wallet": target.address,
        "action_type": request.action_type.value,
        "evidence_ids": sorted(str(item) for item in evidence_uuid_ids),
        "finding_ids": sorted(str(item) for item in finding_uuid_ids),
    }
    fingerprint = hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True).encode()).hexdigest()
    existing = await db.scalar(select(AssetActionRequest).where(AssetActionRequest.request_fingerprint == fingerprint))
    if existing:
        return _serialize(existing)

    item = AssetActionRequest(
        case_id=case.id,
        actor_id=current_user.id,
        target_wallet=target.address,
        action_type=AssetActionType(request.action_type.value),
        status=AssetActionStatus.DRAFT,
        evidence_ids=[str(item) for item in evidence_uuid_ids],
        finding_ids=[str(item) for item in finding_uuid_ids],
        observed_asset=context["asset"],
        observed_amount=context["observed_amount"],
        last_movement_at=context["last_movement_at"],
        attribution_status=context["attribution_status"],
        attribution_confidence=context["attribution_confidence"],
        attribution_entity=context["attribution_entity"],
        attribution_provenance=context["attribution_provenance"],
        attribution_source_reference=context["attribution_source_reference"],
        attribution_reasoning=context["attribution_reasoning"],
        supporting_reason=context["supporting_reason"],
        request_fingerprint=fingerprint,
    )
    db.add(item)
    await db.flush()
    record_audit_event(db, user=current_user, action="request_created", resource_type="asset_action_request", resource_id=str(item.id), details={"case_id": str(case.id), "action_type": request.action_type.value}, request=request_context)
    return _serialize(item)


@router.get("/{case_id}/action-requests/{request_id}", response_model=AssetActionRequestResponse)
async def get_action_request(
    case_id: str,
    request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_get_user),
):
    return _serialize(await _get_request(case_id, request_id, db, current_user))


@router.post("/{case_id}/action-requests/{request_id}/prepare", response_model=AssetActionRequestResponse)
async def prepare_action_request(
    case_id: str,
    request_id: str,
    request_context: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_get_user),
):
    item = await _get_request(case_id, request_id, db, current_user)
    if item.status == AssetActionStatus.PREPARED:
        return _serialize(item)
    if item.status != AssetActionStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Only draft requests can be prepared")
    item.status = AssetActionStatus.PREPARED
    item.updated_at = _now()
    record_audit_event(db, user=current_user, action="request_prepared", resource_type="asset_action_request", resource_id=str(item.id), details={"case_id": str(item.case_id)}, request=request_context)
    return _serialize(item)


@router.patch("/{case_id}/action-requests/{request_id}/status", response_model=AssetActionRequestResponse)
async def update_action_request_status(
    case_id: str,
    request_id: str,
    request: AssetActionStatusUpdate,
    request_context: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_get_user),
):
    item = await _get_request(case_id, request_id, db, current_user)
    next_status = AssetActionStatus(request.status.value)
    if next_status == item.status:
        return _serialize(item)
    if next_status not in _TRANSITIONS[item.status]:
        raise HTTPException(status_code=409, detail=f"Invalid request transition from {item.status.value} to {next_status.value}")
    item.status = next_status
    item.updated_at = _now()
    record_audit_event(db, user=current_user, action=f"request_{next_status.value}", resource_type="asset_action_request", resource_id=str(item.id), details={"case_id": str(item.case_id)}, request=request_context)
    return _serialize(item)
