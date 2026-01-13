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
from services.data_manager import data_manager
from utils.formatters import (
    format_session_summary, 
    format_recommendations,
    format_answer_summary,
    create_restart_keyboard,
    format_openai_usage,
    format_niche,  # Добавленная функция
    format_analysis  # Добавленная функция
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
                user_name=user_name,
                created_at=datetime.now()
            )
            data_manager.save_session(session)
            logger.info(f"📝 Создана новая сессия для пользователя {user_id}")
        else:
            session.user_name = user_name
            session.last_activity = datetime.now()
            data_manager.save_session(session)
            logger.info(f"📝 Обновлена сессия для пользователя {user_id}")
        
        # Приветственное сообщение
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
            f"1. Пройди анкету из 18 вопросов\n"
            f"2. Получи психологический анализ\n"
            f"3. Выбери подходящие ниши\n"
            f"4. Получи детальный план действий\n\n"
            f"🚀 *Начнем?*\n"
            f"Просто напиши /questionnaire или нажми кнопку ниже👇"
        )
        
        # Создаем клавиатуру
        keyboard = [
            [
                InlineKeyboardButton("📝 Начать анкету", callback_data="start_questionnaire"),
                InlineKeyboardButton("ℹ️ Помощь", callback_data="help_info")
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
        "1. Пройдите анкету (18 вопросов)\n"
        "2. Получите психологический анализ\n"
        "3. Выберите подходящие ниши\n"
        "4. Получите детальный план\n\n"
        "❓ *Частые вопросы:*\n"
        "• Анкета сохраняет прогресс\n"
        "• Можно прервать и продолжить позже\n"
        "• Все данные конфиденциальны\n"
        "• Анализ занимает 1-2 минуты\n\n"
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
        stats = data_manager.get_statistics()
        
        stats_text = (
            f"📊 *Статистика Бизнес-Навигатора v7.0*\n\n"
            f"👤 Пользователей всего: {stats.total_users}\n"
            f"📝 Активных сессий: {stats.active_sessions}\n"
            f"✅ Завершённых анкет: {stats.completed_questionnaires}\n"
            f"⏱️ Среднее время анкеты: {stats.avg_questionnaire_time:.1f} мин\n"
            f"📅 Бот работает с: {stats.bot_start_time.strftime('%d.%m.%Y')}\n\n"
            f"🎯 *Рекомендации выдано:* {stats.recommendations_given}\n"
            f"💎 *Популярные ниши:*\n"
        )
        
        # Добавляем популярные ниши
        for niche, count in stats.popular_niches[:3]:
            stats_text += f"• {niche}: {count}\n"
        
        if stats.recent_activity:
            stats_text += f"\n🔄 *Недавняя активность:*\n"
            for activity in stats.recent_activity[:2]:
                stats_text += f"• {activity}\n"
        
        await update.message.reply_text(
            text=stats_text,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в stats_command: {e}")
        await update.message.reply_text(
            "📊 Статистика временно недоступна"
        )

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /balance"""
    try:
        from services.openai_service import openai_service
        
        if not openai_service:
            await update.message.reply_text(
                "🤖 OpenAI отключен. Работаем в базовом режиме."
            )
            return
        
        balance_info = await openai_service.get_balance_info()
        
        balance_text = (
            f"💰 *Баланс OpenAI*\n\n"
            f"💳 Текущий баланс: ${balance_info.get('balance', 0):.2f}\n"
            f"📊 Использовано токенов: {balance_info.get('tokens_used', 0)}\n"
            f"📈 Запросов выполнено: {balance_info.get('requests_made', 0)}\n"
            f"⏱️ Последняя проверка: {balance_info.get('last_check', 'никогда')}\n\n"
        )
        
        if balance_info.get('balance_warning', False):
            balance_text += "⚠️ *Внимание:* Баланс заканчивается!\n"
        
        await update.message.reply_text(
            text=balance_text,
            parse_mode="Markdown"
        )
        
    except ImportError:
        await update.message.reply_text(
            "🤖 Модуль OpenAI не настроен"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в balance_command: {e}")
        await update.message.reply_text(
            "💰 Не удалось получить информацию о балансе"
        )

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /restart"""
    try:
        user_id = update.effective_user.id
        
        # Получаем сессию
        session = data_manager.get_session(user_id)
        if not session:
            await update.message.reply_text(
                "У вас нет активной сессии. Используйте /start для начала работы."
            )
            return
        
        # Подтверждение перезапуска
        confirm_text = (
            f"🔄 *Перезапуск анкеты*\n\n"
            f"Вы уверены, что хотите начать анкету заново?\n\n"
            f"📋 *Текущий прогресс:*\n"
            f"• Вопросов пройдено: {session.current_question_index}/18\n"
            f"• Ответов сохранено: {len(session.answers)}\n\n"
            f"⚠️ *Внимание:* Все ваши текущие ответы будут удалены!"
        )
        
        reply_markup = create_restart_keyboard()
        
        await update.message.reply_text(
            text=confirm_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в restart_command: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при попытке перезапуска"
        )

async def questionnaire_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /questionnaire"""
    try:
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "Пользователь"
        
        logger.info(f"📝 Команда /questionnaire от пользователя {user_id}")
        
        # Получаем или создаем сессию
        session = data_manager.get_session(user_id)
        if not session:
            session = UserSession(
                user_id=user_id,
                user_name=user_name,
                created_at=datetime.now()
            )
            data_manager.save_session(session)
        
        # Проверяем, есть ли незавершенная анкета
        if session.current_question_index > 0 and session.current_question_index < 18:
            continue_text = (
                f"📊 *Продолжить анкету?*\n\n"
                f"У вас есть незавершенная анкета:\n"
                f"• Пройдено вопросов: {session.current_question_index}/18\n"
                f"• Состояние: {session.current_state.value}\n\n"
                f"Хотите продолжить с того же места?"
            )
            
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
        from core.bot import bot_instance
        
        if not bot_instance:
            await update.message.reply_text(
                "❌ Бот не инициализирован. Попробуйте позже."
            )
            return
        
        # Сбрасываем сессию для новой анкеты
        session.reset_for_new_questionnaire()
        session.current_state = BotState.START
        data_manager.save_session(session)
        
        start_text = (
            f"🎯 *Начинаем анкету!*\n\n"
            f"Всего вопросов: 18\n"
            f"Примерное время: 5-7 минут\n\n"
            f"📋 *Типы вопросов:*\n"
            f"• 📝 Текстовые ответы\n"
            f"• 🔘 Выбор из вариантов\n"
            f"• ☑️ Множественный выбор\n"
            f"• 🎚️ Слайдеры (оценки)\n\n"
            f"💡 *Совет:*\n"
            f"Отвечайте честно — это важно для точного анализа!\n\n"
            f"🚀 *Первый вопрос:*"
        )
        
        await update.message.reply_text(
            text=start_text,
            parse_mode="Markdown"
        )
        
        # Запускаем первый вопрос через бота
        from config.settings import config
        
        if config.questions:
            first_question = config.questions[0]
            await bot_instance.send_question(user_id, first_question)
        else:
            await update.message.reply_text(
                "❌ Вопросы не загружены. Обратитесь к администратору."
            )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в questionnaire_command: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при запуске анкеты. Попробуйте позже."
        )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /status (статус сессии)"""
    try:
        user_id = update.effective_user.id
        
        session = data_manager.get_session(user_id)
        if not session:
            await update.message.reply_text(
                "📭 У вас нет активной сессии. Используйте /start для начала работы."
            )
            return
        
        status_text = format_session_summary(session)
        
        if session.answers:
            status_text += "\n\n" + format_answer_summary(session.answers)
        
        # Добавляем кнопки действий
        keyboard = []
        
        if session.current_state == BotState.IN_QUESTIONNAIRE and session.current_question_index < 18:
            keyboard.append([InlineKeyboardButton("▶️ Продолжить анкету", callback_data="continue_questionnaire")])
        
        if session.current_question_index > 0:
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
        await update.message.reply_text(
            "📊 Не удалось получить статус сессии"
        )

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для отладки (только для разработчиков)"""
    try:
        user_id = update.effective_user.id
        
        # Проверяем, является ли пользователь разработчиком
        # Можно добавить проверку по ID или другому признаку
        debug_info = (
            f"🐛 *Отладочная информация*\n\n"
            f"👤 User ID: {user_id}\n"
            f"📊 Всего сессий: {data_manager.get_active_sessions_count()}\n"
            f"🕒 Время сервера: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"📁 Конфигурация:\n"
        )
        
        from config.settings import config
        debug_info += f"• Вопросов: {len(config.questions)}\n"
        debug_info += f"• Ниш: {len(config.niche_categories)}\n"
        debug_info += f"• Токен бота: {'Установлен' if config.telegram_token else 'Отсутствует'}\n"
        debug_info += f"• Токен OpenAI: {'Установлен' if config.openai_api_key else 'Отсутствует'}\n"
        
        await update.message.reply_text(
            text=debug_info,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в debug_command: {e}")
        await update.message.reply_text(
            "🐛 Ошибка при получении отладочной информации"
        )

# Экспортируем все функции для импорта в bot.py
__all__ = [
    'start_command',
    'help_command', 
    'stats_command',
    'balance_command',
    'restart_command',
    'questionnaire_command',
    'status_command',
    'debug_command'
]