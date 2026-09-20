"""
Обработчики команд бота
"""

from .start import router as start_router
from .student import router as student_router
from .admin import router as admin_router
from .admin_additions import router as admin_additions_router

# Список всех роутеров для регистрации
routers = [
    start_router,
    admin_router,
    admin_additions_router,
    student_router
]

__all__ = ["routers"]
