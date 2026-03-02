#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
БИЗНЕС-НАВИГАТОР v7.0 - DEMO VERSION
Полностью автоматический Webhook (Render)
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

# -------------------------------------------------
# Path fix
# -------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

# -------------------------------------------------
# Logging
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

bot_instance = None


# =================================================
# LIFESPAN — АВТОМАТИЧЕСКИЙ WEBHOOK
# =================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_instance

    logger.info("=" * 70)
    logger.info("🚀 ЗАПУСК БИЗНЕС-НАВИГАТОРА v7.0 (AUTO WEBHOOK)")
    logger.info("=" * 70)

    try:
        from config.settings import config

        # -----------------------------------------
        # Проверка токена
        # -----------------------------------------
        if not config.telegram_token:
            logger.critical("❌ TELEGRAM_BOT_TOKEN не найден!")
            sys.exit(1)

        masked = (
            config.telegram_token[:4] + "***" + config.telegram_token[-4:]
            if len(config.telegram_token) > 8 else "***"
        )

        logger.info(f"✅ Токен бота: {masked}")
        logger.info(f"📝 Вопросов: {len(config.questions)}")
        logger.info(f"⚠️ Режим: {'DEMO' if config.demo_mode else 'FULL'}")

        # -----------------------------------------
        # Создание бота
        # -----------------------------------------
        from core.bot import BusinessNavigatorBot

        logger.info("🤖 Создаю экземпляр Telegram бота...")
        bot = BusinessNavigatorBot(config)
        bot_instance = bot

        logger.info("▶️ Запускаю Telegram Application...")
        await bot.start()

        # -----------------------------------------
        # АВТОМАТИЧЕСКИЙ WEBHOOK
        # -----------------------------------------

        base_url = os.getenv("RENDER_EXTERNAL_URL")

        if not base_url:
            logger.critical("❌ RENDER_EXTERNAL_URL не найден!")
            logger.critical("Webhook невозможен без публичного URL.")
            sys.exit(1)

        webhook_url = f"{base_url}/webhook"

        telegram_bot = bot.application.bot

        # 1️⃣ Удаляем старый webhook
        logger.info("🧹 Удаляю старый webhook (если существует)...")
        await telegram_bot.delete_webhook(drop_pending_updates=True)

        # 2️⃣ Устанавливаем новый webhook
        logger.info(f"🔗 Устанавливаю webhook: {webhook_url}")
        await telegram_bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=None
        )

        # 3️⃣ Проверяем установку
        info = await telegram_bot.get_webhook_info()

        logger.info("📡 Проверяю установленный webhook...")

        if info.url != webhook_url:
            logger.critical("❌ Webhook НЕ установился корректно!")
            logger.critical(f"Telegram сообщает URL: {info.url}")
            sys.exit(1)

        if info.last_error_message:
            logger.warning(f"⚠️ Telegram сообщает об ошибке: {info.last_error_message}")

        logger.info("✅ Webhook успешно установлен и подтвержден")
        logger.info(f"📬 Pending updates: {info.pending_update_count}")
        logger.info("🎯 Бот полностью готов к работе")

        yield

    except Exception as e:
        logger.critical(f"❌ Критическая ошибка запуска: {e}", exc_info=True)
        raise

    finally:
        logger.info("⏹️ Останавливаю бота...")

        if bot_instance:
            try:
                await bot_instance.application.bot.delete_webhook()
                await bot_instance.stop()
                logger.info("✅ Бот остановлен корректно")
            except Exception as e:
                logger.error(f"❌ Ошибка при остановке: {e}")


