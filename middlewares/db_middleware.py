"""
Middleware для работы с базой данных
Добавляет сессию БД в каждый хендлер
"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from database import async_session_maker


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для добавления сессии БД"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Добавляет сессию БД в data
        
        Args:
            handler: Обработчик события
            event: Событие Telegram
            data: Данные для передачи в обработчик
            
        Returns:
            Результат обработчика
        """
        async with async_session_maker() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                raise e
