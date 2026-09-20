"""
Настройка подключения к базе данных
SQLAlchemy async engine и сессии
Оптимизировано для 50+ одновременных пользователей
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool
from sqlalchemy import text
from config import settings


# Создаем асинхронный движок для SQLite с оптимизациями
engine = create_async_engine(
    settings.database_url,
    echo=settings.DEBUG,
    
    # Оптимизации для SQLite под высокую нагрузку
    connect_args={
        "check_same_thread": False,
        "timeout": 30,  # Увеличенный таймаут для блокировок
    },
    
    # Connection pooling для лучшей производительности
    poolclass=StaticPool,  # StaticPool лучше для SQLite в async режиме
    pool_pre_ping=True,  # Проверка соединения перед использованием
    pool_recycle=3600,  # Переподключение каждый час
    
    # Оптимизация выполнения запросов
    execution_options={
        "isolation_level": "AUTOCOMMIT"  # Автокоммит для SQLite
    }
)

# Создаем фабрику сессий с оптимизациями
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Не обновлять объекты после commit
    autoflush=False,  # Ручное управление flush для производительности
)


# Базовый класс для моделей
class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """
    Получение сессии базы данных
    Используется как dependency
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    Инициализация базы данных
    Создает все таблицы и оптимизирует SQLite
    """
    # Импортируем все модели чтобы они зарегистрировались в Base.metadata
    from models import User, AccessCode, Task, Progress  # noqa
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Применяем оптимизации SQLite для высокой нагрузки
        await conn.execute(text("PRAGMA journal_mode=WAL"))  # Write-Ahead Logging для concurrency
        await conn.execute(text("PRAGMA synchronous=NORMAL"))  # Баланс скорости и безопасности
        await conn.execute(text("PRAGMA cache_size=10000"))  # Увеличенный кэш (10MB)
        await conn.execute(text("PRAGMA temp_store=MEMORY"))  # Временные таблицы в памяти
        await conn.execute(text("PRAGMA mmap_size=268435456"))  # Memory-mapped I/O (256MB)
        await conn.execute(text("PRAGMA page_size=4096"))  # Оптимальный размер страницы


async def close_db():
    """
    Закрытие соединения с базой данных
    """
    await engine.dispose()
