#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Бизнес-навигатор: Telegram бот для подбора бизнес-идей
Версия 3.3 - Упрощенный код, исправлены синтаксические ошибки
"""

import os
import logging
import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Optional
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

import aiohttp
from aiohttp import web

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
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
class BusinessIdea:
    id: int
    title: str
    description: str
    suitability: str

@dataclass
class UserProfile:
    user_id: int
    timestamp: datetime = field(default_factory=datetime.now)
    answers: Dict[int, str] = field(default_factory=dict)
    current_question: int = 0
    business_ideas: List[BusinessIdea] = field(default_factory=list)
    current_idea_index: int = 0
    selected_idea: Optional[BusinessIdea] = None
    business_plan: str = ""
    ai_enabled: bool = True

user_sessions: Dict[int, UserProfile] = {}

# ==================== OPENAI ИНТЕГРАЦИЯ ====================
class OpenAIService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.is_available = bool(self.api_key)
        logger.info(f"🔌 OpenAI статус: {'Доступен' if self.is_available else 'Не доступен'}")
    
    def _create_ideas_prompt(self, answers: Dict[int, str]) -> str:
        """Создание промта для генерации идей (исправленная версия)"""
        context_lines = []
        
        for i, answer in answers.items():
            # Упрощенная версия без сложных f-строк
            question_text = self._extract_question_text(i)
            context_lines.append(f"Вопрос {i+1}: {question_text}")
            context_lines.append(f"Ответ: {answer}")
        
        context = "\n".join(context_lines)
        
        prompt = """Ты - профессиональный бизнес-консультант. На основе профиля пользователя предложи 5 КОНКРЕТНЫХ бизнес-идей.

ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:
{context}

ТРЕБОВАНИЯ:
1. Каждая идея должна быть реалистичной для этого человека
2. Учитывай бюджет, навыки, интересы и местоположение
3. Идеи должны быть разными по формату
4. Для каждой идеи укажи:
   - Название (кратко, 3-7 слов)
   - Описание (2-3 предложения, что конкретно делать)
   - Почему подходит (1 предложение, связь с профилем)

ВЕРНИ ТОЛЬКО JSON в таком формате:
{{
  "ideas": [
    {{
      "id": 1,
      "title": "Название идеи",
      "description": "Описание что делать",
      "suitability": "Почему подходит пользователю"
    }}
  ]
}}

ТОЛЬКО JSON, без лишнего текста."""
        
        return prompt.format(context=context)
    
    def _extract_question_text(self, index: int) -> str:
        """Извлечение текста вопроса"""
        if index >= len(QUESTIONS):
            return f"Вопрос {index+1}"
        
        question = QUESTIONS[index]
        # Упрощенная логика извлечения
        parts = question.split('*')
        if len(parts) > 1:
            return parts[1].strip()
        return question[:50]
    
    def _create_plan_prompt(self, answers: Dict[int, str], idea: BusinessIdea) -> str:
        """Создание промта для бизнес-плана"""
        # Упрощенное извлечение данных
        key_info = []
        
        city = answers.get(0, "не указан")
        budget = answers.get(7, "не указан")
        time_per_week = answers.get(8, "не указано")
        risk = answers.get(10, "не указан")
        format_type = answers.get(11, "не указан")
        
        key_info.append(f"Город: {city}")
        key_info.append(f"Бюджет: {budget}")
        key_info.append(f"Время в неделю: {time_per_week}")
        key_info.append(f"Риск: {risk}")
        key_info.append(f"Формат: {format_type}")
        
        info_str = "\n".join(key_info)
        
        prompt = """Создай ДЕТАЛЬНЫЙ бизнес-план для этой идеи:

ИДЕЯ: {title}
ОПИСАНИЕ: {description}
ПОЧЕМУ ПОДХОДИТ: {suitability}

ДАННЫЕ ПОЛЬЗОВАТЕЛЯ:
{user_info}

