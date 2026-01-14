#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обработчики вопросов анкеты
"""

import logging
from typing import Dict, Any, Optional, List
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from models.enums import BotState, QuestionType
from models.session import UserSession
from config.settings import config
from core.question_engine import question_engine
from services.data_manager import data_manager
from utils.formatters import format_question_text

logger = logging.getLogger(__name__)

# Глобальные переменные для управления состоянием мультиселекта
user_multiselect_states = {}  # {user_id: {'selected': [], 'question': {}}}

async def start_questionnaire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать анкету"""
    user = update.effective_user
    user_id = user.id
    
    logger.info(f"Начало анкеты для пользователя {user_id} ({user.username})")
    
    # Получаем или создаем сессию
    session = data_manager.get_session(user_id)
    if not session:
        session = UserSession(
            user_id=user_id,
            username=user.username or "",
            full_name=user.full_name or ""
        )
        data_manager.save_session(session)
    
    # Сбрасываем состояние анкеты
    session.current_state = BotState.DEMOGRAPHY
    session.current_question_index = 0
    session.is_completed = False
    session.completion_date = None
    
    # Приветственное сообщение
    welcome_text = (
        "👋 *Добро пожаловать в Бизнес-Навигатор v7.0!*\n\n"
        "Я помогу вам найти идеальную бизнес-нишу на основе вашей личности, "
        "навыков и целей.\n\n"
        "📋 *Предстоит 35 вопросов* в 5 частях:\n"
        "1. 📊 Демография (3 вопроса)\n"
        "2. 🧠 Личность (11 вопросов)\n"
        "3. 🔧 Навыки (9 вопросов)\n"
        "4. 🌟 Ценности (7 вопросов)\n"
        "5. 🚫 Ограничения (5 вопросов)\n\n"
        "⚠️ *Важно:* Отвечайте честно и подробно. "
        "Каждый ответ влияет на точность рекомендаций.\n\n"
        "Начинаем с первого вопроса..."
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown'
    )
    
    # Показываем первый вопрос
    await show_current_question(update, context, session)

async def show_current_question(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               session: Optional[UserSession] = None):
    """Показать текущий вопрос пользователю"""
    if not session:
        user_id = update.effective_user.id
        session = data_manager.get_session(user_id)
    
    if not session:
        await update.message.reply_text("❌ Сессия не найдена. Начните заново: /start")
        return
    
    # Получаем текущий вопрос
    question = question_engine.get_question_by_index(session.current_question_index)
    if not question:
        logger.error(f"Вопрос не найден для индекса {session.current_question_index}")
        await handle_questionnaire_complete(update, context, session)
        return
    
    # Форматируем текст вопроса
    question_text = question_engine.get_question_text(question, session)
    
    # Получаем подсказку
    help_text = question_engine.get_help_text(question)
    if help_text:
        question_text += f"\n\n💡 *Подсказка:* {help_text}"
    
    # Создаем клавиатуру
    keyboard = question_engine.create_keyboard_for_question(question)
    
    # Отправляем вопрос
    if keyboard:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                question_text,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
        else:
            await update.message.reply_text(
                question_text,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
    else:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                question_text,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                question_text,
                parse_mode='Markdown'
            )
    
    # Сохраняем состояние
    data_manager.save_session(session)

