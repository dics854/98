"""
Сервис автоматического резервного копирования базы данных
Отправляет бэкапы в Telegram каждые 6 часов
"""

import asyncio
import json
from datetime import datetime
from typing import Optional
from pathlib import Path

from aiogram import Bot
from aiogram.types import BufferedInputFile
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import async_session_maker
from models import User, Task, Progress, AccessCode
from utils import setup_logger

logger = setup_logger()


class BackupService:
    """Сервис резервного копирования"""
    
    def __init__(self, bot: Bot, backup_channel_id: int):
        self.bot = bot
        self.backup_channel_id = backup_channel_id
        self.backup_task: Optional[asyncio.Task] = None
        self.is_running = False
    
    async def start(self):
        """Запуск автоматического бэкапа"""
        if self.is_running:
            logger.warning("Сервис бэкапа уже запущен")
            return
        
        self.is_running = True
        self.backup_task = asyncio.create_task(self._backup_loop())
        logger.info(f"🔄 Автоматический бэкап запущен. Канал: {self.backup_channel_id}")
        
        # Отправляем уведомление о запуске
        try:
            await self.bot.send_message(
                chat_id=self.backup_channel_id,
                text=(
                    "🔄 <b>Автоматический бэкап активирован</b>\n\n"
                    "📦 Резервные копии базы данных будут отправляться каждые 6 часов\n"
                    f"⏰ Следующий бэкап: через 6 часов\n"
                    f"📅 Запуск: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о запуске бэкапа: {e}")
    
    async def stop(self):
        """Остановка автоматического бэкапа"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.backup_task:
            self.backup_task.cancel()
            try:
                await self.backup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Автоматический бэкап остановлен")
    
    async def _backup_loop(self):
        """Цикл автоматического бэкапа каждые 6 часов"""
        # Делаем первый бэкап сразу при запуске
        await asyncio.sleep(10)  # Даем время боту запуститься
        await self.create_and_send_backup()
        
        # Затем каждые 6 часов
        while self.is_running:
            try:
                await asyncio.sleep(6 * 60 * 60)  # 6 часов в секундах
                if self.is_running:
                    await self.create_and_send_backup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле бэкапа: {e}", exc_info=True)
                await asyncio.sleep(60)  # Ждем минуту перед повтором
    
    async def create_and_send_backup(self):
        """Создание и отправка бэкапа"""
        try:
            logger.info("Начало создания резервной копии...")
            
            async with async_session_maker() as session:
                # Собираем данные из всех таблиц
                backup_data = await self._collect_database_data(session)
            
            # Создаем JSON файл
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"math_tutor_backup_{timestamp}.json"
            
            json_content = json.dumps(backup_data, ensure_ascii=False, indent=2)
            json_bytes = json_content.encode('utf-8')
            
            # Создаем BufferedInputFile
            document = BufferedInputFile(
                file=json_bytes,
                filename=filename
            )
            
            # Формируем статистику
            stats = self._format_stats(backup_data)
            
            # Отправляем в Telegram
            await self.bot.send_document(
                chat_id=self.backup_channel_id,
                document=document,
                caption=(
                    f"📦 <b>Резервная копия базы данных</b>\n\n"
                    f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
                    f"{stats}\n\n"
                    f"✅ Бэкап создан успешно"
                ),
                parse_mode="HTML"
            )
            
            logger.info(f"✅ Бэкап успешно отправлен: {filename}")
            
        except Exception as e:
            logger.error(f"Ошибка при создании бэкапа: {e}", exc_info=True)
            
            # Отправляем уведомление об ошибке
            try:
                await self.bot.send_message(
                    chat_id=self.backup_channel_id,
                    text=(
                        f"❌ <b>Ошибка при создании бэкапа</b>\n\n"
                        f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
                        f"❗ {str(e)[:500]}"
                    ),
                    parse_mode="HTML"
                )
            except:
                pass
    
    async def _collect_database_data(self, session: AsyncSession) -> dict:
        """
        Сбор данных из всех таблиц
        
        ВАЖНО: 
        - Сохраняются ТОЛЬКО пользователи с username
        - Коды доступа только привязанные к пользователям с username
        - Задачи и прогресс только от пользователей с username
        """
        
        # Получаем пользователей ТОЛЬКО с username
        users_result = await session.execute(
            select(User).where(User.username.isnot(None))
        )
        users = users_result.scalars().all()
        user_ids = [user.id for user in users]
        
        logger.info(f"Бэкап: найдено {len(users)} пользователей с username")
        
        # Получаем данные только от пользователей с username
        if user_ids:
            # Получаем задачи ТОЛЬКО от пользователей с username
            tasks_result = await session.execute(
                select(Task).where(Task.user_id.in_(user_ids))
            )
            tasks = tasks_result.scalars().all()
            
            # Получаем прогресс ТОЛЬКО от пользователей с username
            progress_result = await session.execute(
                select(Progress).where(Progress.user_id.in_(user_ids))
            )
            progress_records = progress_result.scalars().all()
            
            # Получаем коды доступа ТОЛЬКО привязанные к пользователям с username
            telegram_ids = [user.telegram_id for user in users]
            codes_result = await session.execute(
                select(AccessCode).where(
                    AccessCode.activated_by.in_(telegram_ids)
                )
            )
            access_codes = codes_result.scalars().all()
        else:
            tasks = []
            progress_records = []
            access_codes = []
        
        # Формируем структуру данных
        backup_data = {
            "backup_info": {
                "timestamp": datetime.now().isoformat(),
                "version": "2.0",  # Новая версия с токенами и фильтрацией
                "filter": "only_users_with_username",
                "database": settings.DB_PATH
            },
            "users": [self._user_to_dict(user) for user in users],
            "tasks": [self._task_to_dict(task) for task in tasks],
            "progress": [self._progress_to_dict(prog) for prog in progress_records],
            "access_codes": [self._access_code_to_dict(code) for code in access_codes]
        }
        
        return backup_data
    
    def _user_to_dict(self, user: User) -> dict:
        """Конвертация пользователя в словарь"""
        # Получаем активную подписку (если есть)
        active_subscription = None
        subscription_days_left = 0
        
        if user.access_codes:
            # Ищем активную (не истекшую и не заблокированную) подписку
            for code in user.access_codes:
                if not code.is_blocked and code.expires_at and not code.is_expired:
                    active_subscription = code.expires_at.isoformat()
                    subscription_days_left = code.days_left
                    break
        
        return {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role.value if user.role else None,
            "class_number": user.class_number,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            # ТОКЕНЫ - важно для корректного восстановления
            "tokens_limit": user.tokens_limit,
            "tokens_used": user.tokens_used,
            "tokens_reset_date": user.tokens_reset_date.isoformat() if user.tokens_reset_date else None,
            "tokens_frozen": user.tokens_frozen,
            "first_tutor_usage": user.first_tutor_usage,
            # ПОДПИСКА - сохраняем дату окончания и дни
            "subscription_end_date": active_subscription,
            "subscription_days_left": subscription_days_left
        }
    
    def _task_to_dict(self, task: Task) -> dict:
        """Конвертация задачи в словарь"""
        return {
            "id": task.id,
            "user_id": task.user_id,
            "task_text": task.task_text,
            "topic": task.topic,
            "difficulty": task.difficulty.value if task.difficulty else None,
            "student_answer": task.student_answer,
            "is_correct": task.is_correct,
            "ai_explanation": task.ai_explanation,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None
        }
    
    def _progress_to_dict(self, progress: Progress) -> dict:
        """Конвертация прогресса в словарь"""
        return {
            "id": progress.id,
            "user_id": progress.user_id,
            "total_tasks": progress.total_tasks,
            "solved_tasks": progress.solved_tasks,
            "correct_answers": progress.correct_answers,
            "mistakes": progress.mistakes,
            "last_activity": progress.last_activity.isoformat() if progress.last_activity else None,
            "created_at": progress.created_at.isoformat() if progress.created_at else None
        }
    
    def _access_code_to_dict(self, code: AccessCode) -> dict:
        """Конвертация кода доступа в словарь"""
        return {
            "id": code.id,
            "code": code.code,
            "code_name": code.code_name,
            "duration_days": code.duration_days,
            "created_by": code.created_by,
            "activated_by": code.activated_by,
            "is_active": code.is_active,
            "is_blocked": code.is_blocked,
            "created_at": code.created_at.isoformat() if code.created_at else None,
            "activated_at": code.activated_at.isoformat() if code.activated_at else None,
            "expires_at": code.expires_at.isoformat() if code.expires_at else None
        }
    
    def _format_stats(self, backup_data: dict) -> str:
        """Форматирование статистики для отправки"""
        return (
            f"📊 <b>Статистика:</b>\n"
            f"👥 Пользователей: {len(backup_data['users'])}\n"
            f"📝 Задач: {len(backup_data['tasks'])}\n"
            f"📈 Записей прогресса: {len(backup_data['progress'])}\n"
            f"🔑 Кодов доступа: {len(backup_data['access_codes'])}"
        )


# Глобальный экземпляр сервиса
_backup_service: Optional[BackupService] = None


def init_backup_service(bot: Bot, backup_channel_id: int):
    """Инициализация сервиса бэкапа"""
    global _backup_service
    _backup_service = BackupService(bot, backup_channel_id)
    return _backup_service


def get_backup_service() -> Optional[BackupService]:
    """Получить экземпляр сервиса бэкапа"""
    return _backup_service


async def start_backup_service():
    """Запуск сервиса бэкапа"""
    if _backup_service:
        await _backup_service.start()


async def stop_backup_service():
    """Остановка сервиса бэкапа"""
    if _backup_service:
        await _backup_service.stop()


async def manual_backup():
    """Создание бэкапа вручную"""
    if _backup_service:
        await _backup_service.create_and_send_backup()
    else:
        raise RuntimeError("Сервис бэкапа не инициализирован")
