"""
Конфигурация приложения
Загружает настройки из .env файла
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Telegram Bot
    BOT_TOKEN: str
    ADMIN_IDS: str
    ERROR_LOG_CHANNEL_ID: int = None  # ID канала для логов ошибок
    BACKUP_CHANNEL_ID: int = None  # ID канала для резервных копий БД
    
    # Database
    DB_PATH: str = "math_tutor.db"  # Путь к файлу SQLite
    
    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4"
    
    # Application
    DEBUG: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @property
    def database_url(self) -> str:
        """Формирует URL для подключения к БД"""
        return f"sqlite+aiosqlite:///{self.DB_PATH}"
    
    @property
    def admin_ids_list(self) -> List[int]:
        """Преобразует строку с ID админов в список"""
        return [int(admin_id.strip()) for admin_id in self.ADMIN_IDS.split(",") if admin_id.strip()]


# Создаем глобальный экземпляр настроек
settings = Settings()
