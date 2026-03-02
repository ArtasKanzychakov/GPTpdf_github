#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обработчики для анкетирования - UX IMPROVED v7.1
"""
import logging
import asyncio
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from models.session import UserSession, SessionStatus
from models.enums import ConversationState
from handlers.ui_components import UIComponents, QuestionFormatter, LoadingMessages, SuccessMessages
from services.data_manager import data_manager
from services.openai_service import openai_service

logger = logging.getLogger(__name__)


class QuestionnaireHandler:
    """Обработчик анкетирования с улучшенным UX"""
    
    def __init__(self):
        self.data_manager = data_manager
        self.openai_service = openai_service
        
        self.category_emojis = {
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
        
        self.category_names = {
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
        
        # Сообщения-подсказки для каждого типа вопроса
        self.interaction_hints = {
            'quick_buttons': '💡 *Как ответить:* Нажмите на одну кнопку',
            'multi_select': '💡 *Как ответить:* Нажмите на несколько кнопок (минимум 1)',
            'energy_distribution': '💡 *Как ответить:* Используйте ➕ и ➖ для каждого периода',
            'skill_rating': '💡 *Как ответить:* Нажмите на цифру 1-5 для каждого навыка',
            'learning_allocation': '💡 *Как ответить:* Распределите 10 баллов между форматами (➕➖)',
            'slider_with_scenario': '💡 *Как ответить:* Сначала выберите сценарий, затем настройте уровень',
            'scenario_test': '💡 *Как ответить:* Выберите один вариант',
            'text': '💡 *Как ответить:* Напишите ответ текстом',
            'existential_text': '💡 *Как ответить:* Напишите развёрнутый ответ (необязательно)',
            'confirmation': '💡 *Как ответить:* Нажмите "Завершить анкету"'
        }
        
        # Поздравления между секциями
        self.section_celebrations = {
            3: '🎉 *Отлично!* Первый раздел завершён!\n\nПереходим к вопросам о личности...',
            5: '🌟 *Превосходно!* Halfway there!\n\nТеперь давайте оценим ваши навыки...',
            7: '🚀 *Вы молодец!* Осталось всего 3 вопроса!\n\nПоследняя прямая...',
            9: '🏆 *Финишная прямая!* Последний вопрос!'
        }
        
        self.total_questions = 10
    
    async def _show_typing(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE, seconds: float = 1.0):
        """Показать индикатор набора текста"""
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action='typing')
            await asyncio.sleep(seconds)
        except:
            pass
    
    async def _show_temp_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                  text: str, seconds: float = 3.0):
        """Показать временное сообщение (исчезнет через N секунд)"""
        try:
            if hasattr(update, 'callback_query') and update.callback_query:
                msg = await update.callback_query.message.reply_text(
                    text, 
                    parse_mode='Markdown'
                )
            else:
                msg = await update.message.reply_text(
                    text, 
                    parse_mode='Markdown'
                )
            await asyncio.sleep(seconds)
            await context.bot.delete_message(chat_id=msg.chat_id, message_id=msg.message_id)
        except:
            pass
    
    async def _edit_or_reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                              text: str, keyboard=None, parse_mode='Markdown'):
        """Умно отправить сообщение (edit если callback, иначе reply)"""
        try:
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(
                    text,
                    reply_markup=keyboard,
                    parse_mode=parse_mode
                )
            else:
                await update.message.reply_text(
                    text,
                    reply_markup=keyboard,
                    parse_mode=parse_mode
                )
        except Exception as e:
            logger.warning(f"Ошибка отправки сообщения: {e}")
            # Fallback - новое сообщение
            try:
                await update.message.reply_text(text, reply_markup=keyboard, parse_mode=parse_mode)
            except:
                pass
    
    async def start_questionnaire(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начать анкетирование"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "Пользователь"
        
        await self._show_typing(user_id, context, 1.0)
        
        session = await self.data_manager.get_session(user_id)
        if not session:
            session = await self.data_manager.create_session(user_id)
        
        await self.data_manager.update_status(user_id, SessionStatus.IN_PROGRESS)
        
        welcome_text = f"""
🎯 *БИЗНЕС-НАВИГАТОР v7.0*

Привет, {user_name}! 👋