СТРУКТУРА ПЛАНА (на русском, Markdown):
1. **Краткое резюме** - суть бизнеса
2. **Анализ рынка** - спрос, конкуренты, ниша
3. **Целевая аудитория** - кто будет покупать
4. **Маркетинг-план** - как привлекать клиентов
5. **Операционный план** - ежедневные процессы
6. **Финансовый план** - стартовые затраты, доходы, окупаемость
7. **Пошаговый план на 3 месяца** - конкретные действия по неделям

Сделай план практичным, с цифрами и конкретными шагами."""
        
        return prompt.format(
            title=idea.title,
            description=idea.description,
            suitability=idea.suitability,
            user_info=info_str
        )
    
    async def generate_business_ideas(self, answers: Dict[int, str]) -> Optional[List[BusinessIdea]]:
        """Генерация бизнес-идей через OpenAI"""
        if not self.is_available:
            logger.warning("OpenAI не доступен, использую запасные идеи")
            return None
        
        try:
            import requests
            
            prompt = self._create_ideas_prompt(answers)
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": "Ты - бизнес-консультант."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                # Извлекаем JSON из ответа
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    json_str = json_match.group()
                    ideas_data = json.loads(json_str)
                    
                    ideas = []
                    for idea_data in ideas_data.get("ideas", [])[:5]:
                        ideas.append(BusinessIdea(
                            id=idea_data.get("id", len(ideas) + 1),
                            title=idea_data.get("title", "Без названия"),
                            description=idea_data.get("description", ""),
                            suitability=idea_data.get("suitability", "")
                        ))
                    
                    logger.info(f"✅ Сгенерировано {len(ideas)} AI-идей")
                    return ideas
            
            logger.error(f"❌ OpenAI ошибка: {response.status_code}")
            return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка генерации идей: {e}")
            return None
    
    async def generate_business_plan(self, answers: Dict[int, str], idea: BusinessIdea) -> Optional[str]:
        """Генерация бизнес-плана через OpenAI"""
        if not self.is_available:
            return None
        
        try:
            import requests
            
            prompt = self._create_plan_prompt(answers, idea)
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": "Ты - бизнес-планировщик."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.5,
                    "max_tokens": 2000
                },
                timeout=45
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                logger.info("✅ Бизнес-план сгенерирован через AI")
                return content
            
            return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка генерации плана: {e}")
            return None

# Глобальный сервис OpenAI
openai_service = OpenAIService()

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    
    user_sessions[user_id] = UserProfile(
        user_id=user_id,
        ai_enabled=openai_service.is_available
    )
    
    ai_status = ""
    if openai_service.is_available:
        ai_status = "✅ (AI-режим)"
    else:
        ai_status = "⚠️ (Базовый режим)"
    
    welcome_text = f"""👋 *Добро пожаловать в Бизнес-Навигатор!* {ai_status}

Я помогу найти бизнес-идею на основе ваших навыков.

📋 *Что я сделаю:*
1. Задам 16 простых вопросов
2. Сгенерирую 5 ПЕРСОНАЛИЗИРОВАННЫХ идей
3. Подробно распишу план для выбранной идеи

⏱️ *Время:* 5-10 минут

