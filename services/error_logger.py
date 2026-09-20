"""
Сервис для логирования ошибок в Telegram канал
"""

import traceback
from datetime import datetime
from typing import Optional
from aiogram import Bot
from config import settings


class ErrorLogger:
    """Логирование ошибок в Telegram канал"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.channel_id = settings.ERROR_LOG_CHANNEL_ID
    
    async def log_error(
        self,
        error: Exception,
        context: str = "Неизвестный контекст",
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        message_text: Optional[str] = None
    ):
        """
        Отправить ошибку в канал логов
        
        Args:
            error: Исключение
            context: Контекст где произошла ошибка
            user_id: ID пользователя
            username: Username пользователя
            message_text: Текст сообщения пользователя
        """
        if not self.channel_id:
            # Если канал не настроен - просто выводим в консоль
            print(f"❌ ОШИБКА [{context}]: {error}")
            return
        
        try:
            # Формируем сообщение об ошибке
            error_message = self._format_error_message(
                error=error,
                context=context,
                user_id=user_id,
                username=username,
                message_text=message_text
            )
            
            # Отправляем в канал
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=error_message,
                parse_mode="HTML"
            )
            
        except Exception as e:
            # Если не удалось отправить в канал - выводим в консоль
            print(f"❌ Не удалось отправить ошибку в канал: {e}")
            print(f"❌ Исходная ошибка [{context}]: {error}")
    
    def _format_error_message(
        self,
        error: Exception,
        context: str,
        user_id: Optional[int],
        username: Optional[str],
        message_text: Optional[str]
    ) -> str:
        """Форматирует сообщение об ошибке"""
        
        # Заголовок
        message = f"🔴 <b>ОШИБКА В БОТЕ</b>\n\n"
        
        # Время
        now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        message += f"🕐 <b>Время:</b> {now}\n"
        
        # Контекст
        message += f"📍 <b>Контекст:</b> {context}\n\n"
        
        # Информация о пользователе
        if user_id:
            message += f"👤 <b>Пользователь:</b>\n"
            message += f"   • ID: <code>{user_id}</code>\n"
            if username:
                message += f"   • Username: @{username}\n"
            message += "\n"
        
        # Сообщение пользователя
        if message_text:
            # Обрезаем если очень длинное
            truncated_text = message_text[:200] + "..." if len(message_text) > 200 else message_text
            message += f"💬 <b>Сообщение:</b>\n<code>{self._escape_html(truncated_text)}</code>\n\n"
        
        # Тип ошибки
        error_type = type(error).__name__
        message += f"⚠️ <b>Тип ошибки:</b> {error_type}\n"
        
        # Описание ошибки
        error_text = str(error)
        # Обрезаем если очень длинное
        truncated_error = error_text[:500] + "..." if len(error_text) > 500 else error_text
        message += f"📝 <b>Описание:</b>\n<code>{self._escape_html(truncated_error)}</code>\n\n"
        
        # Traceback (сокращённый)
        try:
            tb = traceback.format_exc()
            # Берём последние 10 строк
            tb_lines = tb.split("\n")[-10:]
            tb_short = "\n".join(tb_lines)
            if tb_short and tb_short != "NoneType: None":
                message += f"🔍 <b>Traceback:</b>\n<code>{self._escape_html(tb_short[:800])}</code>\n"
        except:
            pass
        
        return message
    
    @staticmethod
    def _escape_html(text: str) -> str:
        """Экранирует HTML символы"""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))


# Глобальный экземпляр (будет инициализирован в main.py)
error_logger: Optional[ErrorLogger] = None


def init_error_logger(bot: Bot):
    """Инициализация логгера ошибок"""
    global error_logger
    error_logger = ErrorLogger(bot)
    return error_logger


async def log_error(
    error: Exception,
    context: str = "Неизвестный контекст",
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    message_text: Optional[str] = None
):
    """Удобная функция для логирования ошибок"""
    if error_logger:
        await error_logger.log_error(
            error=error,
            context=context,
            user_id=user_id,
            username=username,
            message_text=message_text
        )
    else:
        print(f"❌ ErrorLogger не инициализирован. Ошибка [{context}]: {error}")
