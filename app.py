#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Бизнес-навигатор: Telegram бот для подбора бизнес-идей
Версия 3.0 - Интеграция OpenAI, персонализация
"""

import os
import logging
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
import re

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

from openai import OpenAI, AsyncOpenAI
import aiohttp
from aiohttp import web
from jinja2 import Template

# ==================== НАСТРОЙКА ====================
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
    "🎓 *Какое у вас образование, курсы или сертификаты?*",
    "🔧 *Какие технические навыки у вас есть?*\n_Что умеете делать?_",
    "💼 *Какие профессиональные навыки?*\n_Что умеете в работе?_",
    "🌟 *Какие у вас сильные личные качества?*",
    "❤️ *Какие сферы или темы вам интересны?*",
    "📅 *Какой у вас опыт работы?*",
    "💰 *Какой стартовый бюджет есть для бизнеса?*\n_В рублях, например: 50000_",
    "⏰ *Сколько времени готовы уделять бизнесу в неделю?*\n_Часов, например: 20_",
    "👥 *Есть ли у вас команда или партнеры для бизнеса?*",
    "🎲 *Насколько вы готовы к риску?*\n_1-10, где 1 - минимальный риск, 10 - максимальный_",
    "🏢 *Какой формат бизнеса предпочитаете?*\n_онлайн/офлайн/смешанный_",
    "🛠️ *Есть ли у вас специальные ресурсы или доступ к чему-то?*",
    "📆 *На какой срок планируете этот бизнес?*\n_например: 1 год, 3 года, долгосрочно_",
    "🎯 *Какие цели у вас кроме заработка денег?*",
    "🎨 *Есть ли у вас хобби, которые можно превратить в бизнес?*"
]

# ==================== OPENAI КЛИЕНТ ====================
class OpenAIClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = None
        self.is_available = False
        
    async def initialize(self):
        """Проверка подключения к OpenAI"""
        if not self.api_key:
            logger.warning("❌ OPENAI_API_KEY не найден в переменных окружения")
            self.is_available = False
            return False
            
        try:
            self.client = AsyncOpenAI(api_key=self.api_key)
            
            # Тестовый запрос для проверки
            test_response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Тест"}],
                max_tokens=5
            )
            
            self.is_available = True
            logger.info("✅ OpenAI API успешно подключен")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к OpenAI: {e}")
            self.is_available = False
            return False
    
    def create_ideas_prompt(self, answers: Dict[int, str]) -> str:
        """Создание промта для генерации идей"""
        
        # Собираем все ответы в структурированный текст
        answers_text = "\n".join([f"{i+1}. {QUESTIONS[i].split('*')[1]} {answer}" 
                                 for i, answer in answers.items()])
        
        prompt = f"""Ты - бизнес-консультант. На основе следующих данных пользователя предложи 5 КОНКРЕТНЫХ бизнес-идей:

ДАННЫЕ ПОЛЬЗОВАТЕЛЯ:
{answers_text}

ТРЕБОВАНИЯ К ИДЕЯМ:
1. Каждая идея должна быть РЕАЛЬНОЙ и выполнимой
2. Учитывай бюджет, навыки и интересы пользователя
3. Идеи должны быть РАЗНЫМИ по формату (услуги, продукты, онлайн, офлайн)
4. Для каждой идеи укажи:
   - Название (1 строка)
   - Краткое описание (2-3 предложения)
   - Почему подходит пользователю (1-2 предложения)
5. Формат вывода ТОЛЬКО JSON:
{{
  "ideas": [
    {{
      "id": 1,
      "name": "Название идеи",
      "description": "Описание идеи",
      "why_suitable": "Почему подходит"
    }}
  ]
}}

Верни ТОЛЬКО JSON, без дополнительного текста."""
        
        return prompt
    
    def create_plan_prompt(self, answers: Dict[int, str], selected_idea: str) -> str:
        """Создание промта для детального плана"""
        
        # Извлекаем ключевую информацию
        budget = answers.get(7, "не указан")
        time_per_week = answers.get(8, "не указано")
        risk_level = answers.get(10, "5")
        city = answers.get(0, "не указан")
        
        prompt = f"""Ты - бизнес-консультант. Создай ДЕТАЛЬНЫЙ бизнес-план для следующей идеи:

