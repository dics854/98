"""
Сервис для работы с пользователями
Оптимизирован с кэшированием для высокой нагрузки
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import User, Progress
from models.user import UserRole
from typing import Optional, List
from .cache_service import get_cache


class UserService:
    """Сервис для управления пользователями"""
    
    @staticmethod
    async def get_user(session: AsyncSession, telegram_id: int) -> Optional[User]:
        """
        Получить пользователя по Telegram ID (с кэшированием)
        
        Args:
            session: Сессия БД
            telegram_id: Telegram ID пользователя
            
        Returns:
            Объект User или None
        """
        # Проверяем кэш
        cache = get_cache()
        cache_key = cache.make_key("user", telegram_id)
        cached_user = await cache.get(cache_key)
        
        if cached_user is not None:
            # Пересоздаём объект в текущей сессии
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()
        
        # Запрашиваем из БД
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        # Сохраняем в кэш на 5 минут
        if user:
            await cache.set(cache_key, user.telegram_id, ttl_seconds=300)
        
        return user
    
    @staticmethod
    async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
        """
        Получить пользователя по username
        
        Args:
            session: Сессия БД
            username: Username без @
            
        Returns:
            Объект User или None
        """
        # Убираем @ если он есть
        username = username.lstrip('@')
        
        # Ищем БЕЗ учёта регистра используя функцию lower()
        from sqlalchemy import func
        result = await session.execute(
            select(User).where(func.lower(User.username) == func.lower(username))
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_user(
        session: AsyncSession,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> User:
        """
        Создать нового пользователя
        
        Args:
            session: Сессия БД
            telegram_id: Telegram ID
            username: Username
            first_name: Имя
            last_name: Фамилия
            
        Returns:
            Созданный пользователь
        """
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        session.add(user)
        await session.flush()
        
        # Добавляем в кэш
        cache = get_cache()
        cache_key = cache.make_key("user", telegram_id)
        await cache.set(cache_key, telegram_id, ttl_seconds=300)
        
        return user
    
    @staticmethod
    async def set_user_role(session: AsyncSession, telegram_id: int, role: UserRole) -> User:
        """
        Установить роль пользователя
        
        Args:
            session: Сессия БД
            telegram_id: Telegram ID
            role: Роль пользователя
            
        Returns:
            Обновленный пользователь
        """
        user = await UserService.get_user(session, telegram_id)
        if user:
            user.role = role
            await session.flush()
            
            # Инвалидируем кэш
            cache = get_cache()
            cache_key = cache.make_key("user", telegram_id)
            await cache.delete(cache_key)
        
        return user
    
    @staticmethod
    async def set_user_class(session: AsyncSession, telegram_id: int, class_number: int) -> User:
        """
        Установить класс ученика
        
        Args:
            session: Сессия БД
            telegram_id: Telegram ID
            class_number: Номер класса (1-11)
            
        Returns:
            Обновленный пользователь
        """
        user = await UserService.get_user(session, telegram_id)
        if user:
            user.class_number = class_number
            
            # Создаем запись прогресса для ученика если её нет
            progress_result = await session.execute(
                select(Progress).where(Progress.user_id == user.id)
            )
            existing_progress = progress_result.scalar_one_or_none()
            
            if not existing_progress:
                progress = Progress(user_id=user.id)
                session.add(progress)
            
            await session.flush()
            
            # Инвалидируем кэш
            cache = get_cache()
            cache_key = cache.make_key("user", telegram_id)
            await cache.delete(cache_key)
        
        return user
    
    @staticmethod
    async def get_all_students(session: AsyncSession) -> List[User]:
        """
        Получить всех учеников
        
        Args:
            session: Сессия БД
            
        Returns:
            Список учеников
        """
        result = await session.execute(
            select(User).where(User.role == UserRole.STUDENT)
        )
        return result.scalars().all()
