"""
Основной класс бота
"""
import logging
import asyncio
from typing import Optional

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from config.settings import BotConfig
from services.data_manager import DataManager
from services.openai_service import OpenAIService
from core.question_engine import QuestionEngine
from handlers.commands import CommandHandlers
from handlers.callbacks import CallbackHandlers
from handlers.questionnaire import QuestionnaireHandler

logger = logging.getLogger(__name__)

class BusinessNavigatorBot:
    """Основной класс бота"""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.data_manager = DataManager(config.session_timeout_hours)
        self.openai_service = None
        self.question_engine = None
        self.command_handlers = None
        self.callback_handlers = None
        self.questionnaire_handler = None
        self.application = None
        
        # Инициализация сервисов
        self._initialize_services()
        
        # Создание приложения Telegram
        self._create_application()
        
        logger.info("🤖 Бизнес-Навигатор инициализирован")
    
    def _initialize_services(self):
        """Инициализировать сервисы"""
        # OpenAI сервис
        if self.config.openai_api_key:
            self.openai_service = OpenAIService(self.config)
        else:
            logger.warning("⚠️ OpenAI API ключ не установлен, AI функции отключены")
        
        # Движок вопросов
        self.question_engine = QuestionEngine(self.config)
        
        # Обработчики
        self.questionnaire_handler = QuestionnaireHandler(
            self.data_manager, 
            self.openai_service, 
            self.question_engine
        )
        
        self.command_handlers = CommandHandlers(
            self.data_manager,
            self.openai_service,
            self.question_engine
        )
        
        self.callback_handlers = CallbackHandlers(
            self.data_manager,
            self.openai_service,
            self.question_engine,
            self.questionnaire_handler
        )
    
    def _create_application(self):
        """Создать приложение Telegram"""
        self.application = Application.builder() \
            .token(self.config.telegram_token) \
            .build()
        
        # Регистрация обработчиков команд
        self.application.add_handler(CommandHandler("start", self.command_handlers.start_command))
        self.application.add_handler(CommandHandler("help", self.command_handlers.help_command))
        self.application.add_handler(CommandHandler("stats", self.command_handlers.stats_command))
        self.application.add_handler(CommandHandler("balance", self.command_handlers.balance_command))
        self.application.add_handler(CommandHandler("restart", self.command_handlers.restart_command))
        
        # Регистрация обработчика callback-запросов
        self.application.add_handler(CallbackQueryHandler(self.callback_handlers.handle_callback_query))
        
        # Регистрация обработчика текстовых сообщений
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self._handle_text_message
        ))
        
        # Обработчик ошибок
        self.application.add_error_handler(self._error_handler)
    
    async def _handle_text_message(self, update, context):
        """Обработчик текстовых сообщений"""
        # Увеличиваем счетчик сообщений
        self.data_manager.increment_messages()
        
        user = update.effective_user
        message_text = update.message.text
        
        # Получаем сессию
        session = self.data_manager.get_or_create_session(
            user_id=user.id,
            chat_id=update.message.chat_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        session.update_activity()
        
        # Если пользователь находится в состоянии анкеты
        if session.current_state in [BotState.DEMOGRAPHY, BotState.PERSONALITY, 
                                    BotState.SKILLS, BotState.VALUES, BotState.LIMITATIONS]:
            await self.questionnaire_handler.handle_text_message(update, session, message_text)
        else:
            await update.message.reply_text(
                "Пожалуйста, используйте кнопки для навигации или команду /start",
                parse_mode='Markdown'
            )
    
    async def _error_handler(self, update, context):
        """Обработчик ошибок"""
        logger.error(f"Ошибка: {context.error}", exc_info=context.error)
        
        try:
            if update and update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ *Произошла ошибка*\n\nПожалуйста, попробуйте начать заново /start",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Ошибка в обработчике ошибок: {e}")
    
    async def run(self):
        """Запустить бота"""
        try:
            # Запускаем поллинг
            await self.application.initialize()
            await self.application.start()
            
            logger.info("🚀 Бот запускается...")
            
            # Настройки поллинга для Python 3.9 и Render
            updater = self.application.updater
            if updater:
                await updater.start_polling(
                    drop_pending_updates=True,
                    allowed_updates=None,
                    poll_interval=1.0,
                    timeout=self.config.polling_timeout,
                    connect_timeout=self.config.polling_connect_timeout,
                    read_timeout=self.config.polling_read_timeout,
                    write_timeout=self.config.polling_write_timeout
                )
            
            logger.info("✅ Бот запущен и готов к работе!")
            
            # Бесконечный цикл
            while True:
                await asyncio.sleep(3600)  # Спим 1 час
        
        except KeyboardInterrupt:
            logger.info("⏹ Остановка бота по запросу пользователя")
        except Exception as e:
            logger.critical(f"❌ Критическая ошибка бота: {e}", exc_info=True)
            raise
        finally:
            await self._shutdown()
    
    async def _shutdown(self):
        """Завершение работы бота"""
        logger.info("🔄 Завершение работы бота...")
        
        try:
            # Сохраняем все сессии
            for session in self.data_manager.get_all_sessions():
                self.data_manager.save_session(session)
            
            # Останавливаем приложение
            if self.application:
                if self.application.updater and self.application.updater.running:
                    await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            
            logger.info("✅ Бот успешно остановлен")
            
        except Exception as e:
            logger.error(f"Ошибка при завершении работы: {e}")