ВЫБРАННАЯ ИДЕЯ: {selected_idea}

ДАННЫЕ ПОЛЬЗОВАТЕЛЯ:
- Город: {city}
- Бюджет: {budget} рублей
- Время в неделю: {time_per_week} часов
- Уровень риска: {risk_level}/10
- Прочие данные: {json.dumps(answers, ensure_ascii=False, indent=2)}

ТРЕБОВАНИЯ К ПЛАНУ:
1. Реалистичность - план должен быть выполним
2. Конкретность - четкие шаги и сроки
3. Финансовая часть - расчеты доходов/расходов
4. Маркетинг - как привлекать клиентов
5. Риски и их минимизация

Структура плана:
1. **Описание бизнеса** (что, для кого, уникальность)
2. **Анализ рынка** (конкуренты, спрос, тренды)
3. **Маркетинг-план** (как находить клиентов)
4. **Операционный план** (ежедневные процессы)
5. **Финансовый план** (стартовые вложения, доходы, расходы, окупаемость)
6. **Пошаговый план на 3 месяца** (конкретные действия по неделям)

Формат вывода - ЧИСТЫЙ текст Markdown, без JSON."""
        
        return prompt
    
    async def generate_business_ideas(self, answers: Dict[int, str]) -> Optional[List[Dict]]:
        """Генерация бизнес-идей через OpenAI"""
        if not self.is_available or not self.client:
            return None
            
        try:
            prompt = self.create_ideas_prompt(answers)
            
            response = await self.client.chat.completions.create(
                model="gpt-4-turbo-preview",  # Или gpt-3.5-turbo для экономии
                messages=[
                    {"role": "system", "content": "Ты - опытный бизнес-консультант."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content
            
            # Извлекаем JSON из ответа
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                return data.get("ideas", [])
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации идей: {e}")
            return None
    
    async def generate_business_plan(self, answers: Dict[int, str], selected_idea: str) -> Optional[str]:
        """Генерация бизнес-плана через OpenAI"""
        if not self.is_available or not self.client:
            return None
            
        try:
            prompt = self.create_plan_prompt(answers, selected_idea)
            
            response = await self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "Ты - детальный бизнес-планировщик."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=2500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации плана: {e}")
            return None

# Глобальный клиент OpenAI
openai_client = OpenAIClient()

# ==================== МОДЕЛИ ====================
@dataclass
class BusinessIdea:
    id: int
    name: str
    description: str
    why_suitable: str
    plan_generated: bool = False

@dataclass
class UserProfile:
    user_id: int
    timestamp: datetime = field(default_factory=datetime.now)
    answers: Dict[int, str] = field(default_factory=dict)
    current_question: int = 0
    business_ideas: List[BusinessIdea] = field(default_factory=list)
    selected_idea: Optional[BusinessIdea] = None
    business_plan: str = ""
    viewing_idea_index: int = 0

user_sessions: Dict[int, UserProfile] = {}

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    
    # Проверяем доступность OpenAI
    openai_status = "✅" if openai_client.is_available else "⚠️"
    
    welcome_text = f"""
{openai_status} *Добро пожаловать в Бизнес-Навигатор!*

🤖 *Режим работы:* {'AI-консультант (GPT)' if openai_client.is_available else 'Базовый режим'}

📋 *Что я сделаю:*
1. Задам 16 вопросов о вас
2. Сгенерирую 5 ПЕРСОНАЛИЗИРОВАННЫХ бизнес-идей
3. Подробно распишу план для выбранной идеи
4. Сохраню результат

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
    
    await send_question(profile, query)
    return QUESTIONNAIRE_STATE

async def send_question(profile: UserProfile, query=None, message=None):
    """Отправка текущего вопроса"""
    current_q = profile.current_question
    progress = "🟢" * (current_q + 1) + "⚪" * (len(QUESTIONS) - current_q - 1)
    
    text = f"""
{progress}
📝 *Вопрос {current_q + 1} из {len(QUESTIONS)}*

{QUESTIONS[current_q]}

✏️ *Напишите ответ:*
"""
    
    if query:
        await query.edit_message_text(text, parse_mode='Markdown')
    elif message:
        await message.reply_text(text, parse_mode='Markdown')

