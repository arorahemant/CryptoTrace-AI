"""Case-scoped deterministic investigator recommendations."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cases import _get_authorized_case, _get_user
from app.core.database import get_db
from app.models.models import User
from app.schemas.schemas import RecommendationsResponse
from app.services.recommendation_service import build_recommendations

router = APIRouter(prefix="/cases", tags=["Investigator Recommendations"])


@router.get("/{case_id}/recommendations", response_model=RecommendationsResponse)
async def get_recommendations(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_get_user),
):
    case = await _get_authorized_case(case_id, db, current_user)
    return {"case_id": case.id, "recommendations": await build_recommendations(db, case)}
