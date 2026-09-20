"""
Дополнительные обработчики для админ-панели
Добавление и управление пользователями
"""

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from services import AccessService, UserService, StatisticsService
from keyboards import get_admin_menu, get_user_management_keyboard, get_cancel_keyboard_inline
from models import User
from config import settings

router = Router(name="admin_additions")


class AdminUserStates(StatesGroup):
    """Состояния администратора при работе с пользователями"""
    waiting_username_to_add = State()
    waiting_days_for_new_user = State()
    waiting_username_to_search = State()
    waiting_days_to_extend = State()


def is_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
    return user_id in settings.admin_ids_list


# ===== ДОБАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯ =====

@router.callback_query(F.data == "admin_add_user")
async def start_add_user(callback: CallbackQuery, state: FSMContext):
    """Начало процесса добавления пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "➕ Добавление пользователя\n\n"
        "Введите username пользователя (с @ или без):\n"
        "Например: @username или username\n\n"
        "✅ Можно добавить пользователя даже если он еще не запускал бота!",
        reply_markup=get_cancel_keyboard_inline()
    )
    await state.set_state(AdminUserStates.waiting_username_to_add)
    await callback.answer()


@router.message(AdminUserStates.waiting_username_to_add)
async def get_username_to_add(message: Message, session: AsyncSession, state: FSMContext):
    """Получение username для добавления"""
    if not is_admin(message.from_user.id):
        return
    
    username = message.text.strip().lstrip('@')
    
    if not username:
        await message.answer(
            "❌ Username не может быть пустым\n\nПопробуйте еще раз:",
            reply_markup=get_cancel_keyboard_inline()
        )
        return
    
    # Ищем пользователя (ВАЖНО: поиск без учёта регистра)
    user = await UserService.get_user_by_username(session, username)
    
    if user:
        # Пользователь НАЙДЕН в базе - УЖЕ запускал бота!
        
        # Проверяем текущий доступ
        has_access, _ = await AccessService.check_user_access(session, user.telegram_id)
        active_code = await AccessService.get_user_active_code(session, user.telegram_id)
        
        access_info = ""
        if has_access and active_code:
            days_left = (active_code.expires_at - datetime.utcnow()).days
            access_info = f"\n⚠️ У пользователя УЖЕ ЕСТЬ доступ!\n   Осталось дней: {days_left}\n   Истекает: {active_code.expires_at.strftime('%d.%m.%Y')}\n"
        else:
            access_info = "\n✅ У пользователя НЕТ активного доступа\n"
        
        # Сохраняем данные
        await state.update_data(
            target_username=username,
            target_telegram_id=user.telegram_id,
            target_user_name=user.full_name,
            user_exists=True
        )
        
        await message.answer(
            f"✅ Пользователь НАЙДЕН в базе!\n"
            f"(Пользователь УЖЕ запускал бота)\n\n"
            f"👤 Имя: {user.full_name}\n"
            f"📱 Username: @{username}\n"
            f"🆔 Telegram ID: {user.telegram_id}\n"
            f"📅 Зарегистрирован: {user.created_at.strftime('%d.%m.%Y')}\n"
            f"{access_info}\n"
            f"Введите количество дней доступа (например: 30, 90, 365):",
            reply_markup=get_cancel_keyboard_inline()
        )
    else:
        # Пользователь НЕ найден - НЕ запускал бота!
        
        await state.update_data(
            target_username=username,
            target_telegram_id=None,
            target_user_name=username,
            user_exists=False
        )
        
        await message.answer(
            f"ℹ️ Пользователь @{username} НЕ найден в базе\n"
            f"❌ Пользователь ЕЩЁ НЕ ЗАПУСКАЛ БОТА!\n\n"
            f"💡 Что делать:\n\n"
            f"Вариант 1 (рекомендуемый):\n"
            f"1. Попросите пользователя @{username} нажать /start в боте\n"
            f"2. После этого попробуйте добавить снова\n\n"
            f"Вариант 2 (отложенный доступ):\n"
            f"Вы можете выдать доступ заранее!\n"
            f"Когда пользователь запустит бота, доступ активируется автоматически.\n\n"
            f"Введите количество дней доступа или нажмите Отмена:",
            reply_markup=get_cancel_keyboard_inline()
        )
    
    await state.set_state(AdminUserStates.waiting_days_for_new_user)


@router.message(AdminUserStates.waiting_days_for_new_user)
async def give_access_to_user(message: Message, session: AsyncSession, state: FSMContext):
    """Выдача доступа пользователю"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        days = int(message.text.strip())
        if days <= 0 or days > 3650:
            raise ValueError()
    except ValueError:
        await message.answer(
            "❌ Введите корректное количество дней (от 1 до 3650):",
            reply_markup=get_cancel_keyboard_inline()
        )
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    username = data.get("target_username")
    user_exists = data.get("user_exists", False)
    
    # Используем новую функцию которая работает с username
    success, msg, telegram_id = await AccessService.give_access_by_username(
        session,
        username,
        days,
        message.from_user.id
    )
    await session.commit()
    
    if success:
        if telegram_id:
            # Пользователь существует
            await message.answer(
                f"✅ Доступ успешно выдан!\n\n"
                f"👤 Пользователь: @{username}\n"
                f"⏰ Срок: {days} дней\n"
                f"📅 Истекает: {(datetime.utcnow() + timedelta(days=days)).strftime('%d.%m.%Y')}\n\n"
                f"Пользователь может сразу начинать работу!",
                reply_markup=get_admin_menu()
            )
        else:
            # Отложенный доступ
            await message.answer(
                f"✅ Отложенный доступ создан!\n\n"
                f"👤 Username: @{username}\n"
                f"⏰ Срок: {days} дней\n\n"
                f"💡 Когда пользователь @{username} запустит бота командой /start,\n"
                f"доступ активируется автоматически!",
                reply_markup=get_admin_menu()
            )
    else:
        await message.answer(
            f"❌ Ошибка: {msg}",
            reply_markup=get_admin_menu()
        )
    
    await state.clear()


