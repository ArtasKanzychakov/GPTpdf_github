"""
Обработчики callback-запросов (кнопок)
"""
import logging
import asyncio
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from models.enums import BotState
from models.session import UserSession
from services.data_manager import DataManager
from services.openai_service import OpenAIService
from core.question_engine import QuestionEngine
from handlers.questionnaire import QuestionnaireHandler
from utils.formatters import (
    get_random_praise, format_niche, format_analysis,
    create_niche_navigation, split_message
)

logger = logging.getLogger(__name__)

class CallbackHandlers:
    """Обработчики callback-запросов"""
    
    def __init__(self, data_manager: DataManager, openai_service: Optional[OpenAIService], 
                 question_engine: QuestionEngine, questionnaire_handler: QuestionnaireHandler):
        self.data_manager = data_manager
        self.openai_service = openai_service
        self.question_engine = question_engine
        self.questionnaire_handler = questionnaire_handler
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главный обработчик callback-запросов"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        callback_data = query.data
        
        # Увеличиваем счетчик сообщений
        self.data_manager.increment_messages()
        
        # Получаем сессию
        session = self.data_manager.get_or_create_session(
            user_id=user_id,
            chat_id=query.message.chat_id,
            username=query.from_user.username,
            first_name=query.from_user.first_name,
            last_name=query.from_user.last_name
        )
        
        session.update_activity()
        
        # Обработка в зависимости от состояния
        if session.current_state == BotState.START:
            await self._handle_start_state(query, session, callback_data)
        elif session.current_state in [BotState.DEMOGRAPHY, BotState.PERSONALITY, 
                                      BotState.SKILLS, BotState.VALUES, BotState.LIMITATIONS]:
            await self._handle_questionnaire_state(query, session, callback_data)
        elif session.current_state == BotState.ANALYZING:
            await query.edit_message_text("🤖 *Идет анализ...*\n\nПожалуйста, подождите.")
        elif session.current_state == BotState.NICHE_SELECTION:
            await self._handle_niche_selection_state(query, session, callback_data, context)
        elif session.current_state == BotState.DETAILED_PLAN:
            await self._handle_detailed_plan_state(query, session, callback_data, context)
        elif session.current_state == BotState.PSYCH_ANALYSIS:
            await self._handle_psych_analysis_state(query, session, callback_data, context)
    
    async def _handle_start_state(self, query, session, callback_data):
        """Обработка состояния START"""
        if callback_data == 'start_questionnaire':
            await self.questionnaire_handler.start_questionnaire(query, session)
    
    async def _handle_questionnaire_state(self, query, session, callback_data):
        """Обработка состояний вопросника"""
        # Передаем обработку в questionnaire_handler
        await self.questionnaire_handler.handle_callback(query, session, callback_data)
    
    async def _handle_niche_selection_state(self, query, session, callback_data, context):
        """Обработка состояния NICHE_SELECTION"""
        if callback_data == 'niche_prev':
            if session.selected_niche_index > 0:
                session.selected_niche_index -= 1
                await self._show_current_niche(query, session)
        
        elif callback_data == 'niche_next':
            if session.selected_niche_index < len(session.generated_niches) - 1:
                session.selected_niche_index += 1
                await self._show_current_niche(query, session)
        
        elif callback_data.startswith('plan_'):
            await self._show_detailed_plan(query, session, callback_data, context)
        
        elif callback_data == 'show_analysis':
            await self._show_psych_analysis(query, session, context)
        
        elif callback_data == 'save_all':
            await self._save_all_data(query, session, context)
        
        elif callback_data == 'start_over':
            await self._start_over(query, session)
        
        elif callback_data == 'show_stats':
            await self._show_stats(query, session, context)
    
    async def _handle_detailed_plan_state(self, query, session, callback_data, context):
        """Обработка состояния DETAILED_PLAN"""
        if callback_data == 'back_to_niches':
            session.current_state = BotState.NICHE_SELECTION
            await self._show_current_niche(query, session)
    
    async def _handle_psych_analysis_state(self, query, session, callback_data, context):
        """Обработка состояния PSYCH_ANALYSIS"""
        if callback_data == 'back_to_niches':
            session.current_state = BotState.NICHE_SELECTION
            await self._show_current_niche(query, session)
    
    async def _show_current_niche(self, query, session):
        """Показать текущую нишу"""
        if not session.generated_niches:
            await query.edit_message_text(
                "❌ Ниши не сгенерированы. Попробуйте начать заново /start",
                parse_mode='Markdown'
            )
            return
        
        niche = session.generated_niches[session.selected_niche_index]
        niche_text = format_niche(
            niche, 
            session.selected_niche_index + 1, 
            len(session.generated_niches)
        )
        
        keyboard = create_niche_navigation(session)
        
        await query.edit_message_text(
            niche_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def _show_detailed_plan(self, query, session, callback_data, context):
        """Показать детальный план"""
        try:
            niche_id = callback_data.split('_')[1]
            plan = session.detailed_plans.get(niche_id)
            
            if plan:
                # Разбиваем длинное сообщение
                plan_parts = split_message(plan)
                
                # Отправляем первую часть с кнопкой "Назад"
                keyboard = [[
                    InlineKeyboardButton("◀️ Назад к нишам", callback_data="back_to_niches"),
                    InlineKeyboardButton("💾 Сохранить", callback_data=f"save_plan_{niche_id}")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                plan_text = f"📋 *ДЕТАЛЬНЫЙ БИЗНЕС-ПЛАН*\n\n{plan_parts[0]}"
                
                await query.edit_message_text(
                    plan_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
                # Отправляем остальные части как отдельные сообщения
                for part in plan_parts[1:]:
                    await context.bot.send_message(
                        chat_id=session.chat_id,
                        text=part,
                        parse_mode='Markdown'
                    )
                    await asyncio.sleep(0.5)
                
                session.current_state = BotState.DETAILED_PLAN
            else:
                await query.answer("❌ План для этой ниши еще не сгенерирован", show_alert=True)
        
        except Exception as e:
            logger.error(f"Ошибка показа плана: {e}")
            await query.answer("❌ Ошибка загрузки плана", show_alert=True)
    
    async def _show_psych_analysis(self, query, session, context):
        """Показать психологический анализ"""
        if session.psychological_analysis:
            # Разбиваем анализ на части
            analysis_parts = split_message(session.psychological_analysis)
            
            # Отправляем первую часть с кнопкой "Назад"
            keyboard = [[InlineKeyboardButton("◀️ Назад к нишам", callback_data="back_to_niches")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            analysis_text = f"🧠 *ПСИХОЛОГИЧЕСКИЙ АНАЛИЗ*\n\n{analysis_parts[0]}"
            
            await query.edit_message_text(
                analysis_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            # Отправляем остальные части
            for part in analysis_parts[1:]:
                await context.bot.send_message(
                    chat_id=session.chat_id,
                    text=part,
                    parse_mode='Markdown'
                )
                await asyncio.sleep(0.5)
            
            session.current_state = BotState.PSYCH_ANALYSIS
        else:
            await query.answer("❌ Анализ не сгенерирован", show_alert=True)
    
    async def _save_all_data(self, query, session, context):
        """Сохранить все данные"""
        await query.answer("💾 Сохраняю все данные...", show_alert=True)
        
        try:
            # Сохраняем сессию
            self.data_manager.save_session(session)
            
            # Отправляем психологический анализ
            if session.psychological_analysis:
                analysis_parts = split_message(session.psychological_analysis)
                for i, part in enumerate(analysis_parts):
                    header = "🧠 *ПСИХОЛОГИЧЕСКИЙ АНАЛИЗ*" if i == 0 else ""
                    await context.bot.send_message(
                        chat_id=session.chat_id,
                        text=f"{header}\n\n{part}",
                        parse_mode='Markdown'
                    )
                    await asyncio.sleep(0.5)
            
            # Отправляем все ниши
            for i, niche in enumerate(session.generated_niches):
                niche_text = format_niche(niche, i + 1, len(session.generated_niches))
                await context.bot.send_message(
                    chat_id=session.chat_id,
                    text=niche_text,
                    parse_mode='Markdown'
                )
                await asyncio.sleep(0.5)
            
            # Отправляем планы
            for niche_id, plan in session.detailed_plans.items():
                plan_parts = split_message(plan)
                for i, part in enumerate(plan_parts):
                    header = f"📋 *ПЛАН ДЛЯ НИШИ {niche_id}*" if i == 0 else ""
                    await context.bot.send_message(
                        chat_id=session.chat_id,
                        text=f"{header}\n\n{part}",
                        parse_mode='Markdown'
                    )
                    await asyncio.sleep(0.5)
            
            await query.answer("✅ Все данные сохранены в истории чата!", show_alert=True)
            
        except Exception as e:
            logger.error(f"Ошибка сохранения данных: {e}")
            await query.answer("❌ Ошибка сохранения данных", show_alert=True)
    
    async def _start_over(self, query, session):
        """Начать заново"""
        # Сохраняем текущую сессию
        self.data_manager.save_session(session)
        
        # Сбрасываем состояние
        session.current_state = BotState.START
        session.current_question = 0
        session.questions_answered = 0
        session.selected_niche_index = 0
        session.temp_multiselect = []
        session.temp_energy_selection = None
        
        keyboard = [[InlineKeyboardButton("🚀 Начать новую анкету", callback_data='start_questionnaire')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔄 *Готовы начать новую анкету?*\n\n"
            "Все данные вашей текущей сессии сохранены.\n"
            "Начнем с чистого листа?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _show_stats(self, query, session, context):
        """Показать статистику"""
        stats_text = f"""📊 *СТАТИСТИКА БОТА*

{self.data_manager.stats.get_stats_str()}

{self.data_manager.openai_usage.get_stats_str() if self.data_manager.openai_usage.total_requests > 0 else ''}

*Ваша сессия:*
• Вопросов отвечено: {session.questions_answered}
• Время заполнения: ~{(session.last_activity - session.start_time).seconds // 60} мин
• Состояние: {session.current_state.name}"""
        
        await query.edit_message_text(stats_text, parse_mode='Markdown')