async def handle_questionnaire_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответов на вопросы"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if user_id not in user_sessions:
        await update.message.reply_text("❌ Сессия устарела. Нажмите /start")
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
        return await generate_business_ideas_ai(update, context)
    
    # Показываем следующий вопрос
    await send_question(profile, message=update.message)
    return QUESTIONNAIRE_STATE

async def generate_business_ideas_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация бизнес-идей через AI"""
    user_id = update.effective_user.id
    
    if user_id not in user_sessions:
        await update.message.reply_text("❌ Данные не найдены. Нажмите /start")
        return ConversationHandler.END
    
    profile = user_sessions[user_id]
    
    # Показываем статус
    status_msg = await update.message.reply_text("🧠 *Генерирую персонализированные идеи...*", parse_mode='Markdown')
    
    # Генерируем идеи через OpenAI
    if openai_client.is_available:
        ideas_data = await openai_client.generate_business_ideas(profile.answers)
        
        if ideas_data:
            # Преобразуем в объекты BusinessIdea
            profile.business_ideas = [
                BusinessIdea(
                    id=idea["id"],
                    name=idea["name"],
                    description=idea["description"],
                    why_suitable=idea.get("why_suitable", "")
                ) for idea in ideas_data[:5]  # Берем максимум 5 идей
            ]
            
            await status_msg.delete()
            return await show_business_idea(update, context, idea_index=0)
        else:
            await status_msg.edit_text("⚠️ *AI не сгенерировал идеи. Использую базовые варианты...*", parse_mode='Markdown')
            await asyncio.sleep(1)
    
    # Fallback - базовые идеи если AI не сработал
    return await generate_fallback_ideas(update, context)

async def generate_fallback_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Резервная генерация идей"""
    user_id = update.effective_user.id
    profile = user_sessions[user_id]
    
    city = profile.answers.get(0, "вашем городе")
    
    # Базовые идеи
    fallback_ideas = [
        BusinessIdea(
            id=1,
            name=f"Контент-услуги в {city}",
            description="Создание контента для местного бизнеса: фото, видео, тексты для соцсетей и сайтов.",
            why_suitable="Минимальные вложения, можно начать с имеющихся навыков"
        ),
        BusinessIdea(
            id=2,
            name="Онлайн-консультации",
            description="Консультации по вашей профессиональной теме через Zoom/Telegram.",
            why_suitable="Работа из дома, гибкий график, масштабируемость"
        ),
        BusinessIdea(
            id=3,
            name=f"Услуги для дома в {city}",
            description="Ремонт, уборка, сборка мебели и другие бытовые услуги.",
            why_suitable="Постоянный спрос, можно начать без помещения"
        ),
        BusinessIdea(
            id=4,
            name="Обучение через Telegram-канал",
            description="Создание образовательного канала по вашей теме с платным контентом.",
            why_suitable="Пассивный доход после настройки, низкие затраты"
        ),
        BusinessIdea(
            id=5,
            name="Посреднические услуги",
            description="Соединение клиентов с исполнителями в вашей сфере знаний.",
            why_suitable="Использование ваших профессиональных связей и знаний рынка"
        )
    ]
    
    profile.business_ideas = fallback_ideas
    return await show_business_idea(update, context, idea_index=0)