# ===== ПОИСК ПОЛЬЗОВАТЕЛЯ =====

@router.callback_query(F.data == "admin_search_user")
async def start_search_user(callback: CallbackQuery, state: FSMContext):
    """Начало поиска пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔍 Поиск пользователя\n\n"
        "Введите username пользователя (с @ или без):\n\n"
        "💡 Поиск не учитывает регистр\n"
        "Например: @Username, username, USERNAME",
        reply_markup=get_cancel_keyboard_inline()
    )
    await state.set_state(AdminUserStates.waiting_username_to_search)
    await callback.answer()


@router.message(AdminUserStates.waiting_username_to_search)
async def search_user_by_username(message: Message, session: AsyncSession, state: FSMContext):
    """Поиск и отображение информации о пользователе"""
    if not is_admin(message.from_user.id):
        return
    
    username = message.text.strip().lstrip('@')
    
    # Ищем пользователя (теперь поиск без учёта регистра!)
    user = await UserService.get_user_by_username(session, username)
    
    if not user:
        # Показываем список похожих username'ов для помощи
        similar = await session.execute(
            select(User).where(User.username.ilike(f"%{username}%")).limit(5)
        )
        similar_users = similar.scalars().all()
        
        response = f"❌ Пользователь @{username} не найден\n\n"
        
        if similar_users:
            response += "💡 Похожие username в базе:\n"
            for u in similar_users:
                response += f"• @{u.username} ({u.full_name})\n"
            response += "\n"
        
        response += "Попробуйте еще раз:"
        
        await message.answer(
            response,
            reply_markup=get_cancel_keyboard_inline()
        )
        return
    
    # Получаем информацию о доступе
    active_code = await AccessService.get_user_active_code(session, user.telegram_id)
    
    # Получаем статистику
    stats = await StatisticsService.get_user_progress(session, user.telegram_id)
    
    # Формируем ответ
    response = f"👤 Информация о пользователе\n\n"
    response += f"Имя: {user.full_name}\n"
    response += f"Username: @{user.username}\n"
    response += f"ID: {user.telegram_id}\n"
    response += f"Роль: {user.role.value if user.role else 'Не установлена'}\n"
    
    if user.class_number:
        response += f"Класс: {user.class_number}\n"
    
    response += f"Регистрация: {user.created_at.strftime('%d.%m.%Y')}\n\n"
    
    # Информация о подписке
    if active_code:
        response += f"✅ Подписка активна\n"
        response += f"Осталось дней: {active_code.days_left}\n"
        response += f"Истекает: {active_code.expires_at.strftime('%d.%m.%Y')}\n\n"
    else:
        response += f"❌ Подписка неактивна\n\n"
    
    # Статистика
    if stats and stats.get('total_tasks', 0) > 0:
        response += f"📊 Статистика:\n"
        response += f"Решено задач: {stats.get('solved_tasks', 0)}\n"
        response += f"Правильно: {stats.get('correct_answers', 0)}\n"
        response += f"Успеваемость: {stats.get('success_rate', 0)}%\n"
    
    await message.answer(
        response,
        reply_markup=get_user_management_keyboard(user.telegram_id)
    )
    
    await state.clear()


# ===== ПРОДЛЕНИЕ ДОСТУПА =====

@router.callback_query(F.data.startswith("extend_access_"))
async def start_extend_access(callback: CallbackQuery, state: FSMContext):
    """Начало процесса продления доступа"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    telegram_id = int(callback.data.split("_")[2])
    
    # Сохраняем ID пользователя
    await state.update_data(target_telegram_id=telegram_id)
    
    await callback.message.answer(
        "⏰ Продление доступа\n\n"
        "Введите количество дней для продления (например: 30, 90, 365):",
        reply_markup=get_cancel_keyboard_inline()
    )
    await state.set_state(AdminUserStates.waiting_days_to_extend)
    await callback.answer()


