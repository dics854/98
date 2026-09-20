"""
Обработчик команд для администраторов
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from services import AccessService, UserService, StatisticsService, manual_backup
from keyboards import get_admin_menu, get_codes_admin_menu, get_users_admin_menu, get_cancel_keyboard_inline
from models import User
from config import settings

router = Router(name="admin")


class AdminStates(StatesGroup):
    """Состояния администратора"""
    waiting_code_name = State()
    waiting_code_duration = State()
    waiting_code_to_delete = State()
    waiting_backup_file = State()  # Ожидание файла бэкапа


def is_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
    return user_id in settings.admin_ids_list


@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: CallbackQuery):
    """Главная админ-панель через callback"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа к админ-панели", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔧 Админ-панель\n\n"
        "Выберите раздел:",
        reply_markup=get_admin_menu()
    )
    await callback.answer()


@router.message(F.text == "🔧 Админ-панель")
@router.message(Command("admin"))
async def admin_panel(message: Message):
    """Главная админ-панель"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели")
        return
    
    await message.answer(
        "🔧 Админ-панель\n\n"
        "Выберите раздел:",
        reply_markup=get_admin_menu()
    )


@router.callback_query(F.data == "admin_menu")
async def show_admin_menu(callback: CallbackQuery):
    """Показать главное меню админки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔧 Админ-панель\n\n"
        "Выберите раздел:",
        reply_markup=get_admin_menu()
    )
    await callback.answer()


# ===== УПРАВЛЕНИЕ КОДАМИ ДОСТУПА =====

@router.callback_query(F.data == "admin_codes")
async def codes_menu(callback: CallbackQuery):
    """Меню управления кодами"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔑 Управление кодами доступа\n\n"
        "Выберите действие:",
        reply_markup=get_codes_admin_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "code_create")
async def start_code_creation(callback: CallbackQuery, state: FSMContext):
    """Начало создания кода"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer(
        "➕ Создание нового кода\n\n"
        "Введите название кода (например: MATH2026, PROMO30):",
        reply_markup=get_cancel_keyboard_inline()
    )
    await state.set_state(AdminStates.waiting_code_name)
    await callback.answer()


@router.message(AdminStates.waiting_code_name, F.text != "❌ Отмена")
async def get_code_name(message: Message, state: FSMContext):
    """Получение названия кода"""
    if not is_admin(message.from_user.id):
        return
    
    code_name = message.text.strip().upper()
    
    # Проверяем длину кода
    if len(code_name) < 4 or len(code_name) > 20:
        await message.answer(
            "❌ Код должен быть от 4 до 20 символов.\n\n"
            "Попробуйте еще раз:",
            reply_markup=get_cancel_keyboard_inline()
        )
        return
    
    await state.update_data(code_name=code_name)
    await message.answer(
        f"Код: {code_name}\n\n"
        f"Теперь введите срок действия в днях (например: 30, 90, 365):",
        reply_markup=get_cancel_keyboard_inline()
    )
    await state.set_state(AdminStates.waiting_code_duration)


@router.message(AdminStates.waiting_code_duration, F.text != "❌ Отмена")
async def create_code(message: Message, session: AsyncSession, state: FSMContext):
    """Создание кода"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        duration = int(message.text.strip())
        if duration <= 0 or duration > 3650:
            raise ValueError()
    except ValueError:
        await message.answer(
            "❌ Введите корректное количество дней (от 1 до 3650):",
            reply_markup=get_cancel_keyboard_inline()
        )
        return
    
    data = await state.get_data()
    code_name = data.get("code_name")
    
    # Проверяем существование кода
    existing_code = await AccessService.get_code(session, code_name)
    if existing_code:
        await message.answer(
            f"❌ Код {code_name} уже существует.\n\n"
            f"Введите другое название:",
            reply_markup=get_cancel_keyboard_inline()
        )
        await state.set_state(AdminStates.waiting_code_name)
        return
    
    # Создаем код
    code = await AccessService.create_access_code(
        session,
        code_name,
        duration,
        message.from_user.id
    )
    await session.commit()
    
    await message.answer(
        f"✅ Код успешно создан!\n\n"
        f"🔑 Код: {code.code}\n"
        f"📅 Срок действия: {code.duration_days} дней\n\n"
        f"Отправьте этот код пользователю для активации."
    )
    
    await state.clear()


@router.callback_query(F.data == "code_list_active")
async def list_active_codes(callback: CallbackQuery, session: AsyncSession):
    """Список активных кодов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    codes = await AccessService.get_active_codes(session)
    
    if not codes:
        await callback.answer("Нет активных кодов", show_alert=True)
        return
    
    response = "🔑 Активные коды:\n\n"
    for code in codes:
        response += f"• {code.code}\n"
        response += f"  Срок: {code.duration_days} дней\n"
        response += f"  Создан: {code.created_at.strftime('%d.%m.%Y')}\n\n"
    
    await callback.message.edit_text(response, reply_markup=get_codes_admin_menu())
    await callback.answer()


