"""Separate processing/closure and identify legacy demonstration accounts."""
from alembic import op
import sqlalchemy as sa

revision = "0007_access_capability"
down_revision = "0006_case_accepted_status"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    for table in ("users", "reporter_accounts"):
        columns = {c["name"] for c in sa.inspect(connection).get_columns(table)}
        if "is_demo_account" not in columns:
            op.add_column(table, sa.Column("is_demo_account", sa.Boolean(), nullable=False, server_default=sa.false()))
        names = ("investigator", "supervisor", "admin") if table == "users" else ("reporter",)
        for name in names:
            connection.execute(sa.text(f"UPDATE {table} SET is_demo_account = :demo WHERE username = :name AND email = :email"),
                               {"demo": True, "name": name, "email": f"{name}@cryptotrace.ai"})
    columns = {c["name"] for c in sa.inspect(connection).get_columns("cases")}
    if "analysis_summary" not in columns:
        op.add_column("cases", sa.Column("analysis_summary", sa.JSON(), nullable=True))
    if "closed_at" not in columns:
        op.add_column("cases", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    # Previous COMPLETED meant processing success, never an investigator closure.
    connection.execute(sa.text("UPDATE cases SET status = 'REVIEW' WHERE status = 'COMPLETED' AND closed_at IS NULL"))


def downgrade():
    # Removing these fields would erase closure/provenance distinctions.
    raise RuntimeError("Restore a reviewed backup instead of removing Phase 1 security metadata")