Я помогу вам найти идеальную бизнес-нишу.
Сейчас я задам `{self.total_questions}` вопросов.

📋 *Вас ждёт:*
• 🔘 Кнопки выбора
• ☑️ Мультиселект
• 🎚️ Слайдеры и рейтинги
• 📝 Текстовые ответы

⏱️ Время: 3-5 минут

💡 *Совет:* Отвечайте честно — это важно для точного анализа!

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
    
    async def show_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE, question_id: str):
        """Показать вопрос пользователю"""
        user_id = update.effective_user.id
        
        await self._show_typing(user_id, context, 0.8)
        
        query = update.callback_query if hasattr(update, 'callback_query') else None
        session = await self.data_manager.get_session(user_id)
        
        if not session:
            if query:
                await query.answer("Сессия не найдена. Начните с /start", show_alert=True)
            return
        
        from config.settings import config
        question_data = config.get_question_by_id(question_id)
        
        if not question_data:
            logger.error(f"Вопрос {question_id} не найден")
            return
        
        # Обновить навигацию
        category = question_data.get('category', 'start')
        question_num = int(question_id[1:])
        session.add_to_navigation(category, question_num)
        session.current_question = question_num
        session.current_category = category
        await self.data_manager.update_session(session)
        
        # Проверить поздравление с завершением секции
        celebration_text = self.section_celebrations.get(question_num - 1)
        if celebration_text and query:
            await self._show_temp_message(update, context, celebration_text, seconds=2.5)
        
        # Форматировать текст
        category_emoji = self.category_emojis.get(category, '📝')
        question_text = question_data.get('text', '')
        
        formatted_text = QuestionFormatter.format_with_context(
            question_text,
            question_num,
            total_questions=self.total_questions,
            category_emoji=category_emoji
        )
        
        # Добавить подсказку по взаимодействию
        question_type = question_data.get('type', 'text')
        hint = self.interaction_hints.get(question_type, '')
        if hint:
            formatted_text += f"\n\n{hint}"
        
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
    
    def _create_keyboard(self, question_data: dict, session: UserSession) -> Optional[InlineKeyboardMarkup]:
        """Создать клавиатуру для вопроса"""
        question_type = question_data.get('type', 'text')
        question_id = question_data.get('id', 'Q1')
        
        if question_type == 'text' or question_type == 'existential_text':
            return None
        
        keyboard = []
        
        if question_type == 'quick_buttons':
            for option in question_data.get('options', []):
                emoji = option.get('emoji', '')
                label = option.get('label', '')
                value = option.get('value', '')
                keyboard.append([InlineKeyboardButton(f"{emoji} {label}", callback_data=f"answer:{value}")])
            
            # ✅ Кнопка продолжить всегда доступна
            keyboard.append([InlineKeyboardButton("⏭️ Пропустить", callback_data="submit")])
        
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
            
            # Статус выбора
            status = f"📊 Выбрано: {len(selected)}"
            keyboard.append([InlineKeyboardButton(status, callback_data="info")])
            
            # ✅ Кнопка продолжить всегда доступна (даже если 0 выбрано)
            keyboard.append([InlineKeyboardButton("✅ Продолжить", callback_data="submit")])
        
        elif question_type == 'energy_distribution':
            energy_levels = session.temp_data.get(f"{question_id}_energy", {})
            for period in question_data.get('time_periods', []):
                period_id = period.get('period', '')
                label = period.get('label', '')
                emoji = period.get('emoji', '')
                current = energy_levels.get(period_id, 4)  # ✅ Дефолт 4
                
                keyboard.append([InlineKeyboardButton(f"{emoji} {label}: {current}/7", callback_data="info")])
                row = []
                if current > 1:
                    row.append(InlineKeyboardButton("➖", callback_data=f"energy_dec:{period_id}"))
                row.append(InlineKeyboardButton(f"{current}", callback_data="info"))
                if current < 7:
                    row.append(InlineKeyboardButton("➕", callback_data=f"energy_inc:{period_id}"))
                keyboard.append(row)
            
            # ✅ Кнопка продолжить всегда доступна
            keyboard.append([InlineKeyboardButton("✅ Продолжить", callback_data="submit")])
        
        elif question_type == 'skill_rating':
            ratings = session.temp_data.get(f"{question_id}_ratings", {})
            for skill in question_data.get('skills', []):
                skill_id = skill.get('id', '')
                label = skill.get('label', '')
                emoji = skill.get('emoji', '')
                current = ratings.get(skill_id, 3)  # ✅ Дефолт 3
                
                stars = "⭐" * current + "☆" * (5 - current)
                keyboard.append([InlineKeyboardButton(f"{emoji} {label}", callback_data="info")])
                keyboard.append([InlineKeyboardButton(f"{stars}", callback_data="info")])
                
                row = []
                for i in range(1, 6):
                    row.append(InlineKeyboardButton(str(i), callback_data=f"rating:{skill_id}:{i}"))
                keyboard.append(row)
            
            # ✅ Кнопка продолжить всегда доступна
            keyboard.append([InlineKeyboardButton("✅ Продолжить", callback_data="submit")])
        
        elif question_type == 'learning_allocation':
            allocation = session.temp_data.get(f"{question_id}_allocation", {})
            total_points = question_data.get('total_points', 10)
            used = sum(allocation.values())
            remaining = total_points - used
            
            # 📌 Инструкция по распределению
            keyboard.append([InlineKeyboardButton("📋 Распределите 10 баллов", callback_data="info")])
            
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
            
            # ✅ Кнопка продолжить всегда доступна (даже если не все распределили)
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
                current_val = session.temp_data.get(f"{question_id}_value", 5)  # ✅ Дефолт 5
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
            
            # ✅ Кнопка продолжить всегда доступна
            keyboard.append([InlineKeyboardButton("⏭️ Пропустить", callback_data="submit")])
        
        elif question_type == 'confirmation':
            keyboard.append([InlineKeyboardButton("✅ Завершить анкету", callback_data="submit")])
        
        # Кнопка назад (кроме первого вопроса)
        if question_id != 'Q1':
            keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])
        
        return InlineKeyboardMarkup(keyboard) if keyboard else None
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработать callback от кнопок"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        session = await self.data_manager.get_session(user_id)
        
        if not session:
            await query.edit_message_text("Сессия истекла. Начните с /start")
            return ConversationHandler.END
        
        callback_data = query.data
        
        await self._show_typing(user_id, context, 0.5)
        
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
        
        return session.current_question
    
    # ... (остальные методы _handle_* остаются как были, с добавлением всегда доступной кнопки submit)
    
    async def _submit_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Подтвердить и сохранить ответ"""
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
                'value': session.temp_data.get(f"{current_q_id}_value", 5)  # ✅ Дефолт
            }
        elif question_type == 'skill_rating':
            temp_key = f"{current_q_id}_ratings"
            final_answer = session.temp_data.get(temp_key, {s['id']: 3 for s in question_data.get('skills', [])})  # ✅ Дефолт 3
        elif question_type == 'learning_allocation':
            temp_key = f"{current_q_id}_allocation"
            final_answer = session.temp_data.get(temp_key, {})
            # ✅ Если ничего не распределили - оставляем пустым или распределяем поровну
            if not final_answer:
                formats = question_data.get('formats', [])
                total = question_data.get('total_points', 10)
                per_format = total // len(formats) if formats else 0
                final_answer = {f['id']: per_format for f in formats}
        elif question_type == 'energy_distribution':
            final_answer = session.temp_data.get(f"{current_q_id}_energy", {'morning': 4, 'day': 4, 'evening': 4})  # ✅ Дефолт
        elif question_type == 'confirmation':
            return await self._complete_questionnaire(update, context, session)
        else:
            return await self._proceed_to_next(update, context, session)
        
        # ⚠️ Валидация только для sum_equals (распределение баллов)
        validation = question_data.get('validation', {})
        if validation.get('sum_equals'):
            expected_sum = validation['sum_equals']
            actual_sum = sum(final_answer.values()) if isinstance(final_answer, dict) else 0
            if actual_sum != expected_sum:
                # ✅ Показываем временное сообщение об ошибке (исчезнет через 3 сек)
                await self._show_temp_message(
                    update, 
                    context, 
                    f"⚠️ Нужно распределить все {expected_sum} баллов!\n\nТекущая сумма: {actual_sum}",
                    seconds=3.0
                )
                return session.current_question
        
        await self.data_manager.save_answer(session.user_id, current_q_id, final_answer)
        
        # Очистить temp_data
        keys_to_clear = [k for k in session.temp_data.keys() if k.startswith(current_q_id)]
        for key in keys_to_clear:
            session.temp_data.pop(key, None)
        await self.data_manager.update_session(session)
        
        return await self._proceed_to_next(update, context, session)
    
    async def _proceed_to_next(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Перейти к следующему вопросу"""
        next_num = session.current_question + 1
        
        if next_num > self.total_questions:
            return await self._complete_questionnaire(update, context, session)
        
        next_q_id = f"Q{next_num}"
        await self.show_question(update, context, next_q_id)
        
        return self._get_state_for_question(next_q_id)
    
    async def _go_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Вернуться к предыдущему вопросу"""
        prev = session.go_back()
        
        if not prev:
            query = update.callback_query
            await query.answer("Это первый вопрос", show_alert=True)
            return session.current_question
        
        category, question_num = prev
        prev_q_id = f"Q{question_num}"
        
        await self.show_question(update, context, prev_q_id)
        return self._get_state_for_question(prev_q_id)
    
    async def _restart_questionnaire(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Перезапустить анкету"""
        query = update.callback_query
        
        # Очистить сессию
        session.answers = {}
        session.temp_data = {}
        session.current_question = 1
        session.current_category = "start"
        session.navigation_history = []
        await self.data_manager.update_session(session)
        
        await query.answer("🔄 Анкета сброшена! Начинаем заново.")
        
        await self.show_question(update, context, "Q1")
        
        return ConversationState.DEMO_AGE.value
    
    async def _complete_questionnaire(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession) -> int:
        """Завершить анкету и начать анализ"""
        query = update.callback_query
        
        await self.data_manager.update_status(session.user_id, SessionStatus.QUESTIONNAIRE_COMPLETED)
        await query.edit_message_text(SuccessMessages.QUESTIONNAIRE_COMPLETED, parse_mode='Markdown')
        
        await self._start_analysis(update, context, session)
        
        return ConversationState.PROCESSING.value
    
    async def _start_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession):
        """Запустить анализ ответов"""
        user_id = session.user_id
        
        await self._show_typing(user_id, context, 2.0)
        
        loading_msg = await context.bot.send_message(
            chat_id=user_id,
            text=LoadingMessages.ANALYZING,
            parse_mode='Markdown'
        )
        
        try:
            await asyncio.sleep(2)
            
            analysis = await self.openai_service.analyze_user_profile(update, context, session)
            
            await loading_msg.edit_text(f"✅ Анализ завершен!\n\n{analysis}", parse_mode='Markdown')
            
            await self._generate_niches(update, context, session)
            
        except Exception as e:
            logger.error(f"Ошибка анализа: {e}")
            await loading_msg.edit_text("❌ Произошла ошибка при анализе.")
    
    async def _generate_niches(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession):
        """Генерация бизнес-ниш"""
        user_id = session.user_id
        
        await self._show_typing(user_id, context, 2.0)
        
        loading_msg = await context.bot.send_message(
            chat_id=user_id,
            text=LoadingMessages.GENERATING_NICHES,
            parse_mode='Markdown'
        )
        
        try:
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
            
            keyboard.append([InlineKeyboardButton("🔄 Пройти заново", callback_data="restart_questionnaire")])
            
            await loading_msg.edit_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Ошибка генерации ниш: {e}")
            await loading_msg.edit_text("❌ Ошибка при генерации ниш.")
    
    def _get_state_for_question(self, question_id: str) -> int:
        """Получить состояние для вопроса"""
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
    
    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработать текстовый ввод"""
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
                # ✅ Временное сообщение об ошибке
                await self._show_temp_message(
                    update, 
                    context, 
                    f"❌ Минимальная длина: {min_length} символов",
                    seconds=3.0
                )
                return session.current_question
            
            if len(text) > max_length:
                await self._show_temp_message(
                    update, 
                    context, 
                    f"❌ Максимальная длина: {max_length} символов",
                    seconds=3.0
                )
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


# Глобальный экземпляр
questionnaire_handler = QuestionnaireHandler()