async def handle_text_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать текстовый ответ"""
    user_id = update.effective_user.id
    answer_text = update.message.text.strip()
    
    session = data_manager.get_session(user_id)
    if not session:
        await update.message.reply_text("❌ Сессия не найдена. Начните заново: /start")
        return
    
    # Получаем текущий вопрос
    question = question_engine.get_question_by_index(session.current_question_index)
    if not question:
        await update.message.reply_text("❌ Ошибка: вопрос не найден")
        return
    
    # Проверяем тип вопроса
    question_type = question.get('type', 'text')
    
    if question_type == 'text':
        # Обработка текстового ответа
        is_valid, error_msg = question_engine.validate_answer(question, answer_text)
        if not is_valid:
            await update.message.reply_text(f"❌ {error_msg}\n\nПопробуйте еще раз:")
            return
        
        # Сохраняем ответ
        if question_engine.process_answer(session, question, answer_text):
            # Проверяем, завершена ли анкета
            if session.is_completed:
                await handle_questionnaire_complete(update, context, session)
            else:
                # Показываем следующий вопрос
                await show_current_question(update, context, session)
        else:
            await update.message.reply_text("❌ Ошибка при сохранении ответа")
    
    elif question_type == 'slider':
        # Обработка числового ответа для ползунка
        try:
            value = int(answer_text)
            is_valid, error_msg = question_engine.validate_answer(question, value)
            if not is_valid:
                await update.message.reply_text(f"❌ {error_msg}\n\nВведите число:")
                return
            
            # Форматируем значение
            formatted_value = question_engine.format_slider_value(value, question)
            
            # Сохраняем ответ
            if question_engine.process_answer(session, question, value):
                await update.message.reply_text(
                    f"✅ Сохранено: {formatted_value}\n\nПереходим к следующему вопросу..."
                )
                
                if session.is_completed:
                    await handle_questionnaire_complete(update, context, session)
                else:
                    await show_current_question(update, context, session)
            else:
                await update.message.reply_text("❌ Ошибка при сохранении ответа")
                
        except ValueError:
            await update.message.reply_text(
                "❌ Пожалуйста, введите число.\n\n"
                f"Диапазон: от {question.get('min', 1)} до {question.get('max', 10)}"
            )

async def handle_button_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать ответ через кнопку"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    answer_value = query.data
    
    session = data_manager.get_session(user_id)
    if not session:
        await query.edit_message_text("❌ Сессия не найдена. Начните заново: /start")
        return
    
    # Проверяем, не это ли завершение мультиселекта
    if answer_value == "multiselect_done":
        await handle_multiselect_done(update, context, session)
        return
    
    # Получаем текущий вопрос
    question = question_engine.get_question_by_index(session.current_question_index)
    if not question:
        await query.edit_message_text("❌ Ошибка: вопрос не найден")
        return
    
    question_type = question.get('type', 'buttons')
    
    if question_type == 'multiselect':
        # Обработка мультиселекта
        await handle_multiselect_choice(update, context, session, question, answer_value)
        return
    
    # Обработка обычных кнопок
    is_valid, error_msg = question_engine.validate_answer(question, answer_value)
    if not is_valid:
        await query.edit_message_text(f"❌ {error_msg}")
        return
    
    # Сохраняем ответ
    if question_engine.process_answer(session, question, answer_value):
        # Проверяем, есть ли кастомный ввод
        options = question.get('options', [])
        for option in options:
            if option.get('value') == answer_value and option.get('is_custom'):
                # Запрашиваем кастомный ввод
                custom_prompt = option.get('custom_prompt', 'Введите значение:')
                await query.edit_message_text(custom_prompt, parse_mode='Markdown')
                return
        
        # Проверяем, завершена ли анкета
        if session.is_completed:
            await handle_questionnaire_complete(update, context, session)
        else:
            # Показываем следующий вопрос
            await show_current_question(update, context, session)
    else:
        await query.edit_message_text("❌ Ошибка при сохранении ответа")

async def handle_multiselect_choice(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   session: UserSession, question: Dict[str, Any], 
                                   choice_value: str):
    """Обработать выбор в мультиселекте"""
    user_id = session.user_id
    
    # Убираем префикс "select_"
    if choice_value.startswith("select_"):
        choice_value = choice_value[7:]
    
    # Инициализируем состояние мультиселекта
    if user_id not in user_multiselect_states:
        user_multiselect_states[user_id] = {
            'selected': [],
            'question': question,
            'session': session
        }
    
    state = user_multiselect_states[user_id]
    selected = state['selected']
    
    # Добавляем или удаляем выбор
    if choice_value in selected:
        selected.remove(choice_value)
    else:
        selected.append(choice_value)
    
    # Обновляем клавиатуру
    keyboard = create_updated_multiselect_keyboard(question, selected)
    
    # Обновляем сообщение
    question_text = question_engine.get_question_text(question, session)
    help_text = question_engine.get_help_text(question)
    
    # Добавляем информацию о выбранных элементах
    selected_count = len(selected)
    min_select = question.get('min_selections', 1)
    max_select = question.get('max_selections', 10)
    
    status_text = f"✅ Выбрано: {selected_count} "
    if min_select == max_select:
        status_text += f"(нужно {min_select})"
    else:
        status_text += f"(нужно от {min_select} до {max_select})"
    
    full_text = f"{question_text}\n\n💡 *Подсказка:* {help_text}\n\n{status_text}"
    
    await update.callback_query.edit_message_text(
        full_text,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

async def handle_multiselect_done(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 session: Optional[UserSession] = None):
    """Завершить выбор в мультиселекте"""
    if not session:
        user_id = update.effective_user.id
        session = data_manager.get_session(user_id)
    
    if not session:
        return
    
    user_id = session.user_id
    
    if user_id not in user_multiselect_states:
        await update.callback_query.edit_message_text("❌ Ошибка: состояние выбора не найдено")
        return
    
    state = user_multiselect_states.pop(user_id, None)
    if not state:
        return
    
    selected = state['selected']
    question = state['question']
    
    # Проверяем минимальное количество
    min_select = question.get('min_selections', 1)
    max_select = question.get('max_selections', 10)
    
    if len(selected) < min_select:
        await update.callback_query.edit_message_text(
            f"❌ Выберите хотя бы {min_select} вариант(а)\n\nПродолжаем выбор..."
        )
        # Восстанавливаем состояние
        user_multiselect_states[user_id] = state
        return
    
    if len(selected) > max_select:
        await update.callback_query.edit_message_text(
            f"❌ Выберите не более {max_select} вариантов\n\nПродолжаем выбор..."
        )
        user_multiselect_states[user_id] = state
        return
    
    # Сохраняем ответ
    if question_engine.process_answer(session, question, selected):
        await update.callback_query.edit_message_text(
            f"✅ Сохранено {len(selected)} выборов\n\nПереходим к следующему вопросу..."
        )
        
        # Проверяем, завершена ли анкета
        if session.is_completed:
            await handle_questionnaire_complete(update, context, session)
        else:
            await show_current_question(update, context, session)
    else:
        await update.callback_query.edit_message_text("❌ Ошибка при сохранении ответа")

def create_updated_multiselect_keyboard(question: Dict[str, Any], selected: List[str]) -> InlineKeyboardMarkup:
    """Создать обновленную клавиатуру для мультиселекта"""
    keyboard = []
    options = question.get('options', [])
    
    for option in options:
        option_value = option.get('value', '')
        option_text = option.get('text', '')
        
        # Добавляем или убираем галочку
        if option_value in selected:
            display_text = f"✅ {option_text}"
        else:
            display_text = f"□ {option_text}"
        
        keyboard.append([
            InlineKeyboardButton(display_text, callback_data=f"select_{option_value}")
        ])
    
    # Кнопка завершения
    keyboard.append([
        InlineKeyboardButton("✅ Завершить выбор", callback_data="multiselect_done")
    ])
    
    return InlineKeyboardMarkup(keyboard)

async def handle_questionnaire_complete(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                       session: UserSession):
    """Обработать завершение анкеты"""
    logger.info(f"Анкета завершена для пользователя {session.user_id}")
    
    completion_text = (
        "🎉 *Поздравляю! Вы завершили анкету!*\n\n"
        f"✅ Ответов сохранено: 35 из 35\n"
        f"📊 Прогресс: 100%\n\n"
        "🔄 *Сейчас происходит анализ ваших ответов...*\n\n"
        "Я изучаю:\n"
        "• Ваш психологический профиль\n"
        "• Сильные стороны и потенциал\n"
        "• Подходящие бизнес-ниши\n\n"
        "⏱️ *Это займет около 1-2 минут.*\n"
        "Как только анализ будет готов, я покажу вам подходящие ниши."
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            completion_text,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            completion_text,
            parse_mode='Markdown'
        )
    
    # Сохраняем сессию
    data_manager.save_session(session)
    
    # Запускаем анализ (будет в отдельном обработчике)
    from services.openai_service import analyze_user_profile
    await analyze_user_profile(update, context, session)

async def skip_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропустить вопрос (если разрешено)"""
    user_id = update.effective_user.id
    session = data_manager.get_session(user_id)
    
    if not session:
        await update.message.reply_text("❌ Сессия не найдена")
        return
    
    question = question_engine.get_question_by_index(session.current_question_index)
    if not question:
        await update.message.reply_text("❌ Вопрос не найден")
        return
    
    # Проверяем, можно ли пропустить
    if question.get('skippable', False):
        # Сохраняем пустой ответ
        if question_engine.process_answer(session, question, ""):
            await update.message.reply_text("⏭️ Вопрос пропущен")
            
            if session.is_completed:
                await handle_questionnaire_complete(update, context, session)
            else:
                await show_current_question(update, context, session)
        else:
            await update.message.reply_text("❌ Ошибка при пропуске вопроса")
    else:
        await update.message.reply_text(
            "⚠️ Этот вопрос обязателен для ответа.\n"
            "Пожалуйста, ответьте на него."
        )

