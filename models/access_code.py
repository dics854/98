"""
Модель кода доступа
Хранит информацию о кодах активации
"""

from sqlalchemy import String, Integer, BigInteger, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timedelta
from database.database import Base


class AccessCode(Base):
    __tablename__ = "access_codes"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    code_name: Mapped[str] = mapped_column(String(100), nullable=True)  # Название кода для админа
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    activated_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # True = не использован, False = активирован
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # True = заблокирован админом
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    activated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Связь с пользователем
    user = relationship("User", back_populates="access_codes", foreign_keys=[activated_by])
    
    def __repr__(self):
        return f"<AccessCode(code={self.code}, is_active={self.is_active}, is_blocked={self.is_blocked})>"
    
    def activate(self, user_id: int):
        """Активация кода пользователем"""
        self.activated_by = user_id
        self.activated_at = datetime.utcnow()
        self.expires_at = datetime.utcnow() + timedelta(days=self.duration_days)
        self.is_active = False
    
    def block(self):
        """Блокировка доступа администратором"""
        self.is_blocked = True
    
    def unblock(self):
        """Разблокировка доступа администратором"""
        self.is_blocked = False
    
    @property
    def is_expired(self) -> bool:
        """Проверка истечения срока действия"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def days_left(self) -> int:
        """Количество дней до истечения"""
        if not self.expires_at:
            return 0
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)
