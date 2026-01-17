
"""
Обработчики для анкетирования пользователей v2.0
Поддержка всех типов интерактивных вопросов
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from models.session import UserSession, SessionStatus
from models.enums import ConversationState
from models.question_types import QuestionType
from core.question_engine_v2 import QuestionEngineV2
from handlers.ui_components import (
    UIComponents, 
    QuestionFormatter, 
    ErrorMessages, 
    SuccessMessages,
    LoadingMessages
)
from services.data_manager import DataManager
from services.openai_service import OpenAIService

logger = logging.getLogger(__name__)


class QuestionnaireHandler:
    """Обработчик анкетирования"""
    
    def __init__(
        self, 
        data_manager: DataManager,
        openai_service: OpenAIService
    ):
        """
        Инициализация обработчика
        
        Args:
            data_manager: Менеджер данных
            openai_service: Сервис OpenAI
        """
        self.data_manager = data_manager
        self.openai_service = openai_service
        self.question_engine = QuestionEngineV2()
        
        # Маппинг категорий на эмодзи
        self.category_emojis = {
            'demographic': '👤',
            'personality': '🧠',
            'skills': '💪',
            'values': '💎',
            'resources': '🛠️'
        }
        
        # Маппинг категорий на названия
        self.category_names = {
            'demographic': 'Демография',
            'personality': 'Личность и мотивация',
            'skills': 'Способности и навыки',
            'values': 'Ценности и интересы',
            'resources': 'Практические ограничения'
        }
    
    async def start_questionnaire(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Начать анкетирование
        
        Returns:
            Следующее состояние
        """
        user_id = update.effective_user.id
        
        # Создать или получить сессию
        session = await self.data_manager.get_session(user_id)
        if not session:
            session = await self.data_manager.create_session(user_id)
        
        # Обновить статус
        await self.data_manager.update_status(user_id, SessionStatus.IN_PROGRESS)
        
        # Показать приветствие
        welcome_text = """
🎯 БИЗНЕС-НАВИГАТОР v7.0

Добро пожаловать! Сейчас я задам вам 18 вопросов, чтобы создать персональную бизнес-стратегию.

📋 Анкета состоит из 5 разделов:
• Демография (3 вопроса)
• Личность и мотивация (5 вопросов)
• Способности и навыки (4 вопроса)
• Ценности и интересы (3 вопроса)
• Практические ограничения (3 вопроса)

⏱️ Время заполнения: 10-15 минут

Готовы начать?
"""
        
        keyboard = [
            [InlineKeyboardButton("✅ Начать анкету", callback_data="start_q1")],
            [InlineKeyboardButton("❓ Подробнее о боте", callback_data="about")]
        ]
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return ConversationState.DEMO_AGE.value
    
    async def show_question(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        question_id: str
    ):
        """
        Показать вопрос пользователю
        
        Args:
            update: Update объект
            context: Контекст
            question_id: ID вопроса (например, "Q1")
        """
        query = update.callback_query
        user_id = update.effective_user.id
        
        # Получить сессию
        session = await self.data_manager.get_session(user_id)
        if not session:
            await query.answer("Сессия не найдена. Начните заново с /start")
            return
        
        # Получить данные вопроса
        question_data = self.question_engine.get_question(question_id)
        if not question_data:
            logger.error(f"Вопрос {question_id} не найден")
            await query.answer("Ошибка загрузки вопроса")
            return
        
        # Обновить навигацию
        category = question_data.get('category')
        question_num = int(question_id[1:])  # "Q1" -> 1
        session.add_to_navigation(category, question_num)
        session.current_question = question_num
        session.current_category = category
        await self.data_manager.update_session(session)
        
        # Форматировать текст вопроса
        category_emoji = self.category_emojis.get(category, '📝')
        question_text = self.question_engine.format_question_text(question_data)
        
        formatted_text = QuestionFormatter.format_with_context(
            question_text,
            question_num,
            total_questions=18,
            category_emoji=category_emoji
        )
        
        # Создать клавиатуру
        keyboard = self.question_engine.create_keyboard(question_data, session)
        
        # Отправить вопрос
        if query:
            await query.edit_message_text(
                formatted_text,
                reply_markup=keyboard
            )
        else:
            await update.message.reply_text(
                formatted_text,
                reply_markup=keyboard
            )
    
    async def handle_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Обработать callback от кнопок
        
        Returns:
            Следующее состояние
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        session = await self.data_manager.get_session(user_id)
        
        if not session:
            await query.edit_message_text("Сессия истекла. Начните заново с /start")
            return ConversationHandler.END
        
        callback_data = query.data
        
        # Обработка разных типов callback
        if callback_data.startswith("start_q"):
            # Начать с вопроса Q1
            await self.show_question(update, context, "Q1")
            return ConversationState.DEMO_AGE.value
        
        elif callback_data.startswith("answer:"):
            # Простой ответ на вопрос
            return await self._handle_simple_answer(update, context, session)
        
        elif callback_data.startswith("multiselect:"):
            # Множественный выбор
            return await self._handle_multiselect(update, context, session)
        
        elif callback_data.startswith("scenario:"):
            # Сценарный выбор
            return await self._handle_scenario(update, context, session)
        
        elif callback_data.startswith("slider_"):
            # Слайдер
            return await self._handle_slider(update, context, session)
        
        elif callback_data.startswith("rating:"):
            # Рейтинг
            return await self._handle_rating(update, context, session)
        
        elif callback_data.startswith("alloc_"):
            # Распределение баллов
            return await self._handle_allocation(update, context, session)
        
        elif callback_data.startswith("energy_"):
            # Энергия
            return await self._handle_energy(update, context, session)
        
        elif callback_data.startswith("flow:"):
            # Состояние потока
            return await self._handle_flow(update, context, session)
        
        elif callback_data.startswith("portrait:"):
            # Портрет клиента
            return await self._handle_portrait(update, context, session)
        
        elif callback_data == "submit":
            # Подтверждение ответа
            return await self._submit_answer(update, context, session)
        
        elif callback_data == "back":
            # Возврат назад
            return await self._go_back(update, context, session)
        
        elif callback_data == "info":
            # Информационная кнопка (ничего не делает)
            await query.answer("ℹ️ Информация")
            return session.current_question
        
        else:
            await query.answer("Неизвестная команда")
            return session.current_question
    
    async def _handle_simple_answer(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: UserSession
    ) -> int:
        """Обработать простой ответ"""
        query = update.callback_query
        answer_value = query.data.split(":", 1)[1]
        
        current_q_id = f"Q{session.current_question}"
        question_data = self.question_engine.get_question(current_q_id)
        
        # Проверить, требуется ли custom input
        if question_data.get('allow_custom_input') and answer_value == 'custom':
            # Переключиться на текстовый ввод
            await self.data_manager.update_temp_data(
                session.user_id,
                f"{current_q_id}_awaiting_custom",
                True
            )
            
            prompt = question_data.get('custom_input_prompt', 'Введите ваш ответ:')
            await query.edit_message_text(f"✏️ {prompt}")
            
            return ConversationState.DEMO_CITY.value  # Ждем текстового ввода
        
        # Сохранить ответ
        await self.data_manager.save_answer(session.user_id, current_q_id, answer_value)
        
        # Перейти к следующему вопросу
        return await self._proceed_to_next(update, context, session)
    
    async def _handle_multiselect(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: UserSession
    ) -> int:
        """Обработать множественный выбор"""
        query = update.callback_query
        value = query.data.split(":", 1)[1]
        
        current_q_id = f"Q{session.current_question}"
        temp_key = f"{current_q_id}_selected"
        
        # Получить текущий список выбранных
        selected = session.temp_data.get(temp_key, [])
        
        # Переключить выбор
        if value in selected:
            selected.remove(value)
        else:
            # Проверить максимум
            question_data = self.question_engine.get_question(current_q_id)
            validation = question_data.get('validation', {})
            max_choices = validation.get('max_choices', 10)
            
            if len(selected) >= max_choices:
                await query.answer(f"⚠️ Максимум {max_choices} вариант(ов)")
                return session.current_question
            
            selected.append(value)
        
        # Обновить temp_data
        await self.data_manager.update_temp_data(session.user_id, temp_key, selected)
        
        # Обновить клавиатуру
        keyboard = self.question_engine.create_keyboard(question_data, session)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        
        return session.current_question
    
    async def _handle_scenario(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: UserSession
    ) -> int:
        """Обработать сценарный ответ"""
        query = update.callback_query
        value = query.data.split(":", 1)[1]
        
        current_q_id = f"Q{session.current_question}"
        
        # Сохранить ответ
        await self.data_manager.save_answer(session.user_id, current_q_id, value)
        
        # Перейти к следующему
        return await self._proceed_to_next(update, context, session)
    
    async def _handle_slider(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: UserSession
    ) -> int:
        """Обработать слайдер"""
        query = update.callback_query
        callback_data = query.data
        
        current_q_id = f"Q{session.current_question}"
        question_data = self.question_engine.get_question(current_q_id)
        
        if callback_data.startswith("slider_option:"):
            # Выбран вариант сценария
            option = callback_data.split(":", 1)[1]
            await self.data_manager.update_temp_data(
                session.user_id,
                f"{current_q_id}_option",
                option
            )
            
            # Инициализировать значение слайдера
            slider_data = question_data.get('slider', {})
            initial_value = (slider_data.get('min', 1) + slider_data.get('max', 10)) // 2
            await self.data_manager.update_temp_data(
                session.user_id,
                f"{current_q_id}_value",
                initial_value
            )
        
        elif callback_data == "slider_inc":
            # Увеличить значение
            current_value = session.temp_data.get(f"{current_q_id}_value", 5)
            slider_data = question_data.get('slider', {})
            max_val = slider_data.get('max', 10)
            
            if current_value < max_val:
                await self.data_manager.update_temp_data(
                    session.user_id,
                    f"{current_q_id}_value",
                    current_value + 1
                )
        
        elif callback_data == "slider_dec":
            # Уменьшить значение
            current_value = session.temp_data.get(f"{current_q_id}_value", 5)
            slider_data = question_data.get('slider', {})
            min_val = slider_data.get('min', 1)
            
            if current_value > min_val:
                await self.data_manager.update_temp_data(
                    session.user_id,
                    f"{current_q_id}_value",
                    current_value - 1
                )
        
        # Обновить клавиатуру
        keyboard = self.question_engine.create_keyboard(question_data, session)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        
        return session.current_question
    
    async def _handle_rating(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: UserSession
    ) -> int:
        """Обработать рейтинг"""
        query = update.callback_query
        _, skill_id, rating = query.data.split(":")
        rating = int(rating)
        
        current_q_id = f"Q{session.current_question}"
        temp_key = f"{current_q_id}_ratings"
        
        # Обновить рейтинг
        ratings = session.temp_data.get(temp_key, {})
        ratings[skill_id] = rating
        await self.data_manager.update_temp_data(session.user_id, temp_key, ratings)
        
        # Обновить клавиатуру
        question_data = self.question_engine.get_question(current_q_id)
        keyboard = self.question_engine.create_keyboard(question_data, session)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        
        return session.current_question
    
    async def _handle_allocation(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: UserSession
    ) -> int:
        """Обработать распределение баллов"""
        query = update.callback_query
        callback_data = query.data
        
        current_q_id = f"Q{session.current_question}"
        question_data = self.question_engine.get_question(current_q_id)
        total_points = question_data.get('total_points', 10)
        
        temp_key = f"{current_q_id}_allocation"
        allocation = session.temp_data.get(temp_key, {})
        
        if callback_data.startswith("alloc_inc:"):
            fmt_id = callback_data.split(":", 1)[1]
            used = sum(allocation.values())
            
            if used < total_points:
                allocation[fmt_id] = allocation.get(fmt_id, 0) + 1
                await self.data_manager.update_temp_data(session.user_id, temp_key, allocation)
        
        elif callback_data.startswith("alloc_dec:"):
            fmt_id = callback_data.split(":", 1)[1]
            
            if allocation.get(fmt_id, 0) > 0:
                allocation[fmt_id] -= 1
                await self.data_manager.update_temp_data(session.user_id, temp_key, allocation)
        
        # Обновить клавиатуру
        keyboard = self.question_engine.create_keyboard(question_data, session)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        
        return session.current_question
    
    async def _handle_energy(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: UserSession
    ) -> int:
        """Обработать энергетический профиль"""
        query = update.callback_query
        callback_data = query.data
        
        current_q_id = f"Q{session.current_question}"
        question_data = self.question_engine.get_question(current_q_id)
        
        if callback_data.startswith("energy_inc:"):
            period = callback_data.split(":", 1)[1]
            temp_key = f"{current_q_id}_energy"
            energy_levels = session.temp_data.get(temp_key, {})
            
            current_level = energy_levels.get(period, 4)
            if current_level < 7:
                energy_levels[period] = current_level + 1
                await self.data_manager.update_temp_data(session.user_id, temp_key, energy_levels)
        
        elif callback_data.startswith("energy_dec:"):
            period = callback_data.split(":", 1)[1]
            temp_key = f"{current_q_id}_energy"
            energy_levels = session.temp_data.get(temp_key, {})
            
            current_level = energy_levels.get(period, 4)
            if current_level > 1:
                energy_levels[period] = current_level - 1
                await self.data_manager.update_temp_data(session.user_id, temp_key, energy_levels)
        
        elif callback_data == "energy_next":
            # Переключиться на выбор активностей
            await self.data_manager.update_temp_data(
                session.user_id,
                f"{current_q_id}_step",
                'activities'
            )
        
        elif callback_data.startswith("activity:"):
            _, act_type, time = callback_data.split(":")
            temp_key = f"{current_q_id}_activities"
            activities = session.temp_data.get(temp_key, {})
            activities[act_type] = time
            await self.data_manager.update_temp_data(session.user_id, temp_key, activities)
        
        # Обновить клавиатуру
        keyboard = self.question_engine.create_keyboard(question_data, session)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        
        return session.current_question
    
    async def _handle_flow(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: UserSession
    ) -> int:
        """Обработать выбор примера потока"""
        query = update.callback_query
        value = query.data.split(":", 1)[1]
        
        current_q_id = f"Q{session.current_question}"
        
        # Сохранить выбранный пример
        await self.data_manager.update_temp_data(
            session.user_id,
            f"{current_q_id}_example",
            value
        )
        
        # Запросить текстовое описание ощущений
        question_data = self.question_engine.get_question(current_q_id)
        text_input = question_data.get('text_input', {})
        prompt = text_input.get('prompt', 'Опишите свои ощущения:')
        
        await query.edit_message_text(f"✏️ {prompt}")
        
        # Ожидаем текстовый ввод
        return ConversationState.VALUES_FLOW.value
    
    async def _handle_portrait(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: UserSession
    ) -> int:
        """Обработать портрет клиента"""
        query = update.callback_query
        _, field, value = query.data.split(":", 2)
        
        current_q_id = f"Q{session.current_question}"
        temp_key = f"{current_q_id}_portrait"
        
        portrait = session.temp_data.get(temp_key, {})
        portrait[field] = value
        await self.data_manager.update_temp_data(session.user_id, temp_key, portrait)
        
        # Проверить, все ли поля заполнены
        question_data = self.question_engine.get_question(current_q_id)
        demographics = question_data.get('demographics', {})
        
        if len(portrait) >= len(demographics):
            # Все демографические поля заполнены, запросить текстовое описание
            text_input = question_data.get('text_input', {})
            prompt = text_input.get('prompt', 'Опишите подробнее:')
            
            await query.edit_message_text(f"✏️ {prompt}")
            
            return ConversationState.VALUES_CLIENT.value
        else:
            # Показать следующее поле
            next_field = None
            for field_name in demographics.keys():
                if field_name not in portrait:
                    next_field = field_name
                    break
            
            if next_field:
                await self.data_manager.update_temp_data(
                    session.user_id,
                    f"{current_q_id}_current_field",
                    next_field
                )
                
                keyboard = self.question_engine.create_keyboard(question_data, session)
                await query.edit_message_reply_markup(reply_markup=keyboard)
            
            return session.current_question
    
    async def _submit_answer(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: UserSession
    ) -> int:
        """Подтвердить и сохранить ответ"""
        current_q_id = f"Q{session.current_question}"
        question_data = self.question_engine.get_question(current_q_id)
        question_type = question_data.get('type')
        
        # Собрать финальный ответ из temp_data
        final_answer = None
        
        if question_type == 'multi_select':
            temp_key = f"{current_q_id}_selected"
            final_answer = session.temp_data.get(temp_key, [])
        
        elif question_type == 'slider_with_scenario':
            final_answer = {
                'option': session.temp_data.get(f"{current_q_id}_option"),
                'value': session.temp_data.get(f"{current_q_id}_value")
            }
        
        elif question_type == 'skill_rating':
            temp_key = f"{current_q_id}_ratings"
            final_answer = session.temp_data.get(temp_key, {})
        
        elif question_type == 'learning_allocation':
            temp_key = f"{current_q_id}_allocation"
            final_answer = session.temp_data.get(temp_key, {})
        
        elif question_type == 'energy_distribution':
            final_answer = {
                'energy_levels': session.temp_data.get(f"{current_q_id}_energy", {}),
                'activities': session.temp_data.get(f"{current_q_id}_activities", {})
            }
        
        # Валидация
        is_valid, error_msg = self.question_engine.validate_answer(
            current_q_id,
            final_answer,
            session
        )
        
        if not is_valid:
            query = update.callback_query
            await query.answer(error_msg, show_alert=True)
            return session.current_question
        
        # Сохранить ответ
        await self.data_manager.save_answer(session.user_id, current_q_id, final_answer)
        
        # Очистить temp_data для этого вопроса
        keys_to_clear = [k for k in session.temp_data.keys() if k.startswith(current_q_id)]
        for key in keys_to_clear:
            session.temp_data.pop(key, None)
        await self.data_manager.update_session(session)
        
        # Перейти к следующему вопросу
        return await self._proceed_to_next(update, context, session)
    
    async def _proceed_to_next(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: UserSession
    ) -> int:
        """Перейти к следующему вопросу"""
        current_q_id = f"Q{session.current_question}"
        next_q_id = self.question_engine.get_next_question_id(current_q_id)
        
        if not next_q_id:
            # Анкета завершена
            return await self._complete_questionnaire(update, context, session)
        
        # Показать следующий вопрос
        await self.show_question(update, context, next_q_id)
        
        # Вернуть соответствующее состояние
        return self._get_state_for_question(next_q_id)
    
    async def _go_back(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: UserSession
    ) -> int:
        """Вернуться к предыдущему вопросу"""
        prev = session.go_back()
        
        if not prev:
            query = update.callback_query
            await query.answer("Это первый вопрос")
            return session.current_question
        
        category, question_num = prev
        prev_q_id = f"Q{question_num}"
        
        await self.show_question(update, context, prev_q_id)
        
        return self._get_state_for_question(prev_q_id)
    
    async def _complete_questionnaire(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: UserSession
    ) -> int:
        """Завершить анкету и начать анализ"""
        query = update.callback_query
        
        # Обновить статус
        await self.data_manager.update_status(
            session.user_id,
            SessionStatus.QUESTIONNAIRE_COMPLETED
        )
        
        # Показать сообщение о завершении
        await query.edit_message_text(SuccessMessages.QUESTIONNAIRE_COMPLETED)
        
        # Начать анализ
        await self._start_analysis(update, context, session)
        
        return ConversationState.PROCESSING.value
    
    async def _start_analysis(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: UserSession
    ):
        """Запустить анализ ответов через GPT"""
        user_id = session.user_id
        
        # Показать загрузку
        loading_msg = await context.bot.send_message(
            chat_id=user_id,
            text=LoadingMessages.ANALYZING
        )
        
        try:
            # Вызвать OpenAI для анализа
            analysis = await self.openai_service.generate_psychological_analysis(session)
            
            # Сохранить результат
            session.psychological_analysis = analysis
            await self.data_manager.update_status(
                user_id,
                SessionStatus.ANALYSIS_GENERATED
            )
            await self.data_manager.update_session(session)
            
            # Показать результат
            await loading_msg.edit_text(
                f"✅ Анализ завершен!\n\n{analysis[:500]}..."
            )
            
            # Генерировать ниши
            await self._generate_niches(update, context, session)
            
        except Exception as e:
            logger.error(f"Ошибка анализа: {e}")
            await loading_msg.edit_text(
                "❌ Произошла ошибка при анализе. Попробуйте позже."
            )
    
    async def _generate_niches(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: UserSession
    ):
        """Генерация бизнес-ниш"""
        # Реализация в следующих файлах
        pass
    
    def _get_state_for_question(self, question_id: str) -> int:
        """Получить состояние ConversationHandler для вопроса"""
        question_num = int(question_id[1:])
        
        # Маппинг номеров вопросов на состояния
        state_map = {
            1: ConversationState.DEMO_AGE.value,
            2: ConversationState.DEMO_EDUCATION.value,
            3: ConversationState.DEMO_CITY.value,
            4: ConversationState.PERSONALITY_MOTIVATION.value,
            5: ConversationState.PERSONALITY_TYPE.value,
            6: ConversationState.PERSONALITY_RISK.value,
            7: ConversationState.PERSONALITY_ENERGY.value,
            8: ConversationState.PERSONALITY_FEARS.value,
            9: ConversationState.SKILLS_COGNITIVE.value,
            10: ConversationState.SKILLS_SUPERPOWER.value,
            11: ConversationState.SKILLS_WORK_MODE.value,
            12: ConversationState.SKILLS_LEARNING.value,
            13: ConversationState.VALUES_EXISTENTIAL.value,
            14: ConversationState.VALUES_FLOW.value,
            15: ConversationState.VALUES_CLIENT.value,
            16: ConversationState.RESOURCES_MAP.value,
            17: ConversationState.RESOURCES_TIME.value,
            18: ConversationState.RESOURCES_GEOGRAPHY.value,
        }
        
        return state_map.get(question_num, ConversationState.MAIN_MENU.value)
    
    async def handle_text_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Обработать текстовый ввод пользователя
        
        Returns:
            Следующее состояние
        """
        user_id = update.effective_user.id
        text = update.message.text
        
        session = await self.data_manager.get_session(user_id)
        if not session:
            await update.message.reply_text("Сессия не найдена. Начните с /start")
            return ConversationHandler.END
        
        current_q_id = f"Q{session.current_question}"
        question_data = self.question_engine.get_question(current_q_id)
        
        # Проверка на custom input (например, город)
        if session.temp_data.get(f"{current_q_id}_awaiting_custom"):
            # Сохранить custom ответ
            await self.data_manager.save_answer(session.user_id, current_q_id, {
                'type': 'custom',
                'value': text
            })
            
            # Очистить флаг
            session.temp_data.pop(f"{current_q_id}_awaiting_custom", None)
            await self.data_manager.update_session(session)
            
            # Перейти к следующему вопросу
            next_q_id = self.question_engine.get_next_question_id(current_q_id)
            if next_q_id:
                await self.show_question(update, context, next_q_id)
                return self._get_state_for_question(next_q_id)
            else:
                return await self._complete_questionnaire(update, context, session)
        
        # Проверка на текстовые вопросы (Q8, Q13, Q14, Q15)
        question_type = question_data.get('type')
        
        if question_type in ['existential_text', 'text']:
            # Валидация длины
            text_input = question_data.get('text_input', {})
            validation = question_data.get('validation', {})
            
            min_length = validation.get('min_length', text_input.get('min_length', 0))
            max_length = validation.get('max_length', text_input.get('max_length', 5000))
            
            if len(text) < min_length:
                await update.message.reply_text(
                    ErrorMessages.format_validation_error('min_length', value=min_length)
                )
                return session.current_question
            
            if len(text) > max_length:
                await update.message.reply_text(
                    ErrorMessages.format_validation_error('max_length', value=max_length)
                )
                return session.current_question
            
            # Сохранить текстовый ответ
            await self.data_manager.save_answer(session.user_id, current_q_id, text)
            
            # Перейти к следующему
            next_q_id = self.question_engine.get_next_question_id(current_q_id)
            if next_q_id:
                await self.show_question(update, context, next_q_id)
                return self._get_state_for_question(next_q_id)
            else:
                return await self._complete_questionnaire(update, context, session)
        
        # Для составных вопросов (Q8 - страхи с текстом, Q14 - flow, Q15 - портрет)
        if current_q_id == "Q8":
            # Сохранить текстовое описание страха
            selected_fears = session.temp_data.get(f"{current_q_id}_selected", [])
            final_answer = {
                'selected_fears': selected_fears,
                'description': text
            }
            
            await self.data_manager.save_answer(session.user_id, current_q_id, final_answer)
            
            # Очистить temp
            session.temp_data.pop(f"{current_q_id}_selected", None)
            await self.data_manager.update_session(session)
            
            # Следующий вопрос
            next_q_id = self.question_engine.get_next_question_id(current_q_id)
            await self.show_question(update, context, next_q_id)
            return self._get_state_for_question(next_q_id)
        
        elif current_q_id == "Q14":
            # Сохранить описание ощущений потока
            example = session.temp_data.get(f"{current_q_id}_example")
            final_answer = {
                'example': example,
                'feelings_description': text
            }
            
            await self.data_manager.save_answer(session.user_id, current_q_id, final_answer)
            
            # Очистить temp
            session.temp_data.pop(f"{current_q_id}_example", None)
            await self.data_manager.update_session(session)
            
            # Следующий вопрос
            next_q_id = self.question_engine.get_next_question_id(current_q_id)
            await self.show_question(update, context, next_q_id)
            return self._get_state_for_question(next_q_id)
        
        elif current_q_id == "Q15":
            # Сохранить текстовое описание клиента
            portrait = session.temp_data.get(f"{current_q_id}_portrait", {})
            final_answer = {
                'demographics': portrait,
                'description': text
            }
            
            await self.data_manager.save_answer(session.user_id, current_q_id, final_answer)
            
            # Очистить temp
            session.temp_data.pop(f"{current_q_id}_portrait", None)
            session.temp_data.pop(f"{current_q_id}_current_field", None)
            await self.data_manager.update_session(session)
            
            # Следующий вопрос
            next_q_id = self.question_engine.get_next_question_id(current_q_id)
            await self.show_question(update, context, next_q_id)
            return self._get_state_for_question(next_q_id)
        
        # Неожиданный текстовый ввод
        await update.message.reply_text(
            "Пожалуйста, используйте кнопки для ответа на вопрос."
        )
        return session.current_question
    
    async def cancel_questionnaire(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Отменить анкетирование"""
        user_id = update.effective_user.id
        
        session = await self.data_manager.get_session(user_id)
        if session:
            await self.data_manager.update_status(
                user_id,
                SessionStatus.ABANDONED
            )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Начать заново", callback_data="start_q1")],
            [InlineKeyboardButton("❌ Выйти", callback_data="exit")]
        ]
        
        await update.message.reply_text(
            "❌ Анкетирование отменено.\n\nВы можете начать заново в любое время.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return ConversationHandler.END