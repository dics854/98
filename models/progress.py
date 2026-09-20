"""
Модель прогресса ученика
Хранит статистику обучения
"""

from sqlalchemy import BigInteger, Integer, DateTime, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from database.database import Base


class Progress(Base):
    __tablename__ = "progress"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
        index=True
    )
    total_tasks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    solved_tasks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_answers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mistakes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Связь с пользователем
    user = relationship("User", back_populates="progress")
    
    def __repr__(self):
        return f"<Progress(user_id={self.user_id}, solved={self.solved_tasks}/{self.total_tasks})>"
    
    @property
    def success_rate(self) -> float:
        """Процент правильных ответов"""
        if self.solved_tasks == 0:
            return 0.0
        return round((self.correct_answers / self.solved_tasks) * 100, 2)
    
    def start_task(self):
        """Начать новую задачу - увеличить счетчик начатых задач"""
        self.total_tasks += 1
        self.last_activity = datetime.utcnow()
    
    def complete_task(self, is_correct: bool):
        """Завершить задачу - обновить статистику решения"""
        self.solved_tasks += 1
        if is_correct:
            self.correct_answers += 1
        else:
            self.mistakes += 1
        self.last_activity = datetime.utcnow()
    
    def add_task(self, is_correct: bool):
        """Добавить новую задачу в статистику (старый метод для обратной совместимости)"""
        self.total_tasks += 1
        self.solved_tasks += 1
        if is_correct:
            self.correct_answers += 1
        else:
            self.mistakes += 1
        self.last_activity = datetime.utcnow()
    
    def get_statistics(self) -> dict:
        """Получить статистику в виде словаря"""
        return {
            "total_tasks": self.total_tasks,
            "solved_tasks": self.solved_tasks,
            "correct_answers": self.correct_answers,
            "mistakes": self.mistakes,
            "success_rate": self.success_rate,
            "last_activity": self.last_activity.strftime("%d.%m.%Y %H:%M")
        }
