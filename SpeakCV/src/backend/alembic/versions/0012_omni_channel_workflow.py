"""omni channel workflow

Revision ID: 0012_omni_channel_workflow
Revises: 0011_practice_context
Create Date: 2026-11-07 22:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0012_omni_channel_workflow'
down_revision: Union[str, Sequence[str], None] = '0011_practice_context'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('jobs', sa.Column('interview_sla_hours', sa.Integer(), nullable=True))
    op.add_column('applications', sa.Column('candidate_name', sa.String(255), nullable=True))
    op.add_column('applications', sa.Column('candidate_email', sa.String(255), nullable=True))
    op.add_column('applications', sa.Column('candidate_phone', sa.String(50), nullable=True))
    op.add_column('applications', sa.Column('contact_hash', sa.String(64), nullable=True))
    op.add_column('applications', sa.Column('claim_token_hash', sa.String(64), nullable=True))
    op.add_column('applications', sa.Column('invited_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_applications_candidate_email', 'applications', ['candidate_email'], unique=False)
    op.create_index('ix_applications_contact_hash', 'applications', ['contact_hash'], unique=False)
    op.create_index('ix_applications_claim_token_hash', 'applications', ['claim_token_hash'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_applications_claim_token_hash', table_name='applications')
    op.drop_index('ix_applications_contact_hash', table_name='applications')
    op.drop_index('ix_applications_candidate_email', table_name='applications')
    op.drop_column('applications', 'invited_at')
    op.drop_column('applications', 'claim_token_hash')
    op.drop_column('applications', 'contact_hash')
    op.drop_column('applications', 'candidate_phone')
    op.drop_column('applications', 'candidate_email')
    op.drop_column('applications', 'candidate_name')
    op.drop_column('jobs', 'interview_sla_hours')