@router.callback_query(F.data == "code_list_all")
async def list_all_codes(callback: CallbackQuery, session: AsyncSession):
    """Список всех кодов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    codes = await AccessService.get_all_codes(session)
    
    if not codes:
        await callback.answer("Нет кодов", show_alert=True)
        return
    
    response = "📜 Все коды:\n\n"
    for code in codes[:20]:  # Показываем первые 20
        status = "✅ Активен" if code.is_active else "❌ Использован"
        response += f"• {code.code} - {status}\n"
        response += f"  Срок: {code.duration_days} дней\n"
        
        if code.activated_by:
            response += f"  Активирован: {code.activated_at.strftime('%d.%m.%Y')}\n"
            if code.expires_at:
                response += f"  Истекает: {code.expires_at.strftime('%d.%m.%Y')}\n"
        
        response += "\n"
    
    if len(codes) > 20:
        response += f"\n... и еще {len(codes) - 20} кодов"
    
    await callback.message.edit_text(response, reply_markup=get_codes_admin_menu())
    await callback.answer()


# ===== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ =====

@router.callback_query(F.data == "admin_users")
async def users_menu(callback: CallbackQuery, session: AsyncSession):
    """Меню управления пользователями - показываем только с username"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    # Получаем только пользователей с username
    result = await session.execute(
        select(User)
        .where(User.username.isnot(None))
        .order_by(User.created_at.desc())
        .limit(20)
    )
    users = result.scalars().all()
    
    if not users:
        await callback.answer("Нет пользователей с username в базе", show_alert=True)
        return
    
    response = f"👥 Последние пользователи с username ({len(users)}):\n\n"
    
    for user in users:
        response += f"👤 {user.full_name}\n"
        response += f"   @{user.username}\n"
        response += f"   ID: {user.telegram_id}\n"
        response += f"   Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        
        # Проверяем доступ
        active_code = await AccessService.get_user_active_code(session, user.telegram_id)
        if active_code:
            days_left = (active_code.expires_at - datetime.utcnow()).days
            response += f"   ✅ Доступ: {days_left} дней (до {active_code.expires_at.strftime('%d.%m.%Y')})\n"
            
            # Показываем кто выдал доступ
            creator_result = await session.execute(
                select(User.username, User.first_name).where(User.telegram_id == active_code.created_by)
            )
            creator = creator_result.first()
            if creator and creator[0]:
                response += f"   👤 Выдал: @{creator[0]}\n"
            elif creator and creator[1]:
                response += f"   👤 Выдал: {creator[1]}\n"
        else:
            response += f"   ❌ Нет доступа\n"
        
        response += "\n"
    
    await callback.message.edit_text(
        response,
        reply_markup=get_users_admin_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "users_students")
async def list_students(callback: CallbackQuery, session: AsyncSession):
    """Список учеников"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    students = await UserService.get_all_students(session)
    
    if not students:
        await callback.answer("Нет учеников", show_alert=True)
        return
    
    response = f"👨‍🎓 Ученики ({len(students)}):\n\n"
    
    for student in students[:15]:  # Показываем первых 15
        response += f"👤 {student.full_name}\n"
        response += f"   ID: {student.telegram_id}\n"
        
        if student.username:
            response += f"   @{student.username}\n"
        
        response += f"   🎓 Класс: {student.class_number}\n"
        response += f"   📅 Регистрация: {student.created_at.strftime('%d.%m.%Y')}\n"
        
        # Проверяем подписку
        active_code = await AccessService.get_user_active_code(session, student.telegram_id)
        if active_code:
            response += f"   ✅ Подписка до: {active_code.expires_at.strftime('%d.%m.%Y')}\n"
            
            # Показываем кто выдал доступ
            creator_result = await session.execute(
                select(User.username, User.first_name).where(User.telegram_id == active_code.created_by)
            )
            creator = creator_result.first()
            if creator and creator[0]:
                response += f"   👤 Выдал: @{creator[0]}\n"
            elif creator and creator[1]:
                response += f"   👤 Выдал: {creator[1]}\n"
        else:
            response += f"   ❌ Подписка неактивна\n"
        
        response += "\n"
    
    if len(students) > 15:
        response += f"\n... и еще {len(students) - 15} учеников"
    
    await callback.message.edit_text(response, reply_markup=get_users_admin_menu())
    await callback.answer()


# ===== СТАТИСТИКА =====

@router.callback_query(F.data == "admin_stats")
async def show_statistics(callback: CallbackQuery, session: AsyncSession):
    """Глобальная статистика"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    stats = await StatisticsService.get_global_statistics(session)
    
    response = (
        f"📊 Общая статистика проекта\n\n"
        f"👨‍🎓 Учеников: {stats.get('students')}\n"
        f"✅ Активных подписок: {stats.get('active_subscriptions')}\n"
        f"📝 Всего решено задач: {stats.get('total_tasks_solved')}\n\n"
    )
    
    # Распределение по классам
    class_dist = stats.get('class_distribution', {})
    if class_dist:
        response += "🎓 Распределение по классам:\n"
        for class_num in sorted(class_dist.keys()):
            if class_num:
                response += f"   {class_num} класс: {class_dist[class_num]} учеников\n"
    
    await callback.message.edit_text(response, reply_markup=get_admin_menu())
    await callback.answer()


# ===== РЕЗЕРВНОЕ КОПИРОВАНИЕ =====

