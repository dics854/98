"""
Инициализация моделей базы данных
"""

from .user import User, UserRole
from .access_code import AccessCode
from .task import Task
from .progress import Progress

__all__ = ["User", "UserRole", "AccessCode", "Task", "Progress"]
