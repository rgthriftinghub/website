"""baseline empty schema

Phase 1 has no business tables. This revision is intentionally empty: it exists
so `alembic upgrade head` succeeds and creates the `alembic_version` table,
giving later phases a migration base to build on.

Revision ID: 979fd1d45bdb
Revises:
Create Date: 2026-08-11 16:24:47.323944
"""
from typing import Sequence, Union

revision: str = '979fd1d45bdb'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
