"""
Главный файл бота
Инициализация и запуск
"""

# Автоматическая установка зависимостей при первом запуске
import subprocess
import sys

def install_dependencies():
    """Проверка и установка необходимых зависимостей"""
    required_packages = {
        'aiohttp': 'aiohttp==3.9.1',
        'aiogram': 'aiogram==3.4.1',
        'sqlalchemy': 'sqlalchemy==2.0.25',
        'aiosqlite': 'aiosqlite==0.19.0',
        'alembic': 'alembic==1.13.1',
        'dotenv': 'python-dotenv==1.0.0',
        'openai': 'openai==1.10.0',
        'pydantic': 'pydantic==2.5.3',
        'pydantic_settings': 'pydantic-settings==2.1.0',
        'greenlet': 'greenlet==3.0.3',
        'httpx': 'httpx==0.27.0'
    }
    
    missing_packages = []
    
    # Проверяем какие пакеты отсутствуют
    for package_import, package_install in required_packages.items():
        try:
            __import__(package_import)
        except ImportError:
            missing_packages.append(package_install)
    
    # Устанавливаем недостающие пакеты
    if missing_packages:
        print(f"🔧 Устанавливаю недостающие зависимости: {', '.join(missing_packages)}")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install"] + missing_packages,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("✅ Все зависимости успешно установлены!")
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Ошибка при установке зависимостей: {e}")
            print("Попробуйте установить вручную: pip install -r requirements.txt")
            sys.exit(1)

# Устанавливаем зависимости перед импортом
install_dependencies()

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ErrorEvent

from config import settings
from database import init_db, close_db
from middlewares import DatabaseMiddleware, AccessMiddleware
from handlers import routers
from utils import setup_logger
from services import init_error_logger, init_backup_service, start_backup_service, stop_backup_service, start_cache_service, stop_cache_service

# Настройка логирования
logger = setup_logger()


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    logger.info("Запуск бота...")
    
    try:
        # Автоматический запуск миграций Alembic
        logger.info("Запуск миграций базы данных...")
        try:
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                logger.info("✅ Миграции успешно применены")
            else:
                logger.warning(f"⚠️ Ошибка при применении миграций: {result.stderr}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось запустить миграции: {e}")
        
        # Инициализация базы данных
        await init_db()
        logger.info("База данных инициализирована")
        
        # Запуск кэш-сервиса
        await start_cache_service()
        logger.info("Кэш-сервис запущен")
        
        # Инициализация логгера ошибок
        init_error_logger(bot)
        if settings.ERROR_LOG_CHANNEL_ID:
            logger.info(f"Логирование ошибок в канал: {settings.ERROR_LOG_CHANNEL_ID}")
            # Тестовое сообщение
            try:
                await bot.send_message(
                    chat_id=settings.ERROR_LOG_CHANNEL_ID,
                    text="✅ <b>Бот запущен</b>\n\nСистема логирования ошибок активна.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить тестовое сообщение в канал логов: {e}")
        else:
            logger.warning("Канал для логов ошибок не настроен (ERROR_LOG_CHANNEL_ID)")
        
        # Инициализация и запуск автоматического бэкапа
        if settings.BACKUP_CHANNEL_ID:
            init_backup_service(bot, settings.BACKUP_CHANNEL_ID)
            await start_backup_service()
            logger.info(f"Автоматический бэкап БД в канал: {settings.BACKUP_CHANNEL_ID}")
        else:
            logger.warning("Канал для бэкапов не настроен (BACKUP_CHANNEL_ID)")
        
        logger.info(f"Администраторы: {settings.admin_ids_list}")
        logger.info("Бот успешно запущен!")
    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}")
        raise


async def on_shutdown():
    """Действия при остановке бота"""
    logger.info("Остановка бота...")
    
    try:
        # Остановка сервиса бэкапов
        await stop_backup_service()
        
        # Остановка кэш-сервиса
        await stop_cache_service()
        
        # Закрытие соединения с БД
        await close_db()
        logger.info("Соединение с БД закрыто")
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка при остановке: {e}")


async def error_handler(event: ErrorEvent):
    """Глобальный обработчик ошибок"""
    from services import log_error
    
    logger.error(f"Необработанная ошибка: {event.exception}", exc_info=True)
    
    # Получаем информацию о пользователе если возможно
    user_id = None
    username = None
    message_text = None
    
    try:
        if event.update.message:
            user_id = event.update.message.from_user.id
            username = event.update.message.from_user.username
            message_text = event.update.message.text or event.update.message.caption
        elif event.update.callback_query:
            user_id = event.update.callback_query.from_user.id
            username = event.update.callback_query.from_user.username
            message_text = f"Callback: {event.update.callback_query.data}"
    except:
        pass
    
    # Логируем в канал
    await log_error(
        error=event.exception,
        context="Глобальный обработчик ошибок",
        user_id=user_id,
        username=username,
        message_text=message_text
    )


async def main():
    """Главная функция"""
    try:
        # Инициализация бота и диспетчера
        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        # Хранилище состояний FSM
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        
        # Регистрация глобального обработчика ошибок
        dp.errors.register(error_handler)
        
        # Регистрация middleware
        # DatabaseMiddleware должен быть первым чтобы добавить сессию
        dp.message.middleware(DatabaseMiddleware())
        dp.callback_query.middleware(DatabaseMiddleware())
        
        # AccessMiddleware проверяет доступ после того как сессия добавлена
        dp.message.middleware(AccessMiddleware())
        dp.callback_query.middleware(AccessMiddleware())
        
        # Регистрация роутеров
        for router in routers:
            dp.include_router(router)
        
        # Вызов функции startup
        await on_startup(bot)
        
        # Запуск polling
        logger.info("Бот начал получать обновления")
        try:
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        finally:
            await on_shutdown()
            await bot.session.close()
    
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}", exc_info=True)
        sys.exit(1)