@router.message(AdminUserStates.waiting_days_to_extend)
async def extend_user_access_handler(message: Message, session: AsyncSession, state: FSMContext):
    """Продление доступа пользователю"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        days = int(message.text.strip())
        if days <= 0 or days > 3650:
            raise ValueError()
    except ValueError:
        await message.answer(
            "❌ Введите корректное количество дней (от 1 до 3650):",
            reply_markup=get_cancel_keyboard_inline()
        )
        return
    
    # Получаем ID пользователя
    data = await state.get_data()
    telegram_id = data.get("target_telegram_id")
    
    # Продляем доступ
    success, msg = await AccessService.extend_user_access(session, telegram_id, days)
    await session.commit()
    
    if success:
        await message.answer(
            f"✅ {msg}",
            reply_markup=get_admin_menu()
        )
    else:
        await message.answer(
            f"❌ Ошибка: {msg}",
            reply_markup=get_admin_menu()
        )
    
    await state.clear()


# ===== БЛОКИРОВКА ПОЛЬЗОВАТЕЛЯ =====

@router.callback_query(F.data.startswith("block_user_"))
async def block_user(callback: CallbackQuery, session: AsyncSession):
    """Блокировка пользователя (отключение доступа)"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    telegram_id = int(callback.data.split("_")[2])
    
    # Получаем пользователя
    user = await UserService.get_user(session, telegram_id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    # Получаем активный код
    active_code = await AccessService.get_user_active_code(session, telegram_id)
    
    if not active_code:
        await callback.answer("⚠️ У пользователя нет активного доступа", show_alert=True)
        return
    
    # Блокируем доступ
    try:
        # Пытаемся использовать метод block() если поле is_blocked существует
        active_code.block()
        await session.commit()
        
        await callback.message.edit_text(
            f"✅ Пользователь заблокирован\n\n"
            f"👤 Имя: {user.full_name}\n"
            f"📱 Username: @{user.username}\n"
            f"🆔 ID: {telegram_id}\n\n"
            f"🚫 Доступ к боту отключен\n"
            f"Код доступа заблокирован",
            reply_markup=get_admin_menu()
        )
        await callback.answer("✅ Пользователь заблокирован")
        
    except AttributeError:
        # Если метод block() не существует (модель не обновлена)
        await callback.answer(
            "⚠️ Функция блокировки недоступна. Запустите миграцию: python add_blocked_field.py",
            show_alert=True
        )
    except Exception as e:
        if "is_blocked" in str(e).lower():
            await callback.answer(
                "⚠️ Поле is_blocked не найдено в БД. Запустите: python add_blocked_field.py",
                show_alert=True
            )
        else:
            await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


# ===== СТАТИСТИКА ПОЛЬЗОВАТЕЛЯ =====

@router.callback_query(F.data.startswith("user_stats_"))
async def show_user_statistics(callback: CallbackQuery, session: AsyncSession):
    """Показать детальную статистику пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    telegram_id = int(callback.data.split("_")[2])
    
    # Получаем пользователя
    user = await UserService.get_user(session, telegram_id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    # Получаем статистику
    stats = await StatisticsService.get_user_progress(session, telegram_id)
    
    # Получаем информацию о доступе
    active_code = await AccessService.get_user_active_code(session, telegram_id)
    
    # Формируем ответ
    response = f"📊 Детальная статистика пользователя\n\n"
    response += f"👤 *Профиль:*\n"
    response += f"Имя: {user.full_name}\n"
    response += f"Username: @{user.username}\n"
    response += f"ID: {telegram_id}\n"
    response += f"Роль: {user.role.value if user.role else 'Не установлена'}\n"
    
    if user.class_number:
        response += f"Класс: {user.class_number}\n"
    
    response += f"Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
    
    # Информация о подписке
    response += f"💼 *Подписка:*\n"
    if active_code:
        response += f"✅ Статус: Активна\n"
        response += f"Осталось дней: {active_code.days_left}\n"
        response += f"Истекает: {active_code.expires_at.strftime('%d.%m.%Y')}\n"
        response += f"Код: `{active_code.code_name}`\n\n"
    else:
        response += f"❌ Статус: Неактивна\n\n"
    
    # Статистика использования
    response += f"📈 *Использование бота:*\n"
    if stats and stats.get('total_tasks', 0) > 0:
        response += f"Всего задач: {stats.get('total_tasks', 0)}\n"
        response += f"Решено: {stats.get('solved_tasks', 0)}\n"
        response += f"Правильно: {stats.get('correct_answers', 0)}\n"
        response += f"Успеваемость: {stats.get('success_rate', 0)}%\n"
        response += f"Средний балл: {stats.get('average_score', 0):.1f}\n"
        
        if stats.get('last_activity'):
            response += f"Последняя активность: {stats['last_activity'].strftime('%d.%m.%Y %H:%M')}\n"
    else:
        response += f"Пользователь ещё не решал задачи\n"
    
    await callback.message.edit_text(
        response,
        reply_markup=get_user_management_keyboard(telegram_id),
        parse_mode="Markdown"
    )
    await callback.answer()


# ===== ОТМЕНА ДЕЙСТВИЙ =====

@router.callback_query(AdminUserStates.waiting_username_to_add, F.data == "cancel_action")
@router.callback_query(AdminUserStates.waiting_days_for_new_user, F.data == "cancel_action")
@router.callback_query(AdminUserStates.waiting_username_to_search, F.data == "cancel_action")
@router.callback_query(AdminUserStates.waiting_days_to_extend, F.data == "cancel_action")
async def cancel_admin_user_action(callback: CallbackQuery, state: FSMContext):
    """Отмена действия с пользователем"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await state.clear()
    await callback.message.edit_text(
        "Действие отменено.\n\n"
        "🔧 Админ-панель\n\n"
        "Выберите раздел:",
        reply_markup=get_admin_menu()
    )
    await callback.answer("Действие отменено")
