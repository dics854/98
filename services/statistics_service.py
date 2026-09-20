"""
Сервис для работы со статистикой
"""

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from models import User, Task, Progress, AccessCode
from models.user import UserRole
from typing import Dict, Any
from datetime import datetime, timedelta


class StatisticsService:
    """Сервис для получения статистики"""
    
    @staticmethod
    async def get_user_progress(session: AsyncSession, telegram_id: int) -> Dict[str, Any]:
        """
        Получить прогресс пользователя
        
        Args:
            session: Сессия БД
            telegram_id: Telegram ID пользователя
            
        Returns:
            Словарь со статистикой
        """
        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return {}
        
        # Получаем прогресс
        progress_result = await session.execute(
            select(Progress).where(Progress.user_id == user.id)
        )
        progress = progress_result.scalar_one_or_none()
        
        if not progress:
            return {
                "user": user.full_name,
                "class": user.class_number,
                "total_tasks": 0,
                "solved_tasks": 0,
                "correct_answers": 0,
                "mistakes": 0,
                "success_rate": 0.0
            }
        
        # Получаем темы
        topics_result = await session.execute(
            select(Task.topic, func.count(Task.id))
            .where(Task.user_id == user.id)
            .group_by(Task.topic)
        )
        topics = dict(topics_result.all())
        
        return {
            "user": user.full_name,
            "class": user.class_number,
            "total_tasks": progress.total_tasks,
            "solved_tasks": progress.solved_tasks,
            "correct_answers": progress.correct_answers,
            "mistakes": progress.mistakes,
            "success_rate": progress.success_rate,
            "topics": topics,
            "last_activity": progress.last_activity.strftime("%d.%m.%Y %H:%M")
        }
    
    @staticmethod
    async def get_global_statistics(session: AsyncSession) -> Dict[str, Any]:
        """
        Получить глобальную статистику проекта
        
        Args:
            session: Сессия БД
            
        Returns:
            Словарь со статистикой
        """
        # Количество учеников
        students_count = await session.execute(
            select(func.count(User.id)).where(User.role == UserRole.STUDENT)
        )
        
        # Активные подписки
        active_subscriptions = await session.execute(
            select(func.count(AccessCode.id)).where(
                and_(
                    AccessCode.expires_at > datetime.utcnow(),
                    AccessCode.activated_by.isnot(None)
                )
            )
        )
        
        # Всего решено задач
        total_tasks = await session.execute(
            select(func.sum(Progress.solved_tasks))
        )
        
        # Статистика по классам
        class_stats = await session.execute(
            select(User.class_number, func.count(User.id))
            .where(User.role == UserRole.STUDENT)
            .group_by(User.class_number)
        )
        
        return {
            "students": students_count.scalar() or 0,
            "active_subscriptions": active_subscriptions.scalar() or 0,
            "total_tasks_solved": total_tasks.scalar() or 0,
            "class_distribution": dict(class_stats.all())
        }
    
    @staticmethod
    async def get_recent_activity(
        session: AsyncSession,
        telegram_id: int,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Получить недавнюю активность пользователя
        
        Args:
            session: Сессия БД
            telegram_id: Telegram ID пользователя
            days: Количество дней назад
            
        Returns:
            Словарь с активностью
        """
        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return {
                "period_days": days,
                "tasks_completed": 0,
                "correct_answers": 0,
                "success_rate": 0.0
            }
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Задачи за период
        tasks_result = await session.execute(
            select(func.count(Task.id))
            .where(
                and_(
                    Task.user_id == user.id,
                    Task.created_at >= start_date
                )
            )
        )
        
        # Правильные ответы за период
        correct_result = await session.execute(
            select(func.count(Task.id))
            .where(
                and_(
                    Task.user_id == user.id,
                    Task.created_at >= start_date,
                    Task.is_correct == True
                )
            )
        )
        
        tasks_count = tasks_result.scalar() or 0
        correct_count = correct_result.scalar() or 0
        
        return {
            "period_days": days,
            "tasks_completed": tasks_count,
            "correct_answers": correct_count,
            "success_rate": round((correct_count / tasks_count * 100), 2) if tasks_count > 0 else 0.0
        }
