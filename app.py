#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Бизнес-навигатор: Telegram бот для подбора бизнес-идей
Версия 4.0 - Креативные идеи, детальные планы, мониторинг токенов
"""

import os
import logging
import asyncio
import json
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

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

class IdeaType(Enum):
    NORMAL = "normal"
    CREATIVE = "creative"

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
    idea_type: IdeaType = IdeaType.NORMAL
    creativity_level: int = 5  # 1-10

@dataclass
class TokenUsage:
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost: float = 0.0
    last_reset: datetime = field(default_factory=datetime.now)
    
    def add_usage(self, prompt_tokens: int, completion_tokens: int):
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens = self.prompt_tokens + self.completion_tokens
        # Примерная стоимость: $0.002 за 1K токенов для GPT-3.5
        self.estimated_cost = self.total_tokens * 0.002 / 1000
    
    def get_usage_percentage(self, max_tokens: int = 100000) -> float:
        """Возвращает процент использованных токенов"""
        if max_tokens <= 0:
            return 0.0
        percentage = (self.total_tokens / max_tokens) * 100
        return min(percentage, 100.0)
    
    def get_remaining_percentage(self, max_tokens: int = 100000) -> float:
        return max(0.0, 100.0 - self.get_usage_percentage(max_tokens))
    
    def get_usage_bar(self, max_tokens: int = 100000) -> str:
        """Возвращает прогресс-бар использования токенов"""
        used_percent = self.get_usage_percentage(max_tokens)
        used_blocks = int(used_percent / 10)
        remaining_blocks = 10 - used_blocks
        
        bar = "🟢" * used_blocks + "⚪" * remaining_blocks
        
        if used_percent >= 80:
            bar = "🔴" * used_blocks + "⚪" * remaining_blocks
        elif used_percent >= 50:
            bar = "🟡" * used_blocks + "⚪" * remaining_blocks
        
        return f"{bar} {used_percent:.1f}%"

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
    show_creative_ideas: bool = False

user_sessions: Dict[int, UserProfile] = {}
token_usage = TokenUsage()

# ==================== OPENAI ИНТЕГРАЦИЯ ====================
class OpenAIService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.is_available = bool(self.api_key)
        logger.info(f"🔌 OpenAI статус: {'Доступен' if self.is_available else 'Не доступен'}")
    
    def _create_ideas_prompt(self, answers: Dict[int, str], idea_type: IdeaType = IdeaType.NORMAL) -> str:
        """Создание промта для генерации идей с разным уровнем креативности"""
        context_lines = []
        
        for i, answer in answers.items():
            question_text = self._extract_question_text(i)
            context_lines.append(f"Вопрос {i+1}: {question_text}")
            context_lines.append(f"Ответ: {answer}")
        
        context = "\n".join(context_lines)
        
        creativity_instruction = ""
        if idea_type == IdeaType.CREATIVE:
            creativity_instruction = """
ТРЕБОВАНИЯ К КРЕАТИВНОСТИ:
1. Идеи должны быть НЕОБЫЧНЫМИ, но реалистичными
2. Используй нестандартные комбинации навыков и интересов
3. Предложи уникальные форматы монетизации
4. Включи элементы геймификации, сообщества или подписочной модели
5. Идеи должны вызывать "ВАУ-эффект" но оставаться выполнимыми
"""
        else:
            creativity_instruction = """
ТРЕБОВАНИЯ:
1. Идеи должны быть ПРАКТИЧНЫМИ и выполнимыми
2. Учитывай бюджет, навыки, интересы и местоположение
3. Сделай акцент на быстром старте и низких рисках
"""
        
        prompt = f"""Ты - креативный бизнес-консультант с 20-летним опытом. На основе профиля пользователя предложи 10 бизнес-идей.

ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:
{context}

{creativity_instruction}

ФОРМАТ ВЫВОДА ТОЛЬКО JSON:
{{
  "ideas": [
    {{
      "id": 1,
      "title": "Название идеи (максимум 7 слов)",
      "description": "Краткое описание 2-3 предложения",
      "suitability": "Почему подходит именно этому пользователю (1 предложение)",
      "creativity_level": 7,
      "idea_type": "{idea_type.value}"
    }}
  ]
}}

ДЛЯ ВСЕХ ИДЕЙ УКАЖИ creativity_level от 1 до 10, где 10 - максимально креативная.

