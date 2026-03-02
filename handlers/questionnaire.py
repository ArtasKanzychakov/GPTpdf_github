#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обработчики для анкетирования - DEMO VERSION v7.0
Поддержка всех типов интерактивных вопросов Telegram
"""
import logging
import asyncio
from typing import Optional, Dict, Any, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from models.session import UserSession, SessionStatus
from models.enums import ConversationState
from handlers.ui_components import UIComponents, QuestionFormatter, LoadingMessages, SuccessMessages, ErrorMessages
from services.data_manager import data_manager
from services.openai_service import openai_service

logger = logging.getLogger(__name__)


class QuestionnaireHandler:
    """Обработчик анкетирования пользователей"""
    
    def __init__(self):
        self.data_manager = data_manager
        self.openai_service = openai_service
        
        # Маппинг категорий на эмодзи
        self.category_emojis: Dict[str, str] = {
            'start': '👋',
            'demographic': '📊',
            'interests': '🎯',
            'energy': '⚡',
            'skills': '💪',
            'work_style': '💼',
            'risk': '🎚️',
            'values': '💎',
            'dream': '📝',
            'finish': '✅'
        }
        
        # Маппинг категорий на названия
        self.category_names: Dict[str, str] = {
            'start': 'Знакомство',
            'demographic': 'О вас',
            'interests': 'Интересы',
            'energy': 'Энергия',
            'skills': 'Навыки',
            'work_style': 'Стиль работы',
            'risk': 'Риск',
            'values': 'Ценности',
            'dream': 'Мечта',
            'finish': 'Завершение'
        }
        
        # Общее количество вопросов в демо-режиме
        self.total_questions: int = 10
    
    async def _show_typing(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE, seconds: float = 1.0) -> None:
        """Показать индикатор набора текста"""
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action='typing')
            await asyncio.sleep(seconds)
        except Exception as e:
            logger.warning(f"Не удалось показать индикатор набора: {e}")
    
    async def start_questionnaire(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начать анкетирование"""
        try:
            user_id = update.effective_user.id
            user_name = update.effective_user.first_name or "Пользователь"
            
            await self._show_typing(user_id, context, 1.0)
            
            # Получить или создать сессию
            session = await self.data_manager.get_session(user_id)
            if not session:
                session = await self.data_manager.create_session(user_id)
            
            await self.data_manager.update_status(user_id, SessionStatus.IN_PROGRESS)
            
            welcome_text = f"""
🎯 *БИЗНЕС-НАВИГАТОР v7.0 (DEMO)*

Привет, {user_name}! 👋

Я помогу вам найти идеальную бизнес-нишу.
Сейчас я задам `{self.total_questions}` вопросов с разными типами ответов.

📋 *Типы вопросов:*
• 🔘 Кнопки выбора
• ☑️ Мультиселект
• 🎚️ Слайдеры
• ⭐ Рейтинги
• 📝 Текстовые ответы

⏱️ Время: 3-5 минут
⚠️ _Бот в демонстрационном режиме_

Готовы начать?
"""
            
            keyboard = [
                [InlineKeyboardButton("✅ Начать анкету", callback_data="start_q1")],
                [InlineKeyboardButton("ℹ️ О боте", callback_data="about")]
            ]
            
            await update.message.reply_text(
                welcome_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            return ConversationState.DEMO_AGE.value
            
        except Exception as e:
            logger.error(f"Ошибка в start_questionnaire: {e}", exc_info=True)
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
            return ConversationHandler.END
    
    async def show_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE, question_id: str) -> None:
        """Показать вопрос пользователю"""
        try:
            user_id = update.effective_user.id
            await self._show_typing(user_id, context, 0.8)
            
            query = update.callback_query if hasattr(update, 'callback_query') else None
            session = await self.data_manager.get_session(user_id)
            
            if not session:
                if query:
                    await query.answer("Сессия не найдена. Начните с /start", show_alert=True)
                return
            
            # Получить вопрос из конфига
            from config.settings import config
            question_data = config.get_question_by_id(question_id)
            
            if not question_data:
                logger.error(f"Вопрос {question_id} не найден")
                if query:
                    await query.answer("Ошибка загрузки вопроса", show_alert=True)
                return
            
            # Обновить навигацию
            category = question_data.get('category', 'start')
            question_num = int(question_id[1:])  # "Q1" -> 1
            session.add_to_navigation(category, question_num)
            session.current_question = question_num
            session.current_category = category
            await self.data_manager.update_session(session)
            
            # Форматировать текст
            category_emoji = self.category_emojis.get(category, '📝')
            question_text = question_data.get('text', '')
            
            formatted_text = QuestionFormatter.format_with_context(
                question_text,
                question_num,
                total_questions=self.total_questions,
                category_emoji=category_emoji
            )
            
            # Создать клавиатуру
            keyboard = self._create_keyboard(question_data, session)
            
            if query:
                await query.edit_message_text(
                    formatted_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    formatted_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Ошибка в show_question: {e}", exc_info=True)
    
    def _create_keyboard(self, question_data: Dict[str, Any], session: UserSession) -> Optional[InlineKeyboardMarkup]:
        """Создать клавиатуру для вопроса"""
        try:
            question_type = question_data.get('type', 'text')
            question_id = question_data.get('id', 'Q1')
            
            # Текстовые вопросы без кнопок
            if question_type in ['text', 'existential_text']:
                return None
            
            keyboard: List[List[InlineKeyboardButton]] = []
            
            if question_type == 'quick_buttons':
                for option in question_data.get('options', []):
                    emoji = option.get('emoji', '')
                    label = option.get('label', '')
                    value = option.get('value', '')
                    keyboard.append([InlineKeyboardButton(f"{emoji} {label}", callback_data=f"answer:{value}")])
            
            elif question_type == 'multi_select':
                selected = session.temp_data.get(f"{question_id}_selected", [])
                for option in question_data.get('options', []):
                    value = option.get('value', '')
                    emoji = option.get('emoji', '')
                    label = option.get('label', '')
                    checkmark = "✅ " if value in selected else ""
                    keyboard.append([InlineKeyboardButton(f"{checkmark}{emoji} {label}", callback_data=f"multiselect:{value}")])
                
                validation = question_data.get('validation', {})
                min_choices = validation.get('min_choices', 1)
                if len(selected) >= min_choices:
                    keyboard.append([InlineKeyboardButton("✅ Продолжить", callback_data="submit")])
            
            elif question_type == 'energy_distribution':
                energy_levels = session.temp_data.get(f"{question_id}_energy", {})
                for period in question_data.get('time_periods', []):
                    period_id = period.get('period', '')
                    label = period.get('label', '')
                    emoji = period.get('emoji', '')
                    current = energy_levels.get(period_id, 4)
                    
                    keyboard.append([InlineKeyboardButton(f"{emoji} {label}: {current}/7", callback_data="info")])
                    row = []
                    if current > 1:
                        row.append(InlineKeyboardButton("➖", callback_data=f"energy_dec:{period_id}"))
                    row.append(InlineKeyboardButton(f"{current}", callback_data="info"))
                    if current < 7:
                        row.append(InlineKeyboardButton("➕", callback_data=f"energy_inc:{period_id}"))
                    keyboard.append(row)
                
                if len(energy_levels) == len(question_data.get('time_periods', [])):
                    keyboard.append([InlineKeyboardButton("✅ Продолжить", callback_data="submit")])
            
            elif question_type == 'skill_rating':
                ratings = session.temp_data.get(f"{question_id}_ratings", {})
                for skill in question_data.get('skills', []):
                    skill_id = skill.get('id', '')
                    label = skill.get('label', '')
                    emoji = skill.get('emoji', '')
                    current = ratings.get(skill_id, 0)
                    
                    stars = "⭐" * current + "☆" * (5 - current)
                    keyboard.append([InlineKeyboardButton(f"{emoji} {label}", callback_data="info")])
                    keyboard.append([InlineKeyboardButton(f"{stars}", callback_data="info")])
                    
                    row = []
                    for i in range(1, 6):
                        row.append(InlineKeyboardButton(str(i), callback_data=f"rating:{skill_id}:{i}"))
                    keyboard.append(row)
                
                if len(ratings) == len(question_data.get('skills', [])):
                    keyboard.append([InlineKeyboardButton("✅ Продолжить", callback_data="submit")])
            
            elif question_type == 'learning_allocation':
                allocation = session.temp_data.get(f"{question_id}_allocation", {})
                total_points = question_data.get('total_points', 10)
                used = sum(allocation.values())
                remaining = total_points - used
                
                for fmt in question_data.get('formats', []):
                    fmt_id = fmt.get('id', '')
                    label = fmt.get('label', '')
                    emoji = fmt.get('emoji', '')
                    current = allocation.get(fmt_id, 0)
                    
                    keyboard.append([InlineKeyboardButton(f"{emoji} {label}: {current}", callback_data="info")])
                    row = []
                    if current > 0:
                        row.append(InlineKeyboardButton("➖", callback_data=f"alloc_dec:{fmt_id}"))
                    row.append(InlineKeyboardButton(f"{current}", callback_data="info"))
                    if remaining > 0:
                        row.append(InlineKeyboardButton("➕", callback_data=f"alloc_inc:{fmt_id}"))
                    keyboard.append(row)
                
                keyboard.append([InlineKeyboardButton(f"📊 Осталось: {remaining}/{total_points}", callback_data="info")])
                
                if remaining == 0:
                    keyboard.append([InlineKeyboardButton("✅ Продолжить", callback_data="submit")])
            
            elif question_type == 'slider_with_scenario':
                selected_option = session.temp_data.get(f"{question_id}_option")
                
                if not selected_option:
                    for option in question_data.get('options', []):
                        label = option.get('label', '')
                        value = option.get('value', '')
                        keyboard.append([InlineKeyboardButton(label, callback_data=f"slider_option:{value}")])
                else:
                    slider_data = question_data.get('slider', {})
                    current_val = session.temp_data.get(f"{question_id}_value", 5)
                    min_val = slider_data.get('min', 1)
                    max_val = slider_data.get('max', 10)
                    
                    keyboard.append([InlineKeyboardButton(f"Уровень: {current_val}/{max_val}", callback_data="info")])
                    row = []
                    if current_val > min_val:
                        row.append(InlineKeyboardButton("➖", callback_data="slider_dec"))
                    row.append(InlineKeyboardButton(f"{current_val}", callback_data="info"))
                    if current_val < max_val:
                        row.append(InlineKeyboardButton("➕", callback_data="slider_inc"))
                    keyboard.append(row)
                    keyboard.append([InlineKeyboardButton("✅ Продолжить", callback_data="submit")])
            
            elif question_type == 'scenario_test':
                for option in question_data.get('options', []):
                    label = option.get('label', '')
                    value = option.get('value', '')
                    desc = option.get('description', '')
                    keyboard.append([InlineKeyboardButton(label, callback_data=f"scenario:{value}")])
                    if desc:
                        keyboard.append([InlineKeyboardButton(f"   └─ {desc}", callback_data="info")])
            
            elif question_type == 'confirmation':
                keyboard.append([InlineKeyboardButton("✅ Завершить анкету", callback_data="submit")])
            
            # Кнопка назад (кроме первого вопроса)
            if question_id != 'Q1':
                keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])
            
            return InlineKeyboardMarkup(keyboard) if keyboard else None
            
        except Exception as e:
            logger.error(f"Ошибка в _create_keyboard: {e}", exc_info=True)
            return None
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработать callback от кнопок"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = update.effective_user.id
            session = await self.data_manager.get_session(user_id)
            
            if not session:
                await query.edit_message_text("Сессия истекла. Начните с /start")
                return ConversationHandler.END
            
            callback_data = query.data
            await self._show_typing(user_id, context, 0.5)
            
            # Обработка разных типов callback
            if callback_data.startswith("start_q"):
                await self.show_question(update, context, "Q1")
                return ConversationState.DEMO_AGE.value
            
            elif callback_data.startswith("answer:"):
                return await self._handle_simple_answer(update, context, session)
            
            elif callback_data.startswith("multiselect:"):
                return await self._handle_multiselect(update, context, session)
            
            elif callback_data.startswith("scenario:"):
                return await self._handle_scenario(update, context, session)
            
            elif callback_data.startswith("slider_option:") or callback_data in ["slider_inc", "slider_dec"]:
                return await self._handle_slider(update, context, session)
            
            elif callback_data.startswith("rating:"):
                return await self._handle_rating(update, context, session)
            
            elif callback_data.startswith("alloc_inc:") or callback_data.startswith("alloc_dec:"):
                return await self._handle_allocation(update, context, session)
            
            elif callback_data.startswith("energy_inc:") or callback_data.startswith("energy_dec:"):
                return await self._handle_energy(update, context, session)
            
            elif callback_data == "submit":
                return await self._submit_answer(update, context, session)
            
            elif callback_data == "back":
                return await self._go_back(update, context, session)
            
            elif callback_data == "info":
                await query.answer("ℹ️ Информация", show_alert=False)
                return session.current_question
            
            elif callback_data == "restart_questionnaire":
                return await self._restart_questionnaire(update, context, session)
            
            elif callback_data == "continue_questionnaire":
                next_q_id = f"Q{session.current_question + 1}"
                await self.show_question(update, context, next_q_id)
                return self._get_state_for_question(next_q_id)
            
            else:
                await query.answer("Неизвестная команда", show_alert=False)
                return session.current_question
                
        except Exception as e:
            logger.error(f"Ошибка в handle_callback: {e}", exc_info=True)
            return ConversationHandler.END
    
    async def _handle_simple_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Обработать простой ответ"""
        try:
            query = update.callback_query
            answer_value = query.data.split(":", 1)[1]
            current_q_id = f"Q{session.current_question}"
            
            await self.data_manager.save_answer(session.user_id, current_q_id, answer_value)
            return await self._proceed_to_next(update, context, session)
        except Exception as e:
            logger.error(f"Ошибка в _handle_simple_answer: {e}", exc_info=True)
            return session.current_question
    
    async def _handle_multiselect(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Обработать множественный выбор"""
        try:
            query = update.callback_query
            value = query.data.split(":", 1)[1]
            current_q_id = f"Q{session.current_question}"
            temp_key = f"{current_q_id}_selected"
            
            selected = session.temp_data.get(temp_key, [])
            
            if value in selected:
                selected.remove(value)
            else:
                from config.settings import config
                question_data = config.get_question_by_id(current_q_id)
                validation = question_data.get('validation', {})
                max_choices = validation.get('max_choices', 10)
                
                if len(selected) >= max_choices:
                    await query.answer(f"⚠️ Максимум {max_choices} вариантов", show_alert=True)
                    return session.current_question
                
                selected.append(value)
            
            await self.data_manager.update_temp_data(session.user_id, temp_key, selected)
            await self.show_question(update, context, current_q_id)
            
            return session.current_question
        except Exception as e:
            logger.error(f"Ошибка в _handle_multiselect: {e}", exc_info=True)
            return session.current_question
    
    async def _handle_scenario(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Обработать сценарный ответ"""
        try:
            query = update.callback_query
            value = query.data.split(":", 1)[1]
            current_q_id = f"Q{session.current_question}"
            
            await self.data_manager.save_answer(session.user_id, current_q_id, value)
            return await self._proceed_to_next(update, context, session)
        except Exception as e:
            logger.error(f"Ошибка в _handle_scenario: {e}", exc_info=True)
            return session.current_question
    
    async def _handle_slider(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Обработать слайдер"""
        try:
            query = update.callback_query
            callback_data = query.data
            current_q_id = f"Q{session.current_question}"
            
            from config.settings import config
            question_data = config.get_question_by_id(current_q_id)
            slider_data = question_data.get('slider', {})
            
            if callback_data.startswith("slider_option:"):
                option = callback_data.split(":", 1)[1]
                await self.data_manager.update_temp_data(session.user_id, f"{current_q_id}_option", option)
                initial_value = (slider_data.get('min', 1) + slider_data.get('max', 10)) // 2
                await self.data_manager.update_temp_data(session.user_id, f"{current_q_id}_value", initial_value)
            
            elif callback_data == "slider_inc":
                current_value = session.temp_data.get(f"{current_q_id}_value", 5)
                if current_value < slider_data.get('max', 10):
                    await self.data_manager.update_temp_data(session.user_id, f"{current_q_id}_value", current_value + 1)
            
            elif callback_data == "slider_dec":
                current_value = session.temp_data.get(f"{current_q_id}_value", 5)
                if current_value > slider_data.get('min', 1):
                    await self.data_manager.update_temp_data(session.user_id, f"{current_q_id}_value", current_value - 1)
            
            await self.show_question(update, context, current_q_id)
            return session.current_question
        except Exception as e:
            logger.error(f"Ошибка в _handle_slider: {e}", exc_info=True)
            return session.current_question
    
    async def _handle_rating(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Обработать рейтинг"""
        try:
            query = update.callback_query
            _, skill_id, rating = query.data.split(":")
            rating = int(rating)
            
            current_q_id = f"Q{session.current_question}"
            temp_key = f"{current_q_id}_ratings"
            
            ratings = session.temp_data.get(temp_key, {})
            ratings[skill_id] = rating
            await self.data_manager.update_temp_data(session.user_id, temp_key, ratings)
            
            await self.show_question(update, context, current_q_id)
            return session.current_question
        except Exception as e:
            logger.error(f"Ошибка в _handle_rating: {e}", exc_info=True)
            return session.current_question
    
    async def _handle_allocation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Обработать распределение баллов"""
        try:
            query = update.callback_query
            callback_data = query.data
            current_q_id = f"Q{session.current_question}"
            
            from config.settings import config
            question_data = config.get_question_by_id(current_q_id)
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
            
            await self.show_question(update, context, current_q_id)
            return session.current_question
        except Exception as e:
            logger.error(f"Ошибка в _handle_allocation: {e}", exc_info=True)
            return session.current_question
    
    async def _handle_energy(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Обработать энергию"""
        try:
            query = update.callback_query
            callback_data = query.data
            current_q_id = f"Q{session.current_question}"
            
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
            
            await self.show_question(update, context, current_q_id)
            return session.current_question
        except Exception as e:
            logger.error(f"Ошибка в _handle_energy: {e}", exc_info=True)
            return session.current_question
    
    async def _submit_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Подтвердить и сохранить ответ"""
        try:
            current_q_id = f"Q{session.current_question}"
            
            from config.settings import config
            question_data = config.get_question_by_id(current_q_id)
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
                final_answer = session.temp_data.get(f"{current_q_id}_energy", {})
            elif question_type == 'confirmation':
                return await self._complete_questionnaire(update, context, session)
            else:
                return await self._proceed_to_next(update, context, session)
            
            # Валидация
            validation = question_data.get('validation', {})
            if validation.get('sum_equals'):
                expected_sum = validation['sum_equals']
                actual_sum = sum(final_answer.values()) if isinstance(final_answer, dict) else 0
                if actual_sum != expected_sum:
                    query = update.callback_query
                    await query.answer(f"❌ Сумма должна быть {expected_sum}, текущая: {actual_sum}", show_alert=True)
                    return session.current_question
            
            await self.data_manager.save_answer(session.user_id, current_q_id, final_answer)
            
            # Очистить temp_data
            keys_to_clear = [k for k in session.temp_data.keys() if k.startswith(current_q_id)]
            for key in keys_to_clear:
                session.temp_data.pop(key, None)
            await self.data_manager.update_session(session)
            
            return await self._proceed_to_next(update, context, session)
            
        except Exception as e:
            logger.error(f"Ошибка в _submit_answer: {e}", exc_info=True)
            return session.current_question
    
    async def _proceed_to_next(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Перейти к следующему вопросу"""
        try:
            next_num = session.current_question + 1
            
            if next_num > self.total_questions:
                return await self._complete_questionnaire(update, context, session)
            
            next_q_id = f"Q{next_num}"
            await self.show_question(update, context, next_q_id)
            
            return self._get_state_for_question(next_q_id)
        except Exception as e:
            logger.error(f"Ошибка в _proceed_to_next: {e}", exc_info=True)
            return session.current_question
    
    async def _go_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Вернуться к предыдущему вопросу"""
        try:
            prev = session.go_back()
            
            if not prev:
                query = update.callback_query
                await query.answer("Это первый вопрос", show_alert=True)
                return session.current_question
            
            category, question_num = prev
            prev_q_id = f"Q{question_num}"
            
            await self.show_question(update, context, prev_q_id)
            return self._get_state_for_question(prev_q_id)
        except Exception as e:
            logger.error(f"Ошибка в _go_back: {e}", exc_info=True)
            return session.current_question
    
    async def _restart_questionnaire(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Перезапустить анкету"""
        try:
            query = update.callback_query
            
            # Очистить сессию
            session.answers = {}
            session.temp_data = {}
            session.current_question = 1
            session.current_category = "start"
            session.navigation_history = []
            await self.data_manager.update_session(session)
            
            await query.answer("🔄 Анкета сброшена! Начинаем заново.")
            
            # Показать первый вопрос
            await self.show_question(update, context, "Q1")
            
            return ConversationState.DEMO_AGE.value
        except Exception as e:
            logger.error(f"Ошибка в _restart_questionnaire: {e}", exc_info=True)
            return ConversationHandler.END
    
    async def _complete_questionnaire(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Завершить анкету и начать анализ"""
        try:
            query = update.callback_query
            
            await self.data_manager.update_status(session.user_id, SessionStatus.QUESTIONNAIRE_COMPLETED)
            await query.edit_message_text(SuccessMessages.QUESTIONNAIRE_COMPLETED, parse_mode='Markdown')
            
            await self._start_analysis(update, context, session)
            
            return ConversationState.PROCESSING.value
        except Exception as e:
            logger.error(f"Ошибка в _complete_questionnaire: {e}", exc_info=True)
            return ConversationHandler.END
    
    async def _start_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> None:
        """Запустить анализ ответов"""
        try:
            user_id = session.user_id
            await self._show_typing(user_id, context, 2.0)
            
            loading_msg = await context.bot.send_message(
                chat_id=user_id,
                text=LoadingMessages.ANALYZING,
                parse_mode='Markdown'
            )
            
            await asyncio.sleep(2)
            
            analysis = await self.openai_service.analyze_user_profile(update, context, session)
            
            await loading_msg.edit_text(f"✅ Анализ завершен!\n\n{analysis}", parse_mode='Markdown')
            
            await self._generate_niches(update, context, session)
            
        except Exception as e:
            logger.error(f"Ошибка анализа: {e}", exc_info=True)
            try:
                loading_msg = await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ Произошла ошибка при анализе."
                )
            except:
                pass
    
    async def _generate_niches(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> None:
        """Генерация бизнес-ниш"""
        try:
            user_id = session.user_id
            await self._show_typing(user_id, context, 2.0)
            
            loading_msg = await context.bot.send_message(
                chat_id=user_id,
                text=LoadingMessages.GENERATING_NICHES,
                parse_mode='Markdown'
            )
            
            await asyncio.sleep(2)
            
            niches = await self.openai_service.generate_niches(session)
            
            message = "🎯 *НАЙДЕННЫЕ НИШИ:*\n\n"
            keyboard = []
            
            for i, niche in enumerate(niches, 1):
                message += f"{i}. {niche['emoji']} *{niche['name']}*\n"
                message += f"   📊 {niche['category']}\n"
                desc = niche['description'][:80] + "..." if len(niche['description']) > 80 else niche['description']
                message += f"   📝 {desc}\n"
                message += f"   🎯 Риск: {'★' * niche['risk_level']}{'☆' * (5 - niche['risk_level'])}\n"
                message += f"   ⏱️ {niche['time_to_profit']}\n\n"
                
                keyboard.append([InlineKeyboardButton(
                    f"{i}. {niche['emoji']} {niche['name']}",
                    callback_data=f"select_niche_{niche['id']}"
                )])
            
            # Кнопка "Пройти заново" - ИСПРАВЛЕНО
            keyboard.append([InlineKeyboardButton("🔄 Пройти заново", callback_data="restart_questionnaire")])
            
            await loading_msg.edit_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Ошибка генерации ниш: {e}", exc_info=True)
            try:
                loading_msg = await context.bot.send_message(
                    chat_id=session.user_id,
                    text="❌ Ошибка при генерации ниш."
                )
            except:
                pass
    
    def _get_state_for_question(self, question_id: str) -> int:
        """Получить состояние для вопроса"""
        try:
            question_num = int(question_id[1:])
            
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
                10: ConversationState.PROCESSING.value,
            }
            
            return state_map.get(question_num, ConversationState.MAIN_MENU.value)
        except Exception as e:
            logger.error(f"Ошибка в _get_state_for_question: {e}", exc_info=True)
            return ConversationState.MAIN_MENU.value
    
    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработать текстовый ввод"""
        try:
            user_id = update.effective_user.id
            text = update.message.text.strip()
            
            session = await self.data_manager.get_session(user_id)
            if not session:
                await update.message.reply_text("Сессия не найдена. Начните с /start")
                return ConversationHandler.END
            
            current_q_id = f"Q{session.current_question}"
            
            from config.settings import config
            question_data = config.get_question_by_id(current_q_id)
            
            if not question_data:
                return session.current_question
            
            question_type = question_data.get('type', 'text')
            
            if question_type in ['text', 'existential_text']:
                validation = question_data.get('validation', {})
                min_length = validation.get('min_length', 0)
                max_length = validation.get('max_length', 500)
                
                if len(text) < min_length:
                    await update.message.reply_text(f"❌ Минимальная длина: {min_length} символов")
                    return session.current_question
                
                if len(text) > max_length:
                    await update.message.reply_text(f"❌ Максимальная длина: {max_length} символов")
                    return session.current_question
                
                await self.data_manager.save_answer(session.user_id, current_q_id, text)
                
                next_num = session.current_question + 1
                if next_num > self.total_questions:
                    return await self._complete_questionnaire(update, context, session)
                
                next_q_id = f"Q{next_num}"
                await self.show_question(update, context, next_q_id)
                return self._get_state_for_question(next_q_id)
            
            await update.message.reply_text("Пожалуйста, используйте кнопки для ответа.")
            return session.current_question
            
        except Exception as e:
            logger.error(f"Ошибка в handle_text_input: {e}", exc_info=True)
            return ConversationHandler.END


# Глобальный экземпляр
questionnaire_handler = QuestionnaireHandler()