@router.callback_query(F.data == "admin_backup")
async def create_manual_backup(callback: CallbackQuery):
    """Создание резервной копии вручную"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.answer("⏳ Создаю резервную копию...", show_alert=True)
    
    try:
        from utils import setup_logger
        logger = setup_logger()
        logger.info(f"Запрос на ручной бэкап от пользователя {callback.from_user.id}")
        
        await manual_backup()
        
        logger.info("Ручной бэкап успешно создан")
        await callback.message.answer(
            "✅ <b>Резервная копия создана</b>\n\n"
            "Файл отправлен в канал для бэкапов.",
            parse_mode="HTML"
        )
    except Exception as e:
        from utils import setup_logger
        logger = setup_logger()
        logger.error(f"Ошибка при создании ручного бэкапа: {e}", exc_info=True)
        
        # Отправляем в канал ошибок
        from services import log_error
        await log_error(
            error=e,
            context="Создание ручного бэкапа (admin.py)",
            user_id=callback.from_user.id,
            username=callback.from_user.username
        )
        
        await callback.message.answer(
            f"❌ <b>Ошибка при создании бэкапа</b>\n\n"
            f"Детали: {str(e)[:500]}",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "admin_restore_backup")
async def start_restore_backup(callback: CallbackQuery, state: FSMContext):
    """Начало процесса восстановления из бэкапа"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📥 <b>Восстановление из бэкапа</b>\n\n"
        "⚠️ <b>ВНИМАНИЕ!</b> Это действие:\n"
        "• Добавит пользователей из бэкапа в текущую БД\n"
        "• НЕ удалит существующих пользователей\n"
        "• Обновит данные пользователей если они уже есть\n\n"
        "📎 Отправьте файл бэкапа (.db файл) из канала с бэкапами\n\n"
        "💡 Чтобы скачать последний бэкап:\n"
        "1. Зайдите в канал с бэкапами\n"
        "2. Найдите последний файл .db\n"
        "3. Перешлите его сюда",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard_inline()
    )
    
    await state.set_state(AdminStates.waiting_backup_file)
    await callback.answer()


@router.message(AdminStates.waiting_backup_file, F.document)
async def restore_from_backup(message: Message, session: AsyncSession, state: FSMContext):
    """Восстановление данных из файла бэкапа"""
    if not is_admin(message.from_user.id):
        return
    
    document = message.document
    
    # Проверяем формат файла - поддерживаем .json (новый формат) и .db (старый)
    if document.file_name.endswith('.json'):
        # Новый формат JSON
        await restore_from_json_backup(message, session, state, document)
        return
    elif document.file_name.endswith('.db'):
        # Старый формат SQLite
        await restore_from_db_backup(message, session, state, document)
        return
    else:
        await message.answer(
            "❌ Неверный формат файла!\n\n"
            "Отправьте файл с расширением .json (новый формат) или .db (старый формат)",
            reply_markup=get_cancel_keyboard_inline()
        )
        return


