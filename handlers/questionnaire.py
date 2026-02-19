#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обработчики анкеты v2.0 — Бизнес-Навигатор
Архитектура: Class + Singleton + Wrapper functions
"""
import logging
import asyncio
from typing import Optional, Dict, Any, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import ContextTypes, ConversationHandler

from models.session import UserSession, SessionStatus
from models.enums import ConversationState
from core.question_engine_v2 import QuestionEngineV2
from handlers.ui_components import UIComponents, QuestionFormatter, ErrorMessages, SuccessMessages, LoadingMessages
from services.data_manager import DataManager, data_manager as global_data_manager
from services.openai_service import OpenAIService, openai_service as global_openai_service

logger = logging.getLogger(__name__)


class QuestionnaireHandler:
    """Основной обработчик анкеты"""
    
    def __init__(self, data_manager: DataManager, openai_service: OpenAIService):
        self.dm = data_manager
        self.ai = openai_service
        self.qe = QuestionEngineV2()
        
        self.category_emojis = {
            'demographic': '👤', 'personality': '🧠', 'skills': '💪',
            'values': '💎', 'resources': '🛠️'
        }

    async def _show_typing(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Показать 'бот печатает' с задержкой"""
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
        await asyncio.sleep(1.2)

    async def start_questionnaire(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начать анкету"""
        user_id = update.effective_user.id
        await self._show_typing(update, context, user_id)
        
        session = await self.dm.get_session(user_id) or await self.dm.create_session(user_id)
        await self.dm.update_status(user_id, SessionStatus.IN_PROGRESS)
        
        welcome = f"""
✨ *ДОБРО ПОЖАЛОВАТЬ!* ✨

🚀 *БИЗНЕС-НАВИГАТОР v7.0*
_Интеллектуальный подбор бизнес-ниш_

━━━━━━━━━━━━━━━━━━━━
🎯 *Вас ждёт:*
• 🧠 Психологический анализ
• 💼 Персональные ниши
• 📋 План действий
• ⚡ UX нового поколения

━━━━━━━━━━━━━━━━━━━━
📊 *Процесс:*
1️⃣ 7 интерактивных вопросов
2️⃣ Мгновенный анализ
3️⃣ Готовые рекомендации

💎 *Это демо-версия* технологии.

🚀 *Готовы начать?*
"""
        keyboard = [[
            InlineKeyboardButton("📝 Начать", callback_data="start_q1"),
            InlineKeyboardButton("ℹ️ О проекте", callback_data="about")
        ]]
        
        await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationState.DEMO_AGE.value

    async def show_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE, question_id: str):
        """Показать вопрос"""
        query = update.callback_query if hasattr(update, 'callback_query') else None
        user_id = update.effective_user.id
        
        # 🎨 ТИПИНГ ПЕРЕД КАЖДЫМ ВОПРОСОМ
        await self._show_typing(update, context, user_id)
        
        session = await self.dm.get_session(user_id)
        if not session:
            if query: await query.answer("Сессия не найдена. /start")
            return
        
        qdata = self.qe.get_question(question_id)
        if not qdata:
            logger.error(f"Вопрос {question_id} не найден")
            if query: await query.answer("Ошибка загрузки вопроса")
            return
        
        # Обновляем навигацию
        cat = qdata.get('category')
        qnum = int(question_id[1:])
        session.add_to_navigation(cat, qnum)
        session.current_question = qnum
        session.current_category = cat
        await self.dm.update_session(session)
        
        # Форматируем вопрос
        emoji = self.category_emojis.get(cat, '📝')
        qtext = self.qe.format_question_text(qdata)
        formatted = QuestionFormatter.format_with_context(qtext, qnum, total_questions=7, category_emoji=emoji)
        keyboard = self.qe.create_keyboard(qdata, session)
        
        if query:
            await query.edit_message_text(formatted, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await update.message.reply_text(formatted, reply_markup=keyboard, parse_mode="Markdown")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработать callback"""
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        session = await self.dm.get_session(user_id)
        
        if not session:
            await query.edit_message_text("Сессия истекла. /start")
            return ConversationHandler.END
        
        cb = query.data
        
        if cb.startswith("start_q"): return await self._start_q(update, context, session)
        elif cb.startswith("answer:"): return await self._simple_answer(update, context, session)
        elif cb.startswith("multiselect:"): return await self._multi_answer(update, context, session)
        elif cb.startswith("scenario:"): return await self._scenario_answer(update, context, session)
        elif cb.startswith("slider_"): return await self._slider_answer(update, context, session)
        elif cb.startswith("rating:"): return await self._rating_answer(update, context, session)
        elif cb.startswith("alloc_"): return await self._alloc_answer(update, context, session)
        elif cb.startswith("energy_"): return await self._energy_answer(update, context, session)
        elif cb.startswith("flow:"): return await self._flow_answer(update, context, session)
        elif cb == "submit": return await self._submit_answer(update, context, session)
        elif cb == "back": return await self._go_back(update, context, session)
        elif cb == "info": await query.answer("ℹ️"); return session.current_question
        else: await query.answer("Неизвестная команда"); return session.current_question

    async def _start_q(self, update, context, session):
        await self.show_question(update, context, "Q1")
        return ConversationState.DEMO_AGE.value

    async def _simple_answer(self, update, context, session):
        query = update.callback_query
        value = query.data.split(":", 1)[1]
        qid = f"Q{session.current_question}"
        qdata = self.qe.get_question(qid)
        
        if qdata.get('allow_custom_input') and value == 'custom':
            await self.dm.update_temp_data(session.user_id, f"{qid}_awaiting_custom", True)
            await query.edit_message_text(f"✏️ {qdata.get('custom_input_prompt', 'Введите ответ:')}")
            return ConversationState.DEMO_CITY.value
        
        await self.dm.save_answer(session.user_id, qid, value)
        return await self._next(update, context, session)

    async def _multi_answer(self, update, context, session):
        query = update.callback_query
        value = query.data.split(":", 1)[1]
        qid = f"Q{session.current_question}"
        key = f"{qid}_selected"
        selected = session.temp_data.get(key, [])
        
        if value in selected: selected.remove(value)
        else:
            qdata = self.qe.get_question(qid)
            max_c = qdata.get('validation', {}).get('max_choices', 10)
            if len(selected) >= max_c:
                await query.answer(f"⚠️ Максимум {max_c} вариантов")
                return session.current_question
            selected.append(value)
        
        await self.dm.update_temp_data(session.user_id, key, selected)
        keyboard = self.qe.create_keyboard(self.qe.get_question(qid), session)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return session.current_question

    async def _scenario_answer(self, update, context, session):
        query = update.callback_query
        value = query.data.split(":", 1)[1]
        await self.dm.save_answer(session.user_id, f"Q{session.current_question}", value)
        return await self._next(update, context, session)

    async def _slider_answer(self, update, context, session):
        query = update.callback_query
        cb = query.data
        qid = f"Q{session.current_question}"
        qdata = self.qe.get_question(qid)
        
        if cb.startswith("slider_option:"):
            opt = cb.split(":", 1)[1]
            await self.dm.update_temp_data(session.user_id, f"{qid}_option", opt)
            slider = qdata.get('slider', {})
            init = (slider.get('min', 1) + slider.get('max', 10)) // 2
            await self.dm.update_temp_data(session.user_id, f"{qid}_value", init)
        elif cb == "slider_inc":
            cur = session.temp_data.get(f"{qid}_value", 5)
            mx = qdata.get('slider', {}).get('max', 10)
            if cur < mx: await self.dm.update_temp_data(session.user_id, f"{qid}_value", cur + 1)
        elif cb == "slider_dec":
            cur = session.temp_data.get(f"{qid}_value", 5)
            mn = qdata.get('slider', {}).get('min', 1)
            if cur > mn: await self.dm.update_temp_data(session.user_id, f"{qid}_value", cur - 1)
        
        keyboard = self.qe.create_keyboard(qdata, session)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return session.current_question

    async def _rating_answer(self, update, context, session):
        query = update.callback_query
        _, skill_id, rating = query.data.split(":")
        qid = f"Q{session.current_question}"
        key = f"{qid}_ratings"
        ratings = session.temp_data.get(key, {})
        ratings[skill_id] = int(rating)
        await self.dm.update_temp_data(session.user_id, key, ratings)
        keyboard = self.qe.create_keyboard(self.qe.get_question(qid), session)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return session.current_question

    async def _alloc_answer(self, update, context, session):
        query = update.callback_query
        cb = query.data
        qid = f"Q{session.current_question}"
        qdata = self.qe.get_question(qid)
        total = qdata.get('total_points', 10)
        key = f"{qid}_allocation"
        alloc = session.temp_data.get(key, {})
        
        if cb.startswith("alloc_inc:"):
            fmt_id = cb.split(":", 1)[1]
            if sum(alloc.values()) < total: alloc[fmt_id] = alloc.get(fmt_id, 0) + 1
        elif cb.startswith("alloc_dec:"):
            fmt_id = cb.split(":", 1)[1]
            if alloc.get(fmt_id, 0) > 0: alloc[fmt_id] -= 1
        
        await self.dm.update_temp_data(session.user_id, key, alloc)
        keyboard = self.qe.create_keyboard(qdata, session)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return session.current_question

    async def _energy_answer(self, update, context, session):
        query = update.callback_query
        cb = query.data
        qid = f"Q{session.current_question}"
        qdata = self.qe.get_question(qid)
        
        if cb.startswith("energy_inc:"):
            p = cb.split(":", 1)[1]
            key = f"{qid}_energy"
            el = session.temp_data.get(key, {})
            if el.get(p, 4) < 7: el[p] = el.get(p, 4) + 1; await self.dm.update_temp_data(session.user_id, key, el)
        elif cb.startswith("energy_dec:"):
            p = cb.split(":", 1)[1]
            key = f"{qid}_energy"
            el = session.temp_data.get(key, {})
            if el.get(p, 4) > 1: el[p] = el.get(p, 4) - 1; await self.dm.update_temp_data(session.user_id, key, el)
        elif cb == "energy_next":
            await self.dm.update_temp_data(session.user_id, f"{qid}_step", 'activities')
        elif cb.startswith("activity:"):
            _, act_type, time = cb.split(":")
            key = f"{qid}_activities"
            acts = session.temp_data.get(key, {})
            acts[act_type] = time
            await self.dm.update_temp_data(session.user_id, key, acts)
        
        keyboard = self.qe.create_keyboard(qdata, session)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return session.current_question

    async def _flow_answer(self, update, context, session):
        query = update.callback_query
        value = query.data.split(":", 1)[1]
        qid = f"Q{session.current_question}"
        await self.dm.update_temp_data(session.user_id, f"{qid}_example", value)
        qdata = self.qe.get_question(qid)
        prompt = qdata.get('text_input', {}).get('prompt', 'Опишите ощущения:')
        await query.edit_message_text(f"✏️ {prompt}")
        return ConversationState.VALUES_FLOW.value

    async def _submit_answer(self, update, context, session):
        qid = f"Q{session.current_question}"
        qdata = self.qe.get_question(qid)
        qtype = qdata.get('type')
        
        # Собираем финальный ответ
        ans = None
        if qtype == 'multi_select': ans = session.temp_data.get(f"{qid}_selected", [])
        elif qtype == 'slider_with_scenario': ans = {'option': session.temp_data.get(f"{qid}_option"), 'value': session.temp_data.get(f"{qid}_value")}
        elif qtype == 'skill_rating': ans = session.temp_data.get(f"{qid}_ratings", {})
        elif qtype == 'learning_allocation': ans = session.temp_data.get(f"{qid}_allocation", {})
        elif qtype == 'energy_distribution': ans = {'energy_levels': session.temp_data.get(f"{qid}_energy", {}), 'activities': session.temp_data.get(f"{qid}_activities", {})}
        
        # Валидация
        valid, err = self.qe.validate_answer(qid, ans, session)
        if not valid:
            await update.callback_query.answer(err, show_alert=True)
            return session.current_question
        
        await self.dm.save_answer(session.user_id, qid, ans)
        # Чистим temp
        for k in list(session.temp_data.keys()):
            if k.startswith(qid): session.temp_data.pop(k, None)
        await self.dm.update_session(session)
        
        return await self._next(update, context, session)

    async def _next(self, update, context, session):
        qid = f"Q{session.current_question}"
        next_qid = self.qe.get_next_question_id(qid)
        if not next_qid: return await self._complete(update, context, session)
        await self.show_question(update, context, next_qid)
        return self._state_for_q(next_qid)

    async def _go_back(self, update, context, session):
        prev = session.go_back()
        if not prev:
            await update.callback_query.answer("Это первый вопрос")
            return session.current_question
        cat, qnum = prev
        await self.show_question(update, context, f"Q{qnum}")
        return self._state_for_q(f"Q{qnum}")

    async def _complete(self, update, context, session):
        await self.dm.update_status(session.user_id, SessionStatus.QUESTIONNAIRE_COMPLETED)
        await update.callback_query.edit_message_text(SuccessMessages.QUESTIONNAIRE_COMPLETED, parse_mode="Markdown")
        await self._analyze(update, context, session)
        return ConversationState.PROCESSING.value

    async def _analyze(self, update, context, session):
        user_id = session.user_id
        loading = await context.bot.send_message(chat_id=user_id, text=LoadingMessages.ANALYZING, parse_mode="Markdown")
        await asyncio.sleep(2)
        
        try:
            # MOCK-анализ
            analysis = self._mock_analysis(session)
            session.psychological_analysis = analysis
            await self.dm.update_status(user_id, SessionStatus.ANALYSIS_GENERATED)
            await self.dm.update_session(session)
            await loading.edit_text(f"✅ *Анализ готов!*\n\n{analysis[:400]}...", parse_mode="Markdown")
            await self._generate_niches(update, context, session)
        except Exception as e:
            logger.error(f"Ошибка анализа: {e}")
            await loading.edit_text("❌ Ошибка анализа. Попробуйте позже.", parse_mode="Markdown")

    def _mock_analysis(self, session: UserSession) -> str:
        answers = session.answers
        age = answers.get('Q1', 'не указано')
        risk = answers.get('Q6', {}).get('value', '5') if isinstance(answers.get('Q6'), dict) else '5'
        energy = answers.get('Q7', {}).get('energy_levels', {}) if isinstance(answers.get('Q7'), dict) else {}
        m, d, e = energy.get('morning', 4), energy.get('day', 4), energy.get('evening', 4)
        peak = "утро" if m >= d and m >= e else "день" if d >= e else "вечер"
        
        return f"""
🧠 *ВАШ ПСИХОЛОГИЧЕСКИЙ ПРОФИЛЬ*

━━━━━━━━━━━━━━━━━━━━
👤 *ДЕМОГРАФИЯ:*
• Возраст: {age}
• Профиль: Активный предприниматель

⚡ *ЭНЕРГЕТИКА:*
• Утро: {m}/7 {'🌅'*m}{'▁'*(7-m)}
• День: {d}/7 {'☀️'*d}{'▁'*(7-d)}
• Вечер: {e}/7 {'🌙'*e}{'▁'*(7-e)}
🎯 Пик: *{peak}*

🎲 *РИСК:* {risk}/10
{'🔥 Высокий' if int(risk)>=7 else '⚖️ Умеренный' if int(risk)>=4 else '🔒 Осторожный'}

💎 *ПОТЕНЦИАЛ:*
• Комбинация навыков → цифровые продукты
• Энергетика → проектная работа
• Стиль решений → оптимален для стартапов

━━━━━━━━━━━━━━━━━━━━
🚀 *Система подобрала 3 персональные ниши...*
"""

    async def _generate_niches(self, update, context, session):
        user_id = session.user_id
        loading = await context.bot.send_message(chat_id=user_id, text=LoadingMessages.GENERATING_NICHES, parse_mode="Markdown")
        await asyncio.sleep(2)
        
        niches = self._mock_niches()
        session.generated_niches = niches
        await self.dm.update_session(session)
        await loading.edit_text(niches, parse_mode="Markdown")
        await self._final_presentation(update, context, session)

    def _mock_niches(self) -> str:
        return """
🎯 *ПОДОБРАННЫЕ НИШИ*

━━━━━━━━━━━━━━━━━━━━
🔥 *1. КОНСУЛЬТАЦИИ*
**Категория:** Быстрый старт
**Окупаемость:** 1-3 месяца | **Инвестиции:** от 10,000₽

💻 *2. ОНЛАЙН-КУРСЫ*
**Категория:** Масштабируемый
**Окупаемость:** 2-4 месяца | **Инвестиции:** от 50,000₽

🚀 *3. ФРИЛАНС-УСЛУГИ*
**Категория:** Минимальный риск
**Окупаемость:** 1-2 месяца | **Инвестиции:** от 5,000₽

━━━━━━━━━━━━━━━━━━━━
"""

    async def _final_presentation(self, update, context, session):
        user_id = session.user_id
        await self._show_typing(update, context, user_id)
        
        final = """
🎊 *АНАЛИЗ ЗАВЕРШЁН!*

━━━━━━━━━━━━━━━━━━━━
📊 *РЕЗУЛЬТАТЫ:*
✅ Ответов: *7* | ⚡ Время: *0.3 сек*
🤖 Токенов: *0* (локальная обработка)

━━━━━━━━━━━━━━━━━━━━
🚀 *DEMO UX-ДВИЖОК v7.0*

✨ *Полная версия включает:*
✓ 35 глубоких вопросов
✓ AI-анализ GPT-4
✓ 8 персонализированных ниш
✓ 90-дневный план
✓ PDF-отчёт
✓ Платежи и масштабирование

━━━━━━━━━━━━━━━━━━━━
💡 *ХОТИТЕ ТАКУЮ СИСТЕМУ?*

📩 *Разработчик:* @your_contact

🌐 *Стек:* Python • FastAPI • Telegram Bot • OpenAI • PostgreSQL • Docker

━━━━━━━━━━━━━━━━━━━━
🔄 *Дальше:*
• /restart — Пройти заново
• /start — Главное меню
• /help — Справка

━━━━━━━━━━━━━━━━━━━━
*Спасибо за использование Бизнес-Навигатора!* ✨
"""
        keyboard = [[
            InlineKeyboardButton("🔄 Заново", callback_data="restart_questionnaire"),
            InlineKeyboardButton("🏠 Меню", callback_data="main_menu")
        ], [InlineKeyboardButton("📩 Связаться", url="https://t.me/your_contact")]]
        
        await context.bot.send_message(chat_id=user_id, text=final, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработать текстовый ввод"""
        user_id = update.effective_user.id
        text = update.message.text
        await self._show_typing(update, context, user_id)
        
        session = await self.dm.get_session(user_id)
        if not session:
            await update.message.reply_text("Сессия не найдена. /start")
            return ConversationHandler.END
        
        qid = f"Q{session.current_question}"
        qdata = self.qe.get_question(qid)
        
        # Custom input
        if session.temp_data.get(f"{qid}_awaiting_custom"):
            await self.dm.save_answer(session.user_id, qid, {'type': 'custom', 'value': text})
            session.temp_data.pop(f"{qid}_awaiting_custom", None)
            await self.dm.update_session(session)
            next_qid = self.qe.get_next_question_id(qid)
            if next_qid:
                await self.show_question(update, context, next_qid)
                return self._state_for_q(next_qid)
            else: return await self._complete(update, context, session)
        
        # Текстовые вопросы
        if qdata.get('type') in ['existential_text', 'text']:
            validation = qdata.get('validation', {})
            min_l = validation.get('min_length', 0)
            max_l = validation.get('max_length', 5000)
            if len(text) < min_l:
                await update.message.reply_text(ErrorMessages.format_validation_error('min_length', value=min_l))
                return session.current_question
            if len(text) > max_l:
                await update.message.reply_text(ErrorMessages.format_validation_error('max_length', value=max_l))
                return session.current_question
            
            await self.dm.save_answer(session.user_id, qid, text)
            next_qid = self.qe.get_next_question_id(qid)
            if next_qid:
                await self.show_question(update, context, next_qid)
                return self._state_for_q(next_qid)
            else: return await self._complete(update, context, session)
        
        await update.message.reply_text("Пожалуйста, используйте кнопки для ответа.")
        return session.current_question

    async def cancel_questionnaire(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отменить анкету"""
        user_id = update.effective_user.id
        session = await self.dm.get_session(user_id)
        if session: await self.dm.update_status(user_id, SessionStatus.ABANDONED)
        
        keyboard = [[InlineKeyboardButton("🔄 Заново", callback_data="start_q1")], [InlineKeyboardButton("❌ Выйти", callback_data="exit")]]
        await update.message.reply_text("❌ Анкета отменена. Начните заново в любое время.", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    def _state_for_q(self, qid: str) -> int:
        qnum = int(qid[1:])
        states = {1: ConversationState.DEMO_AGE.value, 2: ConversationState.DEMO_EDUCATION.value, 3: ConversationState.DEMO_CITY.value,
                  4: ConversationState.PERSONALITY_MOTIVATION.value, 5: ConversationState.PERSONALITY_TYPE.value,
                  6: ConversationState.PERSONALITY_RISK.value, 7: ConversationState.PERSONALITY_ENERGY.value}
        return states.get(qnum, ConversationState.MAIN_MENU.value)


# ============================================================================
# SINGLETON + WRAPPER FUNCTIONS (правильная архитектура)
# ============================================================================

# Singleton instance
_questionnaire_handler: Optional[QuestionnaireHandler] = None

def _get_handler() -> QuestionnaireHandler:
    """Получить или создать singleton-инстанс обработчика"""
    global _questionnaire_handler
    if _questionnaire_handler is None:
        _questionnaire_handler = QuestionnaireHandler(
            data_manager=global_data_manager,
            openai_service=global_openai_service
        )
    return _questionnaire_handler


# Standalone wrapper functions для импорта в bot.py
async def start_questionnaire(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Wrapper: начать анкету"""
    return await _get_handler().start_questionnaire(update, context)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Wrapper: обработать callback"""
    return await _get_handler().handle_callback(update, context)

async def handle_question_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Wrapper: обработать текстовый ответ"""
    return await _get_handler().handle_text_input(update, context)

async def cancel_questionnaire(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Wrapper: отменить анкету"""
    return await _get_handler().cancel_questionnaire(update, context)


# Экспорт для импорта
__all__ = [
    'start_questionnaire',
    'handle_callback_query',
    'handle_question_answer',
    'cancel_questionnaire',
    'QuestionnaireHandler'
]
