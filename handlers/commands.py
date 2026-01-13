"""
Обработчики команд бота
"""
import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from models.session import UserSession
from models.enums import BotState
from services.data_manager import DataManager
from services.openai_service import OpenAIService
from core.question_engine import QuestionEngine
from utils.formatters import format_niche, format_analysis

logger = logging.getLogger(__name__)

class CommandHandlers:
    """Обработчики команд"""
    
    def __init__(self, data_manager: DataManager, openai_service: Optional[OpenAIService], question_engine: QuestionEngine):
        self.data_manager = data_manager
        self.openai_service = openai_service
        self.question_engine = question_engine
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        chat = update.effective_chat
        
        # Увеличиваем счетчик сообщений
        self.data_manager.increment_messages()
        
        # Получаем или создаем сессию
        session = self.data_manager.get_or_create_session(
            user_id=user.id,
            chat_id=chat.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        # Сбрасываем состояние
        session.current_state = BotState.START
        session.current_question = 0
        session.questions_answered = 0
        session.selected_niche_index = 0
        session.update_activity()
        
        # Статус AI
        ai_status = "✅ (AI-режим)" if self.openai_service and self.openai_service.is_available else "⚠️ (Базовый режим)"
        
        # Проверяем баланс OpenAI
        balance_info = ""
        if self.openai_service and self.openai_service.is_available:
            available, info = await self.openai_service.check_availability()
            if available:
                balance_info = f"\n\n🤖 *OpenAI статус:* {info}"
        
        welcome_text = f"""👋 *Добро пожаловать в Бизнес-Навигатор v7.0!* {ai_status}

🎯 *Что вас ждет:*
• 18 вопросов для глубокого анализа личности
• Психологический портрет от AI
• 8 персонализированных бизнес-ниш
• Детальные пошаговые планы

📊 *Статистика бота:*
{self.data_manager.stats.get_stats_str()}{balance_info}

👇 *Нажмите кнопку ниже, чтобы начать анализ:*"""
        
        keyboard = [[InlineKeyboardButton("🚀 Начать анкету", callback_data='start_questionnaire')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        self.data_manager.increment_messages()
        
        help_text = """🤖 *ПОМОЩЬ ПО БОТУ*

*Команды:*
/start - Начать новый анализ
/restart - Начать заново (очистить текущую сессию)
/stats - Показать статистику бота
/balance - Проверить баланс OpenAI (админ)
/help - Эта справка

*Процесс анализа:*
1. Заполните анкету (18 вопросов)
2. AI анализирует ваш профиль
3. Получите 8 персонализированных бизнес-ниш
4. Выберите нишу для детального плана

*Советы:*
• Будьте честны в ответах
• Не торопитесь, обдумайте каждый вопрос
• Отвечайте максимально подробно
• Используйте все возможности AI-анализа"""
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /stats"""
        self.data_manager.increment_messages()
        
        stats_text = f"""📊 *СТАТИСТИКА БОТА*

{self.data_manager.stats.get_stats_str()}

{self.data_manager.openai_usage.get_stats_str() if self.data_manager.openai_usage.total_requests > 0 else ''}

*Активные сессии:* {self.data_manager.get_session_count()}"""
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать баланс OpenAI"""
        self.data_manager.increment_messages()
        
        if not self.openai_service:
            await update.message.reply_text("❌ OpenAI не настроен")
            return
        
        user_id = update.effective_user.id
        
        # Проверяем права администратора (здесь можно добавить проверку)
        # if user_id not in ADMIN_IDS:
        #     await update.message.reply_text("❌ Эта команда только для администратора")
        #     return
        
        try:
            available, info = await self.openai_service.check_availability()
            
            if available:
                message = f"✅ *OpenAI доступен*\n\n{info}"
            else:
                message = f"❌ *Проблемы с OpenAI*\n\n{info}"
            
            # Добавляем статистику использования
            usage = self.data_manager.openai_usage
            if usage.total_requests > 0:
                message += f"\n\n{usage.get_stats_str()}"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Ошибка проверки баланса: {e}")
            await update.message.reply_text("❌ Ошибка проверки баланса OpenAI")
    
    async def restart_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /restart"""
        self.data_manager.increment_messages()
        
        user_id = update.effective_user.id
        
        # Сохраняем текущую сессию (если есть)
        session = self.data_manager.get_session(user_id)
        if session:
            self.data_manager.save_session(session)
        
        # Удаляем сессию
        self.data_manager.delete_session(user_id)
        
        await update.message.reply_text(
            "🔄 *Сессия сброшена!*\n\n"
            "Все данные вашей текущей сессии сохранены.\n"
            "Используйте /start для начала нового анализа.",
            parse_mode='Markdown'
        )