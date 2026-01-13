"""
Логика работы с анкетой
"""
import logging
import asyncio
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from models.enums import BotState
from models.session import UserSession
from services.data_manager import DataManager
from services.openai_service import OpenAIService
from core.question_engine import QuestionEngine
from utils.formatters import get_random_praise

logger = logging.getLogger(__name__)

class QuestionnaireHandler:
    """Обработчик анкеты"""
    
    def __init__(self, data_manager: DataManager, openai_service: Optional[OpenAIService], question_engine: QuestionEngine):
        self.data_manager = data_manager
        self.openai_service = openai_service
        self.question_engine = question_engine
    
    async def start_questionnaire(self, query, session: UserSession):
        """Начать анкету"""
        session.current_state = BotState.DEMOGRAPHY
        session.current_question = 1
        session.questions_answered = 0
        
        await self._ask_question(query, session, 1)
    
    async def handle_callback(self, query, session: UserSession, callback_data: str):
        """Обработать callback анкеты"""
        question_id = session.current_question
        question = self.question_engine.get_question(question_id)
        
        if not question:
            logger.error(f"Вопрос {question_id} не найден")
            await query.edit_message_text("❌ Ошибка: вопрос не найден")
            return
        
        # Обрабатываем ответ
        success, error_msg, next_question_id = self.question_engine.process_answer(
            question, callback_data, session
        )
        
        if not success:
            if error_msg:
                await query.answer(error_msg, show_alert=True)
            return
        
        # Если остались на том же вопросе (мультиселект, слайдер)
        if next_question_id == question_id:
            await self._update_question_display(query, session, question_id)
        else:
            # Переходим к следующему вопросу
            if next_question_id:
                session.current_question = next_question_id
                session.questions_answered += 1
                session.current_state = self.question_engine.get_state_for_question(next_question_id)
                
                await self._ask_question(query, session, next_question_id)
            else:
                # Анкета завершена
                await self._finish_questionnaire(query, session)
    
    async def handle_text_message(self, update: Update, session: UserSession, message_text: str):
        """Обработать текстовое сообщение"""
        question_id = session.current_question
        question = self.question_engine.get_question(question_id)
        
        if not question:
            logger.error(f"Вопрос {question_id} не найден")
            return
        
        # Обрабатываем текстовый ответ
        success, error_msg, next_question_id = self.question_engine.process_answer(
            question, message_text, session
        )
        
        if not success:
            if error_msg:
                await update.message.reply_text(f"❌ {error_msg}")
            return
        
        # Переходим к следующему вопросу
        if next_question_id:
            session.current_question = next_question_id
            session.questions_answered += 1
            session.current_state = self.question_engine.get_state_for_question(next_question_id)
            
            await self._ask_question(update, session, next_question_id)
        else:
            # Анкета завершена
            await self._finish_questionnaire(update, session)
    
    async def _ask_question(self, target, session: UserSession, question_id: int):
        """Задать вопрос"""
        question = self.question_engine.get_question(question_id)
        
        if not question:
            logger.error(f"Вопрос {question_id} не найден")
            return
        
        # Рендерим вопрос
        text, keyboard = self.question_engine.render_question(question, session)
        
        # Добавляем похвалу
        praise = get_random_praise()
        full_text = f"{praise}\n\n{text}"
        
        # Отправляем или редактируем сообщение
        if hasattr(target, 'edit_message_text'):  # Callback query
            await target.edit_message_text(
                full_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        elif hasattr(target, 'message'):  # Update object
            await target.message.reply_text(
                full_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
    
    async def _update_question_display(self, query, session: UserSession, question_id: int):
        """Обновить отображение вопроса"""
        question = self.question_engine.get_question(question_id)
        
        if not question:
            return
        
        text, keyboard = self.question_engine.render_question(question, session)
        
        # Добавляем информацию о выбранных опциях
        if question.type == "multiselect":
            selected_count = len(session.temp_multiselect)
            text += f"\n\n✅ Выбрано: {selected_count}"
        
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def _finish_questionnaire(self, target, session: UserSession):
        """Завершить анкету"""
        session.current_state = BotState.ANALYZING
        
        # Сохраняем сессию
        self.data_manager.save_session(session)
        self.data_manager.mark_profile_completed(session.user_id)
        
        finish_text = f"""🎉 *БРАВО! АНКЕТА ЗАВЕРШЕНА!*

{get_random_praise()}

✅ Отвечено: {session.questions_answered} вопросов
⏱️ Время заполнения: ~{(session.last_activity - session.start_time).seconds // 60} минут
🎯 Глубина анализа: профессиональный уровень

🤖 *Запускаю AI-анализ...*
1. Анализирую психологический профиль
2. Ищу скрытый потенциал  
3. Подбираю уникальные ниши
4. Готовлю персонализированные планы

⏳ *Это займет 1-2 минуты*
Пока AI работает, можете отдохнуть ☕"""
        
        if hasattr(target, 'edit_message_text'):  # Callback query
            await target.edit_message_text(finish_text, parse_mode='Markdown')
        elif hasattr(target, 'message'):  # Update object
            await target.message.reply_text(finish_text, parse_mode='Markdown')
        
        # Запускаем AI анализ асинхронно
        asyncio.create_task(self._start_ai_analysis(target, session))
    
    async def _start_ai_analysis(self, target, session: UserSession):
        """Запустить AI анализ"""
        try:
            if not self.openai_service or not self.openai_service.is_available:
                await self._use_fallback_data(target, session)
                return
            
            # Генерация психологического анализа
            analysis = await self.openai_service.generate_psychological_analysis(
                session.to_openai_dict(),
                self.data_manager.openai_usage
            )
            session.psychological_analysis = analysis
            
            # Генерация бизнес-ниш
            niches = await self.openai_service.generate_business_niches(
                session.to_openai_dict(),
                analysis,
                self.data_manager.openai_usage
            )
            session.generated_niches = niches
            self.data_manager.add_generated_niches(len(niches))
            
            # Генерация планов для первых 3 ниш
            plans_generated = 0
            for i, niche in enumerate(session.generated_niches[:3]):
                plan = await self.openai_service.generate_detailed_plan(
                    session.to_openai_dict(),
                    niche,
                    self.data_manager.openai_usage
                )
                if plan:
                    session.detailed_plans[str(niche.get('id', i))] = plan
                    plans_generated += 1
                    self.data_manager.add_generated_plan()
            
            # Показываем результат
            stats = self.data_manager.openai_usage
            stats_text = stats.get_stats_str() if stats.total_requests > 0 else ""
            
            result_text = f"""🎉 *АНАЛИЗ ЗАВЕРШЕН!*

✅ Создано: {len(session.generated_niches)} уникальных бизнес-ниш
📊 Психологический портрет: готов
📋 Детальные планы: {plans_generated} шт

{stats_text}

👇 *Выберите первую нишу для изучения:*"""
            
            # Определяем chat_id
            if hasattr(target, 'message'):
                chat_id = target.message.chat_id
            elif hasattr(target, 'callback_query'):
                chat_id = target.callback_query.message.chat_id
            else:
                chat_id = session.chat_id
            
            from telegram import Bot
            bot = Bot(token=self.data_manager.config.telegram_token) if hasattr(self.data_manager, 'config') else None
            
            if bot:
                await bot.send_message(
                    chat_id=chat_id,
                    text=result_text,
                    parse_mode='Markdown'
                )
            
            session.current_state = BotState.NICHE_SELECTION
            
            # Показываем первую нишу
            from handlers.callbacks import CallbackHandlers
            # Нужно будет вызвать через основной бот
            
        except Exception as e:
            logger.error(f"❌ Ошибка AI анализа: {e}")
            await self._use_fallback_data(target, session)
    
    async def _use_fallback_data(self, target, session: UserSession):
        """Использовать запасные данные"""
        # Создаем базовый анализ
        from services.openai_service import OpenAIService
        temp_service = OpenAIService(None)  # Передаем пустой конфиг
        
        session.psychological_analysis = temp_service._create_fallback_analysis(session.to_openai_dict())
        session.generated_niches = temp_service._create_fallback_niches(session.to_openai_dict())
        
        result_text = f"""🎉 *АНАЛИЗ ЗАВЕРШЕН (базовый режим)*

✅ Создано: {len(session.generated_niches)} бизнес-ниш
📊 Использованы стандартные шаблоны
⚠️ AI временно недоступен

👇 *Выберите первую нишу для изучения:*"""
        
        if hasattr(target, 'edit_message_text'):
            await target.edit_message_text(result_text, parse_mode='Markdown')
        elif hasattr(target, 'message'):
            await target.message.reply_text(result_text, parse_mode='Markdown')
        
        session.current_state = BotState.NICHE_SELECTION