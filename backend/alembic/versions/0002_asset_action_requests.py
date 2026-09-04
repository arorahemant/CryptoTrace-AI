"""Add case-scoped external asset action request workflow."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_asset_action_requests"
down_revision: Union[str, None] = "0001_reporter_experience"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "asset_action_requests" in existing:
        return

    action_type = sa.Enum("freeze_request", "preservation_request", name="assetactiontype")
    action_status = sa.Enum(
        "draft", "prepared", "submitted", "acknowledged", "actioned",
        "declined", "more_information_required", name="assetactionstatus",
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        action_type.create(bind, checkfirst=True)
        action_status.create(bind, checkfirst=True)

    op.create_table(
        "asset_action_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("target_wallet", sa.String(length=255), nullable=False),
        sa.Column("action_type", action_type, nullable=False),
        sa.Column("status", action_status, nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("finding_ids", sa.JSON(), nullable=False),
        sa.Column("observed_asset", sa.String(length=50), nullable=True),
        sa.Column("observed_amount", sa.Float(), nullable=True),
        sa.Column("last_movement_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attribution_status", sa.String(length=50), nullable=False),
        sa.Column("attribution_confidence", sa.String(length=50), nullable=False),
        sa.Column("supporting_reason", sa.Text(), nullable=True),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_fingerprint"),
    )
    op.create_index("ix_asset_action_requests_case", "asset_action_requests", ["case_id"])
    op.create_index("ix_asset_action_requests_status", "asset_action_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_asset_action_requests_status", table_name="asset_action_requests")
    op.drop_index("ix_asset_action_requests_case", table_name="asset_action_requests")
    op.drop_table("asset_action_requests")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="assetactionstatus").drop(bind, checkfirst=True)
        sa.Enum(name="assetactiontype").drop(bind, checkfirst=True)
