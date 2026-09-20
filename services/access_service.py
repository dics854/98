"""
Сервис для работы с кодами доступа
"""

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from models import AccessCode, User
from typing import Optional, List
from datetime import datetime, timedelta
import secrets
import string


class AccessService:
    """Сервис для управления кодами доступа"""
    
    @staticmethod
    def generate_code(length: int = 10) -> str:
        """
        Генерация уникального кода доступа
        
        Args:
            length: Длина кода
            
        Returns:
            Сгенерированный код
        """
        characters = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(characters) for _ in range(length))
    
    @staticmethod
    async def create_access_code(
        session: AsyncSession,
        code: str,
        duration_days: int,
        created_by: int
    ) -> AccessCode:
        """
        Создать новый код доступа
        
        Args:
            session: Сессия БД
            code: Код доступа
            duration_days: Срок действия в днях
            created_by: Telegram ID создателя (администратора)
            
        Returns:
            Созданный код доступа
        """
        access_code = AccessCode(
            code=code.upper(),
            duration_days=duration_days,
            created_by=created_by
        )
        session.add(access_code)
        await session.flush()
        return access_code
    
    @staticmethod
    async def get_code(session: AsyncSession, code: str) -> Optional[AccessCode]:
        """
        Получить код по значению
        
        Args:
            session: Сессия БД
            code: Код доступа
            
        Returns:
            Объект AccessCode или None
        """
        result = await session.execute(
            select(AccessCode).where(AccessCode.code == code.upper())
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def activate_code(
        session: AsyncSession,
        code: str,
        telegram_id: int
    ) -> tuple[bool, str]:
        """
        Активировать код доступа
        
        Args:
            session: Сессия БД
            code: Код доступа
            telegram_id: Telegram ID пользователя
            
        Returns:
            Кортеж (успех, сообщение)
        """
        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return False, "Пользователь не найден"
        
        access_code = await AccessService.get_code(session, code)
        
        if not access_code:
            return False, "Код не найден"
        
        if not access_code.is_active:
            return False, "Код уже использован"
        
        # Активируем код (передаем user.id вместо telegram_id)
        access_code.activate(user.id)
        await session.flush()
        
        # Размораживаем и обновляем токены пользователя
        from services.token_service import TokenService
        await TokenService.reset_tokens_to_limit(session, user)
        
        return True, f"Код успешно активирован! Доступ на {access_code.duration_days} дней"
    
    @staticmethod
    async def check_user_access(session: AsyncSession, telegram_id: int) -> tuple[bool, Optional[str]]:
        """
        Проверить доступ пользователя
        
        Args:
            session: Сессия БД
            telegram_id: Telegram ID пользователя
            
        Returns:
            Кортеж (есть доступ, сообщение если нет)
        """
        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return False, "Пользователь не найден"
        
        # Сохраняем user.id ДО попытки запроса (чтобы не было проблем после rollback)
        user_id = user.id
        
        # Пробуем проверку с is_blocked
        try:
            result = await session.execute(
                select(AccessCode).where(
                    and_(
                        AccessCode.activated_by == user_id,
                        AccessCode.is_active == False,
                        AccessCode.is_blocked == False,
                        AccessCode.expires_at > datetime.utcnow()
                    )
                ).order_by(AccessCode.expires_at.desc()).limit(1)
            )
            
            active_code = result.scalar_one_or_none()
            
            if not active_code:
                # Проверим, заблокирован ли пользователь
                blocked_result = await session.execute(
                    select(AccessCode).where(
                        and_(
                            AccessCode.activated_by == user_id,
                            AccessCode.is_blocked == True
                        )
                    ).limit(1)
                )
                if blocked_result.scalar_one_or_none():
                    return False, "blocked"
                else:
                    return False, "expired"
            
            return True, None
            
        except Exception as e:
            error_str = str(e).lower()
            # Если ошибка связана с отсутствием колонки (is_blocked ИЛИ code_name)
            if 'column' in error_str and ('is_blocked' in error_str or 'code_name' in error_str):
                # Откатываем транзакцию
                await session.rollback()
                # Проверка без is_blocked и code_name - используем только базовые поля
                result = await session.execute(
                    select(AccessCode.id, AccessCode.expires_at).where(
                        and_(
                            AccessCode.activated_by == user_id,
                            AccessCode.is_active == False,
                            AccessCode.expires_at > datetime.utcnow()
                        )
                    ).order_by(AccessCode.expires_at.desc()).limit(1)
                )
                
                active_code = result.first()
                
                if not active_code:
                    return False, "expired"
                
                return True, None
            else:
                raise
    
    @staticmethod
    async def get_user_active_code(session: AsyncSession, telegram_id: int) -> Optional[AccessCode]:
        """
        Получить активный код пользователя
        
        Args:
            session: Сессия БД
            telegram_id: Telegram ID пользователя
            
        Returns:
            Активный код или None
        """
        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return None
        
        # Сохраняем user.id ДО попытки запроса
        user_id = user.id
        
        # Пробуем простой запрос с is_blocked и code_name
        try:
            result = await session.execute(
                select(AccessCode).where(
                    and_(
                        AccessCode.activated_by == user_id,
                        AccessCode.is_active == False,
                        AccessCode.is_blocked == False,
                        AccessCode.expires_at > datetime.utcnow()
                    )
                ).order_by(AccessCode.expires_at.desc()).limit(1)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            error_str = str(e).lower()
            # Если ошибка связана с отсутствием колонки (is_blocked ИЛИ code_name)
            if 'column' in error_str and ('is_blocked' in error_str or 'code_name' in error_str):
                # Откатываем транзакцию чтобы продолжить работу
                await session.rollback()
                # Запрос БЕЗ is_blocked и code_name - только базовые поля
                result = await session.execute(
                    select(
                        AccessCode.id,
                        AccessCode.code, 
                        AccessCode.duration_days,
                        AccessCode.created_by,
                        AccessCode.activated_by,
                        AccessCode.is_active,
                        AccessCode.created_at,
                        AccessCode.activated_at,
                        AccessCode.expires_at
                    ).where(
                        and_(
                            AccessCode.activated_by == user_id,
                            AccessCode.is_active == False,
                            AccessCode.expires_at > datetime.utcnow()
                        )
                    ).order_by(AccessCode.expires_at.desc()).limit(1)
                )
                row = result.first()
                if not row:
                    return None
                
                # Создаём объект AccessCode из полученных данных
                access_code = AccessCode()
                access_code.id = row[0]
                access_code.code = row[1]
                access_code.duration_days = row[2]
                access_code.created_by = row[3]
                access_code.activated_by = row[4]
                access_code.is_active = row[5]
                access_code.created_at = row[6]
                access_code.activated_at = row[7]
                access_code.expires_at = row[8]
                # Устанавливаем значения по умолчанию для отсутствующих полей
                access_code.is_blocked = False
                access_code.code_name = None
                
                return access_code
            else:
                raise
    
    @staticmethod
    async def give_direct_access(
        session: AsyncSession,
        telegram_id: int,
        duration_days: int,
        given_by: int
    ) -> tuple[bool, str]:
        """
        Выдать прямой доступ пользователю (без кода)
        
        Args:
            session: Сессия БД
            telegram_id: Telegram ID пользователя
            duration_days: Срок действия в днях
            given_by: Telegram ID администратора
            
        Returns:
            Кортеж (успех, сообщение)
        """
        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return False, "Пользователь не найден в базе данных"
        
        # Создаем специальный код для прямого доступа
        code = f"DIRECT_{telegram_id}_{datetime.utcnow().timestamp()}"
        
        access_code = AccessCode(
            code=code,
            duration_days=duration_days,
            created_by=given_by,
            activated_by=user.id,
            is_active=False,
            activated_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=duration_days)
        )
        session.add(access_code)
        await session.flush()
        
        # Размораживаем и обновляем токены пользователя
        from services.token_service import TokenService
        await TokenService.reset_tokens_to_limit(session, user)
        
        return True, f"Доступ выдан на {duration_days} дней"
    
    @staticmethod
    async def give_access_by_username(
        session: AsyncSession,
        username: str,
        duration_days: int,
        given_by: int
    ) -> tuple[bool, str, Optional[int]]:
        """
        Выдать доступ по username (создаёт пользователя если его нет)
        
        Args:
            session: Сессия БД
            username: Username пользователя (без @)
            duration_days: Срок действия в днях
            given_by: Telegram ID администратора
            
        Returns:
            Кортеж (успех, сообщение, telegram_id если пользователь найден)
        """
        # Убираем @ если есть
        username = username.lstrip('@')
        
        # Ищем пользователя БЕЗ УЧЁТА РЕГИСТРА используя func.lower
        from sqlalchemy import func
        user_result = await session.execute(
            select(User).where(func.lower(User.username) == func.lower(username))
        )
        user = user_result.scalar_one_or_none()
        
        if user:
            # Пользователь существует - выдаём доступ обычным способом
            success, msg = await AccessService.give_direct_access(
                session,
                user.telegram_id,
                duration_days,
                given_by
            )
            return success, msg, user.telegram_id
        else:
            # Пользователь НЕ существует - создаём отложенный доступ
            # Сохраняем username в нижнем регистре для поиска
            username_lower = username.lower()
            
            # Создаём специальную запись "отложенного доступа"
            code = f"PENDING_{username_lower}_{datetime.utcnow().timestamp()}"
            
            access_code = AccessCode(
                code=code,
                duration_days=duration_days,
                created_by=given_by,
                activated_by=None,  # Пока нет пользователя
                is_active=True,  # Помечаем как "ожидающий активации"
                activated_at=None,
                expires_at=None  # Будет установлено когда пользователь зарегистрируется
            )
            session.add(access_code)
            await session.flush()
            
            return True, f"Доступ на {duration_days} дней создан для @{username}. Активируется когда пользователь запустит бота.", None
    
    @staticmethod
    async def activate_pending_access_for_user(
        session: AsyncSession,
        user_id: int,
        username: str
    ) -> bool:
        """
        Активировать отложенный доступ для пользователя при регистрации
        
        Args:
            session: Сессия БД
            user_id: ID пользователя в базе (user.id)
            username: Username пользователя
            
        Returns:
            True если был активирован отложенный доступ
        """
        # Приводим username к нижнему регистру для поиска
        username_lower = username.lower()
        
        # Ищем коды с префиксом PENDING_ для этого username
        result = await session.execute(
            select(AccessCode).where(
                and_(
                    AccessCode.code.like(f"PENDING_{username_lower}_%"),
                    AccessCode.is_active == True,
                    AccessCode.activated_by.is_(None)
                )
            )
        )
        
        pending_code = result.scalar_one_or_none()
        
        if pending_code:
            # Активируем отложенный доступ
            pending_code.activated_by = user_id
            pending_code.activated_at = datetime.utcnow()
            pending_code.expires_at = datetime.utcnow() + timedelta(days=pending_code.duration_days)
            pending_code.is_active = False  # Помечаем как использованный
            await session.flush()
            
            # Размораживаем токены у пользователя
            from services.token_service import TokenService
            # Получаем объект пользователя
            user_result = await session.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if user:
                await TokenService.reset_tokens_to_limit(session, user)
            
            return True
        
        return False
    
    @staticmethod
    async def extend_user_access(
        session: AsyncSession,
        telegram_id: int,
        extra_days: int
    ) -> tuple[bool, str]:
        """
        Продлить доступ пользователя
        
        Args:
            session: Сессия БД
            telegram_id: Telegram ID пользователя
            extra_days: Дополнительные дни
            
        Returns:
            Кортеж (успех, сообщение)
        """
        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return False, "Пользователь не найден"
        
        # Получаем активный код пользователя
        result = await session.execute(
            select(AccessCode).where(
                AccessCode.activated_by == user.id
            ).order_by(AccessCode.expires_at.desc())
        )
        
        active_code = result.scalar_one_or_none()
        
        if not active_code:
            return False, "У пользователя нет активной подписки"
        
        # Продляем доступ
        if active_code.expires_at and active_code.expires_at > datetime.utcnow():
            # Продляем от текущей даты истечения
            active_code.expires_at = active_code.expires_at + timedelta(days=extra_days)
        else:
            # Если подписка истекла - продляем от текущей даты
            active_code.expires_at = datetime.utcnow() + timedelta(days=extra_days)
        
        await session.flush()
        
        return True, f"Доступ продлен на {extra_days} дней. Новая дата истечения: {active_code.expires_at.strftime('%d.%m.%Y')}"
    
    @staticmethod
    async def get_all_codes(session: AsyncSession) -> List[AccessCode]:
        """
        Получить все коды доступа
        
        Args:
            session: Сессия БД
            
        Returns:
            Список всех кодов
        """
        result = await session.execute(
            select(AccessCode).order_by(AccessCode.created_at.desc())
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_active_codes(session: AsyncSession) -> List[AccessCode]:
        """
        Получить активные (неиспользованные) коды
        
        Args:
            session: Сессия БД
            
        Returns:
            Список активных кодов
        """
        result = await session.execute(
            select(AccessCode).where(
                AccessCode.is_active == True
            ).order_by(AccessCode.created_at.desc())
        )
        return result.scalars().all()
    
    @staticmethod
    async def delete_code(session: AsyncSession, code: str) -> bool:
        """
        Удалить код доступа
        
        Args:
            session: Сессия БД
            code: Код доступа
            
        Returns:
            True если код удален
        """
        access_code = await AccessService.get_code(session, code)
        if access_code:
            await session.delete(access_code)
            await session.flush()
            return True
        return False