🚀 *Готовы начать?*"""
    
    keyboard = [[InlineKeyboardButton("📋 Начать анкету", callback_data='start_questionnaire')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def start_questionnaire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать анкету"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_sessions[user_id] = UserProfile(
        user_id=user_id,
        ai_enabled=openai_service.is_available
    )
    
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
            "🎉 *Анкета завершена!*\n\n🤔 *Анализирую данные и генерирую идеи...*",
            parse_mode='Markdown'
        )
        
        await asyncio.sleep(1)
        return await generate_business_ideas_wrapper(update, context)
    
    # Показываем следующий вопрос
    next_q_num = profile.current_question + 1
    completed = profile.current_question
    remaining = len(QUESTIONS) - profile.current_question
    
    progress = "🟢" * completed + "⚪" * remaining
    
    await update.message.reply_text(
        f"{progress}\n✅ *Ответ сохранен!*\n*Вопрос {next_q_num} из {len(QUESTIONS)}*\n\n{QUESTIONS[profile.current_question]}\n\n✏️ *Напишите ответ:*",
        parse_mode='Markdown'
    )
    
    return QUESTIONNAIRE_STATE

async def generate_business_ideas_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обертка для генерации идей"""
    user_id = update.effective_user.id
    
    if user_id not in user_sessions:
        await update.message.reply_text("❌ Данные не найдены. Начните с /start")
        return ConversationHandler.END
    
    profile = user_sessions[user_id]
    
    # Пытаемся сгенерировать через AI
    ai_ideas = None
    if profile.ai_enabled and openai_service.is_available:
        loading_msg = await update.message.reply_text("🧠 *Генерирую персонализированные идеи через AI...*", parse_mode='Markdown')
        ai_ideas = await openai_service.generate_business_ideas(profile.answers)
        if loading_msg:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=loading_msg.message_id)
            except:
                pass
    
    # Если AI не сработал - базовые идеи
    if not ai_ideas:
        profile.business_ideas = generate_fallback_ideas(profile.answers)
        logger.info(f"📝 Использованы базовые идеи для пользователя {user_id}")
    else:
        profile.business_ideas = ai_ideas
        logger.info(f"🤖 Использованы AI-идеи для пользователя {user_id}")
    
    # Показываем первую идею
    return await show_current_idea(update, context)

def generate_fallback_ideas(answers: Dict[int, str]) -> List[BusinessIdea]:
    """Генерация запасных идей если AI не работает"""
    city = answers.get(0, "вашем городе")
    
    ideas = [
        BusinessIdea(
            id=1,
            title=f"Контент-услуги в {city}",
            description="Создание фото, видео и текстов для местного бизнеса и блогеров. Редактирование, монтаж, копирайтинг.",
            suitability="Использует ваши технические и творческие навыки"
        ),
        BusinessIdea(
            id=2,
            title="Онлайн-консультации и обучение",
            description="Проведение индивидуальных консультаций или групповых вебинаров по вашей профессиональной теме через Zoom/Telegram.",
            suitability="Работа из дома, гибкий график, можно начать без вложений"
        ),
        BusinessIdea(
            id=3,
            title=f"Услуги для дома в {city}",
            description="Ремонтные работы, уборка, сборка мебели, мелкий ремонт техники. Востребованная ниша в любом городе.",
            suitability="Постоянный спрос, можно начать с минимальным оборудованием"
        ),
        BusinessIdea(
            id=4,
            title="Образовательный Telegram-канал",
            description="Создание платного канала с экспертной информацией по вашей теме. Уроки, чек-листы, консультации.",
            suitability="Пассивный доход после настройки, низкие затраты"
        ),
        BusinessIdea(
            id=5,
            title=f"Посреднические услуги в {city}",
            description="Соединение клиентов с исполнителями в вашей сфере знаний. Организация услуг, контроль качества, гарантии.",
            suitability="Использование ваших профессиональных связей и знаний рынка"
        )
    ]
    
    return ideas

async def show_current_idea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать текущую бизнес-идею"""
    user_id = update.effective_user.id
    profile = user_sessions[user_id]
    
    if not profile.business_ideas:
        await update.message.reply_text("❌ Идеи не сгенерированы. Начните заново /start")
        return ConversationHandler.END
    
    idea = profile.business_ideas[profile.current_idea_index]
    total_ideas = len(profile.business_ideas)
    
    text = f"""🎯 *ИДЕЯ {profile.current_idea_index + 1} из {total_ideas}*

*{idea.title}*

📝 *Описание:*
{idea.description}

