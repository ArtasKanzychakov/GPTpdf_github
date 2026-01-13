#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основной класс бота Бизнес-Навигатора
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

# ИМПОРТЫ: убираем циклический импорт config.settings
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
    restart_command,
    questionnaire_command,
    status_command,
    debug_command
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
    
    def __init__(self, config):  
        """
        Инициализация бота
        
        Args:
            config: Объект конфигурации BotConfig
        """
        self.config = config
        self.application: Optional[Application] = None
        self.data_manager = DataManager()
        self.question_engine = QuestionEngine(self)
        
        # Инициализируем сервисы (если есть ключи)
        self.openai_service = None
        if config.openai_api_key:
            try:
                self.openai_service = OpenAIService(config)
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации OpenAI: {e}")
        
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
        self.application.add_handler(CommandHandler("questionnaire", questionnaire_command))
        self.application.add_handler(CommandHandler("status", status_command))
        self.application.add_handler(CommandHandler("debug", debug_command))
        
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
        
        # Сохраняем ссылку на application для доступа из других мест
        self.application = application
        
        # Проверяем сессии при запуске
        active_sessions = self.data_manager.get_active_sessions_count()
        logger.info(f"📊 Активных сессий: {active_sessions}")
        
        # ИСПРАВЛЕНИЕ: Запускаем очистку сессий когда event loop уже работает
        try:
            if hasattr(self.data_manager, 'async_start_cleanup'):
                cleanup_task = await self.data_manager.async_start_cleanup()
                if cleanup_task:
                    logger.info("✅ Задача очистки сессий запущена")
                else:
                    logger.warning("⚠️ Не удалось запустить задачу очистки сессий")
            else:
                logger.warning("⚠️ DataManager не имеет метода async_start_cleanup")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска очистки сессий: {e}")
        
        # Запускаем проверку баланса OpenAI если есть сервис
        if self.openai_service:
            try:
                # Сразу проверяем доступность
                available, info = await self.openai_service.check_availability()
                if available:
                    logger.info(f"✅ OpenAI доступен: {info}")
                    
                    # Запускаем периодическую проверку
                    application.create_task(self.openai_service.periodic_balance_check())
                else:
                    logger.warning(f"⚠️ OpenAI проблемы: {info}")
                    logger.warning("Будет работать в базовом режиме")
                    self.openai_service = None
                    
            except Exception as e:
                logger.error(f"❌ Ошибка проверки OpenAI: {e}")
                self.openai_service = None
        else:
            logger.info("🤖 OpenAI отключен, используется базовый режим")
    
    async def _post_shutdown(self, application: Application):
        """Вызывается перед выключением бота"""
        logger.info("🛑 Бот выключается...")
        
        # Останавливаем задачу очистки сессий
        try:
            if hasattr(self.data_manager, 'stop_cleanup'):
                await self.data_manager.stop_cleanup()
                logger.info("✅ Задача очистки сессий остановлена")
        except Exception as e:
            logger.error(f"❌ Ошибка остановки очистки сессий: {e}")
        
        # Сохраняем статистику при выключении
        try:
            # Если есть метод save_statistics
            if hasattr(self.data_manager, 'save_statistics'):
                self.data_manager.save_statistics()
                logger.info("📈 Статистика сохранена")
            
            # Сохраняем все активные сессии
            sessions = self.data_manager.get_all_sessions()
            for session in sessions:
                self.data_manager.save_session(session)
            logger.info(f"💾 Сохранено {len(sessions)} сессий")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных при выключении: {e}")
    
    def get_user_session(self, user_id: int) -> Optional[UserSession]:
        """Получить сессию пользователя"""
        return self.data_manager.get_session(user_id)
    
    def save_user_session(self, session: UserSession):
        """Сохранить сессию пользователя"""
        self.data_manager.save_session(session)
    
    async def send_message(self, chat_id: int, text: str, **kwargs):
        """Отправить сообщение пользователю"""
        if self.application and self.application.bot:
            try:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    **kwargs
                )
                # Увеличиваем счетчик сообщений
                self.data_manager.increment_messages()
            except Exception as e:
                logger.error(f"❌ Ошибка отправки сообщения: {e}")
        else:
            logger.error("❌ Бот не инициализирован для отправки сообщения")
    
    async def send_question(self, user_id: int, question_data: Dict[str, Any]):
        """Отправить вопрос пользователю"""
        session = self.get_user_session(user_id)
        if session:
            await self.question_engine.send_question(user_id, session, question_data)
    
    async def complete_questionnaire(self, user_id: int):
        """Завершить анкетирование и выдать результат"""
        session = self.get_user_session(user_id)
        if not session:
            logger.error(f"❌ Сессия не найдена для пользователя {user_id}")
            return
        
        try:
            logger.info(f"📋 Завершение анкеты для пользователя {user_id}")
            
            # Помечаем профиль как завершенный
            self.data_manager.mark_profile_completed(user_id)
            
            # Здесь будет логика анализа ответов и генерации рекомендаций
            if self.openai_service and session.answers:
                # Используем AI для анализа
                logger.info(f"🤖 Генерация рекомендаций через OpenAI для пользователя {user_id}")
                try:
                    recommendations = await self.openai_service.generate_recommendations(session)
                    session.recommendations = recommendations
                    
                    # Добавляем сгенерированные ниши в статистику
                    if hasattr(recommendations, 'niches') and recommendations.niches:
                        niches_count = len(recommendations.niches)
                        self.data_manager.add_generated_niches(niches_count)
                    
                    # Добавляем сгенерированный план
                    self.data_manager.add_generated_plan()
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка генерации рекомендаций OpenAI: {e}")
                    session.recommendations = "Базовые рекомендации (ошибка AI анализа)"
            else:
                # Базовые рекомендации (без AI)
                logger.info(f"📊 Генерация базовых рекомендаций для пользователя {user_id}")
                session.recommendations = (
                    "🎯 *Базовые рекомендации (режим без AI)*\n\n"
                    "На основе ваших ответов рекомендуем:\n\n"
                    "1. **Начните с малого** - выберите одну нишу и сфокусируйтесь на ней\n"
                    "2. **Используйте свои навыки** - развивайте то, что уже умеете\n"
                    "3. **Учитесь на практике** - не бойтесь делать ошибки\n"
                    "4. **Ищите ментора** - опытный советник ускорит ваш рост\n\n"
                    "Для персонализированных рекомендаций включите OpenAI в настройках."
                )
            
            # Обновляем состояние
            session.current_state = BotState.COMPLETED
            session.completed_at = datetime.now()
            self.save_user_session(session)
            
            # Отправляем результаты
            await self.send_message(
                chat_id=user_id,
                text="✅ *Анкета завершена!*\n\n"
                    "Вот ваши персонализированные рекомендации:\n\n"
                    f"{session.recommendations[:1500]}..."  # Ограничиваем длину
            )
            
            # Предлагаем следующие шаги
            keyboard = [
                [{"text": "📋 Подробный план действий", "callback_data": "detailed_plan"}],
                [{"text": "💼 Выбрать нишу", "callback_data": "select_niche"}],
                [{"text": "🔄 Пройти заново", "callback_data": "restart_full"}]
            ]
            
            await self.send_message(
                chat_id=user_id,
                text="🎯 *Что дальше?*\n"
                    "Вы можете:\n"
                    "• Получить детальный план действий\n"
                    "• Выбрать конкретную бизнес-нишу\n"
                    "• Пройти анкету заново",
                reply_markup={"inline_keyboard": keyboard}
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка завершения анкеты: {e}", exc_info=True)
            await self.send_message(
                chat_id=user_id,
                text="❌ Произошла ошибка при обработке ваших ответов. Попробуйте позже или обратитесь к администратору."
            )
    
    async def send_error_message(self, user_id: int, error_message: str):
        """Отправить сообщение об ошибке"""
        await self.send_message(
            chat_id=user_id,
            text=f"❌ *Ошибка:* {error_message}\n\n"
                 "Попробуйте позже или обратитесь к администратору."
        )
    
    async def broadcast_message(self, message: str, user_ids: List[int] = None):
        """Отправить сообщение нескольким пользователям"""
        if not user_ids:
            # Если не указаны ID, берем всех активных пользователей
            sessions = self.data_manager.get_all_sessions()
            user_ids = [session.user_id for session in sessions]
        
        success_count = 0
        for user_id in user_ids:
            try:
                await self.send_message(chat_id=user_id, text=message)
                success_count += 1
            except Exception as e:
                logger.error(f"❌ Ошибка отправки broadcast пользователю {user_id}: {e}")
        
        logger.info(f"📢 Broadcast отправлен: {success_count}/{len(user_ids)} успешно")

# Глобальная переменная для доступа к экземпляру бота (опционально)
bot_instance = None

async def get_bot_instance(config=None):
    """Получить или создать экземпляр бота"""
    global bot_instance
    
    if bot_instance is None and config is not None:
        bot_instance = BusinessNavigatorBot(config)
    
    return bot_instance