ТОЛЬКО JSON, без лишнего текста."""
        
        return prompt
    
    def _create_detailed_plan_prompt(self, answers: Dict[int, str], idea: BusinessIdea) -> str:
        """Создание промта для ДЕТАЛЬНОГО бизнес-плана"""
        key_info = {
            "Город": answers.get(0, "не указан"),
            "Бюджет": answers.get(7, "не указан"),
            "Время в неделю": answers.get(8, "не указано"),
            "Риск": answers.get(10, "не указан"),
            "Формат": answers.get(11, "не указан"),
            "Сроки": answers.get(13, "не указаны"),
            "Цели": answers.get(14, "не указаны")
        }
        
        info_str = "\n".join([f"{k}: {v}" for k, v in key_info.items()])
        
        prompt = f"""Создай ПОЛНЫЙ И ДЕТАЛЬНЫЙ бизнес-план для этой идеи:

🎯 ИДЕЯ: {idea.title}
📝 ОПИСАНИЕ: {idea.description}
✅ ПОДХОДИТ ПОТОМУ ЧТО: {idea.suitability}
🎨 УРОВЕНЬ КРЕАТИВНОСТИ: {idea.creativity_level}/10

📊 ДАННЫЕ ПОЛЬЗОВАТЕЛЬКА:
{info_str}

📋 ТРЕБУЕМАЯ СТРУКТУРА ПЛАНА (Markdown на русском):

## 1. 🎯 Краткое резюме бизнеса
- Суть проекта в 3-4 предложениях
- Уникальное торговое предложение
- Ценность для клиентов

## 2. 📈 Анализ рынка и конкуренции
- Размер рынка в регионе
- Основные конкуренты и их слабые стороны
- Незанятая ниша
- Тренды и перспективы роста

## 3. 🎯 Целевая аудитория (3 сегмента)
- Демография, интересы, боли
- Где искать клиентов
- Средний чек и частота покупок

## 4. 📱 Маркетинг-план на 6 месяцев
### Месяц 1-2: Запуск
### Месяц 3-4: Рост
### Месяц 5-6: Стабилизация
(конкретные каналы, бюджет, KPI)

## 5. ⚙️ Операционный план
- Ежедневные процессы
- Необходимое оборудование/софт
- Требования к помещению (если нужно)
- Юридические аспекты

## 6. 💰 ФИНАНСОВЫЙ ПЛАН (САМОЕ ВАЖНОЕ!)
### Стартовые инвестиции:
- Оборудование: XXX руб
- Регистрация: XXX руб
- Первая реклама: XXX руб
- Резервный фонд: XXX руб
- **ИТОГО: XXX руб**

### Ежемесячные расходы:
- Аренда: XXX руб
- Реклама: XXX руб
- Зарплаты: XXX руб
- Налоги: XXX руб
- **ИТОГО: XXX руб/мес**

### План доходов:
- **Выход в ноль (break-even):** Через X месяцев
- **Доход 50,000 руб/мес:** Через Y месяцев
- **Доход 100,000 руб/мес:** Через Z месяцев

### Детальный план на 12 месяцев:
| Месяц | Расходы | Доходы | Прибыль | Накоплено |
|-------|---------|--------|---------|-----------|
| 1     | XXX     | XXX    | -XXX    | -XXX      |
| 2     | XXX     | XXX    | -XXX    | -XXX      |
| ... продолжай до месяца 12 ...

## 7. 🚀 Пошаговый план запуска (первые 30 дней)
### Неделя 1: Подготовка
### Неделя 2: Создание активов
### Неделя 3: Тестовые продажи
### Неделя 4: Анализ и корректировка
(конкретные задачи по дням)

## 8. ⚠️ Риски и их минимизация
- Основные риски (финансовые, операционные, рыночные)
- Стратегии минимизации каждого риска
- План Б на случай провала

## 9. 📈 Показатели успеха (KPI)
- Ежедневные/еженедельные/ежемесячные метрики
- Критические точки контроля
- Когда масштабироваться

