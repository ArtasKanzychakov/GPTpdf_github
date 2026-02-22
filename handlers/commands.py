#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обработчики команд бота - DEMO VERSION
"""
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_name = user.first_name or "Пользователь"
    
    welcome_text = f"""
👋 Привет, {user_name}!
Добро пожаловать в *Бизнес-Навигатор v7.0* 🚀

⚠️ *DEMO MODE*
Бот работает в демонстрационном режиме.
Все функции UI/UX Telegram доступны.
ИИ-анализ будет в полной версии.

📋 *Что я умею:*
• 🔘 Разные типы кнопок
• 🎚️ Интерактивные слайдеры
• ⭐ Рейтинги и оценки
• ☑️ Мультиселект
• 📊 Прогресс-бары
• 📋 Копируемые блоки

🚀 *Начнём?*
Нажмите /questionnaire или кнопку ниже👇
"""
    keyboard = [
        [InlineKeyboardButton("📝 Начать анкету", callback_data="start_questionnaire")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help_info")]
    ]
    
    await update.message.reply_text(
        text=welcome_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
📚 *Помощь по Бизнес-Навигатору v7.0*

🤖 *Доступные команды:*
• /start - Запустить бота
• /help - Эта справка
• /questionnaire - Начать анкету
• /status - Статус сессии
• /restart - Начать заново

📊 *Процесс работы:*
1. Пройдите анкету (10 вопросов)
2. Получите демо-анализ
3. Выберите подходящие ниши
4. Получите демо-план

⚠️ *DEMO MODE:*
• ИИ-функции отключены
• Возвращаются шаблонные ответы
• Полная версия в разработке

📞 *Поддержка:*
По вопросам обращайтесь к разработчику.
"""
    await update.message.reply_text(text=help_text, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /status"""
    user_id = update.effective_user.id
    
    from services.data_manager import data_manager
    session = await data_manager.get_session(user_id)
    
    if not session:
        await update.message.reply_text("📭 У вас нет активной сессии. Используйте /start")
        return
    
    from handlers.ui_components import UIComponents
    
    status_text = f"""
👤 *ВАШ ПРОФИЛЬ*
🆔 ID: `{session.user_id}`
📅 Создана: `{session.created_at.strftime('%d.%m.%Y %H:%M')}`
🔄 Статус: `{'✅ Завершено' if session.status.value == 'completed' else '⏳ В процессе'}`
📝 Прогресс: {UIComponents.create_progress_bar(len(session.answers), 10)}
📊 *Ответов:* `{len(session.answers)}/10`
"""
    keyboard = [
        [InlineKeyboardButton("▶️ Продолжить", callback_data="continue_questionnaire")],
        [InlineKeyboardButton("🔄 Начать заново", callback_data="restart_questionnaire")]
    ]
    
    await update.message.reply_text(
        text=status_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /restart"""
    user_id = update.effective_user.id
    
    from services.data_manager import data_manager
    session = await data_manager.get_session(user_id)
    
    if session:
        session.answers = {}
        session.temp_data = {}
        session.current_question = 1
        session.status = type('obj', (object,), {'value': 'started'})()
        await data_manager.update_session(session)
    
    restart_text = """
🔄 *Анкета сброшена!*
Вы можете начать заново в любое время.

⚠️ _Бот в демонстрационном режиме_
"""
    keyboard = [
        [InlineKeyboardButton("📝 Начать анкету", callback_data="start_q1")]
    ]
    
    await update.message.reply_text(
        text=restart_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def questionnaire_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /questionnaire"""
    from handlers.questionnaire import questionnaire_handler
    await questionnaire_handler.start_questionnaire(update, context)

__all__ = [
    'start_command',
    'help_command',
    'status_command',
    'restart_command',
    'questionnaire_command'
]
