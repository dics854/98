"""
Обработчик команды /start и регистрации пользователей
"""

from aiogram import Router, F
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from services import UserService, AccessService
from keyboards import (
    get_start_keyboard,
    get_class_selection_keyboard,
    get_student_menu,
    get_cancel_keyboard_inline,
    get_support_keyboard,
    remove_keyboard
)
from models.user import UserRole
from config import settings

router = Router(name="start")


class RegistrationStates(StatesGroup):
    """Состояния регистрации"""
    waiting_for_class = State()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    """
    Обработка команды /start
    Проверяет наличие пользователя в БД и его доступ
    """
    user_id = message.from_user.id
    
    # Получаем или создаем пользователя
    user = await UserService.get_user(session, user_id)
    
    if not user:
        # Создаем нового пользователя
        user = await UserService.create_user(
            session,
            telegram_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        await session.commit()
        
        # ВАЖНО: Проверяем есть ли отложенный доступ для этого username
        if message.from_user.username:
            pending_activated = await AccessService.activate_pending_access_for_user(
                session,
                user.id,
                message.from_user.username
            )
            if pending_activated:
                await session.commit()
                # Уведомляем что доступ активирован
                await message.answer(
                    "🎉 Отлично!\n\n"
                    "✅ Ваш доступ активирован автоматически!\n"
                    "Администратор уже выдал вам доступ заранее.\n\n"
                    "Продолжаем регистрацию..."
                )
    else:
        # ВАЖНО: Обновляем username если изменился!
        if message.from_user.username and user.username != message.from_user.username:
            user.username = message.from_user.username
            await session.commit()
            
            # Проверяем есть ли отложенный доступ для НОВОГО username
            pending_activated = await AccessService.activate_pending_access_for_user(
                session,
                user.id,
                message.from_user.username
            )
            if pending_activated:
                await session.commit()
                await message.answer(
                    "🎉 Отлично!\n\n"
                    "✅ Ваш доступ активирован автоматически!\n"
                    "Администратор выдал доступ на ваш новый username.\n\n"
                )
    
    # Проверяем доступ (для не-админов)
    if user_id not in settings.admin_ids_list:
        has_access, _ = await AccessService.check_user_access(session, user_id)
        
        if not has_access:
            await message.answer(
                "👋 Добро пожаловать в бот-репетитор!\n\n"
                "🔐 Для работы с ботом необходим доступ\n\n"
                "📝 Как получить доступ:\n"
                "1. Нажмите кнопку ниже\n"
                "2. Напишите администратору @dvedian\n"
                "3. Отправьте ему ваш username\n"
                "4. Администратор выдаст вам доступ\n"
                "5. После этого вернитесь и нажмите /start\n\n"
                "💡 Ваш username: @" + (message.from_user.username or "не установлен") + "\n\n"
                "🛠 График работы тех поддержки:\n"
                "📅 Понедельник - Пятница: 15:00 - 21:00\n"
                "🚫 Суббота и Воскресенье: выходной",
                reply_markup=get_start_keyboard()
            )
            return
    
    # Если роль не установлена - автоматически делаем учеником и предлагаем выбрать класс
    if not user.role:
        await UserService.set_user_role(session, user_id, UserRole.STUDENT)
        await session.commit()
    
    # Если класс не установлен - предлагаем выбрать
    if not user.class_number:
        await message.answer(
            "Выберите ваш класс:",
            reply_markup=get_class_selection_keyboard()
        )
        await state.set_state(RegistrationStates.waiting_for_class)
        return
    
    # Показываем главное меню
    is_admin = user_id in settings.admin_ids_list
    
    await message.answer(
        f"👋 Привет, {user.full_name}!\n\n"
        f"🎓 Я твой персональный репетитор.\n\n"
        f"📚 Что я умею:\n"
        f"✏️ Решать уравнения и неравенства\n"
        f"📖 Помогать с задачами из учебников\n"
        f"📐 Объяснять геометрию (площади, объёмы, теоремы)\n"
        f"🚗 Разбирать задачи на движение, работу, проценты\n"
        f"🔢 Работать с дробями, пропорциями, степенями\n"
        f"📊 Строить графики функций\n"
        f"🧩 Решать логические задачи\n"
        f"💬 Объяснять любую тему простым языком\n\n"
        f"💡 Как я работаю:\n"
        f"• Задаю наводящие вопросы\n"
        f"• Веду тебя к ответу шаг за шагом\n"
        f"• Объясняю понятным языком\n"
        f"• НЕ даю готовые ответы (это важно для обучения!)\n\n"
        f"🎯 Главное - ты сам дойдёшь до решения и поймёшь материал!\n\n"
        f"Выбери действие:",
        reply_markup=get_student_menu(is_admin)
    )
    
    await state.clear()


@router.callback_query(F.data.startswith("class_"))
async def process_class_selection(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Обработка выбора класса"""
    user_id = callback.from_user.id
    
    try:
        class_number = int(callback.data.split("_")[1])
        
        await UserService.set_user_class(session, user_id, class_number)
        await session.commit()
        
        is_admin = user_id in settings.admin_ids_list
        user = await UserService.get_user(session, user_id)
        
        # Проверяем откуда пришел запрос - из регистрации или настроек
        current_state = await state.get_state()
        
        if current_state == RegistrationStates.waiting_for_class:
            # Из регистрации - показываем приветствие
            await callback.message.edit_text(
                f"✅ Отлично! Ты учишься в {class_number} классе.\n\n"
                f"🎓 Теперь можем начинать занятия!\n\n"
                f"Я буду твоим репетитором - помогу разобраться с задачами 📚",
                reply_markup=get_student_menu(is_admin)
            )
            await state.clear()
        else:
            # Из настроек - показываем подтверждение
            await callback.message.edit_text(
                f"✅ Класс изменен на {class_number}!\n\n"
                f"Теперь задачи будут подбираться под этот уровень.",
                reply_markup=get_student_menu(is_admin)
            )
        
    except (ValueError, IndexError):
        await callback.answer("Ошибка выбора класса", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data == "cancel_action")
async def cancel_handler(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка отмены текущего действия - универсальный обработчик"""
    current_state = await state.get_state()
    user_id = callback.from_user.id
    
    # Очищаем состояние
    await state.clear()
    
    # Получаем пользователя
    user = await UserService.get_user(session, user_id)
    is_admin = user_id in settings.admin_ids_list
    
    # Определяем куда вернуть пользователя
    if not user or not user.role:
        # Пользователь не зарегистрирован - возвращаем на стартовый экран
        await callback.message.edit_text(
            "Действие отменено.\n\n"
            "👋 Добро пожаловать в бот-репетитор по математике!\n\n"
            "💡 Выберите действие:",
            reply_markup=get_start_keyboard()
        )
    else:
        # Ученик - возвращаем в меню ученика
        await callback.message.edit_text(
            "Действие отменено.\n\n"
            f"👋 {user.full_name}, выбери что будем делать:",
            reply_markup=get_student_menu(is_admin)
        )
    
    await callback.answer("Действие отменено")


@router.callback_query(F.data == "support_info")
async def show_support_info(callback: CallbackQuery):
    """Показать информацию о поддержке"""
    support_text = (
        "🆘 Техническая поддержка\n\n"
        "⏰ Время работы поддержки:\n"
        "📅 Понедельник - Пятница: 15:00 - 21:00\n"
        "🚫 Суббота и Воскресенье: выходной\n\n"
        "💬 Вы можете написать нам по любым вопросам:\n"
        "• Технические проблемы с ботом\n"
        "• Вопросы по обучению\n"
        "• Предложения и пожелания\n\n"
        "⚡ Мы ответим вам в рабочее время!"
    )
    
    await callback.message.edit_text(
        support_text,
        reply_markup=get_support_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: CallbackQuery, session: AsyncSession):
    """Возврат в главное меню"""
    user_id = callback.from_user.id
    user = await UserService.get_user(session, user_id)
    is_admin = user_id in settings.admin_ids_list
    
    await callback.message.edit_text(
        f"Главное меню",
        reply_markup=get_student_menu(is_admin)
    )
    
    await callback.answer()

