"""
Сервис кэширования для оптимизации производительности
Кэширует часто используемые данные в памяти
"""

import asyncio
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
from dataclasses import dataclass
import hashlib


@dataclass
class CacheEntry:
    """Запись в кэше"""
    value: Any
    expires_at: datetime


class CacheService:
    """
    In-memory кэш для часто используемых данных
    Автоматическое удаление устаревших записей
    """
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Запуск периодической очистки кэша"""
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop(self):
        """Остановка сервиса"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Получить значение из кэша
        
        Args:
            key: Ключ кэша
            
        Returns:
            Значение или None если не найдено/истекло
        """
        async with self._lock:
            entry = self._cache.get(key)
            
            if not entry:
                return None
            
            # Проверяем не истёк ли срок
            if datetime.utcnow() > entry.expires_at:
                del self._cache[key]
                return None
            
            return entry.value
    
    async def set(self, key: str, value: Any, ttl_seconds: int = 300):
        """
        Сохранить значение в кэш
        
        Args:
            key: Ключ кэша
            value: Значение для сохранения
            ttl_seconds: Время жизни в секундах (по умолчанию 5 минут)
        """
        async with self._lock:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)
    
    async def delete(self, key: str):
        """Удалить ключ из кэша"""
        async with self._lock:
            self._cache.pop(key, None)
    
    async def clear(self):
        """Очистить весь кэш"""
        async with self._lock:
            self._cache.clear()
    
    async def _cleanup_loop(self):
        """Периодическая очистка устаревших записей"""
        while True:
            try:
                await asyncio.sleep(60)  # Каждую минуту
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception:
                pass
    
    async def _cleanup_expired(self):
        """Удаление устаревших записей"""
        async with self._lock:
            now = datetime.utcnow()
            expired_keys = [
                key for key, entry in self._cache.items()
                if now > entry.expires_at
            ]
            
            for key in expired_keys:
                del self._cache[key]
    
    @staticmethod
    def make_key(*parts) -> str:
        """
        Создать ключ кэша из компонентов
        
        Args:
            *parts: Компоненты ключа
            
        Returns:
            Хэш ключа
        """
        key_string = ":".join(str(p) for p in parts)
        return hashlib.md5(key_string.encode()).hexdigest()


# Глобальный экземпляр кэша
_cache_service: Optional[CacheService] = None


def get_cache() -> CacheService:
    """Получить экземпляр кэш-сервиса"""
    global _cache_service
    if not _cache_service:
        _cache_service = CacheService()
    return _cache_service


async def start_cache_service():
    """Запуск кэш-сервиса"""
    cache = get_cache()
    await cache.start()


async def stop_cache_service():
    """Остановка кэш-сервиса"""
    cache = get_cache()
    await cache.stop()
