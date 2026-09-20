"""Remove parent role and parent_child table

Revision ID: remove_parent_role
Revises: add_first_tutor_usage
Create Date: 2026-09-14 00:02:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'remove_parent_role'
down_revision = 'add_first_tutor_usage'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Удаляем таблицу parent_child
    op.drop_index(op.f('ix_parent_child_parent_id'), table_name='parent_child')
    op.drop_index(op.f('ix_parent_child_child_id'), table_name='parent_child')
    op.drop_table('parent_child')
    
    # Обновляем всех пользователей с ролью PARENT на STUDENT
    op.execute("UPDATE users SET role = 'STUDENT' WHERE role = 'PARENT'")
    
    # Примечание: изменение enum типа требует пересоздания типа в PostgreSQL
    # Для SQLite это не требуется, так как SQLite не использует строгие enum типы


def downgrade() -> None:
    # Воссоздаем таблицу parent_child
    op.create_table('parent_child',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('parent_id', sa.BigInteger(), nullable=False),
        sa.Column('child_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['child_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['parent_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('parent_id', 'child_id', name='unique_parent_child')
    )
    op.create_index(op.f('ix_parent_child_child_id'), 'parent_child', ['child_id'], unique=False)
    op.create_index(op.f('ix_parent_child_parent_id'), 'parent_child', ['parent_id'], unique=False)
