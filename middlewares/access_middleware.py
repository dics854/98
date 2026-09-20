"""
Middleware для проверки доступа пользователей
Проверяет активность подписки перед выполнением команд
"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from services import AccessService
from config import settings


class AccessMiddleware(BaseMiddleware):
    """Middleware для проверки доступа к боту"""
    
    # Команды, которые доступны без активной подписки
    ALLOWED_WITHOUT_ACCESS = [
        "/start",
        "🔑 Ввести код доступа",
        "start",
        "activate_code",
        "role_",  # Выбор роли
        "class_",  # Выбор класса
        "cancel_class",  # Отмена выбора класса
        "settings",  # Настройки доступны всегда
        "change_role",  # Смена роли
        "change_class",  # Смена класса
        "switch_to_",  # Переключение роли (student/parent)
        "back_to_main",  # Возврат в главное меню
        "support_info",  # Информация о поддержке
        "admin_panel",  # Админ-панель (дополнительно проверяется is_admin)
        "admin_"  # Все админские callback (дополнительно проверяются)
    ]
    
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        """
        Проверяет доступ пользователя перед выполнением команды
        
        Args:
            handler: Обработчик события
            event: Событие (Message или CallbackQuery)
            data: Данные для передачи в обработчик
            
        Returns:
            Результат обработчика или сообщение об отсутствии доступа
        """
        user_id = event.from_user.id
        session = data.get("session")
        
        # Администраторы имеют полный доступ всегда
        if user_id in settings.admin_ids_list:
            return await handler(event, data)
        
        # Если это фото/документ/GIF - разрешаем (будет проверка в состоянии FSM)
        if isinstance(event, Message):
            if event.photo or event.document or event.animation:
                # Разрешаем медиа-файлы - они будут обработаны только если пользователь в диалоге
                return await handler(event, data)
        
        # Определяем текст команды
        if isinstance(event, Message):
            command_text = event.text
        elif isinstance(event, CallbackQuery):
            command_text = event.data
        else:
            command_text = ""
        
        # Проверяем, является ли команда разрешенной без подписки
        is_allowed = any(allowed in command_text for allowed in self.ALLOWED_WITHOUT_ACCESS)
        
        if is_allowed:
            return await handler(event, data)
        
        # Проверяем активность подписки
        has_access, reason = await AccessService.check_user_access(session, user_id)
        
        if not has_access:
            # Формируем сообщение в зависимости от причины
            if reason == "blocked":
                # Пользователь заблокирован
                if isinstance(event, Message):
                    await event.answer(
                        "🚫 Доступ заблокирован\n\n"
                        "❌ Ваш доступ к боту был заблокирован администратором\n\n"
                        "📝 Для восстановления доступа:\n"
                        "1. Напишите администратору: @dvedian\n"
                        "2. Ваш username: @" + (event.from_user.username or "не установлен") + "\n"
                        "3. Выясните причину блокировки\n"
                        "4. После разблокировки нажмите /start\n\n"
                        "🛠 График работы тех поддержки:\n"
                        "📅 Пн-Пт: 15:00 - 21:00\n"
                        "🚫 Сб-Вс: выходной\n\n"
                        "💬 Тех поддержка: @DICSITRen2200",
                        reply_markup=None
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        "🚫 Ваш доступ заблокирован администратором. Обратитесь к @dvedian.",
                        show_alert=True
                    )
            else:
                # Доступ истёк
                if isinstance(event, Message):
                    await event.answer(
                        "⏰ Доступ истёк\n\n"
                        "❌ Срок вашего доступа к боту закончился\n\n"
                        "📝 Для продления доступа:\n"
                        "1. Напишите администратору: @dvedian\n"
                        "2. Сообщите ваш username: @" + (event.from_user.username or "не установлен") + "\n"
                        "3. Администратор продлит доступ\n"
                        "4. После продления нажмите /start\n\n"
                        "🛠 График работы тех поддержки:\n"
                        "📅 Пн-Пт: 15:00 - 21:00\n"
                        "🚫 Сб-Вс: выходной\n\n"
                        "💬 Тех поддержка: @DICSITRen2200",
                        reply_markup=None
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        "⏰ Срок доступа истёк. Обратитесь к @dvedian для продления.",
                        show_alert=True
                    )
            return
        
        # Доступ есть, продолжаем выполнение
        return await handler(event, data)