async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать прогресс анкеты"""
    user_id = update.effective_user.id
    session = data_manager.get_session(user_id)
    
    if not session:
        await update.message.reply_text("❌ Сессия не найдена. Начните: /start")
        return
    
    progress = session.get_progress_percentage()
    current_q = session.current_question_index + 1
    total_q = question_engine.total_questions
    
    # Определяем текущую часть
    if current_q <= 3:
        part = "Демография"
    elif current_q <= 12:
        part = "Личность"
    elif current_q <= 22:
        part = "Навыки"
    elif current_q <= 29:
        part = "Ценности"
    else:
        part = "Ограничения"
    
    progress_text = (
        f"📊 *Прогресс анкеты*\n\n"
        f"📍 Текущая часть: {part}\n"
        f"📝 Вопросов пройдено: {current_q - 1}/{total_q}\n"
        f"🎯 Прогресс: {progress:.1f}%\n\n"
    )
    
    # Прогресс-бар
    bar_length = 20
    filled = int(bar_length * progress / 100)
    bar = "█" * filled + "░" * (bar_length - filled)
    progress_text += f"[{bar}] {progress:.1f}%\n\n"
    
    if session.is_completed:
        progress_text += "✅ *Анкета завершена!*\nОжидайте результаты анализа..."
    else:
        progress_text += "Продолжайте отвечать на вопросы!"
    
    await update.message.reply_text(progress_text, parse_mode='Markdown')

# Регистрация обработчиков
def register_handlers(application):
    """Зарегистрировать обработчики вопросов"""
    
    # Команды
    application.add_handler(CallbackQueryHandler(handle_button_answer, pattern="^(?!multiselect_).*"))
    application.add_handler(CallbackQueryHandler(handle_multiselect_choice, pattern="^select_.*"))
    application.add_handler(CallbackQueryHandler(handle_multiselect_done, pattern="^multiselect_done$"))
    
    # Текстовые ответы
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_answer))
    
    logger.info("Обработчики вопросов зарегистрированы")