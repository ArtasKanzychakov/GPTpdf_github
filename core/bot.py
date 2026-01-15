#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основной класс бота Бизнес-Навигатор
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes, ConversationHandler
)

from config.settings import config
from models.session import UserSession, BotStatistics
from models.enums import BotState, QuestionType, NicheCategory
from services.data_manager import data_manager
from services.openai_service import OpenAIService, analyze_user_profile, generate_detailed_plan
from core.question_engine import question_engine
from utils.formatters import (
    format_question_text, format_session_summary, format_niche_details,
    format_openai_usage, format_user_profile, create_niche_selection_keyboard,
    get_random_praise, get_random_encouragement
)

logger = logging.getLogger(__name__)

class BusinessNavigatorBot:
    """Основной класс бота Бизнес-Навигатор"""
    
    def __init__(self, config):
        self.config = config
        self.application = None
        self.openai_service = OpenAIService() if config.openai_api_key else None
        self.statistics = BotStatistics()
        
    def setup_handlers(self):
        """Настройка обработчиков команд и сообщений"""
        # Обработчики команд
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("profile", self.profile_command))
        self.application.add_handler(CommandHandler("restart", self.restart_command))
        self.application.add_handler(CommandHandler("test", self.test_command))
        
        # Обработчики анкеты
        from handlers.questionnaire import (
            start_questionnaire, handle_text_answer, handle_button_answer,
            skip_question, show_progress
        )
        
        self.application.add_handler(CommandHandler("questionnaire", start_questionnaire))
        self.application.add_handler(CommandHandler("progress", show_progress))
        self.application.add_handler(CommandHandler("skip", skip_question))
        
        # Обработчики текстовых сообщений
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, handle_text_answer
        ))
        
        # Обработчики callback-запросов (кнопки)
        self.application.add_handler(CallbackQueryHandler(handle_button_answer))
        
        # Обработчики выбора ниши
        self.application.add_handler(CallbackQueryHandler(
            self.handle_niche_selection, pattern="^select_niche_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.handle_restart_questionnaire, pattern="^restart_questionnaire$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.handle_show_profile, pattern="^show_profile$"
        ))
        
        logger.info("✅ Обработчики команд настроены")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start"""
        user = update.effective_user
        user_id = user.id
        
        logger.info(f"👤 Пользователь {user_id} ({user.username}) запустил бота")
        
        # Обновляем статистику
        self.statistics.add_user()
        self.statistics.add_message()
        
        welcome_text = (
            "👋 *Добро пожаловать в Бизнес-Навигатор v7.0!*\n\n"
            "Я помогу вам найти идеальную бизнес-нишу на основе:\n"
            "• 🧠 Вашей личности и мотивации\n"
            "• 🔧 Навыков и компетенций\n"
            "• 🌟 Ценностей и интересов\n"
            "• 🚫 Ограничений и возможностей\n\n"
            "*Доступные команды:*\n"
            "📋 /questionnaire - Начать анкету (35 вопросов)\n"
            "📊 /profile - Посмотреть мой профиль\n"
            "📈 /stats - Статистика бота\n"
            "🔄 /restart - Начать заново\n"
            "❓ /help - Помощь\n\n"
            "💡 *Совет:* Для наилучшего результата отвечайте честно и подробно!"
        )
        
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
        
        # Предлагаем начать анкету
        keyboard = [
            [InlineKeyboardButton("📋 Начать анкету", callback_data="start_questionnaire")],
            [InlineKeyboardButton("❓ Как это работает?", callback_data="how_it_works")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Хотите начать поиск вашей идеальной бизнес-ниши?",
            reply_markup=reply_markup
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /help"""
        help_text = (
            "🆘 *Помощь по Бизнес-Навигатору v7.0*\n\n"
            "*Основные команды:*\n"
            "📋 /questionnaire - Начать/продолжить анкету\n"
            "📊 /profile - Посмотреть ваш профиль и прогресс\n"
            "📈 /stats - Статистика бота и использование OpenAI\n"
            "🔄 /restart - Начать анкету заново\n"
            "⏭️ /skip - Пропустить текущий вопрос (если возможно)\n"
            "📝 /progress - Показать прогресс анкеты\n\n"
            
            "*Как это работает:*\n"
            "1. Вы проходите анкету из 35 вопросов\n"
            "2. Я анализирую ваши ответы с помощью ИИ\n"
            "3. Подбираю 5 подходящих бизнес-ниш\n"
            "4. Вы выбираете нишу и получаете детальный план\n\n"
            
            "*Типы вопросов:*\n"
            "🔘 Кнопки - выберите один вариант\n"
            "✅ Мультиселект - выберите несколько вариантов\n"
            "📊 Ползунок - оцените по шкале\n"
            "📝 Текст - напишите развернутый ответ\n\n"
            
            "💡 *Советы:*\n"
            "• Отвечайте честно для точных рекомендаций\n"
            "• Не бойтесь писать подробные ответы\n"
            "• Можно вернуться к анкете в любой момент\n"
            "• Данные сохраняются между сессиями\n\n"
            
            "❓ *Есть вопросы?* Пишите @ваш_аккаунт_поддержки"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
        self.statistics.add_message()
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /stats"""
        user = update.effective_user
        
        # Обновляем статистику активных сессий
        active_sessions = data_manager.get_active_sessions_count()
        self.statistics.update_active_sessions(active_sessions)
        
        stats_text = (
            f"📊 *Статистика Бизнес-Навигатора v7.0*\n\n"
            f"*Общая статистика:*\n"
            f"👥 Пользователей: {self.statistics.total_users}\n"
            f"📋 Сессий: {self.statistics.total_sessions}\n"
            f"✅ Завершено: {self.statistics.completed_sessions}\n"
            f"💬 Сообщений: {self.statistics.total_messages}\n"
            f"⚡ Активных: {self.statistics.active_sessions}\n"
            f"⏱️ Uptime: {self.statistics.get_uptime()}\n\n"
        )
        
        # Добавляем статистику OpenAI если есть
        if hasattr(self.statistics, 'openai_requests') and self.statistics.openai_requests > 0:
            stats_text += (
                f"*Использование OpenAI:*\n"
                f"🤖 Запросов: {self.statistics.openai_requests}\n"
                f"🔤 Токенов: {self.statistics.openai_tokens:,}\n"
                f"💵 Стоимость: ${self.statistics.openai_cost:.4f}\n\n"
            )
        
        # Информация о конфигурации
        stats_text += (
            f"*Конфигурация:*\n"
            f"📝 Вопросов: {len(config.questions)}\n"
            f"🏢 Ниш: {len(config.niche_categories)}\n"
            f"🤖 Модель: {config.openai_model}\n"
            f"🌐 Язык: {config.bot_language}\n\n"
            
            f"*Ваша сессия:*\n"
            f"🆔 ID: {user.id}\n"
            f"👤 Username: {user.username or 'не указан'}\n"
            f"📅 Регистрация: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
        self.statistics.add_message()
    
    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /profile"""
        user = update.effective_user
        user_id = user.id
        
        # Получаем сессию пользователя
        session = data_manager.get_session(user_id)
        
        if not session:
            # Создаем новую сессию
            session = data_manager.create_session(
                user_id=user_id,
                username=user.username or "",
                full_name=user.full_name or ""
            )
            
            profile_text = (
                "👤 *ВАШ ПРОФИЛЬ*\n\n"
                f"🆔 ID: {user_id}\n"
                f"👤 Имя: {user.full_name or 'Не указано'}\n"
                f"📅 Создан: {datetime.now().strftime('%d.%m.%Y')}\n\n"
                "📋 *Анкета:* не начата\n\n"
                "ℹ️ Начните анкету командой /questionnaire"
            )
        else:
            # Форматируем профиль существующей сессии
            profile_text = format_user_profile(session)
            
            # Добавляем информацию о прогрессе
            progress = session.get_progress_percentage()
            profile_text += f"\n\n🎯 *Прогресс:* {progress:.1f}%"
            
            if session.is_completed:
                profile_text += "\n\n✅ *Анкета завершена!*"
                
                if session.suggested_niches:
                    profile_text += f"\n🎯 Найдено ниш: {len(session.suggested_niches)}"
                
                if session.selected_niche:
                    profile_text += f"\n📌 Выбрана ниша: {session.selected_niche.name}"
                    profile_text += "\n📋 Детальный план готов!"
            else:
                profile_text += f"\n\n📝 *Текущий вопрос:* {session.current_question_index + 1}/35"
                profile_text += "\nℹ️ Продолжите анкету командой /questionnaire"
        
        # Создаем клавиатуру действий
        keyboard = []
        
        if session and not session.is_completed:
            keyboard.append([InlineKeyboardButton("📋 Продолжить анкету", callback_data="continue_questionnaire")])
        
        if session and session.is_completed and session.suggested_niches:
            keyboard.append([InlineKeyboardButton("🎯 Показать ниши", callback_data="show_niches")])
        
        keyboard.append([InlineKeyboardButton("🔄 Начать заново", callback_data="restart_questionnaire")])
        keyboard.append([InlineKeyboardButton("📊 Статистика", callback_data="show_stats")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            profile_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        self.statistics.add_message()
    
    async def restart_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /restart"""
        user = update.effective_user
        user_id = user.id
        
        # Получаем сессию
        session = data_manager.get_session(user_id)
        
        if session:
            # Сбрасываем сессию
            session.current_state = BotState.START
            session.current_question_index = 0
            session.is_completed = False
            session.completion_date = None
            session.analysis_result = ""
            session.suggested_niches = []
            session.selected_niche = None
            session.detailed_plan = ""
            
            data_manager.save_session(session)
            
            await update.message.reply_text(
                "🔄 *Сессия сброшена!*\n\n"
                "Все ваши предыдущие ответы удалены.\n"
                "Можете начать анкету заново с чистого листа.\n\n"
                "Нажмите кнопку ниже чтобы начать:",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "ℹ️ У вас еще нет активной сессии.\n"
                "Начните анкету командой /questionnaire",
                parse_mode='Markdown'
            )
        
        self.statistics.add_message()
    
    async def test_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Тестовая команда для отладки"""
        test_text = (
            "🧪 *Тест системы*\n\n"
            f"✅ Конфигурация загружена\n"
            f"📝 Вопросов: {len(config.questions)}\n"
            f"🏢 Ниш: {len(config.niche_categories)}\n"
            f"🤖 OpenAI: {'✅ Доступен' if self.openai_service and self.openai_service.is_initialized else '❌ Не доступен'}\n"
            f"💾 Data Manager: {'✅ Работает' if data_manager else '❌ Не работает'}\n\n"
            
            f"📊 *Статистика:*\n"
            f"• Пользователей: {self.statistics.total_users}\n"
            f"• Сообщений: {self.statistics.total_messages}\n"
            f"• Uptime: {self.statistics.get_uptime()}"
        )
        
        await update.message.reply_text(test_text, parse_mode='Markdown')
        self.statistics.add_message()
    
    async def handle_niche_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора ниши"""
        query = update.callback_query
        await query.answer()
        
        niche_id = query.data.replace("select_niche_", "")
        
        user_id = update.effective_user.id
        session = data_manager.get_session(user_id)
        
        if not session or not session.suggested_niches:
            await query.edit_message_text(
                "❌ Сессия не найдена или ниши не сгенерированы.\n"
                "Пройдите анкету заново.",
                parse_mode='Markdown'
            )
            return
        
        # Находим выбранную нишу
        selected_niche = None
        for niche in session.suggested_niches:
            if niche.id == niche_id:
                selected_niche = niche
                break
        
        if not selected_niche:
            await query.edit_message_text(
                "❌ Выбранная ниша не найдена.",
                parse_mode='Markdown'
            )
            return
        
        # Показываем детали ниши
        niche_details = format_niche_details(selected_niche, detailed=True)
        
        # Кнопки для выбора действия
        keyboard = [
            [InlineKeyboardButton("📋 Получить детальный план", callback_data=f"get_plan_{niche_id}")],
            [InlineKeyboardButton("🎯 Показать другие ниши", callback_data="show_other_niches")],
            [InlineKeyboardButton("🔄 Пройти заново", callback_data="restart_questionnaire")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🎯 *ВЫБРАНА НИША: {selected_niche.emoji} {selected_niche.name}*\n\n"
            f"{niche_details}\n\n"
            f"Хотите получить детальный пошаговый план?",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def handle_restart_questionnaire(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка перезапуска анкеты"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Получаем или создаем сессию
        session = data_manager.get_session(user_id)
        if not session:
            user = update.effective_user
            session = data_manager.create_session(
                user_id=user_id,
                username=user.username or "",
                full_name=user.full_name or ""
            )
        
        # Сбрасываем сессию
        session.current_state = BotState.START
        session.current_question_index = 0
        session.is_completed = False
        session.completion_date = None
        session.analysis_result = ""
        session.suggested_niches = []
        session.selected_niche = None
        session.detailed_plan = ""
        
        data_manager.save_session(session)
        
        # Запускаем анкету
        from handlers.questionnaire import start_questionnaire
        await start_questionnaire(update, context)
    
    async def handle_show_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка показа профиля"""
        query = update.callback_query
        await query.answer()
        
        # Создаем фейковый update для команды /profile
        class FakeUpdate:
            def __init__(self, original_update):
                self.effective_user = original_update.effective_user
                self.message = type('obj', (object,), {
                    'reply_text': query.edit_message_text,
                    'chat_id': query.message.chat_id,
                    'message_id': query.message.message_id
                })()
        
        fake_update = FakeUpdate(update)
        await self.profile_command(fake_update, context)
    
    async def run(self):
        """Запуск бота"""
        try:
            # Создаем приложение
            self.application = Application.builder().token(self.config.telegram_token).build()
            
            # Настраиваем обработчики
            self.setup_handlers()
            
            # Запускаем polling
            logger.info("▶️ Запускаю бота в режиме polling...")
            await self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска бота: {e}")
            raise