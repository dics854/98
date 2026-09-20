"""update tokens limit to 1M

Revision ID: 2026_09_19_0001
Revises: 2026_09_14_0002
Create Date: 2026-09-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_09_19_0001'
down_revision = '2026_09_14_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Обновляем лимит токенов с 400000 на 1000000 для всех пользователей
    """
    # Обновляем все записи где tokens_limit = 400000
    op.execute("""
        UPDATE users 
        SET tokens_limit = 1000000 
        WHERE tokens_limit = 400000
    """)
    
    # Также обновляем default для новых пользователей (уже в модели, но на всякий случай)
    # SQLite не поддерживает ALTER COLUMN, поэтому пропускаем


def downgrade() -> None:
    """
    Откатываем изменения (возвращаем 400000)
    """
    op.execute("""
        UPDATE users 
        SET tokens_limit = 400000 
        WHERE tokens_limit = 1000000
    """)