async def restore_from_json_backup(message: Message, session: AsyncSession, state: FSMContext, document):
    """Восстановление из JSON бэкапа (новый формат)"""
    msg = await message.answer("⏳ Загружаю и обрабатываю JSON бэкап...")
    
    try:
        import aiohttp
        import json
        import os
        from datetime import datetime
        
        # Скачиваем файл
        file = await message.bot.get_file(document.file_id)
        file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file.file_path}"
        
        # Сохраняем во временный файл
        temp_backup_path = f"temp_restore_{datetime.now().timestamp()}.json"
        
        async with aiohttp.ClientSession() as http_session:
            async with http_session.get(file_url) as resp:
                if resp.status == 200:
                    with open(temp_backup_path, 'wb') as f:
                        f.write(await resp.read())
        
        await msg.edit_text("📊 Анализирую бэкап...")
        
        # Читаем JSON
        with open(temp_backup_path, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        # Проверяем структуру
        if 'users' not in backup_data:
            await msg.edit_text("⚠️ Неверный формат бэкапа!")
            os.remove(temp_backup_path)
            await state.clear()
            return
        
        backup_users = backup_data.get('users', [])
        backup_tasks = backup_data.get('tasks', [])
        backup_progress = backup_data.get('progress', [])
        backup_codes = backup_data.get('access_codes', [])
        
        if not backup_users:
            await msg.edit_text("⚠️ В бэкапе нет пользователей!")
            os.remove(temp_backup_path)
            await state.clear()
            return
        
        await msg.edit_text(f"🔄 Восстанавливаю {len(backup_users)} пользователей...")
        
        # Статистика
        added_count = 0
        updated_count = 0
        errors_count = 0
        
        # Импортируем пользователей
        from models.user import UserRole
        
        for user_data in backup_users:
            try:
                telegram_id = user_data.get('telegram_id')
                
                if not telegram_id:
                    errors_count += 1
                    continue
                
                # Проверяем существует ли пользователь
                result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                existing_user = result.scalar_one_or_none()
                
                if existing_user:
                    # Обновляем существующего
                    existing_user.username = user_data.get('username')
                    existing_user.first_name = user_data.get('first_name')
                    existing_user.last_name = user_data.get('last_name')
                    if user_data.get('role'):
                        existing_user.role = UserRole(user_data['role'])
                    existing_user.class_number = user_data.get('class_number')
                    # Обновляем токены если они есть в бэкапе
                    if 'tokens_limit' in user_data:
                        existing_user.tokens_limit = user_data.get('tokens_limit', 1000000)
                    if 'tokens_used' in user_data:
                        existing_user.tokens_used = user_data.get('tokens_used', 0)
                    if 'tokens_frozen' in user_data:
                        existing_user.tokens_frozen = user_data.get('tokens_frozen', False)
                    if 'first_tutor_usage' in user_data:
                        existing_user.first_tutor_usage = user_data.get('first_tutor_usage', True)
                    if user_data.get('tokens_reset_date'):
                        existing_user.tokens_reset_date = datetime.fromisoformat(user_data['tokens_reset_date'])
                    updated_count += 1
                else:
                    # Создаём нового пользователя
                    new_user = User(
                        telegram_id=telegram_id,
                        username=user_data.get('username'),
                        first_name=user_data.get('first_name'),
                        last_name=user_data.get('last_name'),
                        role=UserRole(user_data['role']) if user_data.get('role') else None,
                        class_number=user_data.get('class_number'),
                        # ТОКЕНЫ - восстанавливаем из бэкапа
                        tokens_limit=user_data.get('tokens_limit', 1000000),
                        tokens_used=user_data.get('tokens_used', 0),
                        tokens_frozen=user_data.get('tokens_frozen', False),
                        first_tutor_usage=user_data.get('first_tutor_usage', True)
                    )
                    
                    if user_data.get('created_at'):
                        new_user.created_at = datetime.fromisoformat(user_data['created_at'])
                    if user_data.get('tokens_reset_date'):
                        new_user.tokens_reset_date = datetime.fromisoformat(user_data['tokens_reset_date'])
                    
                    session.add(new_user)
                    added_count += 1
            
            except Exception as e:
                errors_count += 1
                print(f"Ошибка при импорте пользователя: {e}")
                continue
        
        # Сохраняем изменения пользователей
        await session.commit()
        
        # ===== ВОССТАНОВЛЕНИЕ КОДОВ ДОСТУПА =====
        if backup_codes:
            await msg.edit_text(f"🔑 Восстанавливаю {len(backup_codes)} кодов доступа...")
            
            codes_added = 0
            codes_updated = 0
            codes_errors = 0
            
            from models import AccessCode
            
            for code_data in backup_codes:
                try:
                    # Пропускаем если код уже есть
                    existing_code = await AccessService.get_code(session, code_data.get('code'))
                    if existing_code:
                        codes_updated += 1
                        continue
                    
                    # Создаём код доступа
                    new_code = AccessCode(
                        code=code_data.get('code'),
                        code_name=code_data.get('code_name'),
                        duration_days=code_data.get('duration_days'),
                        created_by=code_data.get('created_by'),
                        activated_by=code_data.get('activated_by'),
                        is_active=code_data.get('is_active', False),
                        is_blocked=code_data.get('is_blocked', False)
                    )
                    
                    if code_data.get('created_at'):
                        new_code.created_at = datetime.fromisoformat(code_data['created_at'])
                    if code_data.get('activated_at'):
                        new_code.activated_at = datetime.fromisoformat(code_data['activated_at'])
                    if code_data.get('expires_at'):
                        new_code.expires_at = datetime.fromisoformat(code_data['expires_at'])
                    
                    session.add(new_code)
                    codes_added += 1
                
                except Exception as e:
                    codes_errors += 1
                    print(f"Ошибка при импорте кода: {e}")
                    continue
            
            await session.commit()
        
        # ===== ВОССТАНОВЛЕНИЕ ЗАДАЧ =====
        if backup_tasks:
            await msg.edit_text(f"📝 Восстанавливаю {len(backup_tasks)} задач...")
            
            tasks_added = 0
            tasks_errors = 0
            
            from models import Task
            from models.task import TaskDifficulty
            
            for task_data in backup_tasks:
                try:
                    user_id = task_data.get('user_id')
                    if not user_id:
                        tasks_errors += 1
                        continue
                    
                    # Находим пользователя
                    result = await session.execute(
                        select(User).where(User.id == user_id)
                    )
                    user = result.scalar_one_or_none()
                    if not user:
                        tasks_errors += 1
                        continue
                    
                    # Создаём задачу
                    new_task = Task(
                        user_id=user.id,
                        task_text=task_data.get('task_text'),
                        topic=task_data.get('topic'),
                        difficulty=TaskDifficulty(task_data['difficulty']) if task_data.get('difficulty') else TaskDifficulty.MEDIUM,
                        student_answer=task_data.get('student_answer'),
                        is_correct=task_data.get('is_correct'),
                        ai_explanation=task_data.get('ai_explanation')
                    )
                    
                    if task_data.get('created_at'):
                        new_task.created_at = datetime.fromisoformat(task_data['created_at'])
                    if task_data.get('completed_at'):
                        new_task.completed_at = datetime.fromisoformat(task_data['completed_at'])
                    
                    session.add(new_task)
                    tasks_added += 1
                
                except Exception as e:
                    tasks_errors += 1
                    print(f"Ошибка при импорте задачи: {e}")
                    continue
            
            await session.commit()
        
        # ===== ВОССТАНОВЛЕНИЕ ПРОГРЕССА =====
        if backup_progress:
            await msg.edit_text(f"📊 Восстанавливаю {len(backup_progress)} записей прогресса...")
            
            progress_added = 0
            progress_updated = 0
            progress_errors = 0
            
            from models import Progress
            
            for progress_data in backup_progress:
                try:
                    user_id = progress_data.get('user_id')
                    if not user_id:
                        progress_errors += 1
                        continue
                    
                    # Находим пользователя
                    result = await session.execute(
                        select(User).where(User.id == user_id)
                    )
                    user = result.scalar_one_or_none()
                    if not user:
                        progress_errors += 1
                        continue
                    
                    # Проверяем есть ли уже прогресс
                    result = await session.execute(
                        select(Progress).where(Progress.user_id == user.id)
                    )
                    existing_progress = result.scalar_one_or_none()
                    
                    if existing_progress:
                        # Обновляем
                        existing_progress.total_tasks = progress_data.get('total_tasks', 0)
                        existing_progress.solved_tasks = progress_data.get('solved_tasks', 0)
                        existing_progress.correct_answers = progress_data.get('correct_answers', 0)
                        existing_progress.mistakes = progress_data.get('mistakes', 0)
                        if progress_data.get('last_activity'):
                            existing_progress.last_activity = datetime.fromisoformat(progress_data['last_activity'])
                        progress_updated += 1
                    else:
                        # Создаём новый
                        new_progress = Progress(
                            user_id=user.id,
                            total_tasks=progress_data.get('total_tasks', 0),
                            solved_tasks=progress_data.get('solved_tasks', 0),
                            correct_answers=progress_data.get('correct_answers', 0),
                            mistakes=progress_data.get('mistakes', 0)
                        )
                        
                        if progress_data.get('last_activity'):
                            new_progress.last_activity = datetime.fromisoformat(progress_data['last_activity'])
                        if progress_data.get('created_at'):
                            new_progress.created_at = datetime.fromisoformat(progress_data['created_at'])
                        
                        session.add(new_progress)
                        progress_added += 1
                
                except Exception as e:
                    progress_errors += 1
                    print(f"Ошибка при импорте прогресса: {e}")
                    continue
            
            await session.commit()
        
        # Удаляем временный файл
        os.remove(temp_backup_path)
        
        # Итоговая статистика
        result_text = (
            f"✅ <b>Восстановление из JSON завершено!</b>\n\n"
            f"📊 <b>Пользователи:</b>\n"
            f"➕ Добавлено: {added_count}\n"
            f"🔄 Обновлено: {updated_count}\n"
        )
        
        if errors_count > 0:
            result_text += f"⚠️ Ошибок: {errors_count}\n"
        
        if backup_codes:
            result_text += f"\n🔑 <b>Коды доступа:</b>\n"
            result_text += f"➕ Добавлено: {codes_added}\n"
            result_text += f"🔄 Уже были: {codes_updated}\n"
            if codes_errors > 0:
                result_text += f"⚠️ Ошибок: {codes_errors}\n"
        
        if backup_tasks:
            result_text += f"\n📝 <b>Задачи:</b>\n"
            result_text += f"➕ Добавлено: {tasks_added}\n"
            if tasks_errors > 0:
                result_text += f"⚠️ Ошибок: {tasks_errors}\n"
        
        if backup_progress:
            result_text += f"\n📊 <b>Прогресс:</b>\n"
            result_text += f"➕ Создано: {progress_added}\n"
            result_text += f"🔄 Обновлено: {progress_updated}\n"
            if progress_errors > 0:
                result_text += f"⚠️ Ошибок: {progress_errors}\n"
        
        await msg.edit_text(result_text, parse_mode="HTML")
        await state.clear()
        
        from utils import setup_logger
        logger = setup_logger()
        logger.info(f"Восстановление из JSON: добавлено {added_count}, обновлено {updated_count}")
    
    except Exception as e:
        # Удаляем временный файл
        try:
            if 'temp_backup_path' in locals() and os.path.exists(temp_backup_path):
                os.remove(temp_backup_path)
        except:
            pass
        
        from services import log_error
        await log_error(
            error=e,
            context="Восстановление из JSON бэкапа",
            user_id=message.from_user.id
        )
        
        await msg.edit_text(
            f"❌ <b>Ошибка при восстановлении!</b>\n\n"
            f"Детали: {str(e)[:500]}",
            parse_mode="HTML"
        )
        await state.clear()


async def restore_from_db_backup(message: Message, session: AsyncSession, state: FSMContext, document):
    """Восстановление из старого .db формата"""
    msg = await message.answer("⏳ Загружаю и обрабатываю .db бэкап...")
    
    await msg.edit_text(
        "⚠️ <b>Старый формат .db больше не поддерживается</b>\n\n"
        "📦 Используйте новый формат бэкапов .json\n"
        "Эти бэкапы создаются автоматически каждые 6 часов\n\n"
        "💡 Чтобы получить актуальный бэкап:\n"
        "1. Создайте новый бэкап через админ-панель\n"
        "2. Используйте полученный .json файл для восстановления",
        parse_mode="HTML"
    )
    await state.clear()
    
    msg = await message.answer("⏳ Загружаю и обрабатываю файл бэкапа...")
    
    try:
        import aiohttp
        import aiosqlite
        import os
        from datetime import datetime
        
        # Скачиваем файл
        file = await message.bot.get_file(document.file_id)
        file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file.file_path}"
        
        # Сохраняем во временный файл
        temp_backup_path = f"temp_restore_{datetime.now().timestamp()}.db"
        
        async with aiohttp.ClientSession() as http_session:
            async with http_session.get(file_url) as resp:
                if resp.status == 200:
                    with open(temp_backup_path, 'wb') as f:
                        f.write(await resp.read())
        
        await msg.edit_text("📊 Анализирую бэкап...")
        
        # Подключаемся к файлу бэкапа
        backup_db = await aiosqlite.connect(temp_backup_path)
        
        # Читаем пользователей из бэкапа
        cursor = await backup_db.execute("SELECT * FROM users")
        backup_users = await cursor.fetchall()
        
        # Получаем названия колонок
        column_names = [description[0] for description in cursor.description]
        
        # НЕ ЗАКРЫВАЕМ БД ЗДЕСЬ - нужна для дальнейшего восстановления
        
        if not backup_users:
            await backup_db.close()
            await msg.edit_text("⚠️ В бэкапе нет пользователей!")
            os.remove(temp_backup_path)
            await state.clear()
            return
        
        await msg.edit_text(f"🔄 Восстанавливаю {len(backup_users)} пользователей...")
        
        # Статистика
        added_count = 0
        updated_count = 0
        errors_count = 0
        
        # Импортируем пользователей
        from models.user import UserRole
        
        for user_row in backup_users:
            try:
                user_data = dict(zip(column_names, user_row))
                telegram_id = user_data.get('telegram_id')
                
                if not telegram_id:
                    errors_count += 1
                    continue
                
                # Проверяем существует ли пользователь
                result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                existing_user = result.scalar_one_or_none()
                
                if existing_user:
                    # Обновляем существующего
                    existing_user.username = user_data.get('username')
                    existing_user.first_name = user_data.get('first_name')
                    existing_user.last_name = user_data.get('last_name')
                    if user_data.get('role'):
                        existing_user.role = UserRole(user_data['role'])
                    existing_user.class_number = user_data.get('class_number')
                    
                    # Обновляем токены если есть в бэкапе
                    if 'tokens_limit' in column_names:
                        existing_user.tokens_limit = user_data.get('tokens_limit', 400000)
                        existing_user.tokens_used = user_data.get('tokens_used', 0)
                        existing_user.tokens_frozen = user_data.get('tokens_frozen', False)
                        if user_data.get('tokens_reset_date'):
                            from datetime import datetime
                            existing_user.tokens_reset_date = datetime.fromisoformat(user_data['tokens_reset_date']) if isinstance(user_data['tokens_reset_date'], str) else user_data['tokens_reset_date']
                    
                    updated_count += 1
                else:
                    # Создаём нового пользователя
                    new_user = User(
                        telegram_id=telegram_id,
                        username=user_data.get('username'),
                        first_name=user_data.get('first_name'),
                        last_name=user_data.get('last_name'),
                        role=UserRole(user_data['role']) if user_data.get('role') else None,
                        class_number=user_data.get('class_number')
                    )
                    
                    # Добавляем токены если есть
                    if 'tokens_limit' in column_names:
                        new_user.tokens_limit = user_data.get('tokens_limit', 400000)
                        new_user.tokens_used = user_data.get('tokens_used', 0)
                        new_user.tokens_frozen = user_data.get('tokens_frozen', False)
                        if user_data.get('tokens_reset_date'):
                            from datetime import datetime
                            new_user.tokens_reset_date = datetime.fromisoformat(user_data['tokens_reset_date']) if isinstance(user_data['tokens_reset_date'], str) else user_data['tokens_reset_date']
                    
                    session.add(new_user)
                    added_count += 1
            
            except Exception as e:
                errors_count += 1
                print(f"Ошибка при импорте пользователя: {e}")
                continue
        
        # Сохраняем изменения пользователей
        await session.commit()
        
        # ===== ВОССТАНОВЛЕНИЕ КОДОВ ДОСТУПА (ПОДПИСОК) =====
        await msg.edit_text("🔑 Восстанавливаю коды доступа...")
        
        # Проверяем есть ли таблица access_codes в бэкапе
        cursor_check = await backup_db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='access_codes'")
        has_access_codes = await cursor_check.fetchone()
        
        codes_added = 0
        codes_updated = 0
        codes_errors = 0
        
        if has_access_codes:
            # Читаем коды доступа из бэкапа
            cursor = await backup_db.execute("SELECT * FROM access_codes")
            backup_codes = await cursor.fetchall()
            code_column_names = [description[0] for description in cursor.description]
            
            from models import AccessCode
            from datetime import datetime
            
            for code_row in backup_codes:
                try:
                    code_data = dict(zip(code_column_names, code_row))
                    
                    # Пропускаем если код уже есть
                    existing_code = await AccessService.get_code(session, code_data.get('code'))
                    if existing_code:
                        codes_updated += 1
                        continue
                    
                    # Получаем user_id по activated_by
                    activated_by_id = code_data.get('activated_by')
                    if activated_by_id:
                        # Находим пользователя в новой БД
                        result = await session.execute(
                            select(User).where(User.id == activated_by_id)
                        )
                        user = result.scalar_one_or_none()
                        if not user:
                            codes_errors += 1
                            continue
                        user_id = user.id
                    else:
                        user_id = None
                    
                    # Создаём код доступа
                    new_code = AccessCode(
                        code=code_data.get('code'),
                        duration_days=code_data.get('duration_days'),
                        created_by=code_data.get('created_by'),
                        activated_by=user_id,
                        is_active=code_data.get('is_active', False),
                        created_at=datetime.fromisoformat(code_data['created_at']) if isinstance(code_data.get('created_at'), str) else code_data.get('created_at'),
                        activated_at=datetime.fromisoformat(code_data['activated_at']) if code_data.get('activated_at') and isinstance(code_data['activated_at'], str) else code_data.get('activated_at'),
                        expires_at=datetime.fromisoformat(code_data['expires_at']) if code_data.get('expires_at') and isinstance(code_data['expires_at'], str) else code_data.get('expires_at')
                    )
                    
                    # Добавляем опциональные поля если есть
                    if 'code_name' in code_column_names:
                        new_code.code_name = code_data.get('code_name')
                    if 'is_blocked' in code_column_names:
                        new_code.is_blocked = code_data.get('is_blocked', False)
                    
                    session.add(new_code)
                    codes_added += 1
                
                except Exception as e:
                    codes_errors += 1
                    print(f"Ошибка при импорте кода: {e}")
                    continue
            
            # Сохраняем коды
            await session.commit()
        
        # ===== ВОССТАНОВЛЕНИЕ ЗАДАЧ =====
        await msg.edit_text("📝 Восстанавливаю задачи...")
        
        cursor_check = await backup_db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
        has_tasks = await cursor_check.fetchone()
        
        tasks_added = 0
        tasks_errors = 0
        
        if has_tasks:
            from models import Task
            from models.task import TaskDifficulty
            
            cursor = await backup_db.execute("SELECT * FROM tasks")
            backup_tasks = await cursor.fetchall()
            task_column_names = [description[0] for description in cursor.description]
            
            for task_row in backup_tasks:
                try:
                    task_data = dict(zip(task_column_names, task_row))
                    
                    # Находим пользователя
                    user_id = task_data.get('user_id')
                    if not user_id:
                        tasks_errors += 1
                        continue
                    
                    result = await session.execute(
                        select(User).where(User.id == user_id)
                    )
                    user = result.scalar_one_or_none()
                    if not user:
                        tasks_errors += 1
                        continue
                    
                    # Создаём задачу
                    new_task = Task(
                        user_id=user.id,
                        task_text=task_data.get('task_text'),
                        topic=task_data.get('topic'),
                        difficulty=TaskDifficulty(task_data['difficulty']) if task_data.get('difficulty') else TaskDifficulty.MEDIUM,
                        student_answer=task_data.get('student_answer'),
                        is_correct=task_data.get('is_correct'),
                        ai_explanation=task_data.get('ai_explanation'),
                        created_at=datetime.fromisoformat(task_data['created_at']) if isinstance(task_data.get('created_at'), str) else task_data.get('created_at'),
                        completed_at=datetime.fromisoformat(task_data['completed_at']) if task_data.get('completed_at') and isinstance(task_data['completed_at'], str) else task_data.get('completed_at')
                    )
                    
                    session.add(new_task)
                    tasks_added += 1
                
                except Exception as e:
                    tasks_errors += 1
                    print(f"Ошибка при импорте задачи: {e}")
                    continue
            
            await session.commit()
        
        # ===== ВОССТАНОВЛЕНИЕ ПРОГРЕССА =====
        await msg.edit_text("📊 Восстанавливаю прогресс...")
        
        cursor_check = await backup_db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='progress'")
        has_progress = await cursor_check.fetchone()
        
        progress_added = 0
        progress_updated = 0
        progress_errors = 0
        
        if has_progress:
            from models import Progress
            
            cursor = await backup_db.execute("SELECT * FROM progress")
            backup_progress = await cursor.fetchall()
            progress_column_names = [description[0] for description in cursor.description]
            
            for progress_row in backup_progress:
                try:
                    progress_data = dict(zip(progress_column_names, progress_row))
                    
                    # Находим пользователя
                    user_id = progress_data.get('user_id')
                    if not user_id:
                        progress_errors += 1
                        continue
                    
                    result = await session.execute(
                        select(User).where(User.id == user_id)
                    )
                    user = result.scalar_one_or_none()
                    if not user:
                        progress_errors += 1
                        continue
                    
                    # Проверяем есть ли уже прогресс у пользователя
                    from models import Progress
                    result = await session.execute(
                        select(Progress).where(Progress.user_id == user.id)
                    )
                    existing_progress = result.scalar_one_or_none()
                    
                    if existing_progress:
                        # Обновляем существующий
                        existing_progress.total_tasks = progress_data.get('total_tasks', 0)
                        existing_progress.solved_tasks = progress_data.get('solved_tasks', 0)
                        existing_progress.correct_answers = progress_data.get('correct_answers', 0)
                        existing_progress.mistakes = progress_data.get('mistakes', 0)
                        existing_progress.last_activity = datetime.fromisoformat(progress_data['last_activity']) if isinstance(progress_data.get('last_activity'), str) else progress_data.get('last_activity')
                        progress_updated += 1
                    else:
                        # Создаём новый
                        new_progress = Progress(
                            user_id=user.id,
                            total_tasks=progress_data.get('total_tasks', 0),
                            solved_tasks=progress_data.get('solved_tasks', 0),
                            correct_answers=progress_data.get('correct_answers', 0),
                            mistakes=progress_data.get('mistakes', 0),
                            last_activity=datetime.fromisoformat(progress_data['last_activity']) if isinstance(progress_data.get('last_activity'), str) else progress_data.get('last_activity'),
                            created_at=datetime.fromisoformat(progress_data['created_at']) if isinstance(progress_data.get('created_at'), str) else progress_data.get('created_at')
                        )
                        session.add(new_progress)
                        progress_added += 1
                
                except Exception as e:
                    progress_errors += 1
                    print(f"Ошибка при импорте прогресса: {e}")
                    continue
            
            await session.commit()
        
        # Закрываем бэкап БД
        await backup_db.close()
        
        # Удаляем временный файл
        os.remove(temp_backup_path)
        
        # Итоговая статистика
        result_text = (
            f"✅ <b>Восстановление завершено!</b>\n\n"
            f"📊 <b>Пользователи:</b>\n"
            f"➕ Добавлено новых: {added_count}\n"
            f"🔄 Обновлено: {updated_count}\n"
        )
        
        if errors_count > 0:
            result_text += f"⚠️ Ошибок: {errors_count}\n"
        
        if has_access_codes:
            result_text += f"\n🔑 <b>Коды доступа (подписки):</b>\n"
            result_text += f"➕ Добавлено: {codes_added}\n"
            result_text += f"🔄 Уже были: {codes_updated}\n"
            if codes_errors > 0:
                result_text += f"⚠️ Ошибок: {codes_errors}\n"
        
        if has_tasks:
            result_text += f"\n📝 <b>Задачи:</b>\n"
            result_text += f"➕ Добавлено: {tasks_added}\n"
            if tasks_errors > 0:
                result_text += f"⚠️ Ошибок: {tasks_errors}\n"
        
        if has_progress:
            result_text += f"\n📊 <b>Прогресс:</b>\n"
            result_text += f"➕ Создано: {progress_added}\n"
            result_text += f"🔄 Обновлено: {progress_updated}\n"
            if progress_errors > 0:
                result_text += f"⚠️ Ошибок: {progress_errors}\n"
        
        result_text += f"\n💾 <b>Всего обработано:</b>\n"
        result_text += f"👥 {len(backup_users)} пользователей\n"
        if has_access_codes:
            result_text += f"🔑 {len(backup_codes)} кодов доступа\n"
        if has_tasks:
            result_text += f"📝 {len(backup_tasks)} задач\n"
        if has_progress:
            result_text += f"📊 {len(backup_progress)} записей прогресса"
        
        await msg.edit_text(result_text, parse_mode="HTML")
        await state.clear()
        
        # Логируем
        from utils import setup_logger
        logger = setup_logger()
        logger.info(f"Восстановление из бэкапа: добавлено {added_count}, обновлено {updated_count}, ошибок {errors_count}")
    
    except Exception as e:
        # Закрываем БД если была открыта
        try:
            if 'backup_db' in locals() and backup_db:
                await backup_db.close()
        except:
            pass
        
        # Удаляем временный файл если есть
        try:
            if 'temp_backup_path' in locals() and os.path.exists(temp_backup_path):
                os.remove(temp_backup_path)
        except:
            pass
        
        # Отправляем в канал ошибок
        from services import log_error
        await log_error(
            error=e,
            context="Восстановление из бэкапа (admin.py)",
            user_id=message.from_user.id,
            username=message.from_user.username
        )
        
        await msg.edit_text(
            f"❌ <b>Ошибка при восстановлении!</b>\n\n"
            f"Детали: {str(e)[:500]}",
            parse_mode="HTML"
        )
        
        from utils import setup_logger
        logger = setup_logger()
        logger.error(f"Ошибка при восстановлении из бэкапа: {e}", exc_info=True)
        
        await state.clear()