# =================================================
# FASTAPI
# =================================================
app = FastAPI(
    title="Business Navigator API",
    version="7.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)


# -------------------------------------------------
# Root
# -------------------------------------------------
@app.get("/")
async def root():
    return {
        "app": "Business Navigator v7.0",
        "status": "running",
        "webhook_mode": True
    }


# -------------------------------------------------
# Health
# -------------------------------------------------
@app.get("/health")
async def health_check():
    global bot_instance

    if bot_instance and bot_instance.is_running:
        return {"status": "healthy", "bot": "running"}

    return JSONResponse(
        status_code=503,
        content={"status": "unhealthy", "bot": "stopped"}
    )


# -------------------------------------------------
# Status
# -------------------------------------------------
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


# -------------------------------------------------
# TELEGRAM WEBHOOK ENDPOINT
# -------------------------------------------------
@app.post("/webhook")
async def telegram_webhook(request: Request):
    if not bot_instance or not bot_instance.is_running:
        return JSONResponse(
            status_code=503,
            content={"status": "bot not ready"}
        )

    try:
        update_dict = await request.json()
        success = await bot_instance.process_update(update_dict)

        if success:
            return {"status": "ok"}

        return JSONResponse(
            status_code=500,
            content={"status": "processing_failed"}
        )

    except Exception as e:
        logger.error(f"❌ Ошибка webhook: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "internal_error"}
        )


# -------------------------------------------------
# WEBHOOK INFO DEBUG
# -------------------------------------------------
@app.get("/webhook-info")
async def webhook_info():
    if not bot_instance:
        return JSONResponse(
            status_code=503,
            content={"status": "bot not ready"}
        )

    try:
        info = await bot_instance.application.bot.get_webhook_info()

        return {
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_date": info.last_error_date,
            "last_error_message": info.last_error_message,
        }

    except Exception as e:
        logger.error(f"❌ Ошибка получения webhook info: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


# -------------------------------------------------
# SIGNALS
# -------------------------------------------------
def signal_handler(signum, frame):
    logger.info(f"📶 Получен сигнал {signum}")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# -------------------------------------------------
# RUN
# -------------------------------------------------
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
# ... (начало файла без изменений) ...

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_instance

    logger.info("=" * 70)
    logger.info("🚀 ЗАПУСК БИЗНЕС-НАВИГАТОРА v7.0 (AUTO WEBHOOK)")
    logger.info("=" * 70)

    try:
        from config.settings import config

        if not config.telegram_token:
            logger.critical("❌ TELEGRAM_BOT_TOKEN не найден!")
            sys.exit(1)

        masked = (
            config.telegram_token[:4] + "***" + config.telegram_token[-4:]
            if len(config.telegram_token) > 8 else "***"
        )
        logger.info(f"✅ Токен бота: {masked}")
        logger.info(f"📝 Вопросов: {len(config.questions)}")
        logger.info(f"⚠️ Режим: {'DEMO' if config.demo_mode else 'FULL'}")

        from core.bot import BusinessNavigatorBot

        logger.info("🤖 Создаю экземпляр Telegram бота...")
        bot = BusinessNavigatorBot(config)
        bot_instance = bot

        # 🔧 ИСПРАВЛЕНИЕ 1: Не вызываем bot.start() здесь — webhook ставится в _post_init
        logger.info("▶️ Инициализирую Telegram Application...")
        await bot.application.initialize()
        await bot.application.start()
        bot._status.is_running = True  # 🔧 вручную ставим статус

        # 🔧 ИСПРАВЛЕНИЕ 2: Webhook ставится ТОЛЬКО в bot._post_init
        # Ждем немного, чтобы _post_init успел отработать
        await asyncio.sleep(1)

        logger.info("🎯 Бот полностью готов к работе")

        yield

    except Exception as e:
        logger.critical(f"❌ Критическая ошибка запуска: {e}", exc_info=True)
        raise

    finally:
        logger.info("⏹️ Останавливаю бота...")
        if bot_instance:
            try:
                # 🔧 ИСПРАВЛЕНИЕ 3: Не удаляем webhook при остановке (Render может перезапустить)
                await bot_instance.application.stop()
                await bot_instance.application.shutdown()
                logger.info("✅ Бот остановлен корректно")
            except Exception as e:
                logger.error(f"❌ Ошибка при остановке: {e}")

# ... (остальная часть app.py без изменений) ...

# 🔧 ИСПРАВЛЕНИЕ 4: В endpoint /webhook добавляем логирование
@app.post("/webhook")
async def telegram_webhook(request: Request):
    if not bot_instance or not bot_instance.is_running:
        logger.warning("⚠️ Webhook получен, но бот не готов")
        return JSONResponse(status_code=503, content={"status": "bot not ready"})

    try:
        update_dict = await request.json()
        # 🔧 Логируем тип обновления для отладки
        update_type = list(update_dict.keys())[0] if update_dict else "unknown"
        logger.debug(f"📬 Webhook: type={update_type}, chat_id={update_dict.get(update_type, {}).get('chat', {}).get('id')}")
        
        success = await bot_instance.process_update(update_dict)
        return {"status": "ok"} if success else JSONResponse(status_code=500, content={"status": "processing_failed"})

    except Exception as e:
        logger.error(f"❌ Ошибка webhook: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"status": "internal_error"})
