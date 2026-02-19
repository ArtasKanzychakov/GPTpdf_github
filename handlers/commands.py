#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обработчики команд бота
"""
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackContext
from telegram.constants import ChatAction
from models.enums import BotState
from models.session import UserSession
from services.data_manager import data_manager
from utils.formatters import (
    format_session_summary,
    format_recommendations,
    format_answer_summary,
    create_restart_keyboard,
    format_openai_usage,
    format_niche,
    format_analysis
)

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    try:
        user = update.effective_user
        user_id = user.id
        user_name = user.first_name or "Пользователь"
        
        logger.info(f"🚀 Команда /start от пользователя {user_id} ({user_name})")
        
        # Показываем "бот печатает"
        await context.bot.send_chat_action(
            chat_id=user_id,
            action=ChatAction.TYPING
        )
        await asyncio.sleep(1.5)  # Небольшая задержка для эффекта
        
        # Создаем или получаем сессию пользователя
        session = data_manager.get_session(user_id)
        if not session:
            session = UserSession(
                user_id=user_id,
                username=user_name,
                full_name=user.full_name or "",
                created_at=datetime.now()
            )
            data_manager.save_session(session)
            logger.info(f"📝 Создана новая сессия для пользователя {user_id}")
        else:
            session.username = user_name
            session.last_interaction = datetime.now()
            data_manager.save_session(session)
            logger.info(f"📝 Обновлена сессия для пользователя {user_id}")
        
        # 🎨 КРАСИВОЕ ПРИВЕТСТВИЕ
        welcome_text = f"""
✨ *ДОБРО ПОЖАЛОВАТЬ, {user_name.upper()}!* ✨

🚀 *БИЗНЕС-НАВИГАТОР v7.0*
_Интеллектуальная система подбора бизнес-ниш_

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 *Что вас ждёт:*

🧠 Глубокий психологический анализ
💼 Персональные бизнес-ниши
📋 Детальный план действий
⚡ UX-интерфейс нового поколения

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 *Как это работает:*
1️⃣ Пройдите интерактивную анкету
2️⃣ Получите психологический профиль
3️⃣ Выберите подходящие ниши
4️⃣ Скачайте план действий

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💎 *Это демо-версия* для демонстрации
технологии UX-взаимодействия.

🚀 *Готовы начать путешествие?*
"""
        
        # Создаем клавиатуру
        keyboard = [
            [
                InlineKeyboardButton("📝 Начать анкету", callback_data="start_questionnaire"),
                InlineKeyboardButton("ℹ️ О проекте", callback_data="about_project")
            ],
            [
                InlineKeyboardButton("📊 Статистика", callback_data="stats_info"),
                InlineKeyboardButton("❓ Помощь", callback_data="help_info")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            text=welcome_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
        # Обновляем состояние сессии
        session.current_state = BotState.START
        data_manager.save_session(session)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в start_command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при запуске бота. Попробуйте позже."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await context.bot.send_chat_action(
        chat_id=update.effective_user.id,
        action=ChatAction.TYPING
    )
    
    help_text = """
📚 *ПОМОЩЬ | БИЗНЕС-НАВИГАТОР v7.0*

🤖 *Доступные команды:*
• /start - Запустить бота заново
• /help - Эта справка
• /questionnaire - Начать анкету
• /status - Проверить прогресс
• /restart - Начать заново

📊 *Процесс работы:*
1. Пройдите анкету (7 вопросов)
2. Получите психологический анализ
3. Выберите подходящие ниши
4. Получите детальный план

⏱️ *Время прохождения:* 3-5 минут
💾 *Прогресс сохраняется* автоматически

