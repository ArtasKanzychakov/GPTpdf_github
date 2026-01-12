#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Бизнес-навигатор: Telegram бот для подбора бизнес-идей
Версия 2.1 - Исправлены кнопки, убраны контакты
"""

import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass, field

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

from openai import OpenAI
import aiohttp
from aiohttp import web

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== КОНСТАНТЫ ====================
QUESTIONNAIRE_STATE = 1
BUSINESS_IDEAS_STATE = 2
BUSINESS_PLAN_STATE = 3

QUESTIONS = [
    "🏙️ *В каком городе или регионе вы живете?*\n_Например: Москва, Санкт-Петербург, Новосибирск_",
    "🎓 *Какое у вас образование, курсы или сертификаты?*\n_Например: Высшее экономическое, курсы маркетинга_",
    "🔧 *Какие технические навыки у вас есть?*\n_Что умеете делать? Например: работа с компьютером, ремонт техники_",
    "💼 *Какие профессиональные навыки?*\n_Что умеете в работе? Например: общение с клиентами, продажи_",
    "🌟 *Какие у вас сильные личные качества?*\n_Например: общительный, ответственный, креативный_",
    "❤️ *Какие сферы или темы вам интересны?*\n_Например: технологии, спорт, здоровье, кулинария_",
    "📅 *Какой у вас опыт работы?*\n_Например: 5 лет менеджером, 3 года фриланс-дизайнер_",
    "💰 *Какой стартовый бюджет есть для бизнеса?*\n_Например: 10 тысяч, 50 тысяч, 100 тысяч рублей_",
    "⏰ *Сколько времени готовы уделять бизнесу в неделю?*\n_Например: 10 часов, 20 часов, полный день_",
    "👥 *Есть ли у вас команда или партнеры для бизнеса?*\n_Работаете один или с кем-то?_",
    "🎲 *Насколько вы готовы к риску?*\n_🛡️ Консервативный / ⚖️ Умеренный / 🚀 Агрессивный_",
    "🏢 *Какой формат бизнеса предпочитаете?*\n_🌐 Онлайн / 🏪 Офлайн / 🔄 Смешанный_",
    "🛠️ *Есть ли у вас специальные ресурсы или доступ к чему-то?*\n_Например: помещение, оборудование, машина_",
    "📆 *На какой срок планируете этот бизнес?*\n_Например: на год-два, на 5 лет, долгосрочно_",
    "🎯 *Какие цели у вас кроме заработка денег?*\n_Например: помощь людям, самореализация, гибкий график_",
    "🎨 *Есть ли у вас хобби, которые можно превратить в бизнес?*\n_Например: фотография, готовка, спорт_"
]

# ==================== МОДЕЛИ ====================
@dataclass
class UserProfile:
    user_id: int
    timestamp: datetime = field(default_factory=datetime.now)
    answers: Dict[int, str] = field(default_factory=dict)
    current_question: int = 0
    business_ideas: List[str] = field(default_factory=list)
    selected_business_idea: str = ""
    business_plan: str = ""

user_sessions: Dict[int, UserProfile] = {}

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    
    user_sessions[user_id] = UserProfile(user_id=user_id)
    
    welcome_text = """
👋 *Добро пожаловать в Бизнес-Навигатор!*

Я помогу найти бизнес-идею на основе ваших навыков.

📋 *Что я сделаю:*
1. Задам 16 простых вопросов
2. Проанализирую ваши ответы  
3. Предложу 5 идей бизнеса
4. Подробно распишу план

⏱️ *Время:* 5-10 минут

