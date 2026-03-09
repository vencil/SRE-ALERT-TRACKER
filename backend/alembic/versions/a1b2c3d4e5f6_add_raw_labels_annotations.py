"""add raw_labels and raw_annotations to alert_records

Revision ID: a1b2c3d4e5f6
Revises: 958029e05409
Create Date: 2026-03-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '958029e05409'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('alert_records', sa.Column('raw_labels', sa.Text(), nullable=True))
    op.add_column('alert_records', sa.Column('raw_annotations', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('alert_records', 'raw_annotations')
    op.drop_column('alert_records', 'raw_labels')
