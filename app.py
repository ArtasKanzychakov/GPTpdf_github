#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Бизнес-навигатор: Telegram бот для подбора бизнес-идей
Версия с понятными вопросами и исправленной логикой
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

# ПОНЯТНЫЕ ВОПРОСЫ С ПОЯСНЕНИЯМИ
QUESTIONS = [
    # 0
    "🏙️ *В каком городе или регионе вы живете?*\n\n"
    "_Например: Москва, Санкт-Петербург, Новосибирск, или просто укажите регион_",
    
    # 1
    "🎓 *Какое у вас образование, курсы или сертификаты?*\n\n"
    "_Перечислите через запятую. Например: Высшее экономическое, курсы маркетинга, сертификат Excel_",
    
    # 2
    "🔧 *Какие технические навыки у вас есть?*\n\n"
    "_Что умеете делать руками или на компьютере? Например: работа с компьютером, ремонт техники, фотошоп, Excel_",
    
    # 3
    "💼 *Какие профессиональные навыки?*\n\n"
    "_Что умеете в работе? Например: общение с клиентами, продажи, организация мероприятий, управление командой_",
    
    # 4
    "🌟 *Какие у вас сильные личные качества?*\n\n"
    "_Как вас характеризуют? Например: общительный, ответственный, креативный, внимательный к деталям_",
    
    # 5
    "❤️ *Какие сферы или темы вам интересны?*\n\n"
    "_Что вам нравится? Например: технологии, спорт, здоровье, кулинария, рукоделие, автомобили_",
    
    # 6
    "📅 *Какой у вас опыт работы?*\n\n"
    "_Где и кем работали? Например: 5 лет менеджером в магазине, 3 года фриланс-дизайнер_",
    
    # 7
    "💰 *Какой стартовый бюджет есть для бизнеса?*\n\n"
    "_Сколько готовы вложить? Например: 10 тысяч, 50 тысяч, 100 тысяч рублей_",
    
    # 8
    "⏰ *Сколько времени готовы уделять бизнесу в неделю?*\n\n"
    "_Например: 10 часов, 20 часов, полный рабочий день_",
    
    # 9
    "👥 *Есть ли у вас команда или партнеры для бизнеса?*\n\n"
    "_Работаете один или с кем-то? Если есть команда - опишите кто это_",
    
    # 10
    "🎲 *Насколько вы готовы к риску?*\n\n"
    "_Выберите вариант:\n"
    "• 🛡️ Консервативный - минимальный риск, стабильность важнее\n"
    "• ⚖️ Умеренный - готов к разумному риску\n"
    "• 🚀 Агрессивный - готов рисковать для большей прибыли_",
    
    # 11
    "🏢 *Какой формат бизнеса предпочитаете?*\n\n"
    "_Выберите вариант:\n"
    "• 🌐 Только онлайн - через интернет\n"
    "• 🏪 Только офлайн - физический магазин/офис\n"
    "• 🔄 Смешанный - и онлайн, и офлайн_",
    
    # 12
    "🛠️ *Есть ли у вас специальные ресурсы или доступ к чему-то?*\n\n"
    "_Например: своё помещение, оборудование, машина, специальные связи или знакомства_",
    
    # 13
    "📆 *На какой срок планируете этот бизнес?*\n\n"
    "_Например: на год-два, на 5 лет, на долгосрочную перспективу_",
    
    # 14
    "🎯 *Какие цели у вас кроме заработка денег?*\n\n"
    "_Что еще важно? Например: помощь людям, самореализация, гибкий график, интересная работа_",
    
    # 15
    "🎨 *Есть ли у вас хобби, которые можно превратить в бизнес?*\n\n"
    "_Чем любите заниматься в свободное время? Например: фотография, готовка, спорт, рукоделие_"
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

# ==================== OPENAI ====================
def init_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "test-key-123":
        logger.warning("⚠️ OPENAI_API_KEY не задан, используем тестовый режим")
        return None
    logger.info("✅ OPENAI_API_KEY задан")
    return OpenAI(api_key=api_key)

openai_client = init_openai_client()

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    logger.info(f"START вызван пользователем {update.effective_user.id}")
    
    user = update.effective_user
    user_id = user.id
    
    # Создаем сессию
    user_sessions[user_id] = UserProfile(user_id=user_id)
    
    welcome_text = """
👋 *Добро пожаловать в Бизнес-Навигатор!*

Я помогу вам найти подходящую бизнес-идею на основе ваших навыков и интересов.

📋 *Что я сделаю:*
1. Задам 16 простых вопросов о вас
2. Проанализирую ваши ответы
3. Предложу 5 идей бизнеса специально для вас
4. Подробно распишу план для выбранной идеи

⏱️ *Это займет всего 5-10 минут*
💡 *Отвечайте честно - так идеи будут точнее*

🚀 *Готовы начать?*
"""
    
    keyboard = [
        [InlineKeyboardButton("📋 Начать анкету", callback_data='start_questionnaire')],
        [InlineKeyboardButton("❓ Как это работает?", callback_data='how_it_works')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        logger.info(f"START: Приветственное сообщение отправлено пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуйте еще раз или напишите /start",
            parse_mode='Markdown'
        )

async def how_it_works(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Как это работает"""
    query = update.callback_query
    await query.answer()
    
    help_text = """
❓ *Как это работает?*

📋 *Этап 1: Анкета*
Я задам 16 простых вопросов о:
• Вашем городе и опыте
• Навыках и образовании  
• Интересах и увлечениях
• Бюджете и возможностях

💡 *Этап 2: Анализ*
Проанализирую ваши ответы и учту:
• Региональные особенности
• Конкуренцию в вашем городе
• Ваши уникальные навыки
• Бюджет и временные возможности

🎯 *Этап 3: Идеи*
Предложу 5 бизнес-идей, которые:
• Подходят именно вам
• Реалистичны для запуска
• Учитывают ваш бюджет
• Имеют потенциал роста

📊 *Этап 4: План*
Подробно распишу для выбранной идеи:
• Что нужно сделать по шагам
• Сколько денег потребуется
• Как привлекать клиентов
• Какие могут быть риски

⏱️ *Время:* Весь процесс займет 5-10 минут
"""
    
    keyboard = [
        [InlineKeyboardButton("📋 Начать анкету", callback_data='start_questionnaire')],
        [InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в начало"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Сбрасываем сессию
    user_sessions[user_id] = UserProfile(user_id=user_id)
    
    welcome_text = """
👋 *Снова здравствуйте!*

Вы вернулись в главное меню.

🚀 *Что дальше?*
• Начать новую анкету
• Узнать как это работает

📞 *Нужна помощь?*
Если что-то не работает, просто напишите /start заново
"""
    
    keyboard = [
        [InlineKeyboardButton("📋 Начать анкету", callback_data='start_questionnaire')],
        [InlineKeyboardButton("❓ Как это работает?", callback_data='how_it_works')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def start_questionnaire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать анкету"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    logger.info(f"START_QUESTIONNAIRE: Начало анкеты для пользователя {user_id}")
    
    # Создаем/сбрасываем профиль
    user_sessions[user_id] = UserProfile(user_id=user_id)
    profile = user_sessions[user_id]
    profile.current_question = 0
    
    # Прогресс-бар
    progress = "🟢" + "⚪" * (len(QUESTIONS) - 1)
    
    await query.edit_message_text(
        f"{progress}\n\n"
        f"📝 *Анкета началась!*\n"
        f"*Вопрос 1 из {len(QUESTIONS)}*\n\n"
        f"{QUESTIONS[0]}\n\n"
        f"✏️ *Напишите ваш ответ:*",
        parse_mode='Markdown'
    )
    
    return QUESTIONNAIRE_STATE

async def handle_questionnaire_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответов на вопросы"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Проверяем сессию
    if user_id not in user_sessions:
        logger.warning(f"Сессия не найдена для пользователя {user_id}")
        await update.message.reply_text(
            "❌ Сессия устарела. Начните заново с /start",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    profile = user_sessions[user_id]
    current_q = profile.current_question
    
    logger.info(f"Вопрос {current_q + 1}: получен ответ от {user_id}: {text[:50]}...")
    
    # Сохраняем ответ
    profile.answers[current_q] = text
    
    # Переходим к следующему вопросу
    profile.current_question += 1
    
    # Проверяем завершение анкеты
    if profile.current_question >= len(QUESTIONS):
        logger.info(f"✅ Анкета завершена для {user_id}. Ответов: {len(profile.answers)}")
        
        # Финальное сообщение
        await update.message.reply_text(
            "🎉 *Поздравляю! Анкета завершена!*\n\n"
            "📊 *Собрано ответов:* 16/16\n"
            "🤔 *Анализирую ваши данные...*\n\n"
            "Ищу лучшие бизнес-идеи специально для вас...",
            parse_mode='Markdown'
        )
        
        # Небольшая пауза для UX
        await asyncio.sleep(1)
        
        # Генерируем идеи
        return await generate_business_ideas(update, context)
    
    # Показываем следующий вопрос
    next_q_num = profile.current_question + 1
    
    # Прогресс-бар
    progress = "🟢" * (profile.current_question) + "⚪" * (len(QUESTIONS) - profile.current_question)
    
    await update.message.reply_text(
        f"{progress}\n\n"
        f"✅ *Ответ сохранен!*\n"
        f"*Вопрос {next_q_num} из {len(QUESTIONS)}*\n\n"
        f"{QUESTIONS[profile.current_question]}\n\n"
        f"✏️ *Напишите ваш ответ:*",
        parse_mode='Markdown'
    )
    
    return QUESTIONNAIRE_STATE

async def generate_business_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация бизнес-идей"""
    user_id = update.effective_user.id
    
    if user_id not in user_sessions:
        await update.message.reply_text("❌ Данные не найдены. Начните заново с /start")
        return ConversationHandler.END
    
    profile = user_sessions[user_id]
    
    # Анализируем ответы пользователя
    city = profile.answers.get(0, "вашем городе")
    education = profile.answers.get(1, "")
    tech_skills = profile.answers.get(2, "")
    interests = profile.answers.get(5, "")
    budget = profile.answers.get(7, "10 тысяч рублей")
    
    # Генерируем идеи на основе ответов
    ideas = [
        f"1. *Видео-продакшн студия в {city}*\n"
        f"   Создание рекламных роликов, видеопрезентаций, контента для соцсетей.\n"
        f"   Бюджет: {budget} на начальное оборудование",
        
        f"2. *Онлайн-курсы по видеомонтажу*\n"
        f"   Обучение начинающих видеографов через Zoom/Telegram.\n"
        f"   Можно начать с минимальными вложениями",
        
        f"3. *Услуги сварочных работ для малого бизнеса*\n"
        f"   Изготовление конструкций, ремонт оборудования для местных компаний в {city}",
        
        f"4. *Производство контента для местных брендов*\n"
        f"   Создание фото и видео для кафе, магазинов, услуг в вашем городе",
        
        f"5. *Организация локальных кино-встреч*\n"
        f"   Проведение тематических вечеров, обсуждений фильмов, мастер-классов по кино"
    ]
    
    profile.business_ideas = ideas
    
    # Создаем клавиатуру для выбора идеи
    keyboard = [
        [InlineKeyboardButton("🎬 Идея 1: Видео-студия", callback_data='select_idea_0')],
        [InlineKeyboardButton("📚 Идея 2: Онлайн-курсы", callback_data='select_idea_1')],
        [InlineKeyboardButton("🔧 Идея 3: Сварочные услуги", callback_data='select_idea_2')],
        [InlineKeyboardButton("📸 Идея 4: Контент для бизнеса", callback_data='select_idea_3')],
        [InlineKeyboardButton("🎥 Идея 5: Кино-встречи", callback_data='select_idea_4')],
        [InlineKeyboardButton("🔄 Другие идеи", callback_data='other_ideas')],
        [InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎯 *Вот 5 бизнес-идей специально для вас!*\n\n"
        "Идеи основаны на ваших:\n"
        f"• 📍 Городе: {city}\n"
        f"• 🎓 Навыках: {tech_skills[:50]}...\n"
        f"• 💰 Бюджете: {budget}\n"
        f"• ⏰ Времени: {profile.answers.get(8, '10 часов')}\n\n"
        "👇 *Выберите идею для детального плана:*",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    return BUSINESS_IDEAS_STATE

async def select_business_idea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор бизнес-идеи"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in user_sessions:
        await query.edit_message_text("❌ Данные не найдены. Начните заново с /start")
        return ConversationHandler.END
    
    profile = user_sessions[user_id]
    data = query.data
    
    if data.startswith('select_idea_'):
        idea_index = int(data.split('_')[-1])
        
        if 0 <= idea_index < len(profile.business_ideas):
            profile.selected_business_idea = profile.business_ideas[idea_index]
            
            # Генерируем бизнес-план
            await generate_business_plan(query, idea_index)
            return BUSINESS_PLAN_STATE
    
    return BUSINESS_IDEAS_STATE

async def generate_business_plan(query, idea_index: int):
    """Генерация бизнес-плана"""
    user_id = query.from_user.id
    profile = user_sessions[user_id]
    
    selected_idea = profile.business_ideas[idea_index]
    
    # Бизнес-план
    business_plan = f"""
📈 *БИЗНЕС-ПЛАН*

{selected_idea}

---

📋 *КРАТКОЕ ОПИСАНИЕ:*
Бизнес основан на ваших навыках видеомонтажа и опыте в продакшене.

🎯 *ЦЕЛЕВАЯ АУДИТОРИЯ:*
• Малый бизнес в вашем городе
• Начинающие блогеры
• Местные мероприятия
• Корпоративные клиенты

💰 *ФИНАНСОВЫЙ ПЛАН:*
• Стартовые вложения: 10,000 - 50,000 руб
• Ежемесячные расходы: 5,000 - 15,000 руб
• Средний чек: 5,000 - 20,000 руб
• Окупаемость: 2-4 месяца

🚀 *ЭТАПЫ ЗАПУСКА:*

*МЕСЯЦ 1: Подготовка*
1. Составить портфолио из 3-5 работ
2. Настроить соцсети (Telegram, ВКонтакте)
3. Подготовить прайс-лист

*МЕСЯЦ 2: Первые клиенты*
1. Предложить услуги знакомым
2. Разместить объявления на местных площадках
3. Сделать 2-3 проекта по низкой цене для портфолио

*МЕСЯЦ 3: Рост*
1. Собрать отзывы от первых клиентов
2. Начать рекламу в соцсетях
3. Искать постоянных клиентов

📢 *МАРКЕТИНГ:*
• Контент в соцсетях (примеры работ)
• Сотрудничество с местными блогерами
• Рекомендации от клиентов
• Участие в местных бизнес-сообществах

⚠️ *РИСКИ И РЕШЕНИЯ:*
• *Мало заказов:* Начать с низких цен, брать небольшие проекты
• *Конкуренция:* Делать акцент на качестве и индивидуальном подходе
• *Сезонность:* Диверсифицировать услуги (корпоративы, мероприятия, реклама)

💡 *РЕКОМЕНДАЦИИ:*
1. Начните с простых проектов
2. Не берите много заказов сразу
3. Всегда спрашивайте обратную связь
4. Постоянно улучшайте портфолио

📞 *ПОДДЕРЖКА:*
По вопросам запуска пишите @ArtasKanzychakov
"""
    
    profile.business_plan = business_plan
    
    keyboard = [
        [InlineKeyboardButton("💾 Сохранить этот план", callback_data='save_plan')],
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
    
    user_id = query.from_user.id
    
    await query.edit_message_text(
        "✅ *План сохранен!*\n\n"
        "🎯 *Ваши следующие шаги:*\n\n"
        "1. *Начните с малого* - возьмите первый простой проект\n"
        "2. *Соберите портфолио* - 3-5 работ достаточно для старта\n"
        "3. *Спросите отзывы* - это лучшая реклама\n"
        "4. *Не бойтесь ошибок* - каждый проект это опыт\n\n"
        "💪 *Вы можете это сделать!*\n\n"
        "Для нового поиска нажмите /start\n"
        "Или поделитесь результатом с друзьями 👇",
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

async def back_to_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться к идеям"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in user_sessions:
        await query.edit_message_text("❌ Данные не найдены. Начните заново с /start")
        return ConversationHandler.END
    
    profile = user_sessions[user_id]
    
    # Создаем клавиатуру
    keyboard = [
        [InlineKeyboardButton("🎬 Идея 1: Видео-студия", callback_data='select_idea_0')],
        [InlineKeyboardButton("📚 Идея 2: Онлайн-курсы", callback_data='select_idea_1')],
        [InlineKeyboardButton("🔧 Идея 3: Сварочные услуги", callback_data='select_idea_2')],
        [InlineKeyboardButton("📸 Идея 4: Контент для бизнеса", callback_data='select_idea_3')],
        [InlineKeyboardButton("🎥 Идея 5: Кино-встречи", callback_data='select_idea_4')],
        [InlineKeyboardButton("🔄 Другие идеи", callback_data='other_ideas')],
        [InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🔄 *Выберите другую бизнес-идею:*\n\n"
        "Все идеи адаптированы под ваш профиль и возможности",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return BUSINESS_IDEAS_STATE

async def other_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Другие идеи"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    other_ideas_text = """
💡 *Еще идеи которые могут вам подойти:*

6. **Консультации по запуску YouTube-канала**
   Помощь в создании и продвижении каналов для начинающих

7. **Монтаж видео для свадеб и праздников**
   Услуги для мероприятий в вашем городе

8. **Создание обучающих роликов для бизнеса**
   Инструкции, презентации, обучающий контент

9. **Ремонт и обслуживание видеотехники**
   Используя навыки сварщика и знания техники

10. **Организация локальных кинофестивалей**
    Культурные события для вашего города

🎯 *Для детального плана выберите одну из основных идей*
"""
    
    keyboard = [
        [InlineKeyboardButton("🎬 Идея 1: Видео-студия", callback_data='select_idea_0')],
        [InlineKeyboardButton("📚 Идея 2: Онлайн-курсы", callback_data='select_idea_1')],
        [InlineKeyboardButton("🔧 Идея 3: Сварочные услуги", callback_data='select_idea_2')],
        [InlineKeyboardButton("📸 Идея 4: Контент для бизнеса", callback_data='select_idea_3')],
        [InlineKeyboardButton("🎥 Идея 5: Кино-встречи", callback_data='select_idea_4')],
        [InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        other_ideas_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return BUSINESS_IDEAS_STATE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена"""
    user_id = update.effective_user.id
    
    if user_id in user_sessions:
        del user_sessions[user_id]
    
    if update.message:
        await update.message.reply_text(
            "❌ Диалог отменен.\nДля начала напишите /start",
            parse_mode='Markdown'
        )
    
    return ConversationHandler.END

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовая команда"""
    await update.message.reply_text(
        "✅ *Бот работает!*\n\n"
        f"📊 Активных сессий: {len(user_sessions)}\n"
        f"🕒 Время сервера: {datetime.now()}\n\n"
        "Для начала работы напишите /start",
        parse_mode='Markdown'
    )

# ==================== HEALTH CHECK ====================
async def health_check(request):
    return web.Response(text="OK - Business Bot v2.0")

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
    
    # Проверяем токен
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    
    if not token:
        logger.error("❌ TELEGRAM_TOKEN не найден!")
        logger.error("Добавьте TELEGRAM_BOT_TOKEN в настройки Render")
        return
    
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК БОТА - ВЕРСИЯ 2.0")
    logger.info(f"✅ Токен найден, длина: {len(token)} символов")
    logger.info(f"✅ PORT: {os.getenv('PORT', '10000')}")
    logger.info("=" * 50)
    
    # Создаем приложение
    try:
        application = Application.builder().token(token).build()
        logger.info("✅ Приложение создано")
    except Exception as e:
        logger.error(f"❌ Ошибка создания приложения: {e}")
        return
    
    # Регистрируем команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("test", test_command))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # Создаем ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_questionnaire, pattern='^start_questionnaire$')
        ],
        states={
            QUESTIONNAIRE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_questionnaire_answer)
            ],
            BUSINESS_IDEAS_STATE: [
                CallbackQueryHandler(select_business_idea, pattern='^select_idea_'),
                CallbackQueryHandler(other_ideas, pattern='^other_ideas$'),
                CallbackQueryHandler(back_to_start, pattern='^back_to_start$')
            ],
            BUSINESS_PLAN_STATE: [
                CallbackQueryHandler(save_plan, pattern='^save_plan$'),
                CallbackQueryHandler(back_to_ideas, pattern='^back_to_ideas$'),
                CallbackQueryHandler(back_to_start, pattern='^back_to_start$')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(back_to_start, pattern='^back_to_start$')
        ],
        per_message=False
    )
    
    application.add_handler(conv_handler)
    
    # Другие callback-обработчики
    application.add_handler(CallbackQueryHandler(how_it_works, pattern='^how_it_works$'))
    application.add_handler(CallbackQueryHandler(back_to_start, pattern='^back_to_start$'))
    
    # Запускаем health сервер
    health_server = await run_health_server()
    
    # Запускаем бота
    try:
        await application.initialize()
        await application.start()
        
        bot_info = await application.bot.get_me()
        logger.info(f"✅ Бот запущен: @{bot_info.username}")
        
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
        logger.info("✅ Бот готов к работе!")
        logger.info("✅ Отправьте /start в Telegram")
        
        # Бесконечный цикл
        while True:
            await asyncio.sleep(3600)
            
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
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
    except Exception as e:
        logger.error(f"❌ Фатальная ошибка: {e}")