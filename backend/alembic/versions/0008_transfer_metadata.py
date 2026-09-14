"""Preserve exact event provenance on fund-flow projections; no legacy backfill."""
from alembic import op
import sqlalchemy as sa

revision = "0008_transfer_metadata"
down_revision = "0007_access_capability"
branch_labels = None
depends_on = None


def upgrade():
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("transactions")}
    if "transfer_id" not in columns:
        op.add_column("transactions", sa.Column("transfer_id", sa.String(1024), nullable=True))
    inspector = sa.inspect(op.get_bind())
    names = {c["name"] for c in inspector.get_unique_constraints("transactions")}
    names.update(c["name"] for c in inspector.get_indexes("transactions"))
    if "uq_case_transfer_event" not in names:
        op.create_index("uq_case_transfer_event", "transactions", ["case_id", "transfer_id"], unique=True)

    for table in ("fund_flows", "asset_action_requests"):
        columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
        if "metadata" not in columns:
            op.add_column(table, sa.Column("metadata", sa.JSON(), nullable=True))


def downgrade():
    raise RuntimeError("Removing event provenance requires a reviewed backup restoration")
