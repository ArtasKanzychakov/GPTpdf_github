#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основной класс бота Бизнес-Навигатора
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

# ИЗМЕНЕНИЕ 1: Убрали импорт BotConfig отсюда
# Вместо этого передаем config как параметр в __init__

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from core.question_engine import QuestionEngine
from services.data_manager import DataManager
from services.openai_service import OpenAIService
from services.payment_service import PaymentService
from handlers.commands import (
    start_command,
    help_command,
    stats_command,
    balance_command,
    restart_command
)
from handlers.callbacks import (
    handle_callback_query,
    handle_multiselect,
    handle_slider
)
from handlers.questionnaire import handle_text_answer
from models.enums import BotState
from models.session import UserSession

logger = logging.getLogger(__name__)

class BusinessNavigatorBot:
    """Основной класс бота Бизнес-Навигатора"""
    
    def __init__(self, config):  # ИЗМЕНЕНИЕ 2: config передается как параметр
        """
        Инициализация бота
        
        Args:
            config: Объект конфигурации BotConfig
        """
        self.config = config
        self.application: Optional[Application] = None
        self.data_manager = DataManager()
        self.question_engine = QuestionEngine(self)
        self.openai_service = OpenAIService(config) if config.openai_api_key else None
        self.payment_service = PaymentService()
        
        logger.info(f"🤖 Бот инициализирован. Режим AI: {'Включен' if self.openai_service else 'Выключен'}")
    
    async def run(self):
        """Запуск бота в режиме polling"""
        try:
            # Создаем Application
            self.application = Application.builder() \
                .token(self.config.telegram_token) \
                .post_init(self._post_init) \
                .post_shutdown(self._post_shutdown) \
                .build()
            
            # Регистрируем обработчики
            self._setup_handlers()
            
            logger.info("🔄 Запуск бота в режиме polling...")
            await self.application.run_polling(
                allowed_updates=['message', 'callback_query'],
                drop_pending_updates=True,
                close_loop=False
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске бота: {e}", exc_info=True)
            raise
    
    def _setup_handlers(self):
        """Настройка обработчиков команд и сообщений"""
        # Команды
        self.application.add_handler(CommandHandler("start", start_command))
        self.application.add_handler(CommandHandler("help", help_command))
        self.application.add_handler(CommandHandler("stats", stats_command))
        self.application.add_handler(CommandHandler("balance", balance_command))
        self.application.add_handler(CommandHandler("restart", restart_command))
        
        # Callback-запросы (кнопки)
        self.application.add_handler(CallbackQueryHandler(
            handle_callback_query,
            pattern="^(?!multiselect_|slider_).*"
        ))
        
        # Мультиселект
        self.application.add_handler(CallbackQueryHandler(
            handle_multiselect,
            pattern="^multiselect_"
        ))
        
        # Слайдеры
        self.application.add_handler(CallbackQueryHandler(
            handle_slider,
            pattern="^slider_"
        ))
        
        # Текстовые ответы (только когда пользователь в состоянии анкеты)
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text_answer
        ))
        
        logger.info("✅ Обработчики зарегистрированы")
    
    async def _post_init(self, application: Application):
        """Вызывается после инициализации бота"""
        logger.info("✅ Бот инициализирован и готов к работе")
        
        # Проверяем сессии при запуске
        active_sessions = self.data_manager.get_active_sessions_count()
        logger.info(f"📊 Активных сессий: {active_sessions}")
        
        # Запускаем фоновые задачи
        application.create_task(self.data_manager.cleanup_old_sessions())
        
        if self.openai_service:
            application.create_task(self.openai_service.periodic_balance_check())
    
    async def _post_shutdown(self, application: Application):
        """Вызывается перед выключением бота"""
        logger.info("🛑 Бот выключается...")
        
        # Сохраняем статистику при выключении
        self.data_manager.save_statistics()
        logger.info("📈 Статистика сохранена")
    
    def get_user_session(self, user_id: int) -> Optional[UserSession]:
        """Получить сессию пользователя"""
        return self.data_manager.get_session(user_id)
    
    def save_user_session(self, session: UserSession):
        """Сохранить сессию пользователя"""
        self.data_manager.save_session(session)
    
    async def send_message(self, chat_id: int, text: str, **kwargs):
        """Отправить сообщение пользователю"""
        if self.application:
            try:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    **kwargs
                )
            except Exception as e:
                logger.error(f"❌ Ошибка отправки сообщения: {e}")
    
    async def send_question(self, user_id: int, question_data: Dict[str, Any]):
        """Отправить вопрос пользователю"""
        session = self.get_user_session(user_id)
        if session:
            await self.question_engine.send_question(user_id, session, question_data)
    
    async def complete_questionnaire(self, user_id: int):
        """Завершить анкетирование и выдать результат"""
        session = self.get_user_session(user_id)
        if not session:
            return
        
        try:
            logger.info(f"📋 Завершение анкеты для пользователя {user_id}")
            
            # Здесь будет логика анализа ответов и генерации рекомендаций
            if self.openai_service:
                # Используем AI для анализа
                recommendations = await self.openai_service.generate_recommendations(session)
                session.recommendations = recommendations
            else:
                # Базовые рекомендации (без AI)
                session.recommendations = "Базовые рекомендации (режим без AI)"
            
            # Обновляем состояние
            session.current_state = BotState.IDLE
            session.completed_at = datetime.now()
            self.save_user_session(session)
            
            # Отправляем результаты
            await self.send_message(
                chat_id=user_id,
                text="✅ Анкета завершена! Вот ваши персонализированные рекомендации...\n\n"
                    f"{session.recommendations[:1000]}..."  # Ограничиваем длину
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка завершения анкеты: {e}", exc_info=True)
            await self.send_message(
                chat_id=user_id,
                text="❌ Произошла ошибка при обработке ваших ответов. Попробуйте позже."
            )