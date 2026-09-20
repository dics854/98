"""
Обработчик команд для учеников
Репетиторский режим - ведём ученика до правильного ответа
"""

import aiohttp
import base64
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from services import UserService, StatisticsService, AIService, AccessService, TokenService, log_error
from keyboards import (
    get_student_menu, 
    get_solve_task_keyboard, 
    get_cancel_keyboard_inline, 
    get_start_keyboard,
    get_settings_keyboard,
    get_class_selection_keyboard
)
from models import Task, Progress
from models.task import TaskDifficulty
from models.user import UserRole
from datetime import datetime
from config import settings

router = Router(name="student")


class StudentStates(StatesGroup):
    """Состояния ученика"""
    tutoring_session = State()  # Режим занятия с репетитором


# Инициализируем AI сервис
ai_service = AIService()


@router.callback_query(F.data == "solve_with_tutor")
async def start_tutoring_session(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало занятия с AI-репетитором"""
    user_id = callback.from_user.id
    user = await UserService.get_user(session, user_id)
    
    # Проверяем, первый ли раз пользователь использует репетитора
    if user.first_tutor_usage:
        # Первый раз - показываем полное описание умений
        message_text = (
            "👨‍🏫 *Занятие с репетитором началось!*\n\n"
            "📚 *Что я умею:*\n"
            "✏️ Уравнения и неравенства\n"
            "📖 Текстовые задачи из учебников\n"
            "📐 Геометрия (площади, объёмы, теоремы)\n"
            "🚗 Задачи на движение, работу, проценты\n"
            "🔢 Дроби, пропорции, степени\n"
            "📊 Функции и графики\n"
            "🎲 Комбинаторика и вероятность\n"
            "🧩 Логические задачи\n"
            "💬 Могу объяснить тему простым языком\n\n"
            "💡 *Как это работает:*\n"
            "• Отправь мне задачу *текстом* или *фотографией* 📸\n"
            "• Я буду задавать наводящие вопросы\n"
            "• Отвечай на мои вопросы и думай над задачей\n"
            "• Вместе мы дойдём до правильного ответа!\n\n"
            "💡 Я НЕ дам готовый ответ - помогу тебе ПОНЯТЬ как решать!\n\n"
            "🔹 *Примеры:*\n"
            "_• Реши уравнение: 2x + 5 = 15_\n"
            "_• Из города А в город Б выехали два автомобиля..._\n"
            "_• Найди площадь треугольника со сторонами 3, 4, 5_\n"
            "_• Объясни что такое производная_\n\n"
            "📸 *Можешь сфотографировать задачу из учебника!*\n\n"
            "✍️ *Отправь задачу текстом или фото:*"
        )
        
        # Отмечаем что пользователь уже использовал репетитора
        user.first_tutor_usage = False
        await session.commit()
    else:
        # Не первый раз - краткое сообщение
        message_text = (
            "👨‍🏫 *Давай начнём решать!*\n\n"
            "✍️ *Отправь мне задачу текстом или фото:*"
        )
    
    await callback.message.edit_text(
        message_text,
        reply_markup=get_cancel_keyboard_inline(),
        parse_mode="Markdown"
    )
    await state.set_state(StudentStates.tutoring_session)
    await callback.answer()


@router.message(StudentStates.tutoring_session)
async def tutoring_dialogue(message: Message, session: AsyncSession, state: FSMContext):
    """Диалог с репетитором - ведём ученика к ответу"""
    user_id = message.from_user.id
    
    user = await UserService.get_user(session, user_id)
    data = await state.get_data()
    
    # Получаем историю диалога
    conversation_history = data.get("conversation_history", [])
    task_text = data.get("task_text")
    task_id = data.get("task_id")
    task_image_url = data.get("task_image_url")  # URL изображения если было
    
    # Если это первое сообщение - это условие задачи
    if not task_text:
        # Проверяем есть ли фото, GIF или документ с изображением
        photo_urls = []
        
        if message.photo:
            # Обычное фото
            photo = message.photo[-1]
            photo_file = await message.bot.get_file(photo.file_id)
            # Скачиваем фото и конвертируем в base64
            async with aiohttp.ClientSession() as http_session:
                photo_url = f"https://api.telegram.org/file/bot{message.bot.token}/{photo_file.file_path}"
                async with http_session.get(photo_url) as resp:
                    if resp.status == 200:
                        photo_bytes = await resp.read()
                        photo_base64 = base64.b64encode(photo_bytes).decode('utf-8')
                        # Определяем MIME тип по расширению
                        file_ext = photo_file.file_path.split('.')[-1].lower()
                        mime_type = f"image/{file_ext}" if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp'] else "image/jpeg"
                        photo_data_url = f"data:{mime_type};base64,{photo_base64}"
                        photo_urls.append(photo_data_url)
            task_text = message.caption if message.caption else "Решить задачу с фотографии"
        
        elif message.animation:
            # GIF-анимация
            animation_file = await message.bot.get_file(message.animation.file_id)
            async with aiohttp.ClientSession() as http_session:
                gif_url = f"https://api.telegram.org/file/bot{message.bot.token}/{animation_file.file_path}"
                async with http_session.get(gif_url) as resp:
                    if resp.status == 200:
                        gif_bytes = await resp.read()
                        gif_base64 = base64.b64encode(gif_bytes).decode('utf-8')
                        gif_data_url = f"data:image/gif;base64,{gif_base64}"
                        photo_urls.append(gif_data_url)
            task_text = message.caption if message.caption else "Решить задачу с GIF"
            await message.answer("🎞 Получил GIF! Анализирую первый кадр как изображение...")
        
        elif message.document:
            # Документ (может быть GIF или изображение)
            mime_type = message.document.mime_type or ""
            if mime_type.startswith("image/"):
                doc_file = await message.bot.get_file(message.document.file_id)
                async with aiohttp.ClientSession() as http_session:
                    doc_url = f"https://api.telegram.org/file/bot{message.bot.token}/{doc_file.file_path}"
                    async with http_session.get(doc_url) as resp:
                        if resp.status == 200:
                            doc_bytes = await resp.read()
                            doc_base64 = base64.b64encode(doc_bytes).decode('utf-8')
                            doc_data_url = f"data:{mime_type};base64,{doc_base64}"
                            photo_urls.append(doc_data_url)
                task_text = message.caption if message.caption else "Решить задачу с изображения"
                
                if "gif" in mime_type:
                    await message.answer("🎞 Получил GIF как документ! Анализирую первый кадр...")
        
        else:
            # Текстовое сообщение
            task_text = message.text
        
        # Сохраняем задачу в БД БЕЗ анализа
        task = Task(
            user_id=user.id,
            task_text=task_text,
            topic="Решается с репетитором",
            difficulty=TaskDifficulty.MEDIUM  # Используем enum вместо строки
        )
        session.add(task)
        await session.flush()
        
        # ОБНОВЛЯЕМ ПРОГРЕСС - пользователь начал решать задачу
        from sqlalchemy import select
        progress_result = await session.execute(
            select(Progress).where(Progress.user_id == user.id)
        )
        progress = progress_result.scalar_one_or_none()
        
        # Если прогресса нет - создаем его
        if not progress:
            progress = Progress(user_id=user.id)
            session.add(progress)
            await session.flush()
        
        # Увеличиваем счетчик начатых задач
        progress.start_task()
        await session.commit()
        
        # СРАЗУ получаем первый вопрос от репетитора
        msg = await message.answer("💭 Думаю над задачей...")
        
        try:
            # Проверяем лимит токенов пользователя
            token_info = await TokenService.check_and_update_tokens(session, user)
            
            if not token_info['has_tokens']:
                if token_info['is_frozen']:
                    error_msg = (
                        "❄️ **Токены заморожены**\n\n"
                        "У вас нет активной подписки. Токены будут разморожены после активации подписки.\n\n"
                        f"📊 {TokenService.format_tokens_info(token_info)}\n\n"
                        "💬 Напишите @dvedian для получения доступа"
                    )
                else:
                    error_msg = (
                        "🚫 **Лимит токенов исчерпан**\n\n"
                        f"📊 {TokenService.format_tokens_info(token_info)}\n\n"
                        "💡 Токены автоматически обновятся в начале следующего месяца"
                    )
                await msg.edit_text(error_msg, parse_mode="Markdown")
                await state.clear()
                return
            
            # Первый запрос - отправляем задачу
            response, tokens_used = await ai_service.get_teaching_response(
                task_text,
                user.class_number,
                [],  # Пустая история
                image_urls=photo_urls if photo_urls else None  # Передаём список фото
            )
            
            # Если ответ - это ошибка, показываем её
            if "❌" in response or "⚠️" in response:
                await msg.edit_text(response)
                await state.clear()
                return
            
            # Списываем токены с баланса пользователя
            await TokenService.use_tokens(session, user, tokens_used)
            
            # Инициализируем историю правильно
            # Если были фото - включаем их в первое сообщение истории
            if photo_urls:
                first_message_content = []
                # Добавляем все фото
                for photo_url in photo_urls:
                    first_message_content.append({
                        "type": "image_url",
                        "image_url": {"url": str(photo_url)}  # Явно конвертируем в строку
                    })
                # Добавляем текст
                first_message_content.append({
                    "type": "text",
                    "text": f"На фото задача. {str(task_text)}\n\nВнимательно изучи задачу на изображении и задавай мне наводящие вопросы!"
                })
            else:
                first_message_content = f"Помоги мне решить эту задачу:\n\n{str(task_text)}\n\nЗадавай мне наводящие вопросы!"
            
            conversation_history = [
                {"role": "user", "content": first_message_content},
                {"role": "assistant", "content": str(response)}  # Явно конвертируем в строку
            ]
            
            await state.update_data(
                task_id=task.id,
                task_text=task_text,
                task_image_urls=photo_urls,  # Сохраняем список URL изображений
                conversation_history=conversation_history
            )
            
            await msg.edit_text(
                f"👨‍🏫 {response}",
                reply_markup=get_solve_task_keyboard()
            )
            await session.commit()
            
        except Exception as e:
            await msg.edit_text(f"❌ Ошибка: {str(e)}")
            await state.clear()
            # Логируем ошибку в канал
            await log_error(
                error=e,
                context="Начало занятия с репетитором (первое сообщение)",
                user_id=user_id,
                username=message.from_user.username,
                message_text=task_text
            )
        
        return
    
    # Это ответ ученика на вопрос репетитора
    # Проверяем есть ли новое фото, GIF или документ с изображением
    image_url = None
    caption_text = None
    
    if message.photo:
        # Обычное фото
        photo = message.photo[-1]
        photo_file = await message.bot.get_file(photo.file_id)
        # Скачиваем фото и конвертируем в base64
        async with aiohttp.ClientSession() as http_session:
            photo_url = f"https://api.telegram.org/file/bot{message.bot.token}/{photo_file.file_path}"
            async with http_session.get(photo_url) as resp:
                if resp.status == 200:
                    photo_bytes = await resp.read()
                    photo_base64 = base64.b64encode(photo_bytes).decode('utf-8')
                    file_ext = photo_file.file_path.split('.')[-1].lower()
                    mime_type = f"image/{file_ext}" if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp'] else "image/jpeg"
                    image_url = f"data:{mime_type};base64,{photo_base64}"
        caption_text = str(message.caption) if message.caption else "Смотри на фото с моим решением"
    
    elif message.animation:
        # GIF-анимация
        animation_file = await message.bot.get_file(message.animation.file_id)
        async with aiohttp.ClientSession() as http_session:
            gif_url = f"https://api.telegram.org/file/bot{message.bot.token}/{animation_file.file_path}"
            async with http_session.get(gif_url) as resp:
                if resp.status == 200:
                    gif_bytes = await resp.read()
                    gif_base64 = base64.b64encode(gif_bytes).decode('utf-8')
                    image_url = f"data:image/gif;base64,{gif_base64}"
        caption_text = str(message.caption) if message.caption else "Смотри на GIF"
        await message.answer("🎞 Получил GIF! Анализирую первый кадр как изображение...")
    
    elif message.document:
        # Документ (может быть GIF или изображение)
        mime_type = message.document.mime_type or ""
        if mime_type.startswith("image/"):
            doc_file = await message.bot.get_file(message.document.file_id)
            async with aiohttp.ClientSession() as http_session:
                doc_url = f"https://api.telegram.org/file/bot{message.bot.token}/{doc_file.file_path}"
                async with http_session.get(doc_url) as resp:
                    if resp.status == 200:
                        doc_bytes = await resp.read()
                        doc_base64 = base64.b64encode(doc_bytes).decode('utf-8')
                        image_url = f"data:{mime_type};base64,{doc_base64}"
            caption_text = str(message.caption) if message.caption else "Смотри на изображение"
            
            if "gif" in mime_type:
                await message.answer("🎞 Получил GIF как документ! Анализирую первый кадр...")
    
    if image_url:
        # Подсчитываем общее количество фото в диалоге
        total_photos = 1  # текущее фото
        for msg in conversation_history:
            if msg.get("role") == "user" and isinstance(msg.get("content"), list):
                total_photos += sum(1 for item in msg.get("content") if isinstance(item, dict) and item.get("type") == "image_url")
        
        # Информируем если много фото (может быть медленнее)
        if total_photos > 20:
            await message.answer(
                f"📸 Получил изображение #{total_photos} в этом диалоге!\n"
                f"⏳ Обработка может занять чуть больше времени...",
                reply_markup=get_solve_task_keyboard()
            )
        
    # Формируем сообщение с изображением
        student_message_content = [
            {
                "type": "image_url",
                "image_url": {"url": str(image_url)}
            },
            {
                "type": "text",
                "text": str(caption_text) if caption_text else "Смотри на изображение"
            }
        ]
        # Для передачи в API (не используется когда есть история, но нужно для совместимости)
        student_message_text = str(caption_text) if caption_text else "Изображение"
    else:
        # Обычное текстовое сообщение
        student_message_text = message.text
        if not student_message_text:
            await message.answer("⚠️ Пожалуйста, отправь текст или фото с ответом.")
            return
        student_message_content = student_message_text
    
    # DEBUG: Проверяем что content корректный
    from utils import setup_logger
    logger = setup_logger()
    
    if isinstance(student_message_content, list):
        for idx, item in enumerate(student_message_content):
            if not isinstance(item, dict):
                logger.error(f"❌ ПЕРЕД ДОБАВЛЕНИЕМ: student_message_content[{idx}] не dict: {type(item)} = {item}")
            elif "text" in item and not isinstance(item.get("text"), str):
                logger.error(f"❌ ПЕРЕД ДОБАВЛЕНИЕМ: student_message_content[{idx}].text не string: {type(item.get('text'))} = {item.get('text')}")
    
    # Добавляем ответ ученика в историю
    conversation_history.append({"role": "user", "content": student_message_content})
    
    # Получаем следующий ответ репетитора
    msg = await message.answer("💭 Думаю...")
    
    try:
        # Проверяем лимит токенов
        token_info = await TokenService.check_and_update_tokens(session, user)
        
        if not token_info['has_tokens']:
            if token_info['is_frozen']:
                error_msg = (
                    "❄️ **Токены заморожены**\n\n"
                    "У вас нет активной подписки.\n\n"
                    f"📊 {TokenService.format_tokens_info(token_info)}\n\n"
                    "💬 Напишите @dvedian для получения доступа"
                )
            else:
                error_msg = (
                    "🚫 **Лимит токенов исчерпан**\n\n"
                    f"📊 {TokenService.format_tokens_info(token_info)}\n\n"
                    "💡 Токены обновятся в начале следующего месяца"
                )
            await msg.edit_text(error_msg, parse_mode="Markdown")
            return
        
        response, tokens_used = await ai_service.get_teaching_response(
            student_message_text,  # Текстовая версия для совместимости
            user.class_number,
            conversation_history  # Полная история включая новое сообщение
        )
        
        # Если ответ - это ошибка
        if "❌" in response or "⚠️" in response:
            await msg.edit_text(response)
            return
        
        # Списываем токены
        await TokenService.use_tokens(session, user, tokens_used)
        
        # Добавляем ответ репетитора в историю
        conversation_history.append({"role": "assistant", "content": str(response)})
        
        await state.update_data(conversation_history=conversation_history)
        
        # СТРОГАЯ ПРОВЕРКА: завершаем только если AI явно сказал что ответ правильный
        # Проверяем ключевые фразы завершения
        completion_phrases = [
            "правильно! ответ:",
            "верно! ответ:",
            "молодец! ответ:",
            "точно! ответ:",
            "правильный ответ:",
            "это правильный ответ",
            "ты получил правильный ответ"
        ]
        
        response_lower = response.lower()
        has_completion = any(phrase in response_lower for phrase in completion_phrases)
        has_celebration = "🎉" in response
        
        # Завершаем только если:
        # 1. Есть 🎉 в ответе
        # 2. И есть явное подтверждение правильности ответа
        # 3. И было минимум 4 сообщения (2 полных обмена)
        if has_celebration and has_completion and len(conversation_history) >= 4:
            # УЧЕНИК ДОШЁЛ ДО ПРАВИЛЬНОГО ОТВЕТА!
            final_response = (
                f"👨‍🏫 {response}\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"🎓 *Занятие завершено!*\n\n"
                f"✅ Ты справился с задачей!\n"
                f"💪 Главное - сам дошёл до решения через размышления.\n"
                f"📚 Так и запоминается лучше всего!"
            )
            
            # Обновляем задачу как решённую
            from sqlalchemy import select
            task_result = await session.execute(
                select(Task).where(Task.id == task_id)
            )
            task = task_result.scalar_one_or_none()
            if task:
                task.is_correct = True
                # Получаем последний текстовый ответ ученика для БД
                last_user_text = ""
                if isinstance(student_message_content, str):
                    last_user_text = student_message_content
                elif isinstance(student_message_content, list):
                    # Ищем текст в массиве контента
                    for item in student_message_content:
                        if item.get("type") == "text":
                            last_user_text = item.get("text", "")
                            break
                
                task.student_answer = last_user_text if last_user_text else "Решено с фото"
                task.completed_at = datetime.utcnow()
                task.ai_explanation = "Ученик самостоятельно дошёл до правильного ответа"
            
            # Обновляем прогресс
            progress_result = await session.execute(
                select(Progress).where(Progress.user_id == user.id)
            )
            progress = progress_result.scalar_one_or_none()
            
            # Если прогресса нет - создаем его
            if not progress:
                progress = Progress(user_id=user.id)
                session.add(progress)
                await session.flush()
            
            # Завершаем задачу как правильную
            progress.complete_task(True)
            
            await session.commit()
            
            is_admin = user_id in settings.admin_ids_list
            await msg.edit_text(
                final_response,
                reply_markup=get_student_menu(is_admin),
                parse_mode="Markdown"
            )
            await state.clear()
            return
        
        # Продолжаем диалог
        await msg.edit_text(
            f"👨‍🏫 {response}",
            reply_markup=get_solve_task_keyboard()
        )
        
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {str(e)}")
        # Логируем ошибку в канал
        await log_error(
            error=e,
            context="Диалог с репетитором (ответ ученика)",
            user_id=user_id,
            username=message.from_user.username,
            message_text=student_message_text if 'student_message_text' in locals() else "Не удалось получить текст"
        )



@router.callback_query(StudentStates.tutoring_session, F.data == "get_hint")
async def get_hint(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Получение подсказки от репетитора"""
    data = await state.get_data()
    task_text = data.get("task_text")
    conversation_history = data.get("conversation_history", [])
    
    if not task_text:
        await callback.answer("Сначала отправь задачу", show_alert=True)
        return
    
    user = await UserService.get_user(session, callback.from_user.id)
    
    await callback.answer("Формулирую подсказку...")
    
    # Добавляем запрос подсказки в историю
    conversation_history.append({
        "role": "user",
        "content": "💡 Дай подсказку! Не знаю как решать, помоги пожалуйста."
    })
    
    # Проверяем токены перед запросом
    user_id = callback.from_user.id
    token_status = await TokenService.check_and_update_tokens(session, user)
    
    if not token_status['has_tokens']:
        await callback.answer(
            "❌ Токены на месяц закончились!\n\n"
            f"Использовано: {token_status['tokens_used']:,} / {token_status['tokens_limit']:,}\n"
            f"Обновление: {token_status['reset_date'].strftime('%d.%m.%Y')}",
            show_alert=True
        )
        return
    
    # Получаем ответ AI с учётом всей истории (возвращает tuple)
    hint, tokens_used = await ai_service.get_teaching_response(
        task_text=task_text,
        class_number=user.class_number,
        conversation_history=conversation_history
    )
    
    # Списываем токены
    await TokenService.use_tokens(session, user, tokens_used)
    await session.commit()
    
    # Добавляем ответ AI в историю
    conversation_history.append({
        "role": "assistant",
        "content": str(hint)
    })
    
    # Сохраняем обновлённую историю
    await state.update_data(conversation_history=conversation_history)
    
    await callback.message.answer(
        f"💡 *Подсказка от репетитора:*\n\n{hint}",
        reply_markup=get_solve_task_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(StudentStates.tutoring_session, F.data == "finish_lesson")
async def finish_tutoring_session(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Завершение занятия"""
    user_id = callback.from_user.id
    data = await state.get_data()
    task_id = data.get("task_id")
    
    # Сохраняем незавершённую задачу
    if task_id:
        from sqlalchemy import select
        task_result = await session.execute(
            select(Task).where(Task.id == task_id)
        )
        task = task_result.scalar_one_or_none()
        if task and not task.completed_at:
            task.completed_at = datetime.utcnow()
            task.is_correct = False
            task.ai_explanation = "Занятие завершено до получения правильного ответа"
            await session.commit()
        
        # Обновляем прогресс пользователя
        user = await UserService.get_user(session, user_id)
        progress_result = await session.execute(
            select(Progress).where(Progress.user_id == user.id)
        )
        progress = progress_result.scalar_one_or_none()
        
        # Если прогресса нет - создаем его
        if not progress:
            progress = Progress(user_id=user.id)
            session.add(progress)
            await session.flush()
        
        # Завершаем задачу как неправильную
        progress.complete_task(False)
        await session.commit()
    
    is_admin = user_id in settings.admin_ids_list
    
    await state.clear()
    await callback.message.edit_text(
        f"📚 *Занятие завершено*\n\n"
        f"Это была интересная задача!\n"
        f"Жду тебя снова 😊",
        reply_markup=get_student_menu(is_admin),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "my_tokens")
async def show_my_tokens(callback: CallbackQuery, session: AsyncSession):
    """Показать информацию о токенах пользователя"""
    user_id = callback.from_user.id
    user = await UserService.get_user(session, user_id)
    
    # Проверяем и обновляем токены
    token_info = await TokenService.check_and_update_tokens(session, user)
    
    # Форматируем информацию
    response = TokenService.format_tokens_info(token_info)
    
    response += "\n\n💡 **Что такое токены?**\n"
    response += "Токены — это единицы, которые расходуются при общении с AI.\n"
    response += "Каждый диалог с фотографией расходует примерно 1500-2000 токенов.\n\n"
    response += "🔄 **Обновление:**\n"
    response += "Токены автоматически обновляются каждый месяц.\n"
    response += f"Следующее обновление: {token_info['reset_date'].strftime('%d.%m.%Y')}"
    
    await callback.message.edit_text(
        response,
        reply_markup=get_student_menu(user_id in settings.admin_ids_list),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "my_progress")
async def show_progress(callback: CallbackQuery, session: AsyncSession):
    """Показать прогресс ученика"""
    user_id = callback.from_user.id
    
    stats = await StatisticsService.get_user_progress(session, user_id)
    
    if not stats or stats.get("total_tasks", 0) == 0:
        await callback.message.edit_text(
            "📊 *Твоя статистика пока пуста*\n\n"
            "Начни заниматься с репетитором, чтобы отслеживать прогресс!\n\n"
            "💡 Нажми *\"Решать с репетитором\"* чтобы начать",
            reply_markup=get_student_menu(user_id in settings.admin_ids_list),
            parse_mode="Markdown"
        )
        await callback.answer()
        return
    
    response = (
        f"📊 *Твой прогресс в обучении*\n\n"
        f"👤 {stats.get('user')}\n"
        f"🎓 Класс: {stats.get('class')}\n\n"
        f"📚 *Результаты занятий:*\n"
        f"📝 Всего задач решено: {stats.get('total_tasks')}\n"
        f"✅ Правильно: {stats.get('correct_answers')}\n"
        f"❌ С ошибками: {stats.get('mistakes')}\n"
        f"📈 Процент успеха: {stats.get('success_rate')}%\n\n"
        f"🕐 Последнее занятие: {stats.get('last_activity')}"
    )
    
    # Добавляем темы если есть
    topics = stats.get('topics', {})
    if topics:
        response += "\n\n📚 *Изученные темы:*\n"
        for topic, count in topics.items():
            if topic:
                response += f"• {topic}: {count} задач\n"
    
    await callback.message.edit_text(
        response, 
        reply_markup=get_student_menu(user_id in settings.admin_ids_list),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "settings")
async def settings_menu(callback: CallbackQuery, session: AsyncSession):
    """Меню настроек"""
    user_id = callback.from_user.id
    user = await UserService.get_user(session, user_id)
    
    # Получаем информацию о подписке
    from services import AccessService
    active_code = await AccessService.get_user_active_code(session, user_id)
    
    # Формируем текст профиля
    response = f"⚙️ Твой профиль\n\n"
    response += f"👤 Имя: {user.full_name}\n"
    response += f"📱 Username: @{user.username}\n" if user.username else ""
    response += f"🎓 Класс: {user.class_number}\n\n"
    response += f"💼 Доступ к репетитору:\n"
    
    if active_code:
        response += f"✅ Активен\n"
        response += f"📅 Осталось дней: {active_code.days_left}\n"
        response += f"📆 Действует до: {active_code.expires_at.strftime('%d.%m.%Y')}\n"
    else:
        response += f"❌ Не активен\n"
        response += f"💬 Напишите @dvedian для получения доступа\n"
    
    response += f"\n🔧 Настройки:\n"
    response += f"• Измените класс если перешли в другой"
    
    await callback.message.edit_text(
        response, 
        reply_markup=get_settings_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "change_class")
async def change_class_menu(callback: CallbackQuery):
    """Меню смены класса"""
    await callback.message.edit_text(
        f"🎓 *Изменение класса*\n\n"
        f"Выберите ваш текущий класс:\n"
        f"(Это поможет мне подбирать задачи нужного уровня)",
        reply_markup=get_class_selection_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(StudentStates.tutoring_session, F.data == "cancel_action")
async def cancel_tutoring_action(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Отмена действия во время занятия"""
    await finish_tutoring_session(callback, session, state)


@router.message(F.photo)
async def handle_photo_outside_session(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка фото - ЛЮБОЙ может отправить фото и получить ответ"""
    current_state = await state.get_state()
    
    # Если уже в диалоге - пропускаем (обработает tutoring_dialogue)
    if current_state == StudentStates.tutoring_session:
        return
    
    # ЛЮБОЙ пользователь может начать диалог с фото
    # Автоматически запускаем занятие БЕЗ проверки доступа
    await state.set_state(StudentStates.tutoring_session)
    await message.answer(
        "📸 *Вижу фото!*\n\n"
        "Начинаю анализ...",
        parse_mode="Markdown"
    )
    
    # Передаём в обработчик диалога
    await tutoring_dialogue(message, session, state)


@router.message(F.animation)
async def handle_animation_outside_session(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка GIF - ЛЮБОЙ может отправить GIF и получить ответ"""
    current_state = await state.get_state()
    
    # Если уже в диалоге - пропускаем
    if current_state == StudentStates.tutoring_session:
        return
    
    # ЛЮБОЙ пользователь может начать диалог с GIF
    # Автоматически запускаем занятие БЕЗ проверки доступа
    await state.set_state(StudentStates.tutoring_session)
    await message.answer("🎞 *Вижу GIF!*\n\nНачинаю анализ...", parse_mode="Markdown")
    await tutoring_dialogue(message, session, state)

