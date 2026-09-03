"""Reporter intake and limited-status API.

Reporter tokens are valid only for these reporter-owned routes. Investigator
case endpoints resolve identities from the separate investigator user table.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.audit import record_audit_event
from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.wallet_validation import validate_wallet_format
from app.models.models import (
    Blockchain,
    Case,
    CaseStatus,
    InvestigatorPublicProfile,
    ReporterAccount,
    ReporterSubmission,
    User,
    UserRole,
)
from app.schemas.schemas import ReporterSubmissionCreate, ReporterSubmissionResponse


router = APIRouter(prefix="/reporter", tags=["Reporter"])


def _new_reference_number() -> str:
    year = datetime.now(timezone.utc).year
    return f"CTR-{year}-{uuid.uuid4().hex[:8].upper()}"


async def _get_reporter(
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> ReporterAccount:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_access_token(authorization[7:])
    if not payload or payload.get("role") != "reporter" or not payload.get("sub"):
        raise HTTPException(status_code=403, detail="Reporter access required")
    try:
        reporter = await db.get(ReporterAccount, uuid.UUID(payload["sub"]))
    except (ValueError, TypeError, AttributeError):
        reporter = None
    if not reporter:
        raise HTTPException(status_code=401, detail="Reporter account not found")
    if not reporter.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    return reporter


async def _owned_submission(
    submission_id: str,
    db: AsyncSession,
    reporter: ReporterAccount,
) -> ReporterSubmission:
    try:
        submission_uuid = uuid.UUID(submission_id)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=404, detail="Report not found")
    result = await db.execute(
        select(ReporterSubmission).where(
            ReporterSubmission.id == submission_uuid,
            ReporterSubmission.reporter_id == reporter.id,
        )
    )
    submission = result.scalars().first()
    if not submission:
        raise HTTPException(status_code=404, detail="Report not found")
    return submission


def _reporter_status(case: Optional[Case]) -> tuple[str, str, str]:
    if not case:
        return (
            "report_received",
            "Report received",
            "Your report is queued for investigator review. Keep the reference ID for future access.",
        )
    if case.status == CaseStatus.COMPLETED:
        return (
            "investigation_completed",
            "Investigation completed",
            "The assigned case is marked complete. Retain your reference ID for future updates.",
        )
    if case.status == CaseStatus.REVIEW:
        return (
            "further_review_required",
            "Further review required",
            "The case remains with the investigation team for further review.",
        )
    return (
        "under_investigation",
        "Under investigation",
        "The case is assigned for investigation. No action is required unless more information is requested.",
    )


async def _serialize_submission(
    db: AsyncSession,
    submission: ReporterSubmission,
) -> dict:
    case = await db.get(Case, submission.case_id) if submission.case_id else None
    status_code, status_label, next_step = _reporter_status(case)
    public_investigator = None
    if case:
        profile = await db.get(InvestigatorPublicProfile, case.investigator_id)
        if profile and profile.is_reporter_visible:
            public_investigator = {
                "display_name": profile.display_name,
                "role_title": profile.role_title,
            }
    last_update = case.updated_at if case and case.updated_at else submission.updated_at
    return {
        "id": submission.id,
        "reference_number": submission.reference_number,
        "title": submission.title,
        "reported_wallet": submission.reported_wallet,
        "blockchain": submission.blockchain,
        "status": status_code,
        "status_label": status_label,
        "submitted_at": submission.submitted_at,
        "last_status_update": last_update or submission.submitted_at,
        "next_step": next_step,
        "assigned_investigator": public_investigator,
    }


@router.post("/submissions", response_model=ReporterSubmissionResponse)
async def create_submission(
    request: ReporterSubmissionCreate,
    request_context: Request,
    db: AsyncSession = Depends(get_db),
    reporter: ReporterAccount = Depends(_get_reporter),
):
    blockchain = Blockchain(request.blockchain.value)
    wallet = request.reported_wallet.strip()
    if not validate_wallet_format(wallet, blockchain):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid wallet address format for {blockchain.value}.",
        )
    submission = ReporterSubmission(
        reference_number=_new_reference_number(),
        reporter_id=reporter.id,
        title=request.title.strip(),
        reported_wallet=wallet,
        blockchain=blockchain.value,
        description=request.description.strip() if request.description else None,
        status="report_received",
    )
    db.add(submission)
    await db.flush()
    await db.refresh(submission)
    record_audit_event(
        db,
        user=None,
        action="reporter_submission_created",
        resource_type="reporter_submission",
        resource_id=str(submission.id),
        details={"reporter_id": str(reporter.id)},
        request=request_context,
    )
    return await _serialize_submission(db, submission)


@router.get("/submissions", response_model=list[ReporterSubmissionResponse])
async def list_own_submissions(
    db: AsyncSession = Depends(get_db),
    reporter: ReporterAccount = Depends(_get_reporter),
):
    result = await db.execute(
        select(ReporterSubmission)
        .where(ReporterSubmission.reporter_id == reporter.id)
        .order_by(ReporterSubmission.submitted_at.desc())
    )
    return [await _serialize_submission(db, item) for item in result.scalars().all()]


@router.get("/submissions/review")
async def list_submissions_for_review(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.INVESTIGATOR, UserRole.SUPERVISOR, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Investigator access required")
    result = await db.execute(
        select(ReporterSubmission)
        .where(ReporterSubmission.case_id.is_(None))
        .order_by(ReporterSubmission.submitted_at.asc())
    )
    return {
        "submissions": [
            {
                "id": str(item.id),
                "reference_number": item.reference_number,
                "title": item.title,
                "reported_wallet": item.reported_wallet,
                "blockchain": item.blockchain,
                "description": item.description,
                "status": item.status,
                "submitted_at": item.submitted_at.isoformat() if item.submitted_at else None,
            }
            for item in result.scalars().all()
        ]
    }


@router.post("/submissions/{submission_id}/assign")
async def assign_submission(
    submission_id: str,
    request_context: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.INVESTIGATOR, UserRole.SUPERVISOR, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Investigator access required")
    try:
        submission_uuid = uuid.UUID(submission_id)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=404, detail="Report not found")
    result = await db.execute(
        select(ReporterSubmission)
        .where(ReporterSubmission.id == submission_uuid)
        .with_for_update()
    )
    submission = result.scalars().first()
    if not submission:
        raise HTTPException(status_code=404, detail="Report not found")
    if submission.case_id:
        raise HTTPException(status_code=409, detail="Report is already assigned")

    blockchain = Blockchain(submission.blockchain)
    case = Case(
        case_number=f"CT-{datetime.now(timezone.utc).year}-{uuid.uuid4().hex[:8].upper()}",
        title=submission.title,
        description=submission.description,
        reported_wallet=submission.reported_wallet,
        blockchain=blockchain,
        status=CaseStatus.NEW,
        investigator_id=current_user.id,
        is_demo=(blockchain == Blockchain.DEMO),
    )
    db.add(case)
    await db.flush()
    submission.case_id = case.id
    submission.status = "under_investigation"
    record_audit_event(
        db,
        user=current_user,
        action="case_created",
        resource_type="case",
        resource_id=str(case.id),
        details={"source": "reporter_submission", "case_id": str(case.id)},
        request=request_context,
    )
    record_audit_event(
        db,
        user=current_user,
        action="reporter_submission_assigned",
        resource_type="case",
        resource_id=str(case.id),
        details={"case_id": str(case.id), "submission_id": str(submission.id)},
        request=request_context,
    )
    return {"case_id": str(case.id), "case_number": case.case_number}


@router.get("/submissions/{submission_id}", response_model=ReporterSubmissionResponse)
async def get_own_submission(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    reporter: ReporterAccount = Depends(_get_reporter),
):
    submission = await _owned_submission(submission_id, db, reporter)
    return await _serialize_submission(db, submission)
