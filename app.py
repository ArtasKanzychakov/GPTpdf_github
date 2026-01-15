#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
БИЗНЕС-НАВИГАТОР v7.0 - Главный файл запуска
"""

import asyncio
import os
import sys
import signal
import logging
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent))

# Сначала импортируем только setup_logging
try:
    from utils.logger import setup_logging
    # Настраиваем логирование сразу
    setup_logging()
except ImportError as e:
    print(f"❌ Не могу импортировать setup_logging: {e}")
    print("Проверьте наличие utils/logger.py")
    sys.exit(1)

logger = logging.getLogger(__name__)

# Теперь импортируем остальное
try:
    from config.settings import BotConfig
    from core.bot import BusinessNavigatorBot
    from services.health_check import start_health_check_server
    from services.openai_service import OpenAIService
except ImportError as e:
    logger.error(f"❌ Ошибка импорта модулей: {e}")
    logger.error("Проверьте структуру проекта и зависимости")
    logger.error("Убедитесь, что все файлы на месте:")
    logger.error("  - config/settings.py")
    logger.error("  - core/bot.py")
    logger.error("  - services/health_check.py")
    logger.error("  - services/openai_service.py")
    sys.exit(1)

# Глобальная переменная для graceful shutdown
bot_instance = None

def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    logger.info(f"📶 Получен сигнал {signum}, начинаю graceful shutdown...")
    sys.exit(0)

async def main():
    """Основная функция запуска бота"""
    global bot_instance
    
    try:
        logger.info("=" * 60)
        logger.info("🚀 ЗАПУСК БИЗНЕС-НАВИГАТОРА v7.0")
        logger.info("=" * 60)
        
        # Проверка Python версии
        python_version = sys.version_info
        logger.info(f"🐍 Python версия: {python_version.major}.{python_version.minor}.{python_version.micro}")
        
        if not (python_version.major == 3 and python_version.minor >= 9):
            logger.warning(f"⚠️ Рекомендуется Python 3.9+. Текущая: {sys.version}")
        
        # Загрузка конфигурации
        logger.info("⚙️ Загружаю конфигурацию...")
        config = BotConfig()
        
        # Проверяем наличие обязательных переменных
        if not config.telegram_token:
            logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: TELEGRAM_BOT_TOKEN не найден!")
            logger.error("Действия для исправления:")
            logger.error("1. Получите токен у @BotFather в Telegram")
            logger.error("2. Добавьте переменную в Render Dashboard:")
            logger.error("   - Name: TELEGRAM_BOT_TOKEN")
            logger.error("   - Value: ваш_токен_бота")
            logger.error("3. Перезапустите деплой")
            sys.exit(1)
        
        # Маскируем токен для логов
        masked_token = config.telegram_token
        if len(masked_token) > 8:
            masked_token = masked_token[:4] + "***" + masked_token[-4:]
        
        logger.info(f"✅ Токен бота: {masked_token}")
        logger.info(f"🤖 OpenAI модель: {config.openai_model}")
        logger.info(f"🌐 Язык бота: {config.bot_language}")
        logger.info(f"📝 Вопросов загружено: {len(config.questions)}")
        logger.info(f"🏢 Ниш загружено: {len(config.niche_categories)}")
        
        # Проверка OpenAI (если ключ есть)
        if config.openai_api_key:
            logger.info("🔍 Проверяем подключение к OpenAI...")
            try:
                if openai_service.is_initialized:
                    logger.info("✅ OpenAI клиент инициализирован")
                else:
                    logger.warning("⚠️ OpenAI клиент не инициализирован")
                    logger.warning("Будет работать в базовом режиме")
                    
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при проверке OpenAI: {e}")
                logger.warning("Будет работать в базовом режиме")
        else:
            logger.warning("⚠️ OPENAI_API_KEY не найден. Будет работать базовый режим без AI.")
            logger.warning("Для полной функциональности добавьте OPENAI_API_KEY в переменные окружения")
        
        # Создание бота
        logger.info("🤖 Создаю экземпляр бота...")
        bot = BusinessNavigatorBot(config)
        bot_instance = bot
        
        # Запуск health check сервера (для Render) в фоне
        port = int(os.getenv('PORT', config.port))
        logger.info(f"🌐 Запускаю health check сервер на порту {port}...")
        
        health_task = asyncio.create_task(
            start_health_check_server(host=config.host, port=port)
        )
        
        logger.info("✅ Health check сервер запущен")
        logger.info("-" * 40)
        
        # Настраиваем обработку сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Запуск бота
        logger.info("▶️ Запускаю бота в режиме polling...")
        logger.info("ℹ️ Для остановки нажмите Ctrl+C")
        
        # Запускаем бота и health сервер параллельно
        bot_task = asyncio.create_task(bot.run())
        
        # Ожидаем завершения любой из задач
        done, pending = await asyncio.wait(
            [bot_task, health_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Отменяем оставшиеся задачи
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        logger.info("⏹ Бот остановлен")
        
    except KeyboardInterrupt:
        logger.info("⏹ Остановка бота по запросу пользователя (Ctrl+C)")
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("=" * 60)
        logger.info("👋 Бизнес-Навигатор завершил работу")
        logger.info("=" * 60)

def run_bot():
    """Функция для запуска бота (используется Render)"""
    # Проверяем, что мы на Render (есть переменная PORT)
    port = os.getenv('PORT', '10000')
    logger.info(f"🔧 Порт из окружения: {port}")
    
    # Устанавливаем переменную PORT для конфига
    os.environ['PORT'] = port
    
    # Настраиваем event loop для асинхронной работы
    if sys.platform == 'win32':
        # Windows требует особого подхода
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        # Запускаем главную функцию
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Завершение работы по запросу пользователя")
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
            logger.info("🔄 Event loop закрыт, нормальное завершение")
        else:
            logger.error(f"❌ RuntimeError: {e}")
    except Exception as e:
        logger.critical(f"❌ Неожиданная ошибка: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    run_bot()