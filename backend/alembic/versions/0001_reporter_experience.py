"""Add reporter intake and approved investigator profile tables.

Revision ID: 0001_reporter_experience
Revises: None

This is the first managed migration after the verified 13-table staging
baseline. It intentionally contains only additive product-hardening tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_reporter_experience"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if "investigator_public_profiles" not in existing:
        op.create_table(
            "investigator_public_profiles",
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=False),
            sa.Column("role_title", sa.String(length=255), nullable=False),
            sa.Column("is_reporter_visible", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id"),
        )

    if "reporter_accounts" not in existing:
        op.create_table(
            "reporter_accounts",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("username", sa.String(length=100), nullable=False),
            sa.Column("hashed_password", sa.String(length=255), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_reporter_accounts_email", "reporter_accounts", ["email"], unique=True)
        op.create_index("ix_reporter_accounts_username", "reporter_accounts", ["username"], unique=True)

    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "reporter_submissions" not in existing:
        op.create_table(
            "reporter_submissions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("reference_number", sa.String(length=50), nullable=False),
            sa.Column("reporter_id", sa.Uuid(), nullable=False),
            sa.Column("case_id", sa.Uuid(), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("reported_wallet", sa.String(length=255), nullable=False),
            sa.Column("blockchain", sa.String(length=50), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["reporter_id"], ["reporter_accounts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("case_id"),
        )
        op.create_index("ix_reporter_submissions_case_id", "reporter_submissions", ["case_id"], unique=True)
        op.create_index("ix_reporter_submissions_reference_number", "reporter_submissions", ["reference_number"], unique=True)
        op.create_index("ix_reporter_submissions_reporter_id", "reporter_submissions", ["reporter_id"], unique=False)
        op.create_index("ix_reporter_submissions_status", "reporter_submissions", ["status"], unique=False)


def downgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "reporter_submissions" in existing:
        op.drop_table("reporter_submissions")
    if "reporter_accounts" in existing:
        op.drop_table("reporter_accounts")
    if "investigator_public_profiles" in existing:
        op.drop_table("investigator_public_profiles")
