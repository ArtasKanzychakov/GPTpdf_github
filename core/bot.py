#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основной модуль бота Бизнес-Навигатор - DEMO VERSION
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
    filters
)

logger = logging.getLogger(__name__)

class BotStatus:
    """Статус работы бота"""
    def __init__(self):
        self.is_running = False
        self.started_at = None
        self.total_users = 0
        self.active_sessions = 0

class BusinessNavigatorBot:
    """Основной класс бота Бизнес-Навигатор"""
    
    def __init__(self, config):
        self.config = config
        self.application: Optional[Application] = None
        self._status = BotStatus()
        self._bot_task: Optional[asyncio.Task] = None
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
            logger.error(f"❌ Ошибка инициализации: {e}")
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
            questionnaire_command
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
        logger.error(f"❌ Ошибка: {context.error}")
        try:
            if update and hasattr(update, 'effective_chat'):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⚠️ Произошла ошибка. Попробуйте позже."
                )
        except Exception as e:
            logger.error(f"❌ Не удалось отправить сообщение об ошибке: {e}")
    
    async def start(self) -> None:
        """Запуск бота в фоновом режиме"""
        if self._status.is_running:
            return
        
        try:
            logger.info("▶️ Запуск бота...")
            if not self.application:
                return
            await self.application.initialize()
            self._bot_task = asyncio.create_task(self._run_polling())
            self._status.is_running = True
            logger.info("✅ Бот запущен")
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске: {e}")
            self._status.is_running = False
            raise
    
    async def _run_polling(self) -> None:
        """Запуск polling"""
        try:
            logger.info("📡 Запуск polling...")
            await self.application.start()
            await self.application.run_polling(
                poll_interval=0.5,
                timeout=10,
                drop_pending_updates=True,
                close_loop=False,
                stop_signals=[]
            )
        except asyncio.CancelledError:
            logger.info("⏹️ Polling отменен")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка в polling: {e}")
            raise
    
    async def stop(self) -> None:
        """Остановка бота"""
        if not self._status.is_running:
            return
        
        try:
            logger.info("⏹️ Остановка бота...")
            if self._bot_task and not self._bot_task.done():
                self._bot_task.cancel()
                try:
                    await self._bot_task
                except asyncio.CancelledError:
                    pass
            if self.application:
                await self.application.stop()
            self._status.is_running = False
            logger.info("✅ Бот остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке: {e}")
            raise
    
    @property
    def is_running(self) -> bool:
        """Статус работы бота"""
        return self._status.is_running