🚀 *Готовы начать?*
"""
    
    keyboard = [[InlineKeyboardButton("📋 Начать анкету", callback_data='start_questionnaire')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def start_questionnaire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать анкету"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_sessions[user_id] = UserProfile(user_id=user_id)
    profile = user_sessions[user_id]
    profile.current_question = 0
    
    progress = "🟢" + "⚪" * (len(QUESTIONS) - 1)
    
    await query.edit_message_text(
        f"{progress}\n📝 *Вопрос 1 из {len(QUESTIONS)}*\n\n{QUESTIONS[0]}\n\n✏️ *Напишите ответ:*",
        parse_mode='Markdown'
    )
    
    return QUESTIONNAIRE_STATE

async def handle_questionnaire_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответов на вопросы"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if user_id not in user_sessions:
        await update.message.reply_text("❌ Сессия устарела. Начните с /start")
        return ConversationHandler.END
    
    profile = user_sessions[user_id]
    current_q = profile.current_question
    
    # Сохраняем ответ
    profile.answers[current_q] = text
    
    # Переходим к следующему вопросу
    profile.current_question += 1
    
    # Проверяем завершение анкеты
    if profile.current_question >= len(QUESTIONS):
        await update.message.reply_text(
            "🎉 *Анкета завершена!*\n\n🤔 *Анализирую данные...*",
            parse_mode='Markdown'
        )
        
        await asyncio.sleep(1)
        return await generate_business_ideas(update, context)
    
    # Показываем следующий вопрос
    next_q_num = profile.current_question + 1
    progress = "🟢" * (profile.current_question) + "⚪" * (len(QUESTIONS) - profile.current_question)
    
    await update.message.reply_text(
        f"{progress}\n✅ *Ответ сохранен!*\n*Вопрос {next_q_num} из {len(QUESTIONS)}*\n\n{QUESTIONS[profile.current_question]}\n\n✏️ *Напишите ответ:*",
        parse_mode='Markdown'
    )
    
    return QUESTIONNAIRE_STATE

async def generate_business_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация бизнес-идей"""
    user_id = update.effective_user.id
    
    if user_id not in user_sessions:
        await update.message.reply_text("❌ Данные не найдены. Начните с /start")
        return ConversationHandler.END
    
    profile = user_sessions[user_id]
    
    # Анализируем ответы
    city = profile.answers.get(0, "вашем городе")
    tech_skills = profile.answers.get(2, "")
    budget = profile.answers.get(7, "10 тысяч рублей")
    
    # Генерируем идеи
    ideas = [
        f"1. *Видеопродакшн студия в {city}*\nСоздание рекламных роликов, контента для соцсетей",
        f"2. *Онлайн-курсы по видеомонтажу*\nОбучение через Zoom/Telegram, можно начать с минимальными вложениями",
        f"3. *Услуги сварочных работ*\nИзготовление конструкций для бизнеса в {city}",
        f"4. *Контент для местных брендов*\nСоздание фото и видео для кафе, магазинов",
        f"5. *Организация кино-встреч*\nТематические вечера, обсуждения фильмов"
    ]
    
    profile.business_ideas = ideas
    
    # Клавиатура
    keyboard = [
        [InlineKeyboardButton("🎬 Идея 1: Видео-студия", callback_data='idea_0')],
        [InlineKeyboardButton("📚 Идея 2: Онлайн-курсы", callback_data='idea_1')],
        [InlineKeyboardButton("🔧 Идея 3: Сварочные услуги", callback_data='idea_2')],
        [InlineKeyboardButton("📸 Идея 4: Контент для бизнеса", callback_data='idea_3')],
        [InlineKeyboardButton("🎥 Идея 5: Кино-встречи", callback_data='idea_4')],
        [InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎯 *5 бизнес-идей для вас:*\n\n" + "\n\n".join(ideas) + "\n\n👇 *Выберите идею:*",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    return BUSINESS_IDEAS_STATE

async def handle_business_idea_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора бизнес-идеи"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in user_sessions:
        await query.edit_message_text("❌ Данные не найдены. Начните с /start")
        return ConversationHandler.END
    
    profile = user_sessions[user_id]
    data = query.data
    
    if data.startswith('idea_'):
        idea_index = int(data.split('_')[1])
        
        if 0 <= idea_index < len(profile.business_ideas):
            profile.selected_business_idea = profile.business_ideas[idea_index]
            
            # Генерируем бизнес-план
            await show_business_plan(query, idea_index)
            return BUSINESS_PLAN_STATE
    
    return BUSINESS_IDEAS_STATE

async def show_business_plan(query, idea_index: int):
    """Показ бизнес-плана"""
    user_id = query.from_user.id
    profile = user_sessions[user_id]
    
    city = profile.answers.get(0, "вашем городе")
    budget = profile.answers.get(7, "10 тысяч рублей")
    
    # Разные планы для разных идей
    plans = [
        f"""📈 *БИЗНЕС-ПЛАН: Видеопродакшн студия*

🎯 *Что это:* Создание видео для бизнеса и частных клиентов

📍 *Для кого:* Малый бизнес {city}, блогеры, мероприятия

💰 *Финансы:*
• Старт: {budget} на оборудование
• Месячные расходы: 5,000 - 15,000 руб
• Средний заказ: 5,000 - 20,000 руб
• Окупаемость: 2-4 месяца

🚀 *Этапы:*
1. Месяц 1: Портфолио (3-5 работ), соцсети
2. Месяц 2: Первые клиенты через знакомых
3. Месяц 3: Реклама, отзывы, постоянные клиенты

✅ *Плюсы:* Высокий спрос, творческая работа""",

        f"""📈 *БИЗНЕС-ПЛАН: Онлайн-курсы*

🎯 *Что это:* Обучение видеомонтажу онлайн

📍 *Для кого:* Начинающие видеографы, блогеры

💰 *Финансы:*
• Старт: Минимальные вложения
• Курс: 5,000 - 15,000 руб с ученика
• Окупаемость: 1-2 месяца

🚀 *Этапы:*
1. Создать программу курса
2. Записать первые уроки  
3. Найти первых учеников
4. Собирать отзывы и улучшать

✅ *Плюсы:* Масштабируемость, работа из дома""",

        f"""📈 *БИЗНЕС-ПЛАН: Сварочные услуги*

🎯 *Что это:* Ремонт и изготовление металлических конструкций

📍 *Для кого:* Строительные фирмы, производства, частные заказчики в {city}

💰 *Финансы:*
• Старт: 20,000 - 50,000 руб на оборудование
• Заказ: от 3,000 руб
• Окупаемость: 3-6 месяцев

🚀 *Этапы:*
1. Получить первые заказы через знакомых
2. Создать портфолио работ
3. Разместить рекламу на местных площадках

✅ *Плюсы:* Постоянный спрос, хорошая оплата""",

        f"""📈 *БИЗНЕС-ПЛАН: Контент для бизнеса*

🎯 *Что это:* Фото и видео для местных компаний

📍 *Для кого:* Кафе, магазины, услуги в {city}

💰 *Финансы:*
• Старт: {budget} на технику
• Пакет услуг: 3,000 - 10,000 руб
• Окупаемость: 1-3 месяца

🚀 *Этапы:*
1. Предложить услуги местным бизнесам
2. Сделать несколько проектов по низкой цене
3. Собрать портфолио и отзывы

✅ *Плюсы:* Много потенциальных клиентов""",

        f"""📈 *БИЗНЕС-ПЛАН: Кино-встречи*

🎯 *Что это:* Тематические вечера для любителей кино

📍 *Для кого:* Жители {city}, студенты, творческие люди

💰 *Финансы:*
• Старт: 5,000 - 15,000 руб
• Билет: 500 - 1,500 руб
• Окупаемость: 2-3 мероприятия

🚀 *Этапы:*
1. Выбрать тему и формат
2. Найти помещение (кафе, библиотека)
3. Пригласить первых участников
4. Создать сообщество

✅ *Плюсы:* Интересное дело, новые знакомства"""
    ]
    
    if idea_index < len(plans):
        business_plan = plans[idea_index]
        profile.business_plan = business_plan
        
        # Кнопки под планом
        keyboard = [
            [InlineKeyboardButton("💾 Сохранить план", callback_data='save_plan')],
            [InlineKeyboardButton("🔄 Выбрать другую идею", callback_data='back_to_ideas')],
            [InlineKeyboardButton("🏠 Начать заново", callback_data='back_to_start')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            business_plan,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def save_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение плана"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "✅ *План сохранен!*\n\n"
        "🎯 *Ваши следующие шаги:*\n"
        "1. Начните с первого простого проекта\n"
        "2. Соберите портфолио из 3-5 работ\n"
        "3. Попросите отзывы у клиентов\n"
        "4. Постепенно увеличивайте цены\n\n"
        "💪 *У вас всё получится!*\n\n"
        "Для нового поиска нажмите /start",
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

async def back_to_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться к идеям"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in user_sessions:
        await query.edit_message_text("❌ Данные не найдены. Начните с /start")
        return ConversationHandler.END
    
    profile = user_sessions[user_id]
    
    # Клавиатура
    keyboard = [
        [InlineKeyboardButton("🎬 Идея 1: Видео-студия", callback_data='idea_0')],
        [InlineKeyboardButton("📚 Идея 2: Онлайн-курсы", callback_data='idea_1')],
        [InlineKeyboardButton("🔧 Идея 3: Сварочные услуги", callback_data='idea_2')],
        [InlineKeyboardButton("📸 Идея 4: Контент для бизнеса", callback_data='idea_3')],
        [InlineKeyboardButton("🎥 Идея 5: Кино-встречи", callback_data='idea_4')],
        [InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🔄 *Выберите другую бизнес-идею:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return BUSINESS_IDEAS_STATE

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в начало"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_sessions[user_id] = UserProfile(user_id=user_id)
    
    keyboard = [[InlineKeyboardButton("📋 Начать анкету", callback_data='start_questionnaire')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👋 *Снова здравствуйте!*\n\nНажмите кнопку чтобы начать новую анкету:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена"""
    user_id = update.effective_user.id
    
    if user_id in user_sessions:
        del user_sessions[user_id]
    
    if update.message:
        await update.message.reply_text("❌ Диалог отменен. Для начала напишите /start")
    
    return ConversationHandler.END

# ==================== HEALTH CHECK ====================
async def health_check(request):
    return web.Response(text="OK - Business Bot v2.1")

async def run_health_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", "10000"))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"✅ Health check сервер запущен на порту {port}")
    return runner

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
async def main():
    """Основная функция"""
    
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    
    if not token:
        logger.error("❌ TELEGRAM_TOKEN не найден!")
        return
    
    logger.info("🚀 Запуск Бизнес-бота v2.1")
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # Создаем ConversationHandler - УПРОЩЕННАЯ ВЕРСИЯ
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_questionnaire, pattern='^start_questionnaire$')
        ],
        states={
            QUESTIONNAIRE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_questionnaire_answer)
            ],
            BUSINESS_IDEAS_STATE: [
                CallbackQueryHandler(handle_business_idea_selection, pattern='^idea_'),
                CallbackQueryHandler(back_to_start, pattern='^back_to_start$')
            ],
            BUSINESS_PLAN_STATE: [
                CallbackQueryHandler(save_plan, pattern='^save_plan$'),
                CallbackQueryHandler(back_to_ideas, pattern='^back_to_ideas$'),
                CallbackQueryHandler(back_to_start, pattern='^back_to_start$')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel)
        ],
        per_message=False
    )
    
    application.add_handler(conv_handler)
    
    # Отдельные callback-обработчики
    application.add_handler(CallbackQueryHandler(back_to_start, pattern='^back_to_start$'))
    
    # Запускаем health сервер
    health_server = await run_health_server()
    
    # Запускаем бота
    try:
        await application.initialize()
        await application.start()
        
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
        logger.info("✅ Бот готов к работе!")
        
        # Бесконечный цикл
        while True:
            await asyncio.sleep(3600)
            
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
    finally:
        # Очистка
        try:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
            await health_server.cleanup()
        except:
            pass

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹ Бот остановлен")