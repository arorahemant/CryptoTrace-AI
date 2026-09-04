"""Add the explicit accepted state for incoming reporter cases."""
from typing import Sequence, Union

from alembic import op


revision: str = "0006_case_accepted_status"
down_revision: Union[str, None] = "0005_reporter_asset_intake"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        # SQLAlchemy's Enum(CaseStatus) stores Python enum member names.
        op.execute("ALTER TYPE casestatus ADD VALUE IF NOT EXISTS 'ACCEPTED'")


def downgrade() -> None:
    # PostgreSQL does not support safely removing an enum value in place.
    # The accepted value is additive and downgrade remains intentionally a no-op.
    pass