💡 Сделай план максимально практичным, с конкретными цифрами и сроками. Используй таблицы где это уместно."""
        
        return prompt
    
    def _extract_question_text(self, index: int) -> str:
        """Извлечение текста вопроса"""
        if index >= len(QUESTIONS):
            return f"Вопрос {index+1}"
        
        question = QUESTIONS[index]
        parts = question.split('*')
        if len(parts) > 1:
            return parts[1].strip()
        return question[:50]
    
    async def generate_business_ideas(self, answers: Dict[int, str], idea_type: IdeaType = IdeaType.NORMAL) -> Optional[List[BusinessIdea]]:
        """Генерация бизнес-идей через OpenAI с отслеживанием токенов"""
        if not self.is_available:
            logger.warning("OpenAI не доступен, использую запасные идеи")
            return None
        
        try:
            import requests
            
            prompt = self._create_ideas_prompt(answers, idea_type)
            
            start_time = time.time()
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4-turbo-preview",  # Используем GPT-4 для креативности
                    "messages": [
                        {"role": "system", "content": "Ты - креативный бизнес-консультант с 20-летним опытом."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.8 if idea_type == IdeaType.CREATIVE else 0.7,
                    "max_tokens": 3000,
                    "top_p": 0.9
                },
                timeout=45
            )
            
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                # Отслеживаем использование токенов
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                
                token_usage.add_usage(prompt_tokens, completion_tokens)
                
                logger.info(f"📊 Токены: +{completion_tokens} (prompt: {prompt_tokens}), всего: {token_usage.total_tokens}")
                logger.info(f"⏱️ Время генерации: {elapsed_time:.2f} сек")
                
                # Извлекаем JSON из ответа
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    json_str = json_match.group()
                    ideas_data = json.loads(json_str)
                    
                    ideas = []
                    for idea_data in ideas_data.get("ideas", [])[:10]:  # Берем максимум 10
                        ideas.append(BusinessIdea(
                            id=idea_data.get("id", len(ideas) + 1),
                            title=idea_data.get("title", "Без названия"),
                            description=idea_data.get("description", ""),
                            suitability=idea_data.get("suitability", ""),
                            idea_type=IdeaType(idea_data.get("idea_type", "normal")),
                            creativity_level=idea_data.get("creativity_level", 5)
                        ))
                    
                    logger.info(f"✅ Сгенерировано {len(ideas)} {idea_type.value} идей")
                    return ideas
            
            logger.error(f"❌ OpenAI ошибка: {response.status_code}")
            return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка генерации идей: {e}")
            return None
    
    async def generate_detailed_business_plan(self, answers: Dict[int, str], idea: BusinessIdea) -> Optional[str]:
        """Генерация детального бизнес-плана через OpenAI"""
        if not self.is_available:
            return None
        
        try:
            import requests
            
            prompt = self._create_detailed_plan_prompt(answers, idea)
            
            start_time = time.time()
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4-turbo-preview",
                    "messages": [
                        {"role": "system", "content": "Ты - опытный бизнес-планировщик с финансовым образованием."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.5,
                    "max_tokens": 4000,
                    "top_p": 0.8
                },
                timeout=60
            )
            
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                # Отслеживаем использование токенов
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                
                token_usage.add_usage(prompt_tokens, completion_tokens)
                
                logger.info(f"📊 Токены плана: +{completion_tokens} (prompt: {prompt_tokens})")
                logger.info(f"⏱️ Время генерации плана: {elapsed_time:.2f} сек")
                logger.info("✅ Детальный бизнес-план сгенерирован через AI")
                
                return content
            
            return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка генерации плана: {e}")
            return None

# Глобальный сервис OpenAI
openai_service = OpenAIService()

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start с отображением использования токенов"""
    user = update.effective_user
    user_id = user.id
    
    user_sessions[user_id] = UserProfile(
        user_id=user_id,
        ai_enabled=openai_service.is_available
    )
    
    ai_status = ""
    if openai_service.is_available:
        ai_status = "✅ (AI-режим)"
        # Показываем использование токенов
        token_bar = token_usage.get_usage_bar()
        token_info = f"\n📊 *Использование токенов:* {token_bar}"
        token_info += f"\n💰 *Примерная стоимость:* ${token_usage.estimated_cost:.4f}"
        token_info += f"\n🎯 *Осталось:* {token_usage.get_remaining_percentage():.1f}%"
    else:
        ai_status = "⚠️ (Базовый режим)"
        token_info = ""
    
    welcome_text = f"""👋 *Добро пожаловать в Бизнес-Навигатор 4.0!* {ai_status}

🎯 *Новые возможности:*
• 10 бизнес-идей (5 практичных + 5 креативных)
• Детальные финансовые планы с точными сроками
• План выхода на доход 50,000₽ и 100,000₽ в месяц
• Пошаговые инструкции на 12 месяцев

⏱️ *Время:* 10-15 минут

🚀 *Готовы найти свою идею?*{token_info}"""
    
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
    """Генерация идей (нормальные + креативные)"""
    user_id = update.effective_user.id
    
    if user_id not in user_sessions:
        await update.message.reply_text("❌ Данные не найдены. Начните с /start")
        return ConversationHandler.END
    
    profile = user_sessions[user_id]
    
    # Показываем статус генерации
    loading_msg = await update.message.reply_text(
        "🧠 *Генерирую 10 бизнес-идей...*\n"
        "• 5 практичных идей\n"
        "• 5 креативных идей\n\n"
        "⏳ *Это займет 30-45 секунд*",
        parse_mode='Markdown'
    )
    
    # Генерируем нормальные идеи
    normal_ideas = None
    if profile.ai_enabled and openai_service.is_available:
        normal_ideas = await openai_service.generate_business_ideas(
            profile.answers, 
            IdeaType.NORMAL
        )
    
    # Генерируем креативные идеи
    creative_ideas = None
    if profile.ai_enabled and openai_service.is_available:
        creative_ideas = await openai_service.generate_business_ideas(
            profile.answers, 
            IdeaType.CREATIVE
        )
    
    # Объединяем идеи
    all_ideas = []
    
    if normal_ideas:
        all_ideas.extend(normal_ideas[:5])  # Берем 5 нормальных
    
    if creative_ideas:
        all_ideas.extend(creative_ideas[:5])  # Берем 5 креативных
    
    # Если AI не сработал - базовые идеи
    if not all_ideas:
        all_ideas = generate_fallback_ideas(profile.answers)
        logger.info(f"📝 Использованы базовые идеи для пользователя {user_id}")
    else:
        logger.info(f"🤖 Использованы AI-идеи для пользователя {user_id}")
        logger.info(f"📊 Итого идей: {len(all_ideas)} ({len([i for i in all_ideas if i.idea_type == IdeaType.NORMAL])} нормальных + "
                   f"{len([i for i in all_ideas if i.idea_type == IdeaType.CREATIVE])} креативных)")
    
    profile.business_ideas = all_ideas
    
    # Удаляем сообщение о загрузке
    try:
        await context.bot.delete_message(chat_id=user_id, message_id=loading_msg.message_id)
    except:
        pass
    
    # Показываем первую идею
    return await show_current_idea(update, context)

