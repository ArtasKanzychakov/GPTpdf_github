#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основной модуль бота Бизнес-Навигатор
Архитектура: FastAPI + python-telegram-bot v20+ (совместимая с uvloop)
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from config.settings import BotConfig
from handlers.commands import (
    start_command,
    help_command,
    restart_command,
    status_command
)
from handlers.questionnaire import (
    start_questionnaire,
    handle_callback_query,
    handle_question_answer,
    cancel_questionnaire
)
from services.data_manager import data_manager

logger = logging.getLogger(__name__)


@dataclass
class BotStatus:
    """Статус работы бота"""
    is_running: bool = False
    started_at: Optional[float] = None
    total_users: int = 0
    active_sessions: int = 0


class BusinessNavigatorBot:
    """Основной класс бота Бизнес-Навигатор"""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.application: Optional[Application] = None
        self._status = BotStatus()
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
            logger.error(f"❌ Ошибка инициализации Application: {e}")
            raise

    def _setup_handlers(self) -> None:
        """Настройка всех обработчиков команд и сообщений"""
        if not self.application:
            logger.error("❌ Application не инициализирован")
            return
            
        logger.info("⚙️ Настройка обработчиков...")
        
        # === Обработчики команд ===
        self.application.add_handler(CommandHandler("start", start_command))
        self.application.add_handler(CommandHandler("help", help_command))
        self.application.add_handler(CommandHandler("restart", restart_command))
        self.application.add_handler(CommandHandler("status", status_command))
        self.application.add_handler(CommandHandler("questionnaire", start_questionnaire))
        self.application.add_handler(CommandHandler("cancel", cancel_questionnaire))
        
        # === Обработчики callback-запросов (кнопки) ===
        self.application.add_handler(
            CallbackQueryHandler(handle_callback_query)
        )
        
        # === Обработчики текстовых сообщений ===
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question_answer)
        )
        
        # === Обработчик ошибок ===
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
        try:
            await data_manager.cleanup_old_sessions(days=1)
            logger.info("🧹 Очистка старых сессий выполнена")
        except Exception as e:
            logger.error(f"❌ Ошибка при очистке сессий: {e}")

    async def _error_handler(self, update: object, context) -> None:
        """Обработчик ошибок"""
        logger.error(f"❌ Ошибка при обработке обновления: {context.error}")
        try:
            if update and hasattr(update, 'effective_chat'):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⚠️ Произошла техническая ошибка. Пожалуйста, попробуйте позже или используйте команду /start"
                )
        except Exception as e:
            logger.error(f"❌ Не удалось отправить сообщение об ошибке: {e}")

    async def start(self) -> None:
        """Запуск бота (FastAPI-совместимый — НЕ блокирует event loop)"""
        if self._status.is_running:
            logger.warning("⚠️ Бот уже запущен")
            return
            
        try:
            logger.info("▶️ Запуск бота в фоновом режиме...")
            
            if not self.application or not self.application.updater:
                logger.error("❌ Application или Updater не инициализирован")
                return
            
            # ✅ КЛЮЧЕВОЕ: Используем updater.start_polling() — НЕ блокирует loop
            self.application.updater.start_polling(
                poll_interval=0.5,
                timeout=10,
                drop_pending_updates=True
            )
            
            self._status.is_running = True
            self._status.total_users = len(data_manager.sessions)
            self._status.active_sessions = sum(
                1 for s in data_manager.sessions.values() if getattr(s, 'is_active', True)
            )
            
            logger.info("✅ Бот запущен (FastAPI-совместимый)")
            logger.info(f"📊 Пользователей: {self._status.total_users}")
            logger.info(f"📊 Активных сессий: {self._status.active_sessions}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске бота: {e}", exc_info=True)
            self._status.is_running = False
            raise

    async def stop(self) -> None:
        """Остановка бота (FastAPI-совместимая)"""
        if not self._status.is_running:
            logger.warning("⚠️ Бот уже остановлен")
            return
            
        try:
            logger.info("⏹️ Остановка бота...")
            self._status.is_running = False
            
            # ✅ Останавливаем только updater (не application — им управляет FastAPI)
            if self.application and self.application.updater:
                await self.application.updater.stop()
                await self.application.updater.shutdown()
                logger.info("✅ Updater остановлен и завершён")
            
            logger.info("✅ Бот полностью остановлен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке бота: {e}")
            raise

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self._status.is_running,
            "started_at": self._status.started_at,
            "total_users": self._status.total_users,
            "active_sessions": self._status.active_sessions,
        }

    @property
    def is_running(self) -> bool:
        return self._status.is_running
