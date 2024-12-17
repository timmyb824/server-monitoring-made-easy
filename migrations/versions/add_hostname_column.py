"""Add hostname column

Revision ID: add_hostname_column
Revises: initial_schema
Create Date: 2024-01-17 02:15:44.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_hostname_column"
down_revision: Union[str, None] = "initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add hostname column
    op.add_column(
        "alerts",
        sa.Column(
            "hostname", sa.String(length=255), nullable=False, server_default="unknown"
        ),
    )
    # Remove server_default after all existing rows have been updated
    op.alter_column("alerts", "hostname", server_default=None)


def downgrade() -> None:
    op.drop_column("alerts", "hostname")
