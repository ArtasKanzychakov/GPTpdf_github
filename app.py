#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
БИЗНЕС-НАВИГАТОР v7.0 - Главный файл запуска (FastAPI версия)
"""
import asyncio
import os
import sys
import signal
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).parent))

try:
    from utils.logger import setup_logging
    setup_logging()
except ImportError as e:
    print(f"❌ Не могу импортировать setup_logging: {e}")
    sys.exit(1)

logger = logging.getLogger(__name__)

bot_instance = None
application = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом FastAPI приложения"""
    global bot_instance, application
    
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК БИЗНЕС-НАВИГАТОРА v7.0 (FastAPI)")
    logger.info("=" * 60)
    
    try:
        from config.settings import BotConfig
        from core.bot import BusinessNavigatorBot
        
        logger.info("⚙️ Загружаю конфигурацию...")
        config = BotConfig()
        
        if not config.telegram_token:
            logger.error("❌ TELEGRAM_BOT_TOKEN не найден!")
            sys.exit(1)
        
        masked_token = config.telegram_token
        if len(masked_token) > 8:
            masked_token = masked_token[:4] + "***" + masked_token[-4:]
        logger.info(f"✅ Токен бота: {masked_token}")
        logger.info(f"🤖 OpenAI модель: {config.openai_model}")
        logger.info(f"📝 Вопросов загружено: {len(config.questions)}")
        
        # ✅ ИСПРАВЛЕНО: DataManager не имеет метода initialize()
        from services.data_manager import data_manager
        logger.info("💾 Менеджер данных готов (in-memory)")
        
        if config.openai_api_key:
            logger.info("🔍 OpenAI ключ найден - полный режим")
        else:
            logger.warning("⚠️ OPENAI_API_KEY не найден - MOCK-режим")
        
        logger.info("-" * 40)
        
        logger.info("🤖 Создаю экземпляр бота...")
        bot = BusinessNavigatorBot(config)
        bot_instance = bot
        application = bot.application
        
        logger.info("▶️ Запускаю бота в фоновом режиме...")
        # ✅ FastAPI-совместимый запуск (не блокирует event loop)
        await bot.start()
        
        await asyncio.sleep(1)
        logger.info("✅ Бот успешно запущен в фоновом режиме")
        logger.info("🌐 FastAPI сервер готов принимать запросы")
        
        yield
        
    except Exception as e:
        logger.critical(f"❌ Ошибка при запуске: {e}", exc_info=True)
        raise
    finally:
        logger.info("⏹️ Останавливаю бота...")
        if bot_instance:
            try:
                await bot_instance.stop()
                logger.info("✅ Бот остановлен")
            except Exception as e:
                logger.error(f"❌ Ошибка при остановке бота: {e}")
        logger.info("👋 Бизнес-Навигатор завершил работу")
        logger.info("=" * 60)

app = FastAPI(
    title="Business Navigator API",
    version="7.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.get("/")
async def root():
    return {
        "app": "Business Navigator v7.0",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    global bot_instance
    if bot_instance and bot_instance.is_running:
        return {"status": "healthy", "bot": "running"}
    else:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "bot": "stopped"}
        )

@app.get("/status")
async def status():
    import psutil
    import datetime
    return {
        "status": "operational",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent
        },
        "bot": {
            "running": bot_instance.is_running if bot_instance else False,
            "users_online": 0
        }
    }

@app.post("/restart-bot")
async def restart_bot():
    global bot_instance
    if not bot_instance:
        raise HTTPException(status_code=500, detail="Bot not initialized")
    try:
        logger.info("🔄 Запрашивается перезапуск бота...")
        await bot_instance.stop()
        await asyncio.sleep(2)
        await bot_instance.start()
        logger.info("✅ Бот перезапущен")
        return {"status": "success", "message": "Bot restarted"}
    except Exception as e:
        logger.error(f"❌ Ошибка при перезапуске бота: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def signal_handler(signum, frame):
    logger.info(f"📶 Получен сигнал {signum}, завершаю работу...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

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
