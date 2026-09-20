"""
Основные клавиатуры бота
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура при первом запуске - доступ выдает админ"""
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Написать администратору", url="https://t.me/dvedian")
    kb.button(text="🛠 Тех поддержка", url="https://t.me/DICSITRen2200")
    kb.adjust(1)  # Каждая кнопка на отдельной строке
    return kb.as_markup()


def get_class_selection_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора класса"""
    kb = InlineKeyboardBuilder()
    for i in range(1, 12):
        kb.button(text=f"{i} класс", callback_data=f"class_{i}")
    kb.adjust(3, 3, 3, 2)  # 3+3+3+2 = 11 классов
    return kb.as_markup()


def get_student_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Главное меню ученика"""
    kb = InlineKeyboardBuilder()
    kb.button(text="📚 Решать с репетитором", callback_data="solve_with_tutor")
    kb.button(text="📊 Мой прогресс", callback_data="my_progress")
    kb.button(text="💰 Мои токены", callback_data="my_tokens")
    kb.button(text="⚙️ Настройки", callback_data="settings")
    kb.button(text="🆘 Поддержка", callback_data="support_info")
    
    if is_admin:
        kb.button(text="🔧 Админ-панель", callback_data="admin_panel")
    
    kb.adjust(1, 2, 2, 1)  # Первая кнопка на всю ширину, потом по 2
    return kb.as_markup()


def get_admin_menu() -> InlineKeyboardMarkup:
    """Меню администратора"""
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить пользователя", callback_data="admin_add_user")
    kb.button(text="🔍 Найти пользователя", callback_data="admin_search_user")
    kb.button(text="👥 Все пользователи", callback_data="admin_users")
    kb.button(text="📊 Статистика", callback_data="admin_stats")
    kb.button(text="💾 Создать бэкап БД", callback_data="admin_backup")
    kb.button(text="📥 Восстановить из бэкапа", callback_data="admin_restore_backup")
    kb.button(text="◀️ Назад в меню", callback_data="back_to_main")
    kb.adjust(2, 2, 2, 1)  # По 2 кнопки в ряд
    return kb.as_markup()


def get_codes_admin_menu() -> InlineKeyboardMarkup:
    """Меню управления кодами"""
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Создать код", callback_data="code_create")
    kb.button(text="📋 Активные коды", callback_data="code_list_active")
    kb.button(text="📜 Все коды", callback_data="code_list_all")
    kb.button(text="◀️ Назад", callback_data="admin_panel")
    kb.adjust(1)
    return kb.as_markup()


def get_users_admin_menu() -> InlineKeyboardMarkup:
    """Меню управления пользователями"""
    kb = InlineKeyboardBuilder()
    kb.button(text="👨‍🎓 Ученики", callback_data="users_students")
    kb.button(text="◀️ Назад", callback_data="admin_panel")
    kb.adjust(1)
    return kb.as_markup()


def get_cancel_keyboard_inline() -> InlineKeyboardMarkup:
    """Inline клавиатура с кнопкой отмены"""
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отменить", callback_data="cancel_action")
    kb.adjust(1)
    return kb.as_markup()


def get_solve_task_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для решения задачи с репетитором"""
    kb = InlineKeyboardBuilder()
    kb.button(text="💡 Дай подсказку", callback_data="get_hint")
    kb.button(text="✅ Закончить занятие", callback_data="finish_lesson")
    kb.adjust(1, 1)
    return kb.as_markup()


def get_confirmation_keyboard(action: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения действия"""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да", callback_data=f"confirm_{action}")
    kb.button(text="❌ Нет", callback_data=f"cancel_{action}")
    kb.adjust(2)
    return kb.as_markup()


def get_user_management_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура управления пользователем"""
    kb = InlineKeyboardBuilder()
    kb.button(text="⏰ Продлить доступ", callback_data=f"extend_access_{user_id}")
    kb.button(text="🚫 Заблокировать", callback_data=f"block_user_{user_id}")
    kb.button(text="📊 Статистика", callback_data=f"user_stats_{user_id}")
    kb.button(text="◀️ Назад", callback_data="admin_panel")
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def remove_keyboard() -> ReplyKeyboardRemove:
    """Удалить клавиатуру"""
    return ReplyKeyboardRemove()


def get_support_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой написать в поддержку"""
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Написать в поддержку", url="https://t.me/DICSITRen2200")
    kb.button(text="◀️ Назад в меню", callback_data="back_to_main")
    kb.adjust(1)
    return kb.as_markup()


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура настроек профиля"""
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Изменить класс", callback_data="change_class")
    kb.button(text="◀️ Назад в меню", callback_data="back_to_main")
    kb.adjust(1)
    return kb.as_markup()

