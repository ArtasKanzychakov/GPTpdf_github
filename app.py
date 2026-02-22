#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
БИЗНЕС-НАВИГАТОР v7.0 - DEMO VERSION
Главный файл запуска (FastAPI версия)
"""
import asyncio
import os
import sys
import signal
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальные переменные
bot_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом FastAPI приложения"""
    global bot_instance
    
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК БИЗНЕС-НАВИГАТОРА v7.0 (DEMO)")
    logger.info("=" * 60)
    
    try:
        from config.settings import config
        
        # Проверка токена
        if not config.telegram_token:
            logger.error("❌ TELEGRAM_BOT_TOKEN не найден!")
            sys.exit(1)
        
        masked_token = config.telegram_token[:4] + "***" + config.telegram_token[-4:] if len(config.telegram_token) > 8 else "***"
        logger.info(f"✅ Токен бота: {masked_token}")
        logger.info(f"📝 Вопросов: {len(config.questions)}")
        logger.info(f"⚠️ Режим: {'DEMO' if config.demo_mode else 'FULL'}")
        
        # Импорты
        from core.bot import BusinessNavigatorBot
        
        # Создание и запуск бота
        logger.info("🤖 Создаю экземпляр бота...")
        bot = BusinessNavigatorBot(config)
        bot_instance = bot
        
        # ЗАПУСК БОТА В ФОНОВОМ РЕЖИМЕ
        logger.info("▶️ Запускаю бота в фоновом режиме...")
        bot_task = asyncio.create_task(bot.start())
        
        await asyncio.sleep(2)
        logger.info("✅ Бот успешно запущен")
        
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
                logger.error(f"❌ Ошибка при остановке: {e}")


# Создаем FastAPI приложение
app = FastAPI(
    title="Business Navigator API",
    version="7.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "app": "Business Navigator v7.0 (DEMO)",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check для Render"""
    global bot_instance
    if bot_instance and bot_instance.is_running:
        return {"status": "healthy", "bot": "running"}
    else:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "bot": "stopped"})


@app.get("/status")
async def status():
    """Подробный статус системы"""
    import psutil
    import datetime
    
    return {
        "status": "operational",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent
        },
        "bot": {
            "running": bot_instance.is_running if bot_instance else False
        }
    }


# Обработчики сигналов
def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    logger.info(f"📶 Получен сигнал {signum}")
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
