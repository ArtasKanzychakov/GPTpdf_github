#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обработчики команд бота
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackContext

from models.enums import BotState
from models.session import UserSession
from services.data_manager import data_manager  # глобальный data_manager
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

        # Создаем или получаем сессию пользователя
        session = data_manager.get_session(user_id)

        if not session:
            session = UserSession(
                user_id=user_id,
                created_at=datetime.now()
            )
            # сохраняем доп. данные отдельно
            session.username = user.username or ""
            session.full_name = user.full_name or ""
            session.last_interaction = datetime.now()

            data_manager.save_session(session)
            logger.info(f"📝 Создана новая сессия для пользователя {user_id}")
        else:
            session.username = user.username or session.username
            session.full_name = user.full_name or session.full_name
            session.last_interaction = datetime.now()
            data_manager.save_session(session)
            logger.info(f"📝 Обновлена сессия для пользователя {user_id}")

        welcome_text = (
            f"👋 Привет, {user_name}!\n\n"
            f"Добро пожаловать в *Бизнес-Навигатор v7.0* 🚀\n\n"
            f"Я помогу тебе найти идеальную бизнес-нишу на основе твоей личности, "
            f"навыков и целей.\n\n"
            f"🔍 *Что я делаю:*\n"
            f"• Проведу глубокий психологический анализ\n"
            f"• Подберу подходящие бизнес-ниши\n"
            f"• Создам детальный план действий\n"
            f"• Помогу избежать типичных ошибок\n\n"
            f"📊 *Как это работает:*\n"
            f"1. Пройди анкету из 35 вопросов\n"
            f"2. Получи психологический анализ\n"
            f"3. Выбери подходящие ниши\n"
            f"4. Получи детальный план действий\n\n"
            f"🚀 *Начнем?*\n"
            f"Просто напиши /questionnaire или нажми кнопку ниже👇"
        )

        keyboard = [
            [
                InlineKeyboardButton("📝 Начать анкету", callback_data="start_questionnaire"),
                InlineKeyboardButton("ℹ️ Помощь", callback_data="help_info")
            ]
        ]

        await update.message.reply_text(
            text=welcome_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        session.current_state = BotState.START
        data_manager.save_session(session)

    except Exception as e:
        logger.error(f"❌ Ошибка в start_command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при запуске бота. Попробуйте позже."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "📚 *Помощь по Бизнес-Навигатору v7.0*\n\n"
        "🤖 *Доступные команды:*\n"
        "• /start - Запустить бота\n"
        "• /help - Эта справка\n"
        "• /questionnaire - Начать анкету\n"
        "• /stats - Статистика бота\n"
        "• /balance - Проверить баланс OpenAI\n"
        "• /restart - Начать заново\n\n"
        "📊 *Процесс работы:*\n"
        "1. Пройдите анкету (35 вопросов)\n"
        "2. Получите психологический анализ\n"
        "3. Выберите подходящие ниши\n"
        "4. Получите детальный план\n\n"
        "📞 *Поддержка:*\n"
        "По вопросам работы бота обращайтесь к разработчику."
    )

    await update.message.reply_text(
        text=help_text,
        parse_mode="Markdown"
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stats"""
    try:
        stats = data_manager.statistics

        stats_text = (
            f"📊 *Статистика Бизнес-Навигатора v7.0*\n\n"
            f"👥 Пользователей: {stats.total_users}\n"
            f"📋 Сессий: {stats.total_sessions}\n"
            f"✅ Завершено: {stats.completed_sessions}\n"
            f"💬 Сообщений: {stats.total_messages}\n"
            f"⚡ Активных: {stats.active_sessions}\n"
            f"⏱️ Uptime: {stats.get_uptime()}\n\n"
        )

        await update.message.reply_text(
            text=stats_text,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"❌ Ошибка в stats_command: {e}")
        await update.message.reply_text(
            "📊 Статистика временно недоступна"
        )


async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /restart"""
    try:
        user_id = update.effective_user.id
        session = data_manager.get_session(user_id)

        if not session:
            await update.message.reply_text(
                "У вас нет активной сессии. Используйте /start."
            )
            return

        reply_markup = create_restart_keyboard()

        await update.message.reply_text(
            text="🔄 Вы уверены, что хотите начать заново?",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"❌ Ошибка в restart_command: {e}")


async def questionnaire_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /questionnaire"""
    try:
        user_id = update.effective_user.id
        session = data_manager.get_or_create_session(user_id)

        session.current_state = BotState.START
        session.current_question_index = 0
        session.last_interaction = datetime.now()
        data_manager.save_session(session)

        await update.message.reply_text(
            "📝 Начинаем анкету!\n\nГотовься отвечать честно 🙂"
        )

    except Exception as e:
        logger.error(f"❌ Ошибка в questionnaire_command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Не удалось запустить анкету."
        )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /status"""
    try:
        user_id = update.effective_user.id
        session = data_manager.get_session(user_id)

        if not session:
            await update.message.reply_text(
                "📭 У вас нет активной сессии."
            )
            return

        status_text = format_session_summary(session)

        await update.message.reply_text(
            text=status_text,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"❌ Ошибка в status_command: {e}")


async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда отладки"""
    try:
        debug_info = (
            f"🐛 Debug\n\n"
            f"Sessions: {len(data_manager.sessions)}\n"
            f"Time: {datetime.now()}"
        )

        await update.message.reply_text(debug_info)

    except Exception as e:
        logger.error(f"❌ Ошибка в debug_command: {e}")


__all__ = [
    'start_command',
    'help_command', 
    'stats_command',
    'restart_command',
    'questionnaire_command',
    'status_command',
    'debug_command'
]