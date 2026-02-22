#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
БИЗНЕС-НАВИГАТОР v7.0 - DEMO VERSION
Главный файл запуска (FastAPI + Webhooks)
"""
import asyncio
import os
import sys
import signal
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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

        if not config.telegram_token:
            logger.error("❌ TELEGRAM_BOT_TOKEN не найден!")
            sys.exit(1)

        masked_token = (
            config.telegram_token[:4] + "***" + config.telegram_token[-4:]
            if len(config.telegram_token) > 8 else "***"
        )
        logger.info(f"✅ Токен бота: {masked_token}")
        logger.info(f"📝 Вопросов: {len(config.questions)}")
        logger.info(f"⚠️ Режим: {'DEMO' if config.demo_mode else 'FULL'}")

        from core.bot import BusinessNavigatorBot

        logger.info("🤖 Создаю экземпляр бота...")
        bot = BusinessNavigatorBot(config)
        bot_instance = bot

        logger.info("▶️ Запускаю бота...")
        await bot.start()
        await asyncio.sleep(2)
        logger.info("✅ Бот успешно запущен")

        render_url = os.getenv("RENDER_EXTERNAL_URL", "")
        if render_url:
            logger.info(f"🌐 URL сервиса: {render_url}")
            logger.info(f"🔗 Webhook URL: {render_url}/webhook")

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
        "app": "Business Navigator v7.0 (DEMO)",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    global bot_instance
    if bot_instance and bot_instance.is_running:
        return {"status": "healthy", "bot": "running"}
    return JSONResponse(status_code=503, content={"status": "unhealthy", "bot": "stopped"})


@app.get("/status")
async def status():
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


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Endpoint для обработки вебхуков от Telegram"""
    if not bot_instance or not bot_instance.is_running:
        return JSONResponse(status_code=503, content={"status": "bot not ready"})
    try:
        update_dict = await request.json()
        success = await bot_instance.process_update(update_dict)
        return {"status": "ok"} if success else JSONResponse(status_code=500, content={"status": "error"})
    except Exception as e:
        logger.error(f"❌ Ошибка webhook: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"status": "internal_error"})


@app.get("/webhook-info")
async def webhook_info():
    """Информация о вебхуке (для отладки)"""
    if not bot_instance:
        return JSONResponse(status_code=503, content={"status": "bot not ready"})
    try:
        info = await bot_instance.application.bot.get_webhook_info()
        return {
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
        }
    except Exception as e:
        logger.error(f"❌ Ошибка получения info: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


def signal_handler(signum, frame):
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
