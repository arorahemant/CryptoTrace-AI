"""Add reporter asset metadata and explicit intake provenance."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_reporter_asset_intake"
down_revision: Union[str, None] = "0004_asset_action_attribution"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # SQLAlchemy's Enum(Blockchain) stores Python enum member names in
        # the existing PostgreSQL type (for example, ETHEREUM), while the
        # API exposes the lower-case values. Add the matching member name.
        op.execute("ALTER TYPE blockchain ADD VALUE IF NOT EXISTS 'TRON'")

    for table_name, column_name, column in (
        ("reporter_submissions", "asset", sa.String(length=50)),
        ("cases", "asset", sa.String(length=50)),
        ("cases", "source_submission_reference", sa.String(length=50)),
    ):
        existing = {item["name"] for item in sa.inspect(bind).get_columns(table_name)}
        if column_name not in existing:
            op.add_column(table_name, sa.Column(column_name, column, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    for table_name, column_name in (
        ("cases", "source_submission_reference"),
        ("cases", "asset"),
        ("reporter_submissions", "asset"),
    ):
        existing = {item["name"] for item in sa.inspect(bind).get_columns(table_name)}
        if column_name in existing:
            op.drop_column(table_name, column_name)
