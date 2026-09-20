"""
Rate Limiter для контроля нагрузки на AI API
Ограничивает количество одновременных запросов к OpenAI
"""

import asyncio
from typing import Optional
from datetime import datetime, timedelta
from collections import deque


class RateLimiter:
    """
    Rate limiter с ограничением одновременных запросов
    """
    
    def __init__(self, max_concurrent: int = 10, max_per_minute: int = 60):
        """
        Args:
            max_concurrent: Максимум одновременных запросов
            max_per_minute: Максимум запросов в минуту
        """
        self.max_concurrent = max_concurrent
        self.max_per_minute = max_per_minute
        
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._request_times: deque = deque()
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Получить разрешение на запрос"""
        # Ограничение одновременных запросов
        await self._semaphore.acquire()
        
        # Ограничение запросов в минуту
        async with self._lock:
            now = datetime.utcnow()
            
            # Удаляем старые запросы (старше минуты)
            while self._request_times and self._request_times[0] < now - timedelta(minutes=1):
                self._request_times.popleft()
            
            # Проверяем лимит
            if len(self._request_times) >= self.max_per_minute:
                # Ждём пока не освободится слот
                wait_time = 60 - (now - self._request_times[0]).total_seconds()
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
            
            # Записываем текущий запрос
            self._request_times.append(now)
    
    def release(self):
        """Освободить разрешение"""
        self._semaphore.release()


# Глобальный rate limiter для AI запросов
_ai_rate_limiter: Optional[RateLimiter] = None


def get_ai_rate_limiter() -> RateLimiter:
    """Получить AI rate limiter"""
    global _ai_rate_limiter
    if not _ai_rate_limiter:
        # 10 одновременных запросов, 60 запросов в минуту
        _ai_rate_limiter = RateLimiter(max_concurrent=10, max_per_minute=60)
    return _ai_rate_limiter