@router.callback_query(AdminStates.waiting_backup_file, F.data == "cancel_action")
async def cancel_restore_backup(callback: CallbackQuery, state: FSMContext):
    """Отмена восстановления"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Восстановление отменено\n\n"
        "🔧 Админ-панель\n\n"
        "Выберите раздел:",
        reply_markup=get_admin_menu()
    )
    await callback.answer("Отменено")


# ===== ОТМЕНА ДЕЙСТВИЙ =====

@router.callback_query(AdminStates.waiting_code_name, F.data == "cancel_action")
@router.callback_query(AdminStates.waiting_code_duration, F.data == "cancel_action")
@router.callback_query(AdminStates.waiting_backup_file, F.data == "cancel_action")
async def cancel_admin_action_callback(callback: CallbackQuery, state: FSMContext):
    """Отмена действия администратора через callback"""
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


@router.message(AdminStates.waiting_code_name, F.text == "❌ Отмена")
@router.message(AdminStates.waiting_code_duration, F.text == "❌ Отмена")
@router.message(AdminStates.waiting_backup_file, F.text == "❌ Отмена")
async def cancel_admin_action(message: Message, state: FSMContext):
    """Отмена действия администратора через текст"""
    if not is_admin(message.from_user.id):
        return
    
    await state.clear()
    await message.answer(
        "Действие отменено.\n\n"
        "🔧 Админ-панель\n\n"
        "Выберите раздел:",
        reply_markup=get_admin_menu()
    )



async def restore_from_db_backup(message: Message, session: AsyncSession, state: FSMContext, document):
    """Восстановление из старого .db формата"""
    msg = await message.answer("⏳ Загружаю и обрабатываю .db бэкап...")
    
    await msg.edit_text(
        "⚠️ <b>Старый формат .db больше не поддерживается</b>\n\n"
        "📦 Используйте новый формат бэкапов .json\n"
        "Эти бэкапы создаются автоматически каждые 6 часов\n\n"
        "💡 Чтобы получить актуальный бэкап:\n"
        "1. Создайте новый бэкап через админ-панель\n"
        "2. Используйте полученный .json файл для восстановления",
        parse_mode="HTML"
    )
    await state.clear()