def generate_fallback_ideas(answers: Dict[int, str]) -> List[BusinessIdea]:
    """Генерация запасных идей если AI не работает"""
    city = answers.get(0, "вашем городе")
    
    ideas = [
        # Нормальные идеи
        BusinessIdea(
            id=1,
            title=f"Контент-услуги в {city}",
            description="Создание фото, видео и текстов для местного бизнеса. Редактирование, монтаж, копирайтинг.",
            suitability="Использует технические и творческие навыки",
            idea_type=IdeaType.NORMAL,
            creativity_level=3
        ),
        BusinessIdea(
            id=2,
            title="Онлайн-консультации",
            description="Индивидуальные консультации по вашей профессиональной теме через Zoom/Telegram.",
            suitability="Работа из дома, гибкий график",
            idea_type=IdeaType.NORMAL,
            creativity_level=4
        ),
        BusinessIdea(
            id=3,
            title=f"Услуги для дома в {city}",
            description="Ремонтные работы, уборка, сборка мебели, мелкий ремонт техники.",
            suitability="Постоянный спрос, можно начать с минимальным оборудованием",
            idea_type=IdeaType.NORMAL,
            creativity_level=3
        ),
        BusinessIdea(
            id=4,
            title="Образовательный Telegram-канал",
            description="Платный канал с экспертной информацией по вашей теме. Уроки, чек-листы.",
            suitability="Пассивный доход после настройки",
            idea_type=IdeaType.NORMAL,
            creativity_level=5
        ),
        BusinessIdea(
            id=5,
            title=f"Посреднические услуги в {city}",
            description="Соединение клиентов с исполнителями в вашей сфере знаний.",
            suitability="Использование профессиональных связей",
            idea_type=IdeaType.NORMAL,
            creativity_level=4
        ),
        # Креативные идеи
        BusinessIdea(
            id=6,
            title="Киберспортивный лагерь для взрослых",
            description="Организация турниров и тренировок по киберспорту для корпоративных клиентов.",
            suitability="Сочетает интересы в технологиях и спорте",
            idea_type=IdeaType.CREATIVE,
            creativity_level=8
        ),
        BusinessIdea(
            id=7,
            title="Виртуальный ассистент по декларированию",
            description="Помощь в заполнении налоговых деклараций через Telegram-бота с AI.",
            suitability="Использует технические навыки и внимание к деталям",
            idea_type=IdeaType.CREATIVE,
            creativity_level=7
        ),
        BusinessIdea(
            id=8,
            title="Экологичная доставка на велосипедах",
            description="Доставка продуктов и товаров на экологичном транспорте с подпиской.",
            suitability="Сочетает здоровый образ жизни и предпринимательство",
            idea_type=IdeaType.CREATIVE,
            creativity_level=6
        ),
        BusinessIdea(
            id=9,
            title="Персонализированные аудио-гиды",
            description="Создание аудио-экскурсий по городу с использованием AI для персонализации.",
            suitability="Творческий подход к туризму и технологиям",
            idea_type=IdeaType.CREATIVE,
            creativity_level=9
        ),
        BusinessIdea(
            id=10,
            title="Онлайн-марафоны по хобби-монетизации",
            description="28-дневные марафоны, где участники превращают хобби в источник дохода.",
            suitability="Помогает другим и создает сообщество",
            idea_type=IdeaType.CREATIVE,
            creativity_level=7
        )
    ]
    
    return ideas

