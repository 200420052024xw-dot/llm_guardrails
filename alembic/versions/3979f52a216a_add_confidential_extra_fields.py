"""add confidential extra fields"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '3979f52a216a'
down_revision: Union[str, None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('confidential_entries', sa.Column('confidential_level', sa.String(length=16), nullable=False, server_default='high'))
    op.add_column('confidential_entries', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('confidential_entries', sa.Column('negative_samples', sa.JSON(), nullable=True))
    op.add_column('confidential_entries', sa.Column('keywords', sa.JSON(), nullable=True))
    # Set default values for existing rows
    op.execute("UPDATE confidential_entries SET negative_samples = '[]' WHERE negative_samples IS NULL")
    op.execute("UPDATE confidential_entries SET keywords = '[]' WHERE keywords IS NULL")
    # Now make them NOT NULL
    op.alter_column('confidential_entries', 'negative_samples', nullable=False)
    op.alter_column('confidential_entries', 'keywords', nullable=False)

def downgrade() -> None:
    op.drop_column('confidential_entries', 'keywords')
    op.drop_column('confidential_entries', 'negative_samples')
    op.drop_column('confidential_entries', 'summary')
    op.drop_column('confidential_entries', 'confidential_level')
