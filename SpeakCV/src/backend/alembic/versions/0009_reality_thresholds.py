"""reality check thresholds

Revision ID: 0009_reality_thresholds
Revises: 0008_measurement
Create Date: 2026-11-02 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0009_reality_thresholds'
down_revision: Union[str, Sequence[str], None] = '0008_measurement'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('companies', sa.Column('reality_low_pct', sa.Integer(), server_default='30', nullable=False))
    op.add_column('companies', sa.Column('reality_high_pct', sa.Integer(), server_default='70', nullable=False))
    op.add_column('companies', sa.Column('reality_min_hired', sa.Integer(), server_default='10', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('companies', 'reality_min_hired')
    op.drop_column('companies', 'reality_high_pct')
    op.drop_column('companies', 'reality_low_pct')