✅ *Почему вам подходит:*
{idea.suitability}"""
    
    # Кнопки навигации
    keyboard = []
    
    # Кнопки переключения между идеями
    nav_buttons = []
    if profile.current_idea_index > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Предыдущая", callback_data='prev_idea'))
    
    nav_buttons.append(InlineKeyboardButton(f"{profile.current_idea_index + 1}/{total_ideas}", callback_data='show_index'))
    
    if profile.current_idea_index < total_ideas - 1:
        nav_buttons.append(InlineKeyboardButton("Следующая ▶️", callback_data='next_idea'))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Кнопки действий
    keyboard.append([InlineKeyboardButton(f"✅ Выбрать эту идею", callback_data=f'select_idea_{profile.current_idea_index}')])
    keyboard.append([InlineKeyboardButton("🔄 Другие идеи", callback_data='other_ideas')])
    keyboard.append([InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    return BUSINESS_IDEAS_STATE

async def navigate_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Навигация по идеям"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    profile = user_sessions.get(user_id)
    
    if not profile or not profile.business_ideas:
        await query.edit_message_text("❌ Данные не найдены. Нажмите /start")
        return ConversationHandler.END
    
    if query.data == 'prev_idea' and profile.current_idea_index > 0:
        profile.current_idea_index -= 1
    elif query.data == 'next_idea' and profile.current_idea_index < len(profile.business_ideas) - 1:
        profile.current_idea_index += 1
    elif query.data == 'other_ideas':
        # Перегенерировать идеи
        profile.current_idea_index = 0
        if profile.ai_enabled:
            ai_ideas = await openai_service.generate_business_ideas(profile.answers)
            if ai_ideas:
                profile.business_ideas = ai_ideas
    
    return await show_current_idea(update, context)

async def select_idea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор идеи для детального плана"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    profile = user_sessions.get(user_id)
    
    if not profile or not profile.business_ideas:
        await query.edit_message_text("❌ Данные не найдены. Нажмите /start")
        return ConversationHandler.END
    
    # Извлекаем индекс идеи
    try:
        idea_index = int(query.data.split('_')[-1])
    except:
        idea_index = 0
    
    if idea_index < 0 or idea_index >= len(profile.business_ideas):
        await query.edit_message_text("❌ Неверный индекс идеи")
        return BUSINESS_IDEAS_STATE
    
    profile.selected_idea = profile.business_ideas[idea_index]
    
    # Генерируем план через AI или запасной
    await query.edit_message_text(
        f"🧠 *Генерирую детальный бизнес-план для:*\n\n*{profile.selected_idea.title}*\n\n⏳ *Пожалуйста, подождите...*",
        parse_mode='Markdown'
    )
    
    business_plan = None
    if profile.ai_enabled and openai_service.is_available:
        business_plan = await openai_service.generate_business_plan(profile.answers, profile.selected_idea)
    
    # Запасной план если AI не сработал
    if not business_plan:
        business_plan = generate_fallback_plan(profile.answers, profile.selected_idea)
    
    profile.business_plan = business_plan
    
    # Показываем план
    return await show_business_plan(update, context)

def generate_fallback_plan(answers: Dict[int, str], idea: BusinessIdea) -> str:
    """Запасной бизнес-план"""
    city = answers.get(0, "вашем городе")
    budget = answers.get(7, "50,000 рублей")
    
    plan = f"""# 📈 БИЗНЕС-ПЛАН: {idea.title}

## 🎯 Краткое резюме
{idea.description}

## 📍 Анализ рынка в {city}
- Высокий спрос на услуги такого типа
- Конкуренция средняя, есть место для новых игроков
- Цены в среднем от 3,000 до 15,000 рублей за проект

## 🎯 Целевая аудитория
- Малый и средний бизнес в {city}
- Частные клиенты
- Студенты и фрилансеры

## 📢 Маркетинг-план
1. Создание аккаунтов в соцсетях (Telegram, VK)
2. Реклама в местных группах и чатах
3. Первые проекты по специальной цене для портфолио
4. Сбор отзывов и рекомендаций

## ⚙️ Операционный план
- Рабочее место: дом/коворкинг
- Оборудование: компьютер, телефон, базовые инструменты
- Режим работы: гибкий график