async def show_business_idea(update: Update, context: ContextTypes.DEFAULT_TYPE, idea_index: int):
    """Показ одной бизнес-идеи"""
    user_id = update.effective_user.id
    profile = user_sessions[user_id]
    
    if not profile.business_ideas or idea_index >= len(profile.business_ideas):
        await update.message.reply_text("❌ Идеи не найдены. Начните заново /start")
        return ConversationHandler.END
    
    profile.viewing_idea_index = idea_index
    idea = profile.business_ideas[idea_index]
    
    # Формируем сообщение
    text = f"""
🎯 *ИДЕЯ {idea_index + 1} из {len(profile.business_ideas)}*

*{idea.name}*

📝 *Описание:*
{idea.description}

✅ *Почему вам подходит:*
{idea.why_suitable}
"""
    
    # Кнопки навигации
    keyboard = []
    
    # Кнопки для переключения между идеями
    if len(profile.business_ideas) > 1:
        row = []
        if idea_index > 0:
            row.append(InlineKeyboardButton("◀️ Предыдущая", callback_data=f'prev_idea'))
        row.append(InlineKeyboardButton(f"{idea_index + 1}/{len(profile.business_ideas)}", callback_data='show_index'))
        if idea_index < len(profile.business_ideas) - 1:
            row.append(InlineKeyboardButton("Следующая ▶️", callback_data=f'next_idea'))
        keyboard.append(row)
    
    # Кнопка выбора текущей идеи
    keyboard.append([InlineKeyboardButton(f"✅ Выбрать эту идею", callback_data=f'select_idea_{idea_index}')])
    
    # Кнопка возврата
    keyboard.append([InlineKeyboardButton("🔄 Сгенерировать новые идеи", callback_data='regenerate_ideas')])
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
    
    current_index = profile.viewing_idea_index
    
    if query.data == 'prev_idea' and current_index > 0:
        new_index = current_index - 1
    elif query.data == 'next_idea' and current_index < len(profile.business_ideas) - 1:
        new_index = current_index + 1
    else:
        return await show_business_idea(update, context, current_index)
    
    return await show_business_idea(update, context, new_index)

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
    idea_index = int(query.data.split('_')[-1])
    
    if idea_index < 0 or idea_index >= len(profile.business_ideas):
        await query.edit_message_text("❌ Неверный индекс идеи")
        return BUSINESS_IDEAS_STATE
    
    profile.selected_idea = profile.business_ideas[idea_index]
    
    # Показываем статус генерации
    await query.edit_message_text(
        f"🧠 *Генерирую детальный бизнес-план для:*\n\n*{profile.selected_idea.name}*\n\n*Пожалуйста, подождите 20-30 секунд...*",
        parse_mode='Markdown'
    )
    
    # Генерируем план через AI
    business_plan = None
    if openai_client.is_available:
        business_plan = await openai_client.generate_business_plan(
            profile.answers,
            f"{profile.selected_idea.name}\n{profile.selected_idea.description}"
        )
    
    # Fallback если AI не сработал
    if not business_plan:
        business_plan = create_fallback_plan(profile)
    
    profile.business_plan = business_plan
    
    # Показываем план
    return await show_business_plan(update, context)

def create_fallback_plan(profile: UserProfile) -> str:
    """Резервный бизнес-план"""
    idea = profile.selected_idea
    city = profile.answers.get(0, "вашем городе")
    budget = profile.answers.get(7, "50000")
    
    return f"""
# 📈 БИЗНЕС-ПЛАН: {idea.name}

## 🎯 Описание бизнеса
{idea.description}

## 📍 Целевая аудитория
- Жители {city}
- Малый и средний бизнес в регионе
- Частные клиенты

## 💰 Финансовый план
- Стартовые вложения: {budget} руб
- Ежемесячные расходы: 15,000 - 30,000 руб
- Средний чек: 3,000 - 10,000 руб
- Окупаемость: 3-6 месяцев

## 🚀 Пошаговый план на 3 месяца

### Месяц 1: Подготовка
1. Создать портфолио (3-5 примеров работ)
2. Настроить соцсети (Telegram, VK)
3. Подготовить коммерческое предложение

### Месяц 2: Поиск клиентов
1. Предложить услуги 10-15 местным бизнесам
2. Сделать 2-3 проекта по специальной цене
3. Собрать первые отзывы

### Месяц 3: Масштабирование
1. Запустить таргетированную рекламу
2. Наладить входящий поток заявок
3. Оптимизировать процессы

## 📊 Потенциальные риски
1. Сезонность спроса
2. Конкуренция
3. Нестабильность заказов

## ✅ Рекомендации
1. Начинайте с малого
2. Собирайте отзывы после каждого проекта
3. Постепенно повышайте цены
"""

async def show_business_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать сгенерированный бизнес-план"""
    query = update.callback_query
    user_id = query.from_user.id
    profile = user_sessions[user_id]
    
    # Разбиваем план на части (Telegram ограничение 4096 символов)
    plan_parts = split_text(profile.business_plan, max_length=4000)
    
    # Отправляем первую часть с кнопками
    text = f"""
