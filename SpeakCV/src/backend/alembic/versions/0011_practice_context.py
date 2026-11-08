"""practice context

Revision ID: 0011_practice_context
Revises: 0010_interview_window
Create Date: 2026-11-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0011_practice_context'
down_revision: Union[str, Sequence[str], None] = '0010_interview_window'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('interview_history', sa.Column('company', sa.String(255), nullable=True))
    op.add_column('interview_history', sa.Column('jd_text', sa.Text(), nullable=True))
    op.add_column('interview_history', sa.Column('voice', sa.String(64), nullable=True))
    op.add_column('interview_history', sa.Column('mode', sa.String(32), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('interview_history', 'mode')
    op.drop_column('interview_history', 'voice')
    op.drop_column('interview_history', 'jd_text')
    op.drop_column('interview_history', 'company')
