#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основной модуль бота Бизнес-Навигатор
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
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
    handle_question_answer,
    handle_callback_query
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
        self._bot_task: Optional[asyncio.Task] = None
        
        # Инициализация
        self._initialize_application()
    
    def _initialize_application(self) -> None:
        """Инициализация Telegram Application"""
        try:
            logger.info("🤖 Инициализация Telegram Application...")
            
            # Создаем Application с использованием токена
            self.application = (
                ApplicationBuilder()
                .token(self.config.telegram_token)
                .post_init(self._post_init)
                .post_shutdown(self._post_shutdown)
                .build()
            )
            
            # Настройка обработчиков
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
        
        # Обработчики команд
        self.application.add_handler(CommandHandler("start", start_command))
        self.application.add_handler(CommandHandler("help", help_command))
        self.application.add_handler(CommandHandler("restart", restart_command))
        self.application.add_handler(CommandHandler("status", status_command))
        
        # Обработчики анкеты
        self.application.add_handler(
            CommandHandler("questionnaire", start_questionnaire)
        )
        
        # Обработчики callback запросов (кнопки)
        self.application.add_handler(
            CallbackQueryHandler(handle_callback_query)
        )
        
        # Обработчики текстовых сообщений
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question_answer)
        )
        
        # Обработчик ошибок
        self.application.add_error_handler(self._error_handler)
        
        logger.info("✅ Обработчики настроены")
    
    async def _post_init(self, application: Application) -> None:
        """Вызывается после инициализации бота"""
        logger.info("🔄 Post-init выполнен")
        self._status.started_at = datetime.now().timestamp()
    
    async def _post_shutdown(self, application: Application) -> None:
        """Вызывается после завершения работы бота"""
        logger.info("🔄 Post-shutdown выполнен")
        self._status.is_running = False
        
        # Сохраняем данные при завершении
        try:
            if data_manager:
                data_manager.cleanup_old_sessions(days=1)
                logger.info("🧹 Очистка старых сессий выполнена")
        except Exception as e:
            logger.error(f"❌ Ошибка при очистке сессий: {e}")
    
    async def _error_handler(self, update: object, context) -> None:
        """Обработчик ошибок"""
        logger.error(f"❌ Ошибка при обработке обновления: {context.error}")
        
        try:
            # Пытаемся отправить сообщение пользователю
            if update and hasattr(update, 'effective_chat'):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⚠️ Произошла техническая ошибка. Пожалуйста, попробуйте позже или используйте команду /start"
                )
        except Exception as e:
            logger.error(f"❌ Не удалось отправить сообщение об ошибке: {e}")
    
    async def start(self) -> None:
        """Запуск бота в фоновом режиме"""
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
            
            # Запускаем polling в фоновой задаче
            self._bot_task = asyncio.create_task(
                self._run_polling()
            )
            
            self._status.is_running = True
            self._status.total_users = len(data_manager.sessions)
            self._status.active_sessions = len(data_manager.sessions)
            
            logger.info("✅ Бот запущен в фоновом режиме")
            logger.info(f"📊 Пользователей в базе: {self._status.total_users}")
            logger.info(f"📊 Активных сессий: {self._status.active_sessions}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске бота: {e}", exc_info=True)
            self._status.is_running = False
            raise
    
    async def _run_polling(self) -> None:
        """Запуск polling в отдельной задаче"""
        try:
            logger.info("📡 Запуск polling...")
            
            await self.application.start()
            
            # Запускаем polling с параметрами
            await self.application.updater.start_polling(
                poll_interval=0.5,
                timeout=10,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"]
            )
            
            # Бесконечный цикл для поддержания работы
            while self._status.is_running:
                await asyncio.sleep(1)
            
        except asyncio.CancelledError:
            logger.info("⏹️ Polling отменен")
            raise
            
        except Exception as e:
            logger.error(f"❌ Ошибка в polling: {e}", exc_info=True)
            raise
    
    async def stop(self) -> None:
        """Остановка бота"""
        if not self._status.is_running:
            logger.warning("⚠️ Бот уже остановлен")
            return
        
        try:
            logger.info("⏹️ Остановка бота...")
            
            # Помечаем как неактивный
            self._status.is_running = False
            
            # Отменяем задачу polling
            if self._bot_task and not self._bot_task.done():
                self._bot_task.cancel()
                try:
                    await self._bot_task
                except asyncio.CancelledError:
                    logger.info("✅ Задача polling отменена")
            
            # Останавливаем Application
            if self.application:
                if self.application.updater and self.application.updater.running:
                    await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
                logger.info("✅ Application остановлен")
            
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
                "bot_name": "Business Navigator",
                "bot_language": self.config.bot_language,
                "questions_loaded": len(self.config.questions)
            }
        }
    
    @property
    def is_running(self) -> bool:
        """Статус работы бота (только чтение)"""
        return self._status.is_running
    
    @property
    def bot_task(self):
        """Задача бота (только чтение)"""
        return self._bot_task
