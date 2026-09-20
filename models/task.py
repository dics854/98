"""
Модель задачи
Хранит информацию о задачах учеников
"""

from sqlalchemy import BigInteger, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import enum
from database.database import Base


class TaskDifficulty(enum.Enum):
    """Уровни сложности задач"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Task(Base):
    __tablename__ = "tasks"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    task_text: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=True)
    difficulty: Mapped[TaskDifficulty] = mapped_column(SQLEnum(TaskDifficulty), nullable=True)
    student_answer: Mapped[str] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=True)
    ai_explanation: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Связь с пользователем
    user = relationship("User", back_populates="tasks")
    
    def __repr__(self):
        return f"<Task(id={self.id}, user_id={self.user_id}, topic={self.topic})>"
    
    @property
    def is_completed(self) -> bool:
        """Проверка завершения задачи"""
        return self.completed_at is not None
    
    def complete(self, is_correct: bool, explanation: str = None):
        """Отметить задачу как завершенную"""
        self.is_correct = is_correct
        self.completed_at = datetime.utcnow()
        if explanation:
            self.ai_explanation = explanation
