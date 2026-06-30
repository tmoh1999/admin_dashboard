"""add email verification flag

Revision ID: d54c3b2201f3
Revises: 62a1193c5ad3
Create Date: 2026-06-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd54c3b2201f3'
down_revision = '62a1193c5ad3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'is_email_verified',
                sa.Boolean(),
                nullable=False,
                server_default=sa.text('false'),
            )
        )
        batch_op.alter_column('is_email_verified', server_default=None)


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_email_verified')
