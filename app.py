#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
БИЗНЕС-НАВИГАТОР v7.0 - Главный файл запуска
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import setup_logging
from config.settings import BotConfig
from core.bot import BusinessNavigatorBot

logger = logging.getLogger(__name__)

async def main():
    """Основная функция запуска бота"""
    try:
        # Настройка логирования
        setup_logging()
        
        # Проверка Python версии
        if sys.version_info < (3, 9) or sys.version_info >= (3, 10):
            logger.error("❌ Требуется Python 3.9.16. Текущая версия: %s", sys.version)
            sys.exit(1)
        
        # Загрузка конфигурации
        config = BotConfig()
        
        if not config.validate():
            logger.error("❌ Ошибка конфигурации")
            sys.exit(1)
        
        # Проверка OpenAI
        if config.openai_api_key:
            from services.openai_service import OpenAIService
            openai_service = OpenAIService(config)
            if await openai_service.check_availability():
                logger.info("✅ OpenAI доступен")
            else:
                logger.warning("⚠️ OpenAI недоступен, включен тестовый режим")
        
        # Создание и запуск бота
        logger.info("🚀 Запуск Бизнес-Навигатора v7.0...")
        bot = BusinessNavigatorBot(config)
        
        # Запуск health check сервера (для Render)
        from services.health_check import start_health_check_server
        health_task = asyncio.create_task(start_health_check_server())
        
        # Запуск бота
        await bot.run()
        
        # Ожидание завершения
        await health_task
        
    except KeyboardInterrupt:
        logger.info("⏹ Остановка бота по запросу пользователя")
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    # Запуск асинхронного event loop
    asyncio.run(main())