#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основной класс бота Бизнес-Навигатор v7.1
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
    status_command,
    questionnaire_command
)
from handlers.questionnaire import (
    start_questionnaire,
    handle_question_answer,
    handle_callback_query
)
from services.data_manager import data_manager
from core.question_engine_v2 import QuestionEngineV2
from openai import AsyncOpenAI

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
    
    def __init__(self, config: BotConfig, data_manager_instance, openai_service=None):
        self.config = config
        self.data_manager = data_manager_instance
        self.openai_service = openai_service
        self.application: Optional[Application] = None
        self._status = BotStatus()
        self._bot_task: Optional[asyncio.Task] = None
        
        # Инициализация компонентов
        self._initialize_components()
        
        # Инициализация приложения Telegram
        self._initialize_application()
    
    def _initialize_components(self) -> None:
        """Инициализация всех компонентов бота"""
        logger.info("🔄 Инициализация компонентов бота...")
        
        try:
            # Инициализация движка вопросов
            from core.question_engine_v2 import QuestionEngineV2
            self.question_engine = QuestionEngineV2()
            logger.info("✅ Движок вопросов инициализирован")
            
            # Инициализация сервиса генерации ниш (если есть OpenAI)
            if self.openai_service:
                from services.niche_generation_detailed import NicheGenerationService
                self.niche_service = NicheGenerationService(
                    client=self.openai_service.client,
                    model=self.config.openai_model
                )
                logger.info("✅ Сервис генерации ниш инициализирован")
            else:
                self.niche_service = None
                logger.info("⚠️ Сервис генерации ниш отключен (нет OpenAI)")
                
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации компонентов: {e}")
            raise
    
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
            
            # Сохраняем компоненты в bot_data для доступа из handlers
            self.application.bot_data.update({
                'config': self.config,
                'data_manager': self.data_manager,
                'openai_service': self.openai_service,
                'niche_service': self.niche_service,
                'question_engine': self.question_engine,
                'bot_instance': self
            })
            
            self._setup_handlers()
            logger.info("✅ Telegram Application инициализирован")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации: {e}")
            raise
    
    def _setup_handlers(self) -> None:
        """Настройка всех обработчиков"""
        if not self.application:
            logger.error("❌ Application не инициализирован")
            return
        
        logger.info("⚙️ Настройка обработчиков...")
        
        # Команды
        self.application.add_handler(CommandHandler("start", start_command))
        self.application.add_handler(CommandHandler("help", help_command))
        self.application.add_handler(CommandHandler("restart", restart_command))
        self.application.add_handler(CommandHandler("status", status_command))
        self.application.add_handler(CommandHandler("questionnaire", questionnaire_command))
        
        # Callback запросы (кнопки)
        self.application.add_handler(CallbackQueryHandler(handle_callback_query))
        
        # Текстовые сообщения
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question_answer)
        )
        
        # Обработчик ошибок
        self.application.add_error_handler(self._error_handler)
        
        logger.info("✅ Обработчики настроены")
    
    async def _post_init(self, application: Application) -> None:
        """Post-init callback"""
        logger.info("🔄 Post-init выполнен")
        self._status.started_at = datetime.now().timestamp()
        
        # Инициализация данных в боте
        application.bot_data['is_initialized'] = True
    
    async def _post_shutdown(self, application: Application) -> None:
        """Post-shutdown callback"""
        logger.info("🔄 Post-shutdown выполнен")
        self._status.is_running = False
        
        try:
            if self.data_manager:
                # Можно добавить очистку или сохранение данных
                logger.info("🧹 Завершение работы менеджера данных...")
        except Exception as e:
            logger.error(f"❌ Ошибка при завершении работы: {e}")
    
    async def _error_handler(self, update: object, context) -> None:
        """Обработчик ошибок"""
        logger.error(f"❌ Ошибка: {context.error}", exc_info=True)
        
        try:
            if update and hasattr(update, 'effective_chat'):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⚠️ Произошла техническая ошибка. Попробуйте /start"
                )
        except Exception as e:
            logger.error(f"❌ Не удалось отправить сообщение об ошибке: {e}")
    
    async def start(self) -> None:
        """Запуск бота"""
        if self._status.is_running:
            logger.warning("⚠️ Бот уже запущен")
            return
        
        try:
            logger.info("▶️ Запуск бота...")
            
            if not self.application:
                logger.error("❌ Application не инициализирован")
                return
            
            await self.application.initialize()
            
            self._bot_task = asyncio.create_task(self._run_polling())
            
            self._status.is_running = True
            self._status.total_users = len(self.data_manager.sessions)
            self._status.active_sessions = len(self.data_manager.sessions)
            
            logger.info("✅ Бот запущен")
            logger.info(f"📊 Пользователей: {self._status.total_users}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске: {e}", exc_info=True)
            self._status.is_running = False
            raise
    
    async def _run_polling(self) -> None:
        """Запуск polling"""
        try:
            logger.info("📡 Запуск polling...")
            
            # Удаляем webhook перед polling
            logger.info("🔄 Удаляю webhook...")
            try:
                await self.application.bot.delete_webhook(drop_pending_updates=True)
                logger.info("✅ Webhook удален")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось удалить webhook: {e}")
            
            await self.application.start()
            
            await self.application.updater.start_polling(
                poll_interval=0.5,
                timeout=10,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"]
            )
            
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
            
            self._status.is_running = False
            
            if self._bot_task and not self._bot_task.done():
                self._bot_task.cancel()
                try:
                    await self._bot_task
                except asyncio.CancelledError:
                    logger.info("✅ Задача polling отменена")
            
            if self.application:
                if self.application.updater and self.application.updater.running:
                    await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
                logger.info("✅ Application остановлен")
            
            logger.info("✅ Бот остановлен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке: {e}")
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса бота"""
        return {
            "is_running": self._status.is_running,
            "started_at": self._status.started_at,
            "total_users": self._status.total_users,
            "active_sessions": self._status.active_sessions,
            "config": {
                "bot_name": "Business Navigator",
                "bot_language": self.config.bot_language,
                "questions_loaded": len(self.config.questions),
                "openai_available": self.openai_service is not None
            }
        }
    
    @property
    def is_running(self) -> bool:
        """Статус работы бота"""
        return self._status.is_running
    
    @property
    def bot_task(self):
        """Задача бота"""
        return self._bot_task