🎯 *ДЕТАЛЬНЫЙ БИЗНЕС-ПЛАН*

*{profile.selected_idea.name}*

{plan_parts[0]}
"""
    
    keyboard = [
        [InlineKeyboardButton("💾 Сохранить в PDF", callback_data='save_pdf')],
        [InlineKeyboardButton("🔄 Выбрать другую идею", callback_data='back_to_ideas')],
        [InlineKeyboardButton("🏠 Начать заново", callback_data='back_to_start')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Отправляем остальные части как отдельные сообщения
    for part in plan_parts[1:]:
        await context.bot.send_message(
            chat_id=user_id,
            text=part,
            parse_mode='Markdown'
        )
    
    return BUSINESS_PLAN_STATE

async def save_to_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение плана в PDF (заглушка для будущей реализации)"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    profile = user_sessions[user_id]
    
    # Создаем простой текстовый файл (в будущем - PDF)
    pdf_content = f"""
БИЗНЕС-ПЛАН
Сгенерирован: {profile.timestamp.strftime('%Y-%m-%d %H:%M')}

ИДЕЯ: {profile.selected_idea.name}

{profile.business_plan}

---
Создано с помощью Бизнес-Навигатора
"""
    
    # В будущем здесь будет генерация настоящего PDF
    # Пока сохраняем как текстовый файл
    
    await query.edit_message_text(
        "📄 *PDF-функция в разработке*\n\n"
        "Пока вы можете скопировать текст плана из сообщений выше.\n\n"
        "Для нового поиска нажмите /start",
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

async def regenerate_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Регенерация идей"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("🔄 *Генерирую новые идеи...*", parse_mode='Markdown')
    
    user_id = query.from_user.id
    if user_id in user_sessions:
        # Очищаем старые идеи
        user_sessions[user_id].business_ideas = []
        user_sessions[user_id].selected_idea = None
    
    return await generate_business_ideas_ai(update, context)

async def back_to_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться к списку идей"""
    query = update.callback_query
    await query.answer()
    
    return await show_business_idea(update, context, idea_index=0)

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
        "👋 *Начнем заново!*\n\nНажмите кнопку чтобы начать новую анкету:",
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

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def split_text(text: str, max_length: int = 4000) -> List[str]:
    """Разделение текста на части"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    while len(text) > max_length:
        # Ищем последний перенос строки до max_length
        split_pos = text.rfind('\n', 0, max_length)
        if split_pos == -1:
            split_pos = max_length
        
        parts.append(text[:split_pos])
        text = text[split_pos:].lstrip()
    
    if text:
        parts.append(text)
    
    return parts

# ==================== HEALTH CHECK ====================
async def health_check(request):
    status = {
        "status": "OK",
        "version": "3.0",
        "openai_available": openai_client.is_available,
        "users_active": len(user_sessions)
    }
    return web.Response(text=json.dumps(status, ensure_ascii=False), content_type='application/json')

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
    
    # Инициализация OpenAI
    logger.info("🔌 Инициализация OpenAI...")
    await openai_client.initialize()
    
    # Получение токена
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    
    if not token:
        logger.error("❌ TELEGRAM_TOKEN не найден!")
        return
    
    logger.info(f"🚀 Запуск Бизнес-бота v3.0 (OpenAI: {openai_client.is_available})")
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_questionnaire, pattern='^start_questionnaire$')
        ],
        states={
            QUESTIONNAIRE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_questionnaire_answer)
            ],
            BUSINESS_IDEAS_STATE: [
                CallbackQueryHandler(navigate_ideas, pattern='^(prev_idea|next_idea)$'),
                CallbackQueryHandler(select_idea, pattern='^select_idea_'),
                CallbackQueryHandler(regenerate_ideas, pattern='^regenerate_ideas$'),
                CallbackQueryHandler(back_to_start, pattern='^back_to_start$')
            ],
            BUSINESS_PLAN_STATE: [
                CallbackQueryHandler(save_to_pdf, pattern='^save_pdf$'),
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