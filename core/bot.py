#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основной модуль бота Бизнес-Навигатор — Production Version (Webhooks)
Автоматическая установка вебхука при запуске
"""
import asyncio
import logging
import os
from typing import Optional
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

logger = logging.getLogger(__name__)


class BotStatus:
    """Статус работы бота"""
    def __init__(self):
        self.is_running: bool = False
        self.started_at: Optional[float] = None
        self.total_users: int = 0
        self.active_sessions: int = 0


class BusinessNavigatorBot:
    """Основной класс бота Бизнес-Навигатор"""

    def __init__(self, config):
        self.config = config
        self.application: Optional[Application] = None
        self._status = BotStatus()
        self._webhook_url: Optional[str] = None
        self._initialize_application()

    def _initialize_application(self) -> None:
        """Инициализация Telegram Application"""
        try:
            logger.info("🤖 Инициализация Telegram Application...")
            self.application = (
                ApplicationBuilder()
                .token(self.config.telegram_token)
                .post_init(self._post_init)
                .post_shutdown(self._post_shutdown)
                .build()
            )
            self._setup_handlers()
            logger.info("✅ Telegram Application инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации: {e}", exc_info=True)
            raise

    def _setup_handlers(self) -> None:
        """Настройка всех обработчиков"""
        if not self.application:
            return

        logger.info("⚙️ Настройка обработчиков...")

        # Команды
        from handlers.commands import (
            start_command,
            help_command,
            restart_command,
            status_command,
            questionnaire_command,
        )
        self.application.add_handler(CommandHandler("start", start_command))
        self.application.add_handler(CommandHandler("help", help_command))
        self.application.add_handler(CommandHandler("restart", restart_command))
        self.application.add_handler(CommandHandler("status", status_command))
        self.application.add_handler(CommandHandler("questionnaire", questionnaire_command))

        # Callback запросы
        from handlers.questionnaire import questionnaire_handler
        self.application.add_handler(CallbackQueryHandler(questionnaire_handler.handle_callback))

        # Текстовые сообщения
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, questionnaire_handler.handle_text_input)
        )

        # Обработчик ошибок
        self.application.add_error_handler(self._error_handler)
        logger.info("✅ Обработчики настроены")

    async def _post_init(self, application: Application) -> None:
        """Вызывается после инициализации бота — АВТОМАТИЧЕСКАЯ УСТАНОВКА ВЕБХУКА"""
        logger.info("🔄 Post-init выполнен")
        self._status.started_at = asyncio.get_event_loop().time()
        
        # Автоматическая установка вебхука (не в демо-режиме)
        if not self.config.demo_mode:
            await self._setup_webhook()
        else:
            logger.info("⚠️ DEMO MODE — вебхук не устанавливается")

    async def _setup_webhook(self) -> None:
        """Автоматическая настройка вебхука для Render"""
        try:
            # Получаем URL из переменной окружения Render
            webhook_base = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
            
            if not webhook_base:
                logger.warning("⚠️ RENDER_EXTERNAL_URL не задан, вебхук не установлен")
                return
            
            self._webhook_url = f"{webhook_base}/webhook"
            
            # Удаляем старый вебхук (на всякий случай)
            try:
                await self.application.bot.delete_webhook()
                logger.info("✅ Старый вебхук удалён")
            except Exception:
                pass
            
            # Устанавливаем новый вебхук
            await self.application.bot.set_webhook(
                url=self._webhook_url,
                allowed_updates=self.application.updater.ALLOWED_UPDATES,
                drop_pending_updates=True,
            )
            
            logger.info(f"✅ Вебхук автоматически установлен: {self._webhook_url}")
            
            # Проверяем установку
            webhook_info = await self.application.bot.get_webhook_info()
            if webhook_info.url == self._webhook_url:
                logger.info("✅ Вебхук подтверждён Telegram API")
            else:
                logger.warning(f"⚠️ Вебхук не совпадает: {webhook_info.url}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка установки вебхука: {e}", exc_info=True)
            raise

    async def _post_shutdown(self, application: Application) -> None:
        """Вызывается после завершения работы бота"""
        logger.info("🔄 Post-shutdown выполнен")
        self._status.is_running = False
        
        # Удаляем вебхук при остановке (опционально, можно закомментировать)
        if not self.config.demo_mode:
            try:
                await self.application.bot.delete_webhook()
                logger.info("✅ Вебхук удалён при остановке")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось удалить вебхук: {e}")

    async def _error_handler(self, update: object, context) -> None:
        """Обработчик ошибок"""
        logger.error(f"❌ Ошибка: {context.error}", exc_info=True)
        try:
            if update and hasattr(update, "effective_chat"):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⚠️ Произошла ошибка. Попробуйте позже.",
                )
        except Exception as e:
            logger.error(f"❌ Не удалось отправить сообщение об ошибке: {e}")

    async def start(self) -> None:
        """Запуск бота (для webhooks — только инициализация)"""
        if self._status.is_running:
            return

        try:
            logger.info("▶️ Запуск бота...")
            if not self.application:
                return

            # Инициализируем приложение
            await self.application.initialize()
            await self.application.start()
            
            self._status.is_running = True
            logger.info("✅ Бот запущен (webhook mode)")

        except Exception as e:
            logger.error(f"❌ Ошибка при запуске: {e}", exc_info=True)
            self._status.is_running = False
            raise

    async def stop(self) -> None:
        """Остановка бота"""
        if not self._status.is_running:
            return

        try:
            logger.info("⏹️ Остановка бота...")
            self._status.is_running = False

            if self.application:
                await self.application.stop()
                await self.application.shutdown()

            logger.info("✅ Бот остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке: {e}", exc_info=True)
            raise

    async def process_update(self, update_dict: dict) -> bool:
        """
        Обработка входящего обновления от вебхука.
        Вызывается из FastAPI endpoint /webhook
        """
        if not self.application or not self._status.is_running:
            return False
        
        try:
            from telegram import Update
            update = Update.de_json(update_dict, self.application.bot)
            await self.application.process_update(update)
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка обработки обновления: {e}", exc_info=True)
            return False

    @property
    def is_running(self) -> bool:
        """Статус работы бота"""
        return self._status.is_running

    @property
    def webhook_url(self) -> Optional[str]:
        """URL вебхука"""
        return self._webhook_url
