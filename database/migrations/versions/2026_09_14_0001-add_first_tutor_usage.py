"""Add first_tutor_usage field to users

Revision ID: add_first_tutor_usage
Revises: 67c139d29503
Create Date: 2026-09-14 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_first_tutor_usage'
down_revision = '67c139d29503'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поле first_tutor_usage в таблицу users
    op.add_column('users', sa.Column('first_tutor_usage', sa.Boolean(), nullable=False, server_default='1'))


def downgrade() -> None:
    # Удаляем поле first_tutor_usage
    op.drop_column('users', 'first_tutor_usage')