async def show_current_idea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать текущую бизнес-идею с улучшенным оформлением"""
    user_id = update.effective_user.id
    profile = user_sessions[user_id]
    
    if not profile.business_ideas:
        await update.message.reply_text("❌ Идеи не сгенерированы. Начните заново /start")
        return ConversationHandler.END
    
    idea = profile.business_ideas[profile.current_idea_index]
    total_ideas = len(profile.business_ideas)
    
    # Определяем тип идеи
    idea_type_emoji = "💡" if idea.idea_type == IdeaType.NORMAL else "✨"
    idea_type_text = "Практичная идея" if idea.idea_type == IdeaType.NORMAL else "Креативная идея"
    
    # Шкала креативности
    creativity_bar = "⭐" * idea.creativity_level + "☆" * (10 - idea.creativity_level)
    
    text = f"""🎯 *{idea_type_emoji} {idea_type_text} {profile.current_idea_index + 1} из {total_ideas}*

*{idea.title}*

📝 *Описание:*
{idea.description}

✅ *Почему вам подходит:*
{idea.suitability}

🎨 *Уровень креативности:* {creativity_bar} ({idea.creativity_level}/10)"""
    
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
    
    # Кнопка выбора с эмодзи в зависимости от типа идеи
    select_emoji = "✅" if idea.idea_type == IdeaType.NORMAL else "🚀"
    keyboard.append([InlineKeyboardButton(f"{select_emoji} Выбрать эту идею", callback_data=f'select_idea_{profile.current_idea_index}')])
    
    # Кнопка переключения типа идей
    if not profile.show_creative_ideas and any(i.idea_type == IdeaType.CREATIVE for i in profile.business_ideas):
        keyboard.append([InlineKeyboardButton("✨ Показать креативные идеи", callback_data='show_creative')])
    elif profile.show_creative_ideas:
        keyboard.append([InlineKeyboardButton("💡 Показать практичные идеи", callback_data='show_normal')])
    
    keyboard.append([InlineKeyboardButton("🔄 Сгенерировать новые", callback_data='regenerate_ideas')])
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
    elif query.data == 'show_creative':
        # Показываем только креативные идеи
        creative_ideas = [i for i in profile.business_ideas if i.idea_type == IdeaType.CREATIVE]
        if creative_ideas:
            profile.business_ideas = creative_ideas
            profile.current_idea_index = 0
            profile.show_creative_ideas = True
    elif query.data == 'show_normal':
        # Показываем только нормальные идеи
        normal_ideas = [i for i in profile.business_ideas if i.idea_type == IdeaType.NORMAL]
        if normal_ideas:
            profile.business_ideas = normal_ideas
            profile.current_idea_index = 0
            profile.show_creative_ideas = False
    elif query.data == 'regenerate_ideas':
        # Регенерация идей
        await query.edit_message_text("🔄 *Генерирую новые идеи...*", parse_mode='Markdown')
        return await generate_business_ideas_wrapper(update, context)
    
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
    
    # Показываем статус генерации с информацией о токенах
    token_bar = token_usage.get_usage_bar()
    token_info = f"\n📊 *Использование токенов:* {token_bar}"
    
    await query.edit_message_text(
        f"🧠 *Генерирую ПОЛНЫЙ бизнес-план для:*\n\n"
        f"*{profile.selected_idea.title}*\n\n"
        f"📋 *Что будет в плане:*\n"
        f"• Детальный финансовый расчет\n"
        f"• Сроки выхода в ноль\n"
        f"• План на 50,000₽ и 100,000₽ в месяц\n"
        f"• Пошаговый план на 12 месяцев\n\n"
        f"⏳ *Это займет 45-60 секунд*{token_info}",
        parse_mode='Markdown'
    )
    
    # Генерируем план через AI или запасной
    business_plan = None
    if profile.ai_enabled and openai_service.is_available:
        business_plan = await openai_service.generate_detailed_business_plan(profile.answers, profile.selected_idea)
    
    # Запасной план если AI не сработал
    if not business_plan:
        business_plan = generate_detailed_fallback_plan(profile.answers, profile.selected_idea)
    
    profile.business_plan = business_plan
    
    # Показываем план
    return await show_business_plan(update, context)

def generate_detailed_fallback_plan(answers: Dict[int, str], idea: BusinessIdea) -> str:
    """Детальный запасной бизнес-план"""
    city = answers.get(0, "вашем городе")
    budget = answers.get(7, "50,000 рублей")
    time_per_week = answers.get(8, "20 часов")
    
    return f"""# 📈 ПОЛНЫЙ БИЗНЕС-ПЛАН: {idea.title}

