#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
БИЗНЕС-НАВИГАТОР v7.1 - Главный файл запуска (Оптимизированная версия)
FastAPI + Self-Ping система пробуждения для Render.com
"""

import asyncio
import os
import sys
import signal
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime
import aiohttp

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent))

# Настройка логирования
try:
    from utils.logger import setup_logging
    setup_logging()
except ImportError as e:
    print(f"❌ Не могу импортировать setup_logging: {e}")
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

# Глобальные переменные
bot_instance = None
application = None
keep_alive_task = None

# ============================================
# СИСТЕМА ПРОБУЖДЕНИЯ: Self-Ping
# ============================================
async def self_ping_task():
    """Пингуем сами себя каждые 10 минут для предотвращения засыпания"""
    await asyncio.sleep(60)  # Даем время на запуск
    
    app_url = os.getenv("RENDER_EXTERNAL_URL")
    if not app_url:
        logger.warning("⚠️ RENDER_EXTERNAL_URL не установлен, self-ping отключен")
        return
    
    logger.info(f"🔔 Self-ping активирован для {app_url}")
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                await asyncio.sleep(600)  # 10 минут
                
                async with session.get(f"{app_url}/health", timeout=10) as response:
                    if response.status == 200:
                        logger.info("✅ Self-ping успешен")
                    else:
                        logger.warning(f"⚠️ Self-ping вернул {response.status}")
                        
            except asyncio.CancelledError:
                logger.info("🛑 Self-ping остановлен")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка self-ping: {e}")
                await asyncio.sleep(60)

# ============================================
# LIFECYCLE MANAGEMENT
# ============================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом FastAPI приложения"""
    global bot_instance, application, keep_alive_task
    
    # ===== ЗАПУСК =====
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК БИЗНЕС-НАВИГАТОРА v7.1 (Оптимизированная версия)")
    logger.info("=" * 60)
    
    try:
        from config.settings import BotConfig
        from core.bot import BusinessNavigatorBot
        
        # Загрузка конфигурации
        logger.info("⚙️ Загружаю конфигурацию...")
        config = BotConfig()
        
        if not config.telegram_token:
            logger.error("❌ TELEGRAM_BOT_TOKEN не найден!")
            sys.exit(1)
        
        # Маскируем токен
        masked_token = config.telegram_token[:4] + "***" + config.telegram_token[-4:] if len(config.telegram_token) > 8 else "***"
        logger.info(f"✅ Токен бота: {masked_token}")
        logger.info(f"🤖 OpenAI модель: {config.openai_model}")
        logger.info(f"📝 Вопросов загружено: {len(config.questions)}")
        
        # Инициализация менеджера данных (используем глобальный экземпляр)
        from services.data_manager import data_manager as global_data_manager
        global_data_manager.initialize()
        logger.info("💾 Менеджер данных инициализирован")
        
        # Проверка OpenAI
        openai_service = None
        if config.openai_api_key:
            logger.info("🔍 Проверяем подключение к OpenAI...")
            try:
                from openai import AsyncOpenAI
                from services.openai_service import OpenAIService
                
                openai_client = AsyncOpenAI(api_key=config.openai_api_key)
                openai_service = OpenAIService(client=openai_client, model=config.openai_model)
                logger.info("✅ OpenAI клиент инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при проверке OpenAI: {e}")
        else:
            logger.warning("⚠️ OPENAI_API_KEY не найден")
        
        logger.info("-" * 40)
        
        # Создание и запуск бота
        logger.info("🤖 Создаю экземпляр бота...")
        bot = BusinessNavigatorBot(config, global_data_manager, openai_service)
        bot_instance = bot
        application = bot.application
        
        # Запуск бота в фоновом режиме
        logger.info("▶️ Запускаю бота...")
        bot_task = asyncio.create_task(bot.start())
        await asyncio.sleep(2)
        
        # Запуск системы пробуждения
        logger.info("🔔 Запускаю систему самопробуждения...")
        keep_alive_task = asyncio.create_task(self_ping_task())
        
        logger.info("✅ Бот успешно запущен")
        logger.info("✅ Система пробуждения активирована")
        logger.info("🌐 FastAPI сервер готов")
        
        yield  # Работа приложения
        
    except Exception as e:
        logger.critical(f"❌ Ошибка при запуске: {e}", exc_info=True)
        raise
    
    finally:
        # ===== ОСТАНОВКА =====
        logger.info("⏹️ Останавливаю систему...")
        
        # Останавливаем self-ping
        if keep_alive_task and not keep_alive_task.done():
            keep_alive_task.cancel()
            try:
                await keep_alive_task
            except asyncio.CancelledError:
                logger.info("✅ Self-ping остановлен")
        
        # Останавливаем бота
        if bot_instance:
            try:
                await bot_instance.stop()
                logger.info("✅ Бот остановлен")
            except Exception as e:
                logger.error(f"❌ Ошибка при остановке: {e}")
        
        logger.info("👋 Завершение работы")
        logger.info("=" * 60)

# ============================================
# FASTAPI APPLICATION
# ============================================
app = FastAPI(
    title="Business Navigator API",
    version="7.1",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# ===== ENDPOINTS =====
@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "app": "Business Navigator v7.1 (Optimized)",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check для Render и мониторинга"""
    global bot_instance
    
    if bot_instance and bot_instance.is_running:
        return {
            "status": "healthy",
            "bot": "running",
            "timestamp": datetime.utcnow().isoformat()
        }
    else:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "bot": "stopped",
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@app.get("/ping")
async def ping():
    """Простой пинг для UptimeRobot"""
    return PlainTextResponse("pong")

# ===== ОБРАБОТЧИКИ СИГНАЛОВ =====
def signal_handler(signum, frame):
    """Graceful shutdown"""
    logger.info(f"📶 Получен сигнал {signum}, завершаю работу...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ===== ТОЧКА ВХОДА =====
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 10000))
    logger.info(f"🔧 Запуск на порту {port}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=False
    )