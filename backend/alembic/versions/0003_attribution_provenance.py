"""Add explicit VASP attribution status and provenance fields."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_attribution_provenance"
down_revision: Union[str, None] = "0002_asset_action_requests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLUMNS = {
    "attribution_status": sa.String(length=50),
    "provenance": sa.String(length=50),
    "source_reference": sa.String(length=500),
    "reasoning": sa.Text(),
    "supporting_evidence_ids": sa.JSON(),
    "supporting_transaction_hashes": sa.JSON(),
    "verified_at": sa.DateTime(timezone=True),
}


def upgrade() -> None:
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("vasp_attributions")}
    for name, column in _COLUMNS.items():
        if name not in existing:
            op.add_column("vasp_attributions", sa.Column(name, column, nullable=True))
    # Existing rows are intentionally normalized by the application fallback;
    # no historical attribution is silently upgraded to verified here.


def downgrade() -> None:
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("vasp_attributions")}
    for name in reversed(tuple(_COLUMNS)):
        if name in existing:
            op.drop_column("vasp_attributions", name)
