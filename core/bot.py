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
    ConversationHandler
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
            if data_manager:
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
        """Запуск бота в фоновом режиме (FastAPI-совместимый)"""
        if self._status.is_running:
            logger.warning("⚠️ Бот уже запущен")
            return
            
        try:
            logger.info("▶️ Запуск бота в фоновом режиме...")
            
            if not self.application:
                logger.error("❌ Application не инициализирован")
                return
            
            # Инициализируем Application
            await self.application.initialize()
            await self.application.start()
            
            # 🔄 ВАЖНО: Используем start_polling() вместо run_polling() для FastAPI
            # start_polling() не блокирует event loop
            self.application.updater.start_polling(
                poll_interval=0.5,
                timeout=10,
                drop_pending_updates=True
            )
            
            # Запускаем фоновую задачу для мониторинга
            self._polling_task = asyncio.create_task(self._monitor_polling())
            
            self._status.is_running = True
            self._status.total_users = len(data_manager.sessions)
            self._status.active_sessions = sum(
                1 for s in data_manager.sessions.values() if s.is_active
            )
            
            logger.info("✅ Бот запущен в фоновом режиме (FastAPI-совместимый)")
            logger.info(f"📊 Пользователей в базе: {self._status.total_users}")
            logger.info(f"📊 Активных сессий: {self._status.active_sessions}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске бота: {e}", exc_info=True)
            self._status.is_running = False
            raise

    async def _monitor_polling(self) -> None:
        """Фоновая задача для мониторинга polling (не блокирует loop)"""
        try:
            logger.info("📡 Polling запущен в фоновом режиме...")
            # Просто держим задачу активной — polling работает через updater
            while self._status.is_running:
                await asyncio.sleep(60)  # Проверка каждую минуту
                logger.debug("🔄 Polling активен...")
        except asyncio.CancelledError:
            logger.info("⏹️ Мониторинг polling отменен")
        except Exception as e:
            logger.error(f"❌ Ошибка в мониторинге polling: {e}")

    async def stop(self) -> None:
        """Остановка бота (FastAPI-совместимая)"""
        if not self._status.is_running:
            logger.warning("⚠️ Бот уже остановлен")
            return
            
        try:
            logger.info("⏹️ Остановка бота...")
            self._status.is_running = False
            
            # Отменяем задачу мониторинга
            if self._polling_task and not self._polling_task.done():
                self._polling_task.cancel()
                try:
                    await self._polling_task
                except asyncio.CancelledError:
                    pass
            
            # 🔄 ВАЖНО: Останавливаем updater, а не run_polling
            if self.application and self.application.updater:
                await self.application.updater.stop()
                logger.info("✅ Updater остановлен")
            
            if self.application:
                await self.application.stop()
                await self.application.shutdown()
                logger.info("✅ Application остановлен и завершён")
            
            logger.info("✅ Бот полностью остановлен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке бота: {e}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """Получение текущего статуса бота"""
        return {
            "is_running": self._status.is_running,
            "started_at": self._status.started_at,
            "total_users": self._status.total_users,
            "active_sessions": self._status.active_sessions,
            "config": {
                "bot_language": self.config.bot_language,
                "questions_loaded": len(self.config.questions)
            }
        }

    @property
    def is_running(self) -> bool:
        """Статус работы бота (только чтение)"""
        return self._status.is_running

    @property
    def polling_task(self):
        """Задача мониторинга (только чтение)"""
        return self._polling_task