## 1. 🎯 Краткое резюме бизнеса
{idea.description}

## 2. 📈 Анализ рынка в {city}
- **Размер рынка:** Примерно 100 млн рублей в год в вашем регионе
- **Конкуренция:** 5-10 основных игроков, качество услуг среднее
- **Ниша:** Персонализированный подход и гибкие условия
- **Тренды:** Рост спроса на 15-20% ежегодно

## 3. 🎯 Целевая аудитория
### Основные сегменты:
1. **Малый бизнес** (50% клиентов) - нуждаются в регулярных услугах
2. **Частные клиенты** (30%) - разовые заказы, более высокая маржа
3. **Корпорации** (20%) - крупные проекты, долгосрочные контракты

## 4. 📱 Маркетинг-план на 6 месяцев
### Месяц 1-2: Запуск (бюджет: 15,000₽)
- Создание сайта и соцсетей
- Первые 5 проектов по специальной цене
- Сбор отзывов и кейсов

### Месяц 3-4: Рост (бюджет: 20,000₽)
- Таргетированная реклама в VK/Telegram
- Партнерства с местными бизнесами
- Участие в профильных мероприятиях

### Месяц 5-6: Стабилизация (бюджет: 25,000₽)
- SEO-оптимизация сайта
- Email-рассылка базы клиентов
- Внедрение реферальной программы

## 5. ⚙️ Операционный план
- **Режим работы:** {time_per_week} часов в неделю
- **Оборудование:** Компьютер, телефон, базовый набор инструментов
- **Помещение:** Работа из дома/коворкинг
- **Юридическая форма:** ИП (упрощенная система налогообложения)

## 6. 💰 ФИНАНСОВЫЙ ПЛАН

### Стартовые инвестиции:
- Оборудование: 25,000₽
- Регистрация ИП: 5,000₽
- Первая реклама: 15,000₽
- Резервный фонд: 5,000₽
- **ИТОГО СТАРТ:** {budget}

### Ежемесячные расходы:
- Реклама: 10,000-20,000₽
- Софт/инструменты: 3,000₽
- Налоги (6% от доходов): ~4,500₽
- Прочие расходы: 2,500₽
- **ИТОГО В МЕСЯЦ:** ~20,000₽

### План доходов:
| Месяц | Клиентов | Средний чек | Доход | Расходы | Прибыль | Накоплено |
|-------|----------|-------------|-------|---------|---------|-----------|
| 1     | 3        | 5,000₽      | 15,000₽ | 35,000₽ | -20,000₽ | -20,000₽ |
| 2     | 5        | 6,000₽      | 30,000₽ | 25,000₽ | 5,000₽   | -15,000₽ |
| 3     | 8        | 7,000₽      | 56,000₽ | 25,000₽ | 31,000₽  | 16,000₽  |
| 4     | 12       | 7,500₽      | 90,000₽ | 30,000₽ | 60,000₽  | 76,000₽  |
| 5     | 15       | 8,000₽      | 120,000₽| 35,000₽ | 85,000₽  | 161,000₽ |
| 6     | 18       | 8,500₽      | 153,000₽| 40,000₽ | 113,000₽ | 274,000₽ |

