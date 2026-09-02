"""
CryptoTrace AI - Cases & Investigation API
Core investigation endpoints — the heart of the product.
"""
import uuid
import re
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.core.database import get_db
from app.core.audit import record_audit_event
from app.core.security import decode_access_token
from app.models.models import (
    Case, Wallet, Transaction, PatternFinding, Evidence,
    InvestigationEvent, FundFlow, RiskAssessment, VASPAttribution,
    Report, User, CaseStatus, Blockchain,
    UserRole,
)
from app.schemas.schemas import (
    CaseCreate, CaseResponse, CaseListResponse, InvestigateRequest, EvidenceCreate,
    AIQueryRequest, AIQueryResponse, ReplayResponse,
)
from app.services.investigation_service import InvestigationService
from app.services.ai_service import AIService

router = APIRouter(prefix="/cases", tags=["Cases & Investigation"])
logger = logging.getLogger(__name__)


async def _get_user(
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> User:
    """Extract an active user from a valid bearer token."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        payload = decode_access_token(token)
        if payload and payload.get("sub"):
            try:
                user = await db.get(User, uuid.UUID(payload["sub"]))
            except (ValueError, AttributeError, TypeError):
                user = None
            if user and user.is_active:
                return user
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid bearer token required",
        headers={"WWW-Authenticate": "Bearer"},
    )


router.dependencies.append(Depends(_get_user))


async def _get_authorized_case(
    case_id: str,
    db: AsyncSession,
    authorization: Optional[str] = None,
) -> Case:
    """Resolve a case while enforcing owner/supervisor/admin access.

    We intentionally return 404 for both unknown and unauthorized case IDs so
    investigators cannot use the API to enumerate other users' cases.
    """
    try:
        case_uuid = uuid.UUID(case_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Case not found")
    case = await db.get(Case, case_uuid)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    user = await _get_user(db, authorization)
    if user.role not in (UserRole.SUPERVISOR, UserRole.ADMIN) and case.investigator_id != user.id:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def _generate_case_number() -> str:
    """Generate a collision-resistant case number like CT-2025-AB12CD34."""
    ts = datetime.now(timezone.utc)
    short_id = uuid.uuid4().hex[:8].upper()
    return f"CT-{ts.year}-{short_id}"


@router.post("", response_model=CaseResponse)
async def create_case(
    request: CaseCreate,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
    request_context: Request = None,
):
    """Create a new investigation case."""
    user = await _get_user(db, authorization)

    blockchain = Blockchain(request.blockchain.value)
    # Validate wallet address format
    wallet = request.reported_wallet.strip()
    if not _validate_wallet_format(wallet, blockchain):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid wallet address format for {blockchain.value}.",
        )

    case = Case(
        case_number=_generate_case_number(),
        title=request.title,
        description=request.description,
        reported_wallet=wallet,
        blockchain=blockchain,
        status=CaseStatus.NEW,
        incident_date=request.incident_date,
        reported_amount=request.reported_amount,
        notes=request.notes,
        investigator_id=user.id,
        is_demo=(blockchain == Blockchain.DEMO),
    )
    db.add(case)
    await db.flush()
    await db.refresh(case)
    record_audit_event(
        db,
        user=user,
        action="case_created",
        resource_type="case",
        resource_id=str(case.id),
        details={"blockchain": case.blockchain.value, "is_demo": case.is_demo},
        request=request_context,
    )

    return _case_to_response(case)


@router.get("", response_model=CaseListResponse)
async def list_cases(
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """List all cases for the current user."""
    user = await _get_user(db, authorization)

    query = select(Case)
    if user.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        query = query.where(Case.investigator_id == user.id)
    result = await db.execute(query.order_by(Case.created_at.desc()))
    cases = result.scalars().all()

    return CaseListResponse(
        cases=[_case_to_response(c) for c in cases],
        total=len(cases),
    )


@router.get("/{case_id}")
async def get_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
    request_context: Request = None,
    current_user: User = Depends(_get_user),
):
    """Get case details with investigation summary."""
    case = await _get_authorized_case(case_id, db, authorization)
    record_audit_event(
        db,
        user=current_user,
        action="case_viewed",
        resource_type="case",
        resource_id=str(case.id),
        request=request_context,
    )

    # Get counts
    wallet_count = await db.scalar(
        select(func.count()).where(Wallet.case_id == case.id)
    )
    tx_count = await db.scalar(
        select(func.count()).where(Transaction.case_id == case.id)
    )
    finding_count = await db.scalar(
        select(func.count()).where(PatternFinding.case_id == case.id)
    )
    evidence_count = await db.scalar(
        select(func.count()).where(Evidence.case_id == case.id)
    )

    # Get overall risk
    risk_result = await db.execute(
        select(RiskAssessment)
        .where(RiskAssessment.case_id == case.id)
        .order_by(RiskAssessment.risk_score.desc())
        .limit(1)
    )
    top_risk = risk_result.scalars().first()

    case_data = _case_to_response(case)
    return {
        **case_data.model_dump(),
        "summary": {
            "total_wallets": wallet_count or 0,
            "total_transactions": tx_count or 0,
            "total_findings": finding_count or 0,
            "total_evidence": evidence_count or 0,
            "risk_level": top_risk.risk_category.value if top_risk else "low",
            "risk_score": top_risk.risk_score if top_risk else 0,
        },
    }


@router.post("/{case_id}/investigate")
async def investigate(
    case_id: str,
    request: InvestigateRequest = InvestigateRequest(),
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
    request_context: Request = None,
    current_user: User = Depends(_get_user),
):
    """
    Run the complete investigation pipeline for a case.
    This is the PRIMARY action — trace, analyze, detect, assess.
    """
    await _get_authorized_case(case_id, db, authorization)
    service = InvestigationService(db)

    try:
        result = await service.run_investigation(
            case_id=case_id,
            max_hops=request.max_hops,
            min_amount=request.min_amount,
            time_window_hours=request.time_window_hours,
            direction=request.direction,
        )
        record_audit_event(
            db,
            user=current_user,
            action="investigation_completed",
            resource_type="case",
            resource_id=case_id,
            details={"max_hops": request.max_hops, "direction": request.direction},
            request=request_context,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("Investigation failed for case %s", case_id)
        raise HTTPException(status_code=500, detail="Investigation failed")


@router.get("/{case_id}/graph")
async def get_graph(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Get the investigation graph for visualization."""
    await _get_authorized_case(case_id, db, authorization)
    service = InvestigationService(db)
    try:
        return await service.get_graph_data(case_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{case_id}/wallets")
async def get_wallets(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Get all discovered wallets for a case."""
    await _get_authorized_case(case_id, db, authorization)
    result = await db.execute(
        select(Wallet).where(Wallet.case_id == uuid.UUID(case_id))
    )
    wallets = result.scalars().all()
    return {
        "wallets": [
            {
                "id": str(w.id),
                "address": w.address,
                "label": w.label,
                "blockchain": w.blockchain.value if w.blockchain else "demo",
                "is_reported": w.is_reported,
                "is_intermediary": w.is_intermediary,
                "is_destination": w.is_destination,
                "is_suspicious": w.is_suspicious,
                "hop_distance": w.hop_distance,
                "total_received": w.total_received,
                "total_sent": w.total_sent,
                "transaction_count": w.transaction_count,
            }
            for w in wallets
        ],
        "total": len(wallets),
    }


@router.get("/{case_id}/transactions")
async def get_transactions(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Get all traced transactions for a case."""
    await _get_authorized_case(case_id, db, authorization)
    result = await db.execute(
        select(Transaction)
        .where(Transaction.case_id == uuid.UUID(case_id))
        .order_by(Transaction.timestamp)
    )
    txs = result.scalars().all()
    return {
        "transactions": [
            {
                "id": str(t.id),
                "hash": t.hash,
                "blockchain": t.blockchain.value if t.blockchain else "demo",
                "block_number": t.block_number,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                "from_address": t.from_address,
                "to_address": t.to_address,
                "asset": t.asset,
                "amount": t.amount,
                "amount_usd": t.amount_usd,
                "status": t.status,
                "source": t.source,
                "is_suspicious": t.is_suspicious,
                "hop_number": t.hop_number,
            }
            for t in txs
        ],
        "total": len(txs),
    }


@router.get("/{case_id}/findings")
async def get_findings(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Get suspicious pattern findings for a case."""
    await _get_authorized_case(case_id, db, authorization)
    result = await db.execute(
        select(PatternFinding).where(PatternFinding.case_id == uuid.UUID(case_id))
    )
    findings = result.scalars().all()
    return {
        "findings": [
            {
                "id": str(f.id),
                "pattern_type": f.pattern_type.value if f.pattern_type else "",
                "pattern_name": f.pattern_name,
                "description": f.description,
                "severity": f.severity.value if f.severity else "medium",
                "confidence": f.confidence,
                "trigger": f.trigger,
                "affected_wallets": f.affected_wallets,
                "supporting_transaction_ids": f.supporting_transaction_ids,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in findings
        ],
        "total": len(findings),
    }


@router.post("/{case_id}/evidence")
async def save_evidence(
    case_id: str,
    request: EvidenceCreate,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
    request_context: Request = None,
    current_user: User = Depends(_get_user),
):
    """Persist an investigator-selected evidence item for this case."""
    case = await _get_authorized_case(case_id, db, authorization)

    if request.finding_id:
        finding = await db.get(PatternFinding, request.finding_id)
        if not finding or finding.case_id != case.id:
            raise HTTPException(status_code=400, detail="Finding does not belong to this case")

    if request.transaction_hash:
        transaction = await db.scalar(
            select(Transaction).where(
                Transaction.case_id == case.id,
                Transaction.hash == request.transaction_hash,
            )
        )
        if not transaction:
            raise HTTPException(status_code=400, detail="Transaction does not belong to this case")

    if request.wallet_address:
        wallet = await db.scalar(
            select(Wallet).where(
                Wallet.case_id == case.id,
                Wallet.address == request.wallet_address,
            )
        )
        if not wallet:
            raise HTTPException(status_code=400, detail="Wallet does not belong to this case")

    evidence = Evidence(
        case_id=case.id,
        finding_id=request.finding_id,
        transaction_hash=request.transaction_hash,
        wallet_address=request.wallet_address,
        evidence_type=request.evidence_type,
        title=request.title,
        description=request.description,
        reason=request.reason,
        source=request.source,
        is_bookmarked=True,
        metadata_=request.metadata,
    )
    db.add(evidence)
    await db.flush()
    await db.refresh(evidence)
    record_audit_event(
        db,
        user=current_user,
        action="evidence_saved",
        resource_type="evidence",
        resource_id=str(evidence.id),
        details={"case_id": str(case.id), "evidence_type": evidence.evidence_type},
        request=request_context,
    )
    return {
        "id": str(evidence.id),
        "case_id": str(evidence.case_id),
        "finding_id": str(evidence.finding_id) if evidence.finding_id else None,
        "evidence_type": evidence.evidence_type,
        "title": evidence.title,
        "description": evidence.description,
        "reason": evidence.reason,
        "transaction_hash": evidence.transaction_hash,
        "wallet_address": evidence.wallet_address,
        "source": evidence.source,
        "is_bookmarked": evidence.is_bookmarked,
        "created_at": evidence.created_at.isoformat() if evidence.created_at else None,
    }


@router.get("/{case_id}/evidence")
async def get_evidence(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Get all evidence items for a case."""
    await _get_authorized_case(case_id, db, authorization)
    result = await db.execute(
        select(Evidence).where(Evidence.case_id == uuid.UUID(case_id))
    )
    evidence = result.scalars().all()
    return {
        "evidence": [
            {
                "id": str(e.id),
                "case_id": str(e.case_id),
                "finding_id": str(e.finding_id) if e.finding_id else None,
                "evidence_type": e.evidence_type,
                "title": e.title,
                "description": e.description,
                "reason": e.reason,
                "transaction_hash": e.transaction_hash,
                "wallet_address": e.wallet_address,
                "source": e.source,
                "is_bookmarked": e.is_bookmarked,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in evidence
        ],
        "total": len(evidence),
    }


@router.get("/{case_id}/timeline")
async def get_timeline(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Get chronological investigation timeline."""
    await _get_authorized_case(case_id, db, authorization)
    result = await db.execute(
        select(InvestigationEvent)
        .where(InvestigationEvent.case_id == uuid.UUID(case_id))
        .order_by(InvestigationEvent.sequence_order)
    )
    events = result.scalars().all()
    return {
        "events": [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "title": e.title,
                "description": e.description,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "transaction_hash": e.transaction_hash,
                "from_address": e.from_address,
                "to_address": e.to_address,
                "amount": e.amount,
                "asset": e.asset,
                "sequence_order": e.sequence_order,
            }
            for e in events
        ],
        "total_events": len(events),
    }


@router.get("/{case_id}/fund-flow")
async def get_fund_flow(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Get fund flow paths."""
    await _get_authorized_case(case_id, db, authorization)
    result = await db.execute(
        select(FundFlow)
        .where(FundFlow.case_id == uuid.UUID(case_id))
        .order_by(FundFlow.hop_number, FundFlow.path_index)
    )
    flows = result.scalars().all()
    return {
        "fund_flows": [
            {
                "from_address": f.from_address,
                "to_address": f.to_address,
                "amount": f.amount,
                "asset": f.asset,
                "hop_number": f.hop_number,
                "timestamp": f.timestamp.isoformat() if f.timestamp else None,
                "transaction_hash": f.transaction_hash,
                "is_primary_path": f.is_primary_path,
            }
            for f in flows
        ],
        "total": len(flows),
    }


@router.get("/{case_id}/why/{wallet_address}")
async def why_flagged(
    case_id: str,
    wallet_address: str,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """WHY WAS THIS FLAGGED? — Signature feature."""
    await _get_authorized_case(case_id, db, authorization)
    service = InvestigationService(db)
    try:
        return await service.get_why_explanation(case_id, wallet_address)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{case_id}/replay", response_model=ReplayResponse)
async def get_replay(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Get replay events for chronological animation."""
    await _get_authorized_case(case_id, db, authorization)
    service = InvestigationService(db)
    events = await service.get_replay_events(case_id)
    return {
        "case_id": case_id,
        "total_steps": len(events),
        "events": events,
    }


@router.post("/{case_id}/ai/query", response_model=AIQueryResponse)
async def ai_query(
    case_id: str,
    request: AIQueryRequest,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """AI Investigation Copilot — grounded answers from case data."""
    await _get_authorized_case(case_id, db, authorization)
    question = request.question
    if len(question) < 3:
        raise HTTPException(status_code=400, detail="Question is too short")

    ai_service = AIService(db)
    return await ai_service.query(case_id, question)


@router.post("/{case_id}/report")
async def generate_report(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
    request_context: Request = None,
    current_user: User = Depends(_get_user),
):
    """Generate investigation report."""
    case = await _get_authorized_case(case_id, db, authorization)

    # Build report from all case data
    ai_service = AIService(db)
    context = await ai_service._build_context(case.id)

    sections = []

    # Case Information (FACT)
    sections.append({
        "title": "Case Information",
        "section_type": "fact",
        "content": (
            f"Case Number: {case.case_number}\n"
            f"Title: {case.title}\n"
            f"Reported Wallet: {case.reported_wallet}\n"
            f"Blockchain: {case.blockchain.value if case.blockchain else 'N/A'}\n"
            f"Status: {case.status.value if case.status else 'N/A'}\n"
            f"Reported Amount: {case.reported_amount or 'N/A'}\n"
            f"Incident Date: {case.incident_date or 'N/A'}"
        ),
    })

    if context:
        # Fund Flow (ANALYSIS)
        fund_flow = context.get("fund_flow_path", [])
        if fund_flow:
            flow_text = "Primary fund flow path:\n\n"
            for step in fund_flow:
                flow_text += (
                    f"Hop {step['hop']}: {step['from'][:16]}... → "
                    f"{step['to'][:16]}... ({step['amount']:.4f} ETH)\n"
                )
            sections.append({
                "title": "Fund Flow Analysis",
                "section_type": "analysis",
                "content": flow_text,
            })

        # Suspicious Patterns (ANALYSIS)
        findings = context.get("findings", [])
        if findings:
            findings_text = f"{len(findings)} suspicious pattern(s) detected:\n\n"
            for f in findings:
                findings_text += (
                    f"• {f['pattern']} (severity: {f['severity']}, "
                    f"confidence: {f['confidence']:.0%})\n"
                    f"  {f['description']}\n\n"
                )
            sections.append({
                "title": "Suspicious Patterns",
                "section_type": "analysis",
                "content": findings_text,
            })

        # Risk Assessment (ANALYSIS)
        risks = context.get("risk_assessments", [])
        if risks:
            risk_text = "Wallet risk assessments:\n\n"
            for r in sorted(risks, key=lambda x: x["score"], reverse=True):
                risk_text += (
                    f"• {r['wallet'][:16]}...: {r['category'].upper()} "
                    f"(score: {r['score']}/100)\n"
                )
            sections.append({
                "title": "Risk Assessment",
                "section_type": "analysis",
                "content": risk_text,
            })

        # VASP Attribution (INFERENCE)
        vasps = context.get("vasp_attributions", [])
        if vasps:
            vasp_text = "Entity attributions:\n\n"
            for v in vasps:
                vasp_text += (
                    f"• {v['wallet'][:16]}...: {v['entity']} "
                    f"(confidence: {v['confidence']}, source: {v['source']})\n"
                )
            vasp_text += (
                "\nNote: Attributions reflect available intelligence data. "
                "Ownership cannot be confirmed without additional verification."
            )
            sections.append({
                "title": "VASP Attribution",
                "section_type": "inference",
                "content": vasp_text,
            })

        # Summary (AI SUMMARY)
        wallets = context.get("wallets", [])
        summary_text = (
            f"Investigation traced {context.get('transactions_count', 0)} transactions "
            f"across {len(wallets)} wallets from the reported wallet "
            f"{case.reported_wallet[:16]}...\n\n"
            f"Key findings: {len(findings)} suspicious patterns detected. "
        )
        if vasps:
            summary_text += (
                f"Funds were traced to a wallet attributed to "
                f"{vasps[0]['entity']} ({vasps[0]['confidence']} confidence). "
            )
        summary_text += "This report is generated from structured investigation data."

        if case.is_demo:
            summary_text += "\n\n⚠️ DEMO DATA: This investigation used demonstration data."

        sections.append({
            "title": "Investigation Summary",
            "section_type": "ai_summary",
            "content": summary_text,
        })

    # Save report
    report = Report(
        case_id=case.id,
        title=f"Investigation Report — {case.case_number}",
        report_type="investigation",
        content=[s for s in sections],
        summary=sections[-1]["content"] if sections else "",
        generated_by="cryptotrace_system",
        status="draft",
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)
    record_audit_event(
        db,
        user=current_user,
        action="report_generated",
        resource_type="report",
        resource_id=str(report.id),
        details={"case_id": str(case.id)},
        request=request_context,
    )

    return {
        "id": str(report.id),
        "case_id": str(case.id),
        "title": report.title,
        "sections": sections,
        "summary": report.summary,
        "generated_by": report.generated_by,
        "status": report.status,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


@router.get("/{case_id}/report")
async def get_report(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Get the latest report for a case."""
    await _get_authorized_case(case_id, db, authorization)
    result = await db.execute(
        select(Report)
        .where(Report.case_id == uuid.UUID(case_id))
        .order_by(Report.created_at.desc())
        .limit(1)
    )
    report = result.scalars().first()
    if not report:
        raise HTTPException(status_code=404, detail="No report generated yet")

    return {
        "id": str(report.id),
        "case_id": str(report.case_id),
        "title": report.title,
        "sections": report.content,
        "summary": report.summary,
        "generated_by": report.generated_by,
        "status": report.status,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


def _validate_wallet_format(address: str, blockchain: Blockchain = Blockchain.DEMO) -> bool:
    """Validate an address without pretending to validate ownership.

    Demo addresses intentionally use readable synthetic identifiers. EVM
    production chains require a canonical 20-byte hex address; Bitcoin accepts
    the common Base58 and bech32 forms. The provider still decides whether an
    address exists on-chain.
    """
    if blockchain == Blockchain.DEMO:
        return re.fullmatch(r"0x[A-Za-z0-9]{8,253}", address) is not None
    if blockchain in (Blockchain.ETHEREUM, Blockchain.POLYGON, Blockchain.BSC):
        return re.fullmatch(r"0x[0-9a-fA-F]{40}", address) is not None
    if blockchain == Blockchain.BITCOIN:
        return re.fullmatch(
            r"(?:bc1[a-z0-9]{11,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})", address
        ) is not None
    return False


def _case_to_response(case: Case) -> CaseResponse:
    return CaseResponse(
        id=case.id,
        case_number=case.case_number,
        title=case.title,
        description=case.description,
        reported_wallet=case.reported_wallet,
        blockchain=case.blockchain.value if case.blockchain else "demo",
        status=case.status.value if case.status else "new",
        incident_date=case.incident_date,
        reported_amount=case.reported_amount,
        notes=case.notes,
        investigator_id=case.investigator_id,
        is_demo=case.is_demo,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )
