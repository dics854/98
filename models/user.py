"""
Модель пользователя
Хранит информацию об учениках, родителях и администраторах
"""

from sqlalchemy import BigInteger, String, Integer, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import enum
from database.database import Base


class UserRole(enum.Enum):
    """Роли пользователей"""
    ADMIN = "admin"
    STUDENT = "student"


class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), nullable=True)
    class_number: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Лимиты токенов
    tokens_limit: Mapped[int] = mapped_column(Integer, default=1000000, nullable=False)  # 1M токенов на месяц
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_reset_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)  # Дата следующего обновления
    tokens_frozen: Mapped[bool] = mapped_column(default=False, nullable=False)  # Заморожены ли токены
    
    # Отслеживание первого использования репетитора
    first_tutor_usage: Mapped[bool] = mapped_column(default=True, nullable=False)  # True = первый раз, показать умения
    
    # Связь с кодами доступа
    access_codes = relationship("AccessCode", back_populates="user", foreign_keys="AccessCode.activated_by")
    
    # Связь с задачами
    tasks = relationship("Task", back_populates="user")
    
    # Связь с прогрессом
    progress = relationship("Progress", back_populates="user", uselist=False)
    
    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, role={self.role})>"
    
    @property
    def full_name(self) -> str:
        """Полное имя пользователя"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.username:
            return f"@{self.username}"
        return f"User {self.telegram_id}"
