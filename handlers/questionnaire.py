"""
Обработчики для анкетирования пользователей v2.0
"""
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import ContextTypes
from models.session import UserSession, SessionStatus
from models.enums import ConversationState
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
    
    def __init__(self, data_manager: DataManager, openai_service: OpenAIService):
        self.data_manager = data_manager
        self.openai_service = openai_service
        self.question_engine = QuestionEngineV2()
        
        self.category_emojis = {
            'demographic': '👤',
            'personality': '🧠',
            'skills': '💪',
            'values': '💎',
            'resources': '🛠️'
        }
        
        self.category_names = {
            'demographic': 'Демография',
            'personality': 'Личность и мотивация',
            'skills': 'Способности и навыки',
            'values': 'Ценности и интересы',
            'resources': 'Практические ограничения'
        }

    async def start_questionnaire(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начать анкетирование"""
        user_id = update.effective_user.id
        
        # Показываем "бот печатает"
        await context.bot.send_chat_action(
            chat_id=user_id,
            action=ChatAction.TYPING
        )
        await asyncio.sleep(1.5)
        
        session = await self.data_manager.get_session(user_id)
        if not session:
            session = await self.data_manager.create_session(user_id)
        
        await self.data_manager.update_status(user_id, SessionStatus.IN_PROGRESS)
        
        welcome_text = """
🎯 *БИЗНЕС-НАВИГАТОР v7.0*

Добро пожаловать! Сейчас я задам вам *7 вопросов*, чтобы создать персональную бизнес-стратегию.

📋 *Анкета состоит из 5 разделов:*
• Демография (2 вопроса)
• Личность и мотивация (2 вопроса)
• Способности и навыки (2 вопроса)
• Ценности и интересы (1 вопрос)

⏱️ *Время заполнения:* 3-5 минут

✨ *Готовы начать?*
"""
        keyboard = [
            [InlineKeyboardButton("✅ Начать анкету", callback_data="start_q1")],
            [InlineKeyboardButton("❓ Подробнее о боте", callback_data="about")]
        ]
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        return ConversationState.DEMO_AGE.value

    async def show_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE, question_id: str):
        """Показать вопрос пользователю"""
        query = update.callback_query if hasattr(update, 'callback_query') else None
        user_id = update.effective_user.id
        
        # 🎨 ПОКАЗЫВАЕМ "БОТ ПЕЧАТАЕТ" ПЕРЕД КАЖДЫМ ВОПРОСОМ
        await context.bot.send_chat_action(
            chat_id=user_id,
            action=ChatAction.TYPING
        )
        await asyncio.sleep(1.2)  # Задержка для эффекта
        
        session = await self.data_manager.get_session(user_id)
        if not session:
            if query:
                await query.answer("Сессия не найдена. Начните заново с /start")
            return
        
        question_data = self.question_engine.get_question(question_id)
        if not question_data:
            logger.error(f"Вопрос {question_id} не найден")
            if query:
                await query.answer("Ошибка загрузки вопроса")
            return
        
        category = question_data.get('category')
        question_num = int(question_id[1:])
        session.add_to_navigation(category, question_num)
        session.current_question = question_num
        session.current_category = category
        await self.data_manager.update_session(session)
        
        category_emoji = self.category_emojis.get(category, '📝')
        question_text = self.question_engine.format_question_text(question_data)
        
        formatted_text = QuestionFormatter.format_with_context(
            question_text,
            question_num,
            total_questions=7,
            category_emoji=category_emoji
        )
        
        keyboard = self.question_engine.create_keyboard(question_data, session)
        
        if query:
            await query.edit_message_text(
                formatted_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                formatted_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработать callback от кнопок"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        session = await self.data_manager.get_session(user_id)
        
        if not session:
            await query.edit_message_text("Сессия истекла. Начните заново с /start")
            return ConversationHandler.END
        
        callback_data = query.data
        
        if callback_data.startswith("start_q"):
            await self.show_question(update, context, "Q1")
            return ConversationState.DEMO_AGE.value
        
        elif callback_data.startswith("answer:"):
            return await self._handle_simple_answer(update, context, session)
        
        elif callback_data.startswith("multiselect:"):
            return await self._handle_multiselect(update, context, session)
        
        elif callback_data.startswith("scenario:"):
            return await self._handle_scenario(update, context, session)
        
        elif callback_data.startswith("slider_"):
            return await self._handle_slider(update, context, session)
        
        elif callback_data.startswith("rating:"):
            return await self._handle_rating(update, context, session)
        
        elif callback_data.startswith("alloc_"):
            return await self._handle_allocation(update, context, session)
        
        elif callback_data.startswith("energy_"):
            return await self._handle_energy(update, context, session)
        
        elif callback_data.startswith("flow:"):
            return await self._handle_flow(update, context, session)
        
        elif callback_data.startswith("portrait:"):
            return await self._handle_portrait(update, context, session)
        
        elif callback_data == "submit":
            return await self._submit_answer(update, context, session)
        
        elif callback_data == "back":
            return await self._go_back(update, context, session)
        
        elif callback_data == "info":
            await query.answer("ℹ️ Информация")
            return session.current_question
        
        else:
            await query.answer("Неизвестная команда")
            return session.current_question

    async def _handle_simple_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Обработать простой ответ"""
        query = update.callback_query
        answer_value = query.data.split(":", 1)[1]
        
        current_q_id = f"Q{session.current_question}"
        question_data = self.question_engine.get_question(current_q_id)
        
        if question_data.get('allow_custom_input') and answer_value == 'custom':
            await self.data_manager.update_temp_data(
                session.user_id,
                f"{current_q_id}_awaiting_custom",
                True
            )
            
            prompt = question_data.get('custom_input_prompt', 'Введите ваш ответ:')
            await query.edit_message_text(f"✏️ {prompt}")
            
            return ConversationState.DEMO_CITY.value
        
        await self.data_manager.save_answer(session.user_id, current_q_id, answer_value)
        return await self._proceed_to_next(update, context, session)

    async def _handle_multiselect(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Обработать множественный выбор"""
        query = update.callback_query
        value = query.data.split(":", 1)[1]
        
        current_q_id = f"Q{session.current_question}"
        temp_key = f"{current_q_id}_selected"
        
        selected = session.temp_data.get(temp_key, [])
        
        if value in selected:
            selected.remove(value)
        else:
            question_data = self.question_engine.get_question(current_q_id)
            validation = question_data.get('validation', {})
            max_choices = validation.get('max_choices', 10)
            
            if len(selected) >= max_choices:
                await query.answer(f"⚠️ Максимум {max_choices} вариант(ов)")
                return session.current_question
            
            selected.append(value)
        
        await self.data_manager.update_temp_data(session.user_id, temp_key, selected)
        
        question_data = self.question_engine.get_question(current_q_id)
        keyboard = self.question_engine.create_keyboard(question_data, session)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        
        return session.current_question

    async def _handle_scenario(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Обработать сценарный ответ"""
        query = update.callback_query
        value = query.data.split(":", 1)[1]
        
        current_q_id = f"Q{session.current_question}"
        await self.data_manager.save_answer(session.user_id, current_q_id, value)
        
        return await self._proceed_to_next(update, context, session)

    async def _handle_slider(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Обработать слайдер"""
        query = update.callback_query
        callback_data = query.data
        
        current_q_id = f"Q{session.current_question}"
        question_data = self.question_engine.get_question(current_q_id)
        
        if callback_data.startswith("slider_option:"):
            option = callback_data.split(":", 1)[1]
            await self.data_manager.update_temp_data(
                session.user_id,
                f"{current_q_id}_option",
                option
            )
            
            slider_data = question_data.get('slider', {})
            initial_value = (slider_data.get('min', 1) + slider_data.get('max', 10)) // 2
            await self.data_manager.update_temp_data(
                session.user_id,
                f"{current_q_id}_value",
                initial_value
            )
        
        elif callback_data == "slider_inc":
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
            current_value = session.temp_data.get(f"{current_q_id}_value", 5)
            slider_data = question_data.get('slider', {})
            min_val = slider_data.get('min', 1)
            
            if current_value > min_val:
                await self.data_manager.update_temp_data(
                    session.user_id,
                    f"{current_q_id}_value",
                    current_value - 1
                )
        
        keyboard = self.question_engine.create_keyboard(question_data, session)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        
        return session.current_question

    async def _handle_rating(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Обработать рейтинг"""
        query = update.callback_query
        _, skill_id, rating = query.data.split(":")
        rating = int(rating)
        
        current_q_id = f"Q{session.current_question}"
        temp_key = f"{current_q_id}_ratings"
        
        ratings = session.temp_data.get(temp_key, {})
        ratings[skill_id] = rating
        await self.data_manager.update_temp_data(session.user_id, temp_key, ratings)
        
        question_data = self.question_engine.get_question(current_q_id)
        keyboard = self.question_engine.create_keyboard(question_data, session)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        
        return session.current_question

    async def _handle_allocation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
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
        
        keyboard = self.question_engine.create_keyboard(question_data, session)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        
        return session.current_question

    async def _handle_energy(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
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
        
        keyboard = self.question_engine.create_keyboard(question_data, session)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        
        return session.current_question

    async def _handle_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Обработать выбор примера потока"""
        query = update.callback_query
        value = query.data.split(":", 1)[1]
        
        current_q_id = f"Q{session.current_question}"
        
        await self.data_manager.update_temp_data(
            session.user_id,
            f"{current_q_id}_example",
            value
        )
        
        question_data = self.question_engine.get_question(current_q_id)
        text_input = question_data.get('text_input', {})
        prompt = text_input.get('prompt', 'Опишите свои ощущения:')
        
        await query.edit_message_text(f"✏️ {prompt}")
        
        return ConversationState.VALUES_FLOW.value

    async def _handle_portrait(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Обработать портрет клиента"""
        query = update.callback_query
        _, field, value = query.data.split(":", 2)
        
        current_q_id = f"Q{session.current_question}"
        temp_key = f"{current_q_id}_portrait"
        
        portrait = session.temp_data.get(temp_key, {})
        portrait[field] = value
        await self.data_manager.update_temp_data(session.user_id, temp_key, portrait)
        
        question_data = self.question_engine.get_question(current_q_id)
        demographics = question_data.get('demographics', {})
        
        if len(portrait) >= len(demographics):
            text_input = question_data.get('text_input', {})
            prompt = text_input.get('prompt', 'Опишите подробнее:')
            
            await query.edit_message_text(f"✏️ {prompt}")
            
            return ConversationState.VALUES_CLIENT.value
        else:
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

    async def _submit_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Подтвердить и сохранить ответ"""
        current_q_id = f"Q{session.current_question}"
        question_data = self.question_engine.get_question(current_q_id)
        question_type = question_data.get('type')
        
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
        
        is_valid, error_msg = self.question_engine.validate_answer(
            current_q_id,
            final_answer,
            session
        )
        
        if not is_valid:
            query = update.callback_query
            await query.answer(error_msg, show_alert=True)
            return session.current_question
        
        await self.data_manager.save_answer(session.user_id, current_q_id, final_answer)
        
        keys_to_clear = [k for k in session.temp_data.keys() if k.startswith(current_q_id)]
        for key in keys_to_clear:
            session.temp_data.pop(key, None)
        await self.data_manager.update_session(session)
        
        return await self._proceed_to_next(update, context, session)

    async def _proceed_to_next(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Перейти к следующему вопросу"""
        current_q_id = f"Q{session.current_question}"
        next_q_id = self.question_engine.get_next_question_id(current_q_id)
        
        if not next_q_id:
            return await self._complete_questionnaire(update, context, session)
        
        await self.show_question(update, context, next_q_id)
        
        return self._get_state_for_question(next_q_id)

    async def _go_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
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

    async def _complete_questionnaire(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Завершить анкету и начать анализ"""
        query = update.callback_query
        
        await self.data_manager.update_status(
            session.user_id,
            SessionStatus.QUESTIONNAIRE_COMPLETED
        )
        
        await query.edit_message_text(
            SuccessMessages.QUESTIONNAIRE_COMPLETED,
            parse_mode="Markdown"
        )
        
        await self._start_analysis(update, context, session)
        
        return ConversationState.PROCESSING.value

    async def _start_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession):
        """Запустить анализ ответов (MOCK - без OpenAI)"""
        user_id = session.user_id
        
        # Показываем анимацию анализа
        loading_msg = await context.bot.send_message(
            chat_id=user_id,
            text=LoadingMessages.ANALYZING,
            parse_mode="Markdown"
        )
        
        # Имитация задержки анализа
        await asyncio.sleep(3)
        
        try:
            # MOCK-анализ вместо OpenAI
            analysis = self._get_mock_analysis(session)
            
            session.psychological_analysis = analysis
            await self.data_manager.update_status(
                user_id,
                SessionStatus.ANALYSIS_GENERATED
            )
            await self.data_manager.update_session(session)
            
            await loading_msg.edit_text(
                f"✅ *Анализ завершен!*\n\n{analysis[:500]}...",
                parse_mode="Markdown"
            )
            
            await self._generate_niches(update, context, session)
            
        except Exception as e:
            logger.error(f"Ошибка анализа: {e}")
            await loading_msg.edit_text(
                "❌ Произошла ошибка при анализе. Попробуйте позже.",
                parse_mode="Markdown"
            )

    def _get_mock_analysis(self, session: UserSession) -> str:
        """MOCK-анализ вместо OpenAI"""
        answers = session.answers
        
        age = answers.get('Q1', 'не указано')
        risk = answers.get('Q6', {}).get('value', '5') if isinstance(answers.get('Q6'), dict) else '5'
        energy = answers.get('Q7', {}).get('energy_levels', {}) if isinstance(answers.get('Q7'), dict) else {}
        
        morning = energy.get('morning', 4)
        day = energy.get('day', 4)
        evening = energy.get('evening', 4)
        
        peak_time = "утро" if morning >= day and morning >= evening else "день" if day >= evening else "вечер"
        
        return f"""
🧠 *ВАШ ПСИХОЛОГИЧЕСКИЙ ПРОФИЛЬ*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 *ДЕМОГРАФИЯ:*
• Возраст: {age}
• Профиль: Активный предприниматель

⚡ *ЭНЕРГЕТИЧЕСКИЙ ПРОФИЛЬ:*
• Утро: {morning}/7 {'🌅' * morning}{'▁' * (7 - morning)}
• День: {day}/7 {'☀️' * day}{'▁' * (7 - day)}
• Вечер: {evening}/7 {'🌙' * evening}{'▁' * (7 - evening)}

🎯 Пик продуктивности: *{peak_time}*

🎲 *ОТНОШЕНИЕ К РИСКУ:* {risk}/10
{'🔥 Высокий' if int(risk) >= 7 else '⚖️ Умеренный' if int(risk) >= 4 else '🔒 Осторожный'}

💎 *СКРЫТЫЕ ВОЗМОЖНОСТИ:*
• Комбинация навыков указывает на потенциал в цифровых продуктах
• Энергетический профиль подходит для проектной работы
• Стиль принятия решений оптимален для стартапов

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 *На основе ваших ответов система подобрала 3 персональные ниши...*
"""

    async def _generate_niches(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession):
        """Генерация ниш (MOCK)"""
        user_id = session.user_id
        
        loading_msg = await context.bot.send_message(
            chat_id=user_id,
            text=LoadingMessages.GENERATING_NICHES,
            parse_mode="Markdown"
        )
        
        await asyncio.sleep(2)
        
        # MOCK-ниши
        niches_text = self._get_mock_niches(session)
        session.generated_niches = niches_text
        
        await self.data_manager.update_session(session)
        
        await loading_msg.edit_text(
            niches_text,
            parse_mode="Markdown"
        )
        
        await self._show_final_presentation(update, context, session)

    def _get_mock_niches(self, session: UserSession) -> str:
        """MOCK-ниши"""
        return """
🎯 *ПОДОБРАННЫЕ НИШИ*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔥 *1. КОНСУЛЬТАЦИОННЫЕ УСЛУГИ*
**Категория:** Быстрый старт
**Окупаемость:** 1-3 месяца
**Инвестиции:** от 10,000₽

💻 *2. ОНЛАЙН-КУРСЫ*
**Категория:** Масштабируемый
**Окупаемость:** 2-4 месяца
**Инвестиции:** от 50,000₽

🚀 *3. ФРИЛАНС-УСЛУГИ*
**Категория:** Минимальный риск
**Окупаемость:** 1-2 месяца
**Инвестиции:** от 5,000₽

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    async def _show_final_presentation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession):
        """🎨 ФИНАЛЬНАЯ ПРЕЗЕНТАЦИЯ ТЕХНОЛОГИИ"""
        user_id = session.user_id
        
        await context.bot.send_chat_action(
            chat_id=user_id,
            action=ChatAction.TYPING
        )
        await asyncio.sleep(2)
        
        final_text = """
🎊 *АНАЛИЗ ЗАВЕРШЁН!*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 *РЕЗУЛЬТАТЫ РАБОТЫ СИСТЕМЫ:*

✅ Обработано ответов: *7*
⚡ Время анализа: *0.3 сек*
🤖 Использовано токенов: *0* (локальная обработка)
💾 Данные сохранены в сессии

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 *ЭТО ДЕМО-ВЕРСИЯ UX-ДВИЖКА v7.0*

✨ *Полная версия включает:*

✓ 35 глубоких вопросов
✓ AI-анализ через GPT-4
✓ 8 персонализированных ниш
✓ 90-дневный план действий
✓ PDF-отчёт с метриками
✓ Интеграция с платежными системами
✓ Поддержка команды и масштабирования

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 *ХОТИТЕ ТАКУЮ ЖЕ СИСТЕМУ ДЛЯ СВОЕГО ПРОЕКТА?*

📩 *Свяжитесь с разработчиком:*
@your_contact

🌐 *Технологии:*
• Python + FastAPI
• Telegram Bot API
• OpenAI GPT-4
• PostgreSQL
• Docker + Render

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔄 *Что дальше?*
• /restart - Пройти анкету заново
• /start - Вернуться в главное меню
• /help - Справка по командам

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Спасибо за использование Бизнес-Навигатора!* ✨
"""
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Пройти заново", callback_data="restart_questionnaire"),
                InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")
            ],
            [
                InlineKeyboardButton("📩 Связаться с разработчиком", url="https://t.me/your_contact")
            ]
        ]
        
        await context.bot.send_message(
            chat_id=user_id,
            text=final_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработать текстовый ввод пользователя"""
        user_id = update.effective_user.id
        text = update.message.text
        
        # Показываем "бот печатает" перед обработкой
        await context.bot.send_chat_action(
            chat_id=user_id,
            action=ChatAction.TYPING
        )
        
        session = await self.data_manager.get_session(user_id)
        if not session:
            await update.message.reply_text("Сессия не найдена. Начните с /start")
            return ConversationHandler.END
        
        current_q_id = f"Q{session.current_question}"
        question_data = self.question_engine.get_question(current_q_id)
        
        if session.temp_data.get(f"{current_q_id}_awaiting_custom"):
            await self.data_manager.save_answer(
                session.user_id,
                current_q_id,
                {'type': 'custom', 'value': text}
            )
            
            session.temp_data.pop(f"{current_q_id}_awaiting_custom", None)
            await self.data_manager.update_session(session)
            
            next_q_id = self.question_engine.get_next_question_id(current_q_id)
            if next_q_id:
                await self.show_question(update, context, next_q_id)
                return self._get_state_for_question(next_q_id)
            else:
                return await self._complete_questionnaire(update, context, session)
        
        question_type = question_data.get('type')
        
        if question_type in ['existential_text', 'text']:
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
            
            await self.data_manager.save_answer(session.user_id, current_q_id, text)
            
            next_q_id = self.question_engine.get_next_question_id(current_q_id)
            if next_q_id:
                await self.show_question(update, context, next_q_id)
                return self._get_state_for_question(next_q_id)
            else:
                return await self._complete_questionnaire(update, context, session)
        
        await update.message.reply_text(
            "Пожалуйста, используйте кнопки для ответа на вопрос."
        )
        return session.current_question

    async def cancel_questionnaire(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отменить анкетирование"""
        user_id = update.effective_user.id
        
        session = await self.data_manager.get_session(user_id)
        if session:
            await self.data_manager.update_status(user_id, SessionStatus.ABANDONED)
        
        keyboard = [
            [InlineKeyboardButton("🔄 Начать заново", callback_data="start_q1")],
            [InlineKeyboardButton("❌ Выйти", callback_data="exit")]
        ]
        
        await update.message.reply_text(
            "❌ Анкетирование отменено.\n\nВы можете начать заново в любое время.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return ConversationHandler.END

    def _get_state_for_question(self, question_id: str) -> int:
        """Получить состояние ConversationHandler для вопроса"""
        question_num = int(question_id[1:])
        
        state_map = {
            1: ConversationState.DEMO_AGE.value,
            2: ConversationState.DEMO_EDUCATION.value,
            3: ConversationState.DEMO_CITY.value,
            4: ConversationState.PERSONALITY_MOTIVATION.value,
            5: ConversationState.PERSONALITY_TYPE.value,
            6: ConversationState.PERSONALITY_RISK.value,
            7: ConversationState.PERSONALITY_ENERGY.value,
        }
        
        return state_map.get(question_num, ConversationState.MAIN_MENU.value)
