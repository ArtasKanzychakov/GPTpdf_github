#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основной модуль бота Бизнес-Навигатор — Production Version
"""
import asyncio
import logging
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
        self._polling_task: Optional[asyncio.Task] = None
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
        """Вызывается после инициализации бота"""
        logger.info("🔄 Post-init выполнен")
        self._status.started_at = asyncio.get_event_loop().time()

    async def _post_shutdown(self, application: Application) -> None:
        """Вызывается после завершения работы бота"""
        logger.info("🔄 Post-shutdown выполнен")
        self._status.is_running = False

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
        """Запуск бота в фоновом режиме (внутри существующего event loop)"""
        if self._status.is_running:
            return

        try:
            logger.info("▶️ Запуск бота...")
            if not self.application:
                return

            # Инициализируем приложение (не запускаем polling ещё)
            await self.application.initialize()
            await self.application.start()

            # Запускаем polling как фоновую задачу в текущем event loop
            self._polling_task = asyncio.create_task(self._polling_loop())
            self._status.is_running = True
            logger.info("✅ Бот запущен")

        except Exception as e:
            logger.error(f"❌ Ошибка при запуске: {e}", exc_info=True)
            self._status.is_running = False
            raise

    async def _polling_loop(self) -> None:
        """
        Фоновый цикл получения обновлений.
        Работает внутри существующего event loop FastAPI.
        """
        try:
            logger.info("📡 Запуск polling loop...")
            while self._status.is_running:
                try:
                    # Получаем обновления вручную
                    await self.application.updater.fetch_updates()
                except Exception as e:
                    logger.error(f"⚠️ Ошибка при получении обновлений: {e}")
                # Небольшая пауза чтобы не нагружать API
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            logger.info("⏹️ Polling loop отменён")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в polling loop: {e}", exc_info=True)
            raise
        finally:
            # Корректная остановка
            if self.application:
                await self.application.stop()
                await self.application.shutdown()
            logger.info("✅ Polling loop завершён")

    async def stop(self) -> None:
        """Остановка бота"""
        if not self._status.is_running:
            return

        try:
            logger.info("⏹️ Остановка бота...")
            self._status.is_running = False

            # Отменяем polling task
            if self._polling_task and not self._polling_task.done():
                self._polling_task.cancel()
                try:
                    await self._polling_task
                except asyncio.CancelledError:
                    pass

            # Останавливаем application (если ещё не остановлен в _polling_loop)
            if self.application and self.application.running:
                await self.application.stop()
                await self.application.shutdown()

            logger.info("✅ Бот остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке: {e}", exc_info=True)
            raise

    @property
    def is_running(self) -> bool:
        """Статус работы бота"""
        return self._status.is_running
