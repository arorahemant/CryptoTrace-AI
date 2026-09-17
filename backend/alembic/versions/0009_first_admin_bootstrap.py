"""Persist first-admin bootstrap consumption and a shared attempt budget."""
from alembic import op
import sqlalchemy as sa

revision = "0009_first_admin_bootstrap"
down_revision = "0008_transfer_metadata"
branch_labels = None
depends_on = None


def upgrade():
    state = op.create_table(
        "first_admin_bootstrap_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("consumed", sa.Boolean(), nullable=False),
        sa.Column("window_started", sa.Float(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_first_admin_bootstrap_singleton"),
    )
    # SQLAlchemy's UserRole enum stores member names (ADMIN), not values.
    connection = op.get_bind()
    has_admin = bool(connection.scalar(sa.text(
        "SELECT COUNT(*) FROM users WHERE role = 'ADMIN' AND is_demo_account = false"
    )))
    op.bulk_insert(state, [{"id": 1, "consumed": has_admin, "window_started": 0, "attempts": 0}])


def downgrade():
    raise RuntimeError("Do not remove permanent bootstrap consumption metadata")
