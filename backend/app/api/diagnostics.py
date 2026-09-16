"""Fixed, read-only Alchemy connectivity checks for authenticated administrators."""
from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.auth import get_current_user
from app.core.permissions import require_permission
from app.models.models import User
from app.services.alchemy_diagnostic import AlchemyDiagnostic, run_alchemy_diagnostic


router = APIRouter(prefix="/diagnostics", tags=["Diagnostics"])


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
    return await run_alchemy_diagnostic()