## 💰 Финансовый план
- Стартовые вложения: {budget}
- Ежемесячные расходы: 5,000 - 15,000 руб
- Средний доход в месяц: 30,000 - 80,000 руб
- Окупаемость: 2-4 месяца

## 🗓️ Пошаговый план на 3 месяца

### Месяц 1: Подготовка
1. Создать портфолио (3-5 работ)
2. Настроить соцсети
3. Подготовить коммерческое предложение

### Месяц 2: Поиск клиентов
1. Предложить услуги 10-15 бизнесам
2. Сделать 2-3 проекта по специальной цене
3. Собрать первые отзывы

### Месяц 3: Развитие
1. Запустить таргетированную рекламу
2. Наладить регулярный поток заказов
3. Оптимизировать процессы работы"""
    
    return plan

async def show_business_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать бизнес-план"""
    query = update.callback_query
    user_id = query.from_user.id
    profile = user_sessions[user_id]
    
    # Разбиваем план на части (ограничение Telegram - 4096 символов)
    plan_text = profile.business_plan
    max_length = 4000
    
    if len(plan_text) <= max_length:
        parts = [plan_text]
    else:
        parts = []
        while len(plan_text) > max_length:
            # Ищем последний перенос строки
            split_pos = plan_text.rfind('\n', 0, max_length)
            if split_pos == -1:
                split_pos = max_length
            
            parts.append(plan_text[:split_pos])
            plan_text = plan_text[split_pos:].lstrip()
        
        if plan_text:
            parts.append(plan_text)
    
    # Отправляем первую часть с кнопками
    text = f"""🎯 *ДЕТАЛЬНЫЙ БИЗНЕС-ПЛАН*

*{profile.selected_idea.title}*

{parts[0]}"""
    
    keyboard = [
        [InlineKeyboardButton("📄 Скачать PDF (скоро)", callback_data='pdf_soon')],
        [InlineKeyboardButton("🔄 Выбрать другую идею", callback_data='back_to_ideas')],
        [InlineKeyboardButton("🏠 Начать заново", callback_data='back_to_start')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Отправляем остальные части
    for part in parts[1:]:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=part,
                parse_mode='Markdown'
            )
        except:
            pass
    
    return BUSINESS_PLAN_STATE

async def pdf_soon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Заглушка для PDF"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📄 *PDF-функция в разработке*\n\nСкоро вы сможете скачать красивый PDF с вашим бизнес-планом!\n\nА пока можете скопировать текст плана из сообщений выше.\n\nДля нового поиска нажмите /start",
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

async def back_to_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться к идеям"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    profile = user_sessions.get(user_id)
    
    if not profile:
        await query.edit_message_text("❌ Данные не найдены. Нажмите /start")
        return ConversationHandler.END
    
    profile.current_idea_index = 0
    return await show_current_idea(update, context)

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в начало"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
    
    keyboard = [[InlineKeyboardButton("📋 Начать анкету", callback_data='start_questionnaire')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👋 *Снова здравствуйте!*\n\nНажмите кнопку чтобы начать новую анкету:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

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
    status = {
        "status": "OK",
        "version": "3.3",
        "openai_available": openai_service.is_available,
        "active_sessions": len(user_sessions)
    }
    return web.Response(
        text=json.dumps(status, ensure_ascii=False, indent=2),
        content_type='application/json'
    )

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
    
    logger.info(f"🚀 Запуск Бизнес-бота v3.3 (OpenAI: {openai_service.is_available})")
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем команды
    application.add_handler(CommandHandler("start", start))
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
                CallbackQueryHandler(navigate_ideas, pattern='^(prev_idea|next_idea|other_ideas)$'),
                CallbackQueryHandler(select_idea, pattern='^select_idea_'),
                CallbackQueryHandler(back_to_start, pattern='^back_to_start$')
            ],
            BUSINESS_PLAN_STATE: [
                CallbackQueryHandler(pdf_soon, pattern='^pdf_soon$'),
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