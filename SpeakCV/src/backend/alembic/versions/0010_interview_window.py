"""interview window

Revision ID: 0010_interview_window
Revises: 0009_reality_thresholds
Create Date: 2026-11-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0010_interview_window'
down_revision: Union[str, Sequence[str], None] = '0009_reality_thresholds'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('jobs', sa.Column('scheduling_enabled', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('jobs', sa.Column('interview_window_start', sa.DateTime(timezone=True), nullable=True))
    op.add_column('jobs', sa.Column('interview_window_end', sa.DateTime(timezone=True), nullable=True))
    op.add_column('jobs', sa.Column('interview_window_timezone', sa.String(64), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('jobs', 'interview_window_timezone')
    op.drop_column('jobs', 'interview_window_end')
    op.drop_column('jobs', 'interview_window_start')
    op.drop_column('jobs', 'scheduling_enabled')