🔒 *Конфиденциальность:*
Все данные обрабатываются локально
и не передаются третьим лицам.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 *Совет:* Отвечайте честно — это
важно для точности рекомендаций!
"""
    await update.message.reply_text(
        text=help_text,
        parse_mode="Markdown"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stats"""
    await context.bot.send_chat_action(
        chat_id=update.effective_user.id,
        action=ChatAction.TYPING
    )
    
    try:
        stats = data_manager.statistics
        stats_text = f"""
📊 *СТАТИСТИКА БИЗНЕС-НАВИГАТОРА v7.0*

👥 Пользователей: {stats.total_users}
📋 Сессий: {stats.total_sessions}
✅ Завершено: {stats.completed_sessions}
💬 Сообщений: {stats.total_messages}
⚡ Активных: {stats.active_sessions}
⏱️ Uptime: {stats.get_uptime()}
"""
        await update.message.reply_text(
            text=stats_text,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в stats_command: {e}")
        await update.message.reply_text("📊 Статистика временно недоступна")

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /restart"""
    await context.bot.send_chat_action(
        chat_id=update.effective_user.id,
        action=ChatAction.TYPING
    )
    
    try:
        user_id = update.effective_user.id
        session = data_manager.get_session(user_id)
        
        if not session:
            await update.message.reply_text(
                "У вас нет активной сессии. Используйте /start для начала работы."
            )
            return
        
        confirm_text = f"""
🔄 *ПЕРезапуск анкеты*

Вы уверены, что хотите начать заново?

📋 *Текущий прогресс:*
• Вопросов пройдено: {session.current_question_index}/7
• Ответов сохранено: {len(session.get_all_answers())}

⚠️ *Внимание:* Все текущие ответы будут удалены!
"""
        reply_markup = create_restart_keyboard()
        await update.message.reply_text(
            text=confirm_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в restart_command: {e}")
        await update.message.reply_text("❌ Произошла ошибка при попытке перезапуска")

async def questionnaire_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /questionnaire"""
    await context.bot.send_chat_action(
        chat_id=update.effective_user.id,
        action=ChatAction.TYPING
    )
    
    try:
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "Пользователь"
        
        logger.info(f"📝 Команда /questionnaire от пользователя {user_id}")
        
        session = data_manager.get_session(user_id)
        if not session:
            session = UserSession(
                user_id=user_id,
                username=update.effective_user.username or "",
                full_name=user_name,
                created_at=datetime.now()
            )
            data_manager.save_session(session)
        
        # Проверяем, есть ли незавершенная анкета
        if session.current_question_index > 0 and session.current_question_index < 7:
            continue_text = f"""
📊 *ПРОДОЛЖИТЬ АНКЕТУ?*

У вас есть незавершенная анкета:
• Пройдено вопросов: {session.current_question_index}/7
• Состояние: {session.current_state.name}

Хотите продолжить с того же места?
"""
            keyboard = [
                [
                    InlineKeyboardButton("✅ Продолжить", callback_data="continue_questionnaire"),
                    InlineKeyboardButton("🔄 Начать заново", callback_data="restart_questionnaire")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                text=continue_text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            return
        
        # Начинаем новую анкету
        from config.settings import config
        if not config.questions:
            await update.message.reply_text(
                "❌ Вопросы не загружены. Обратитесь к администратору."
            )
            return
        
        # Сбрасываем сессию для новой анкеты
        session.current_state = BotState.START
        session.current_question_index = 0
        session.is_completed = False
        session.completion_date = None
        session.analysis_result = ""
        session.suggested_niches = []
        session.selected_niche = None
        session.detailed_plan = ""
        session.last_interaction = datetime.now()
        data_manager.save_session(session)
        
        start_text = f"""
🎯 *НАЧИНАЕМ АНКЕТУ!*

📋 Всего вопросов: *7*
⏱️ Примерное время: *3-5 минут*

💡 *Типы вопросов:*
• 🔘 Выбор из вариантов
• ☑️ Множественный выбор
• 🎚️ Интерактивные слайдеры
• ⭐ Звёздный рейтинг

✨ *Совет:* Отвечайте честно — это
важно для точного анализа!

🚀 *Первый вопрос:*
"""
        await update.message.reply_text(
            text=start_text,
            parse_mode="Markdown"
        )
        
        # Запускаем первый вопрос через QuestionEngine
        from core.question_engine import question_engine
        question = question_engine.get_question_by_index(0)
        
        if question:
            from utils.formatters import format_question_text
            question_text = format_question_text(
                question['text'],
                user_name,
                1,
                7
            )
            keyboard = question_engine.create_keyboard_for_question(question)
            
            # Показываем "бот печатает" перед вопросом
            await context.bot.send_chat_action(
                chat_id=user_id,
                action=ChatAction.TYPING
            )
            await asyncio.sleep(1)
            
            if keyboard:
                await update.message.reply_text(
                    question_text,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            else:
                await update.message.reply_text(
                    question_text,
                    parse_mode='Markdown'
                )
            
            session.current_state = BotState.DEMOGRAPHY
            session.current_question_index = 0
            data_manager.save_session(session)
            
    except Exception as e:
        logger.error(f"❌ Ошибка в questionnaire_command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при запуске анкеты. Попробуйте позже."
        )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /status"""
    await context.bot.send_chat_action(
        chat_id=update.effective_user.id,
        action=ChatAction.TYPING
    )
    
    try:
        user_id = update.effective_user.id
        session = data_manager.get_session(user_id)
        
        if not session:
            await update.message.reply_text(
                "📭 У вас нет активной сессии. Используйте /start для начала работы."
            )
            return
        
        status_text = format_session_summary(session)
        if session.get_all_answers():
            status_text += "\n" + format_answer_summary(session.get_all_answers())
        
        keyboard = []
        if session.current_state in [BotState.DEMOGRAPHY, BotState.PERSONALITY,
                                      BotState.SKILLS, BotState.VALUES, BotState.LIMITATIONS]:
            keyboard.append([InlineKeyboardButton("▶️ Продолжить анкету", callback_data="continue_questionnaire")])
        if session.get_all_answers():
            keyboard.append([InlineKeyboardButton("📊 Показать ответы", callback_data="show_answers")])
        keyboard.append([InlineKeyboardButton("🔄 Начать заново", callback_data="restart_confirm")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            text=status_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в status_command: {e}")
        await update.message.reply_text("📊 Не удалось получить статус сессии")

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для отладки"""
    await context.bot.send_chat_action(
        chat_id=update.effective_user.id,
        action=ChatAction.TYPING
    )
    
    try:
        user_id = update.effective_user.id
        debug_info = f"""
🐛 *ОТЛАДОЧНАЯ ИНФОРМАЦИЯ*

👤 User ID: {user_id}
📊 Всего сессий: {len(data_manager.sessions)}
🕒 Время сервера: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📁 *Конфигурация:*
"""
        from config.settings import config
        debug_info += f"• Вопросов: {len(config.questions)}\n"
        debug_info += f"• Ниш: {len(config.niche_categories)}\n"
        debug_info += f"• Токен бота: {'✅ Установлен' if config.telegram_token else '❌ Отсутствует'}\n"
        debug_info += f"• Токен OpenAI: {'✅ Установлен' if config.openai_api_key else '❌ Отсутствует'}\n"
        
        await update.message.reply_text(
            text=debug_info,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в debug_command: {e}")
        await update.message.reply_text("🐛 Ошибка при получении отладочной информации")

__all__ = [
    'start_command',
    'help_command',
    'stats_command',
    'restart_command',
    'questionnaire_command',
    'status_command',
    'debug_command'
]