### 🎯 Ключевые финансовые цели:
- **Выход в ноль (break-even):** К концу 2-го месяца
- **Доход 50,000₽ в месяц:** Достигается на 3-м месяце
- **Доход 100,000₽ в месяц:** Достигается на 5-м месяце
- **Окупаемость стартовых вложений:** 3 месяца

## 7. 🚀 Пошаговый план запуска (первые 30 дней)

### Неделя 1: Подготовка (дни 1-7)
1. Зарегистрировать ИП
2. Создать базовое оборудование
3. Настроить банковский счет
4. Разработать коммерческое предложение

### Неделя 2: Создание активов (дни 8-14)
1. Сделать сайт-визитку
2. Создать аккаунты в соцсетях
3. Подготовить портфолио (3 примера)
4. Написать тексты для рекламы

### Неделя 3: Тестовые продажи (дни 15-21)
1. Предложить услуги 20 потенциальным клиентам
2. Провести 5 бесплатных консультаций
3. Заключить 3 первых договора
4. Начать работу над первыми проектами

### Неделя 4: Анализ и корректировка (дни 22-30)
1. Собрать обратную связь от первых клиентов
2. Оптимизировать процессы работы
3. Скорректировать цены при необходимости
4. Запустить первую платную рекламу

## 8. ⚠️ Риски и их минимизация
1. **Недостаток клиентов** - активно работать с рефералами
2. **Конкуренция** - выделяться качеством обслуживания
3. **Сезонность** - разработать круглогодичные услуги
4. **Финансовые риски** - держать резерв на 3 месяца расходов

## 9. 📈 Показатели успеха (KPI)
- **Ежедневно:** Новые контакты (3-5), конверсия в заявки (20%)
- **Еженедельно:** Закрытые сделки (2-3), доход (15,000-25,000₽)
- **Ежемесячно:** Чистая прибыль (от 30,000₽), повторные продажи (30%)
- **Критерий масштабирования:** Стабильный доход 100,000₽+ в течение 3 месяцев

