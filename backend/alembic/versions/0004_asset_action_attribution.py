"""Store the canonical attribution snapshot on prepared action requests."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_asset_action_attribution"
down_revision: Union[str, None] = "0003_attribution_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("asset_action_requests")}
    columns = {
        "attribution_entity": sa.String(length=255),
        "attribution_provenance": sa.String(length=50),
        "attribution_source_reference": sa.String(length=500),
        "attribution_reasoning": sa.Text(),
    }
    for name, column in columns.items():
        if name not in existing:
            op.add_column("asset_action_requests", sa.Column(name, column, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("asset_action_requests")}
    for name in ("attribution_reasoning", "attribution_source_reference", "attribution_provenance", "attribution_entity"):
        if name in existing:
            op.drop_column("asset_action_requests", name)
