"""Investigator-only public case reference and comparison endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.cases import _get_user
from app.models.models import User
from app.schemas.schemas import PublicCaseComparisonResponse, PublicCaseResponse
from app.services.public_case_service import build_comparison, get_public_case, list_public_cases


router = APIRouter(prefix="/public-cases", tags=["Public Case Validation"])


@router.get("", response_model=list[PublicCaseResponse])
async def list_public_case_references(current_user: User = Depends(_get_user)):
    """List curated, source-backed public case references for investigators."""
    return list_public_cases()


@router.get("/{case_id}", response_model=PublicCaseResponse)
async def get_public_case_reference(
    case_id: str,
    current_user: User = Depends(_get_user),
):
    case = get_public_case(case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Public case reference not found")
    return case


@router.get("/{case_id}/comparison", response_model=PublicCaseComparisonResponse)
async def get_public_case_comparison(
    case_id: str,
    current_user: User = Depends(_get_user),
):
    comparison = build_comparison(case_id)
    if comparison is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Public case reference not found")
    return comparison
