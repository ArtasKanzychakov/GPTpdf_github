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
        
        # Проверяем наличие обязательных переменных
        if not config.telegram_token:
            logger.error("❌ TELEGRAM_BOT_TOKEN не найден!")
            logger.error("Добавьте переменную в настройках Render:")
            logger.error("1. TELEGRAM_BOT_TOKEN=ваш_токен_бота")
            logger.error("2. Получите токен у @BotFather в Telegram")
            sys.exit(1)
        
        if not config.openai_api_key:
            logger.warning("⚠️ OPENAI_API_KEY не найден. Будет работать базовый режим без AI.")
        
        # Проверка OpenAI (если ключ есть)
        if config.openai_api_key:
            from services.openai_service import OpenAIService
            openai_service = OpenAIService(config)
            
            # Асинхронная проверка доступности
            logger.info("🔍 Проверяем подключение к OpenAI...")
            available, info = await openai_service.check_availability()
            
            if available:
                logger.info(f"✅ OpenAI доступен: {info}")
            else:
                logger.warning(f"⚠️ OpenAI проблемы: {info}")
                logger.warning("Будет работать в базовом режиме")
        else:
            logger.info("🤖 OpenAI отключен, используется базовый режим")
        
        # Создание и запуск бота
        logger.info("🚀 Запуск Бизнес-Навигатора v7.0...")
        bot = BusinessNavigatorBot(config)
        
        # Запуск health check сервера (для Render) в фоне
        from services.health_check import start_health_check_server
        health_task = asyncio.create_task(
            start_health_check_server(host=config.host, port=config.port)
        )
        
        logger.info(f"🌐 Health check сервер запущен на порту {config.port}")
        logger.info("🤖 Бот запускается в режиме polling...")
        
        # Запуск бота
        await bot.run()
        
        # Ожидание завершения (в теории не должно сюда дойти)
        await health_task
        
    except KeyboardInterrupt:
        logger.info("⏹ Остановка бота по запросу пользователя")
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    # Проверяем, что мы на Render (есть переменная PORT)
    port = os.getenv('PORT', '10000')
    logger.info(f"Порт из окружения: {port}")
    
    # Запуск асинхронного event loop
    asyncio.run(main())