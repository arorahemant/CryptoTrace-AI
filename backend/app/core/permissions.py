"""Explicit role permissions. Object ownership is checked separately."""
from fastapi import HTTPException

PERMISSIONS = {
    "reporter": frozenset({"submission.create", "submission.read_own"}),
    "investigator": frozenset({"case.read", "case.write", "submission.review", "submission.accept", "profile.write"}),
    "supervisor": frozenset({"case.read", "submission.review", "profile.write"}),
    "admin": frozenset({"case.read", "case.write", "submission.review", "submission.accept", "profile.write", "users.manage"}),
}


def permissions_for(user) -> list[str]:
    role = getattr(user.role, "value", user.role)
    return sorted(PERMISSIONS.get(role, ()))


def require_permission(user, permission: str) -> None:
    if not user.is_active or permission not in permissions_for(user):
        raise HTTPException(status_code=403, detail="Permission denied")
