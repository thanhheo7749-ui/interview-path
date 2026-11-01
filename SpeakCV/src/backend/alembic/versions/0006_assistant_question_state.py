"""assistant_questions.state, so a question the system failed on is not counted as a knowledge gap

Revision ID: 0006_assistant_question_state
Revises: 0005_must_change_password

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006_assistant_question_state'
down_revision: Union[str, Sequence[str], None] = '0005_must_change_password'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('assistant_questions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('state', sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('assistant_questions', schema=None) as batch_op:
        batch_op.drop_column('state')