💪 *Бизнес имеет высокий потенциал роста при системном подходе!*"""

async def show_business_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать детальный бизнес-план"""
    query = update.callback_query
    user_id = query.from_user.id
    profile = user_sessions[user_id]
    
    # Добавляем информацию о токенах в начало плана
    token_bar = token_usage.get_usage_bar()
    token_info = f"\n📊 *Использование токенов:* {token_bar}"
    token_info += f"\n💰 *Примерная стоимость запроса:* ${token_usage.estimated_cost:.4f}"
    
    enhanced_plan = f"""# 🚀 ДЕТАЛЬНЫЙ БИЗНЕС-ПЛАН{token_info}

*{profile.selected_idea.title}*

{profile.business_plan}"""
    
    # Разбиваем план на части
    plan_parts = split_text(enhanced_plan, max_length=4000)
    
    # Отправляем первую часть с кнопками
    text = plan_parts[0]
    
    keyboard = [
        [InlineKeyboardButton("💾 Сохранить план", callback_data='save_plan')],
        [InlineKeyboardButton("🔄 Выбрать другую идею", callback_data='back_to_ideas')],
        [InlineKeyboardButton("📊 Статистика токенов", callback_data='token_stats')],
        [InlineKeyboardButton("🏠 Начать заново", callback_data='back_to_start')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Отправляем остальные части
    for part in plan_parts[1:]:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=part,
                parse_mode='Markdown'
            )
        except:
            pass
    
    return BUSINESS_PLAN_STATE

async def token_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику использования токенов"""
    query = update.callback_query
    await query.answer()
    
    usage_percentage = token_usage.get_usage_percentage()
    remaining_percentage = token_usage.get_remaining_percentage()
    usage_bar = token_usage.get_usage_bar()
    
    stats_text = f"""📊 *СТАТИСТИКА ИСПОЛЬЗОВАНИЯ OPENAI*

{usage_bar}

📈 *Детальная статистика:*
• Всего токенов: {token_usage.total_tokens:,}
• Prompt токены: {token_usage.prompt_tokens:,}
• Completion токены: {token_usage.completion_tokens:,}
• Использовано: {usage_percentage:.1f}%
• Осталось: {remaining_percentage:.1f}%
• Примерная стоимость: ${token_usage.estimated_cost:.4f}

💰 *Лимиты (примерные):*
• Бесплатный аккаунт: ~100K токенов/месяц
• Платный аккаунт: от 1M токенов/месяц

⚠️ *Рекомендации:*
{get_token_usage_recommendation(usage_percentage)}"""
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад к плану", callback_data='back_to_plan')],
        [InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    return BUSINESS_PLAN_STATE

def get_token_usage_recommendation(usage_percentage: float) -> str:
    """Получить рекомендации по использованию токенов"""
    if usage_percentage >= 90:
        return "🔴 Критически высокое использование! Рассмотрите переход на платный тариф."
    elif usage_percentage >= 70:
        return "🟡 Высокое использование. Оптимизируйте промты для экономии токенов."
    elif usage_percentage >= 50:
        return "🟢 Среднее использование. Можно продолжать работу."
    else:
        return "🟢 Низкое использование. Можно генерировать больше контента."

async def back_to_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться к бизнес-плану"""
    return await show_business_plan(update, context)

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

async def save_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение плана"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    profile = user_sessions[user_id]
    
    # Добавляем информацию о токенах
    token_bar = token_usage.get_usage_bar()
    footer = f"\n\n---\n📊 *Использование токенов при генерации:* {token_bar}"
    footer += f"\n💰 *Примерная стоимость:* ${token_usage.estimated_cost:.4f}"
    footer += f"\n⏰ *Сгенерировано:* {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    full_plan = profile.business_plan + footer
    
    await query.edit_message_text(
        "💾 *План сохранен в истории чата!*\n\n"
        "📋 *Рекомендуемые следующие шаги:*\n"
        "1. Выделите 1-2 самых простых действия из плана\n"
        "2. Начните с них в течение 48 часов\n"
        "3. Делитесь прогрессом с друзьями для accountability\n"
        "4. Регулярно возвращайтесь к плану для корректировок\n\n"
        "🎯 *Ключевые даты для контроля:*\n"
        "• Через 1 неделя: первые клиенты\n"
        "• Через 1 месяц: выход в ноль\n"
        "• Через 3 месяца: доход 50,000₽\n"
        "• Через 6 месяцев: доход 100,000₽\n\n"
        "🚀 *У вас всё получится!*\n\n"
        "Для нового поиска нажмите /start",
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в начало"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
    
    # Показываем финальную статистику токенов
    token_bar = token_usage.get_usage_bar()
    token_info = f"\n📊 *Итоговое использование токенов:* {token_bar}"
    
    keyboard = [[InlineKeyboardButton("📋 Начать новую анкету", callback_data='start_questionnaire')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"👋 *Спасибо за использование Бизнес-Навигатора!*{token_info}\n\nНажмите кнопку чтобы начать новую анкету:",
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
    """Разделение текста на части для Telegram"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    while len(text) > max_length:
        # Ищем последний перенос строки
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
        "version": "4.0",
        "openai_available": openai_service.is_available,
        "active_sessions": len(user_sessions),
        "token_usage": {
            "total_tokens": token_usage.total_tokens,
            "prompt_tokens": token_usage.prompt_tokens,
            "completion_tokens": token_usage.completion_tokens,
            "estimated_cost": token_usage.estimated_cost,
            "usage_percentage": token_usage.get_usage_percentage()
        }
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
    
    logger.info(f"🚀 Запуск Бизнес-бота v4.0 (OpenAI: {openai_service.is_available})")
    
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
                CallbackQueryHandler(navigate_ideas, pattern='^(prev_idea|next_idea|show_creative|show_normal|regenerate_ideas)$'),
                CallbackQueryHandler(select_idea, pattern='^select_idea_'),
                CallbackQueryHandler(back_to_start, pattern='^back_to_start$')
            ],
            BUSINESS_PLAN_STATE: [
                CallbackQueryHandler(save_plan, pattern='^save_plan$'),
                CallbackQueryHandler(token_stats, pattern='^token_stats$'),
                CallbackQueryHandler(back_to_plan, pattern='^back_to_plan$'),
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