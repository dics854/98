"""
Сервис для управления лимитами токенов пользователей
Автоматическое обновление токенов каждый месяц
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.user import User
from datetime import datetime, timedelta
from typing import Optional


class TokenService:
    """Управление токенами пользователей"""
    
    # Лимит токенов на месяц
    # GPT-4o: входящие $5/1M, исходящие $15/1M
    # 1 миллион токенов на пользователя в месяц
    MONTHLY_TOKEN_LIMIT = 1000000
    
    @staticmethod
    async def check_and_update_tokens(session: AsyncSession, user: User) -> dict:
        """
        Проверяет состояние токенов пользователя и обновляет если нужно
        
        Возвращает:
            {
                'has_tokens': bool,
                'tokens_left': int,
                'tokens_used': int,
                'tokens_limit': int,
                'is_frozen': bool,
                'reset_date': datetime
            }
        """
        now = datetime.utcnow()
        
        # Если дата сброса не установлена - устанавливаем на следующий месяц
        if not user.tokens_reset_date:
            user.tokens_reset_date = TokenService._get_next_month_date(now)
            user.tokens_used = 0
            user.tokens_frozen = False
            await session.commit()
        
        # Если наступил новый месяц - обновляем токены
        if now >= user.tokens_reset_date:
            user.tokens_used = 0
            user.tokens_frozen = False
            user.tokens_reset_date = TokenService._get_next_month_date(now)
            await session.commit()
        
        # Проверяем есть ли доступные токены
        tokens_left = user.tokens_limit - user.tokens_used
        has_tokens = tokens_left > 0 and not user.tokens_frozen
        
        return {
            'has_tokens': has_tokens,
            'tokens_left': tokens_left,
            'tokens_used': user.tokens_used,
            'tokens_limit': user.tokens_limit,
            'is_frozen': user.tokens_frozen,
            'reset_date': user.tokens_reset_date
        }
    
    @staticmethod
    async def use_tokens(session: AsyncSession, user: User, tokens_count: int) -> bool:
        """
        Списывает токены с баланса пользователя
        
        Args:
            session: Сессия БД
            user: Пользователь
            tokens_count: Количество токенов для списания
            
        Returns:
            True если токены списаны, False если недостаточно токенов
        """
        # Проверяем состояние токенов
        token_info = await TokenService.check_and_update_tokens(session, user)
        
        if not token_info['has_tokens']:
            return False
        
        if token_info['tokens_left'] < tokens_count:
            return False
        
        # Списываем токены
        user.tokens_used += tokens_count
        await session.commit()
        
        return True
    
    @staticmethod
    async def freeze_tokens(session: AsyncSession, user: User):
        """Замораживает токены пользователя (при окончании подписки)"""
        user.tokens_frozen = True
        await session.commit()
    
    @staticmethod
    async def unfreeze_tokens(session: AsyncSession, user: User):
        """Размораживает токены пользователя (при возобновлении подписки)"""
        now = datetime.utcnow()
        
        # Если дата сброса в прошлом - обновляем токены
        if user.tokens_reset_date and now >= user.tokens_reset_date:
            user.tokens_used = 0
            user.tokens_reset_date = TokenService._get_next_month_date(now)
        
        user.tokens_frozen = False
        await session.commit()
    
    @staticmethod
    async def reset_tokens_to_limit(session: AsyncSession, user: User):
        """Сбрасывает токены до лимита (новый месяц или новая подписка)"""
        now = datetime.utcnow()
        user.tokens_used = 0
        user.tokens_frozen = False
        user.tokens_limit = TokenService.MONTHLY_TOKEN_LIMIT
        user.tokens_reset_date = TokenService._get_next_month_date(now)
        await session.commit()
    
    @staticmethod
    def _get_next_month_date(current_date: datetime) -> datetime:
        """Получает дату первого числа следующего месяца"""
        if current_date.month == 12:
            return datetime(current_date.year + 1, 1, 1, 0, 0, 0)
        else:
            return datetime(current_date.year, current_date.month + 1, 1, 0, 0, 0)
    
    @staticmethod
    def format_tokens_info(token_info: dict) -> str:
        """Форматирует информацию о токенах для отображения пользователю"""
        tokens_left = token_info['tokens_left']
        tokens_used = token_info['tokens_used']
        tokens_limit = token_info['tokens_limit']
        reset_date = token_info['reset_date']
        
        # Процент использования
        usage_percent = int((tokens_used / tokens_limit) * 100) if tokens_limit > 0 else 0
        
        result = f"📊 **Ваш лимит токенов:**\n\n"
        result += f"💰 Использовано: {tokens_used:,} / {tokens_limit:,} ({usage_percent}%)\n"
        result += f"✨ Осталось: {tokens_left:,} токенов\n"
        result += f"🔄 Обновление: {reset_date.strftime('%d.%m.%Y')}\n"
        
        if token_info['is_frozen']:
            result += f"\n❄️ **Токены заморожены** (нет активной подписки)"
        
        return result
