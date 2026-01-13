#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Бизнес-Навигатор: Психологический анализ для поиска уникальных ниш
Версия 6.0 - Стабильная версия с polling и health check
"""

import os
import logging
import asyncio
import json
import re
import random
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

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
class BotState(Enum):
    DEMOGRAPHY = 1
    PERSONALITY = 2
    SKILLS = 3
    VALUES = 4
    LIMITATIONS = 5
    ANALYZING = 6
    NICHE_SELECTION = 7
    DETAILED_PLAN = 8

# ==================== МОДЕЛИ ДАННЫХ ====================
@dataclass
class UserProfile:
    user_id: int
    chat_id: int
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    # Демография
    age_group: Optional[str] = None
    education: Optional[str] = None
    location: Optional[str] = None
    custom_location: Optional[str] = None
    
    # Личность и мотивация
    motivation: List[str] = field(default_factory=list)
    decision_style: Optional[str] = None
    risk_tolerance: int = 5
    risk_scenario: Optional[str] = None
    energy_morning: int = 3
    energy_day: int = 3
    energy_evening: int = 3
    energy_analytical: Optional[str] = None
    energy_creative: Optional[str] = None
    energy_social: Optional[str] = None
    fears_selected: List[str] = field(default_factory=list)
    fears_custom: Optional[str] = None
    
    # Навыки
    skills_analytics: int = 3
    skills_communication: int = 3
    skills_design: int = 3
    skills_organization: int = 3
    skills_manual: int = 3
    skills_eq: int = 3
    superpower: Optional[str] = None
    work_style: Optional[str] = None
    learning_practice: int = 0
    learning_books: int = 0
    learning_courses: int = 0
    learning_group: int = 0
    learning_observation: int = 0
    
    # Ценности
    existential_answer: Optional[str] = None
    flow_experience: Optional[str] = None
    flow_feeling: Optional[str] = None
    ideal_client_age: Optional[str] = None
    ideal_client_field: Optional[str] = None
    ideal_client_pain: Optional[str] = None
    ideal_client_details: Optional[str] = None
    
    # Ограничения
    budget: Optional[str] = None
    equipment: List[str] = field(default_factory=list)
    equipment_custom: Optional[str] = None
    knowledge_assets: List[str] = field(default_factory=list)
    time_per_week: Optional[str] = None
    business_scale: Optional[str] = None
    business_format: Optional[str] = None
    
    # AI результаты
    psychological_analysis: Optional[str] = None
    generated_niches: List[Dict] = field(default_factory=list)
    detailed_plans: Dict[str, str] = field(default_factory=dict)
    current_niche_index: int = 0
    selected_niche: Optional[Dict] = None
    
    # UX
    current_question: int = 0
    questions_answered: int = 0
    total_questions: int = 18
    learning_points_assigned: int = 0

@dataclass
class TokenUsage:
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost: float = 0.0
    
    def add_usage(self, prompt_tokens: int, completion_tokens: int):
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens = self.prompt_tokens + self.completion_tokens
        self.estimated_cost = self.total_tokens * 0.002 / 1000
    
    def get_percentage_used(self, limit: int = 100000) -> float:
        return min((self.total_tokens / limit) * 100, 100.0) if limit > 0 else 0.0
    
    def get_usage_bar(self, limit: int = 100000) -> str:
        percent = self.get_percentage_used(limit)
        filled = int(percent / 10)
        bar = "🟢" * filled + "⚪" * (10 - filled)
        
        if percent >= 80:
            bar = "🔴" * filled + "⚪" * (10 - filled)
        elif percent >= 50:
            bar = "🟡" * filled + "⚪" * (10 - filled)
        
        return f"{bar} {percent:.1f}%"

@dataclass
class ChatMemory:
    total_messages: int = 0
    user_profiles: Dict[int, UserProfile] = field(default_factory=dict)
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    
    def get_memory_usage_percentage(self) -> float:
        try:
            base_memory = 50 * 1024 * 1024
            profile_memory = len(self.user_profiles) * 10 * 1024
            message_memory = self.total_messages * 4 * 1024
            
            total_used = base_memory + profile_memory + message_memory
            total_limit = 512 * 1024 * 1024
            
            return min((total_used / total_limit) * 100, 100.0)
        except:
            return 0.0

# ==================== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ====================
chat_memory = ChatMemory()
PRAISE_PHRASES = [
    "Отлично! Вижу, вы подходите к делу серьезно 👏",
    "Прекрасный ответ! Это многое проясняет 💡",
    "Замечательно! Вы раскрываетесь с каждой минутой 🌟",
    "Восхитительно! Такие ответы делают анализ максимально точным 🎯",
    "Браво! Вы мыслите нестандартно, это ценно 🚀",
    "Потрясающе! Чувствуется глубина мышления 🧠",
    "Великолепно! Вы делаете эту анкету лучше с каждым ответом 💎",
    "Изумительно! Такой анализ будет максимально персонализированным ✨",
    "Превосходно! Вижу системный подход к самоанализу 📊",
    "Блестяще! Ваши ответы - золотая жила для подбора ниши 🏆",
    "Невероятно! Вы раскрываете такие грани, которые редко встречаются 💫",
    "Исключительно! Чувствуется большой потенциал 🌈",
    "Феноменально! Такие ответы делают работу AI по-настоящему ценной 🤖",
    "Восхищаюсь вашей честностью и глубиной! Это ключ к успеху 🔑",
    "Захватывающе! Чем больше узнаю, тем интереснее становится 🎢"
]

# ==================== OPENAI СЕРВИС ====================
class OpenAIService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.is_available = bool(self.api_key)
        logger.info(f"🔌 OpenAI: {'Доступен' if self.is_available else 'Недоступен'}")
    
    def create_analysis_prompt(self, profile: UserProfile) -> str:
        """Создание промта для психологического анализа"""
        return f"""Ты - нейропсихолог и бизнес-стратег с 20-летним опытом. 
Проведи ГЛУБОКИЙ ПСИХОЛОГИЧЕСКИЙ АНАЛИЗ и составь бизнес-стратегию.

## ПОЛНЫЙ ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:

### 1. ДЕМОГРАФИЯ:
- Возрастная группа: {profile.age_group}
- Образование: {profile.education}
- Локация: {profile.custom_location or profile.location}

### 2. ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ:
- Ключевая мотивация: {', '.join(profile.motivation)}
- Стиль принятия решений: {profile.decision_style}
- Толерантность к риску: {profile.risk_tolerance}/10 (сценарий: {profile.risk_scenario})
- Энергетический профиль: Утро={profile.energy_morning}/7, День={profile.energy_day}/7, Вечер={profile.energy_evening}/7
- Пиковая продуктивность: Аналитика={profile.energy_analytical}, Креатив={profile.energy_creative}, Общение={profile.energy_social}
- Глубинные страхи: {', '.join(profile.fears_selected)} + "{profile.fears_custom}"

### 3. НАВЫКИ (оценка 1-5):
- Аналитика/логика: {profile.skills_analytics}/5
- Коммуникация/переговоры: {profile.skills_communication}/5
- Дизайн/креатив: {profile.skills_design}/5
- Организация/планирование: {profile.skills_organization}/5
- Ручной труд/мастерство: {profile.skills_manual}/5
- Эмоциональный интеллект: {profile.skills_eq}/5
- Суперсила: {profile.superpower}
- Стиль работы: {profile.work_style}

### 4. ЦЕННОСТИ И ИНТЕРЕСЫ:
- Экзистенциальный ответ: "{profile.existential_answer}"
- Состояние потока: "{profile.flow_experience}" (ощущения: "{profile.flow_feeling}")
- Идеальный клиент: {profile.ideal_client_age}, сфера: {profile.ideal_client_field}, боль: {profile.ideal_client_pain}, детали: "{profile.ideal_client_details}"

### 5. ПРАКТИЧЕСКИЕ ОГРАНИЧЕНИЯ:
- Стартовый бюджет: {profile.budget}
- Оборудование: {', '.join(profile.equipment)}
- Знания/активы: {', '.join(profile.knowledge_assets)}
- Время в неделю: {profile.time_per_week}
- Масштаб бизнеса: {profile.business_scale}
- Формат работы: {profile.business_format}

## АНАЛИТИЧЕСКОЕ ЗАДАНИЕ:

### 1. ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ (детально):
- Основные черты характера и мышления
- Сильные стороны (как их монетизировать)
- Слабые стороны (как компенсировать)
- Когнитивные стили и предпочтения

### 2. СКРЫТЫЙ ПОТЕНЦИАЛ:
- Неиспользованные комбинации навыков
- Уникальные инсайты из экзистенциального ответа
- Что человек умеет, но не ценит
- Неочевидные возможности из профиля

### 3. ИДЕАЛЬНЫЕ УСЛОВИЯ ДЛЯ БИЗНЕСА:
- Оптимальный формат работы (онлайн/офлайн/гибрид)
- Темп роста (быстрый/умеренный/постепенный)
- Тип клиентов/проектов (детально)
- Рабочее расписание (с учетом энергетического профиля)

### 4. ОСОБЫЕ ВОЗМОЖНОСТИ (с учетом демографии):
- Возрастные преимущества/ограничения
- Как использовать образование и опыт
- Возможности локации (географические ниши)
- Учет временных и финансовых ограничений

ВЕРНИ СТРУКТУРИРОВАННЫЙ ОТВЕТ БЕЗ ОБЩИХ ФРАЗ. Будь конкретным и практичным."""

    def create_niches_prompt(self, profile: UserProfile, analysis: str) -> str:
        """Создание промта для генерации ниш"""
        return f"""Ты - бизнес-аналитик и предприниматель с опытом создания 50+ бизнесов.
На основе психологического анализа создай 5 КОНКРЕТНЫХ БИЗНЕС-НИШ.

## ПСИХОЛОГИЧЕСКИЙ АНАЛИЗ ПОЛЬЗОВАТЕЛЯ:
{analysis}

## ПРАКТИЧЕСКИЕ ПАРАМЕТРЫ ПОЛЬЗОВАТЕЛЯ:
- Возраст: {profile.age_group}
- Образование: {profile.education}
- Локация: {profile.custom_location or profile.location}
- Бюджет: {profile.budget}
- Время: {profile.time_per_week}
- Масштаб: {profile.business_scale}
- Формат: {profile.business_format}

## ТРЕБОВАНИЯ К НИШАМ:

### 1-2. 🔥 БЫСТРЫЙ СТАРТ (первые деньги за 1-2 месяца)
### 3-4. 🚀 СБАЛАНСИРОВАННЫЙ (стабильный доход за 3-6 месяцев)
### 5. 🌱 ДОЛГОСРОЧНЫЙ (масштабирование за 1-2 года)

## ФОРМАТ ДЛЯ КАЖДОЙ НИШИ (строго придерживайся):

НИША 1: [ТИП]
НАЗВАНИЕ: [Краткое название, 3-5 слов]
СУТЬ: [Что конкретно делать, 2-3 предложения]
ПОЧЕМУ ПОДХОДИТ: [Связь с профилем пользователя, 1 предложение]
ФОРМАТ: [онлайн/офлайн/гибрид]
ИНВЕСТИЦИИ: [Диапазон в рублях]
СРОК ОКУПАЕМОСТИ: [Реалистичный срок]
ПЕРВЫЕ 3 ШАГА: 
1. [Конкретное действие]
2. [Конкретное действие]
3. [Конкретное действие]

ВЕРНИ ТОЛЬКО 5 НИШ В ЭТОМ ФОРМАТЕ. Без вступлений, без заключений."""

    def create_detailed_plan_prompt(self, profile: UserProfile, niche: Dict) -> str:
        """Создание промта для детального плана"""
        return f"""Ты - опытный бизнес-консультант и коуч.
Создай ГИПЕРПЕРСОНАЛИЗИРОВАННЫЙ БИЗНЕС-ПЛАН.

## НИША ДЛЯ РАЗРАБОТКИ:
{niche.get('name', '')} ({niche.get('type', '')})
{niche.get('description', '')}

## ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ (ключевые параметры):
- Возраст: {profile.age_group}
- Образование: {profile.education}
- Локация: {profile.custom_location or profile.location}
- Мотивация: {', '.join(profile.motivation)}
- Главные страхи: {', '.join(profile.fears_selected)}
- Бюджет: {profile.budget}
- Время в неделю: {profile.time_per_week}
- Суперсила: {profile.superpower}
- Энергетический пик: Аналитика={profile.energy_analytical}, Креатив={profile.energy_creative}

## СТРУКТУРА ПЛАНА:

### 1. 🧠 ПСИХОЛОГИЧЕСКАЯ ПОДГОТОВКА (неделя 1)
### 2. 🚀 30-ДНЕВНЫЙ ЗАПУСК (по дням)
### 3. 💰 ФИНАНСОВАЯ ДОРОЖНАЯ КАРТА (3-6-12 месяцев)
### 4. 📊 МЕТРИКИ УСПЕХА (KPI)
### 5. ⚠️ ТИПИЧНЫЕ ОШИБКИ И РЕШЕНИЯ
### 6. 📚 РЕСУРСЫ ДЛЯ РОСТА

Сделай план МАКСИМАЛЬНО КОНКРЕТНЫМ, с цифрами, сроками, конкретными действиями."""

    async def call_openai(self, prompt: str, temperature: float = 0.7, max_tokens: int = 3000) -> Optional[str]:
        """Вызов OpenAI API"""
        if not self.is_available:
            logger.warning("OpenAI недоступен")
            return None
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "Ты - опытный бизнес-консультант, психолог и аналитик."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # Отслеживаем использование токенов
                usage = result.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                
                chat_memory.token_usage.add_usage(prompt_tokens, completion_tokens)
                
                logger.info(f"✅ OpenAI: использовано {completion_tokens} токенов")
                return content
            else:
                logger.error(f"❌ OpenAI ошибка: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка вызова OpenAI: {e}")
            return None
    
    async def generate_psychological_analysis(self, profile: UserProfile) -> Optional[str]:
        """Генерация психологического анализа"""
        logger.info(f"🧠 Генерация анализа для пользователя {profile.user_id}")
        
        prompt = self.create_analysis_prompt(profile)
        analysis = await self.call_openai(prompt, temperature=0.5, max_tokens=2000)
        
        if analysis:
            logger.info(f"✅ Психологический анализ сгенерирован")
        else:
            logger.warning("❌ Не удалось сгенерировать анализ")
            analysis = self.create_fallback_analysis(profile)
        
        return analysis
    
    async def generate_business_niches(self, profile: UserProfile, analysis: str) -> Optional[List[Dict]]:
        """Генерация бизнес-ниш"""
        logger.info(f"🎯 Генерация ниш для пользователя {profile.user_id}")
        
        prompt = self.create_niches_prompt(profile, analysis)
        niches_text = await self.call_openai(prompt, temperature=0.8, max_tokens=4000)
        
        if not niches_text:
            logger.warning("❌ Не удалось сгенерировать ниши")
            return self.create_fallback_niches(profile)
        
        # Парсинг сгенерированных ниш
        niches = self.parse_niches_from_text(niches_text)
        
        if niches:
            logger.info(f"✅ Сгенерировано {len(niches)} ниш")
        else:
            logger.warning("❌ Не удалось распарсить ниши")
            niches = self.create_fallback_niches(profile)
        
        return niches
    
    async def generate_detailed_plan(self, profile: UserProfile, niche: Dict) -> Optional[str]:
        """Генерация детального плана"""
        logger.info(f"📋 Генерация плана для ниши: {niche.get('name', '')}")
        
        prompt = self.create_detailed_plan_prompt(profile, niche)
        plan = await self.call_openai(prompt, temperature=0.6, max_tokens=4000)
        
        if not plan:
            logger.warning("❌ Не удалось сгенерировать план")
            plan = self.create_fallback_plan(profile, niche)
        
        return plan
    
    def parse_niches_from_text(self, text: str) -> List[Dict]:
        """Парсинг ниш из текста OpenAI"""
        niches = []
        current_niche = {}
        
        lines = text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('НИША'):
                if current_niche:
                    niches.append(current_niche.copy())
                current_niche = {'id': len(niches) + 1}
                # Извлекаем тип из НИША X: [ТИП]
                match = re.search(r'НИША\s+\d+:\s*(.+?)$', line)
                if match:
                    current_niche['type'] = match.group(1).strip()
            
            elif line.startswith('НАЗВАНИЕ:'):
                current_niche['name'] = line.replace('НАЗВАНИЕ:', '').strip()
            
            elif line.startswith('СУТЬ:'):
                current_niche['description'] = line.replace('СУТЬ:', '').strip()
            
            elif line.startswith('ПОЧЕМУ ПОДХОДИТ:'):
                current_niche['why'] = line.replace('ПОЧЕМУ ПОДХОДИТ:', '').strip()
            
            elif line.startswith('ФОРМАТ:'):
                current_niche['format'] = line.replace('ФОРМАТ:', '').strip()
            
            elif line.startswith('ИНВЕСТИЦИИ:'):
                current_niche['investment'] = line.replace('ИНВЕСТИЦИИ:', '').strip()
            
            elif line.startswith('СРОК ОКУПАЕМОСТИ:'):
                current_niche['roi'] = line.replace('СРОК ОКУПАЕМОСТИ:', '').strip()
            
            elif line.startswith('ПЕРВЫЕ 3 ШАГА:'):
                current_niche['steps'] = []
            elif line.startswith('1.') and 'steps' in current_niche:
                current_niche['steps'].append(line[2:].strip())
            elif line.startswith('2.') and 'steps' in current_niche:
                current_niche['steps'].append(line[2:].strip())
            elif line.startswith('3.') and 'steps' in current_niche:
                current_niche['steps'].append(line[2:].strip())
        
        # Добавляем последнюю нишу
        if current_niche:
            niches.append(current_niche)
        
        # Обеспечиваем, что есть минимум 3 шага
        for niche in niches:
            if 'steps' not in niche or len(niche['steps']) < 3:
                niche['steps'] = [
                    'Провести анализ рынка и конкурентов',
                    'Создать MVP продукта или услуги',
                    'Найти первых 3 клиентов для тестирования'
                ]
        
        return niches[:5]  # Ограничиваем 5 нишами
    
    def create_fallback_analysis(self, profile: UserProfile) -> str:
        """Запасной психологический анализ"""
        return f"""# ПСИХОЛОГИЧЕСКИЙ АНАЛИЗ

## 1. КЛЮЧЕВЫЕ ХАРАКТЕРИСТИКИ:
- **Тип личности:** Практичный аналитик с творческим потенциалом
- **Мотивация:** {', '.join(profile.motivation)}
- **Сильные стороны:** Хорошие аналитические способности ({profile.skills_analytics}/5), умение общаться ({profile.skills_communication}/5)
- **Энергия:** Пик продуктивности - {profile.energy_analytical or 'дневное'} время

## 2. СКРЫТЫЙ ПОТЕНЦИАЛ:
- Неиспользованная комбинация навыков: аналитика + {profile.superpower or 'креативность'}
- Возможность монетизации образования: {profile.education}
- Географическое преимущество: {profile.custom_location or profile.location}

## 3. ИДЕАЛЬНЫЕ УСЛОВИЯ:
- Формат: {profile.business_format or 'гибрид'}
- Темп: Умеренный, с быстрым стартом
- Клиенты: {profile.ideal_client_age or '30-40 лет'}, {profile.ideal_client_field or 'бизнес'}"""
    
    def create_fallback_niches(self, profile: UserProfile) -> List[Dict]:
        """Запасные бизнес-ниши"""
        location = profile.custom_location or profile.location or "вашем городе"
        
        return [
            {
                'id': 1,
                'type': '🔥 Быстрый старт',
                'name': 'Консультационные услуги',
                'description': f'Предоставление профессиональных консультаций в вашей сфере знаний бизнесам в {location}',
                'why': 'Использует ваши профессиональные навыки и образование',
                'format': 'Гибрид',
                'investment': '10,000-50,000₽',
                'roi': '1-2 месяца',
                'steps': [
                    'Определить 3 ключевые темы для консультаций',
                    'Создать профессиональное портфолио',
                    'Найти 5 потенциальных клиентов'
                ]
            },
            {
                'id': 2,
                'type': '🚀 Сбалансированный',
                'name': 'Онлайн-обучение',
                'description': 'Создание и продажа онлайн-курсов по вашей экспертизе',
                'why': 'Сочетает ваше образование и желание делиться знаниями',
                'format': 'Онлайн',
                'investment': '50,000-100,000₽',
                'roi': '3-4 месяца',
                'steps': [
                    'Разработать программу мини-курса',
                    'Создать 3 пробных урока',
                    'Запустить предзаказ через соцсети'
                ]
            },
            {
                'id': 3,
                'type': '🌱 Долгосрочный',
                'name': 'Автоматизация бизнес-процессов',
                'description': f'Разработка систем автоматизации для малого бизнеса в {location}',
                'why': 'Использует аналитические навыки и интерес к технологиям',
                'format': 'Гибрид',
                'investment': '100,000-200,000₽',
                'roi': '6-8 месяцев',
                'steps': [
                    'Изучить популярные CRM системы',
                    'Разработать 3 пакета услуг',
                    'Провести 10 пробных консультаций'
                ]
            }
        ]
    
    def create_fallback_plan(self, profile: UserProfile, niche: Dict) -> str:
        """Запасной детальный план"""
        return f"""# 📋 ДЕТАЛЬНЫЙ БИЗНЕС-ПЛАН

## 🎯 НИША: {niche.get('name', 'Бизнес-услуги')}

### 1. 🧠 ПСИХОЛОГИЧЕСКАЯ ПОДГОТОВКА (неделя 1)
- **Ментальная настройка:** Ежедневно 15 минут на визуализацию успеха
- **Работа со страхами:** Разбивайте большие задачи на маленькие шаги
- **Ритуалы:** Утренний planning и вечерний review дня

### 2. 🚀 30-ДНЕВНЫЙ ЗАПУСК
**Неделя 1-2:** Создание базовых материалов и определение аудитории
**Неделя 3-4:** Первые контакты и тестовые продажи

### 3. 💰 ФИНАНСОВАЯ ДОРОЖНАЯ КАРТА
**Стартовые инвестиции:** {niche.get('investment', '50,000-100,000₽')}
**Месяц 1-3:** Выход в ноль
**Месяц 4-6:** Доход 50,000₽ в месяц
**Месяц 7-12:** Доход 100,000₽ в месяц

### 4. 📊 МЕТРИКИ УСПЕХА
- Ежедневно: 3 новых контакта
- Еженедельно: 2-3 закрытые сделки
- Ежемесячно: Доход от 50,000₽

### 5. ⚠️ ТИПИЧНЫЕ ОШИБКИ
1. Слишком широкий фокос
2. Недооценка времени
3. Отсутствие системы

### 6. 📚 РЕСУРСЫ ДЛЯ РОСТА
- Книги: "От нуля к единице" Питер Тиль
- Сообщества: Местные бизнес-клубы
- Инструменты: Notion, Canva, Tilda"""

# Глобальный экземпляр сервиса OpenAI
openai_service = OpenAIService()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def get_random_praise() -> str:
    """Получить случайную фразу похвалы"""
    return random.choice(PRAISE_PHRASES)

def get_memory_status() -> str:
    """Получить статус памяти"""
    memory_percent = chat_memory.get_memory_usage_percentage()
    token_percent = chat_memory.token_usage.get_percentage_used()
    
    memory_bar = "🟢" * int(memory_percent / 10) + "⚪" * (10 - int(memory_percent / 10))
    token_bar = chat_memory.token_usage.get_usage_bar()
    
    return (
        f"\n\n💾 *Статус системы:*\n"
        f"• Память: {memory_bar} {memory_percent:.1f}%\n"
        f"• Токены AI: {token_bar}\n"
        f"• Стоимость: ${chat_memory.token_usage.estimated_cost:.4f}"
    )

def split_text(text: str, max_length: int = 4000) -> List[str]:
    """Разделение длинного текста на части"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    while len(text) > max_length:
        split_pos = text.rfind('\n', 0, max_length)
        if split_pos == -1:
            split_pos = text.rfind('. ', 0, max_length)
        if split_pos == -1:
            split_pos = text.rfind(' ', 0, max_length)
        if split_pos == -1:
            split_pos = max_length
        
        parts.append(text[:split_pos].strip())
        text = text[split_pos:].strip()
    
    if text:
        parts.append(text)
    
    return parts

# ==================== ОБРАБОТЧИК КОМАНДЫ START ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    chat = update.effective_chat
    
    # Очищаем старые сессии (старше 24 часов)
    now = datetime.now()
    expired_users = [
        user_id for user_id, profile in chat_memory.user_profiles.items()
        if (now - profile.last_activity).total_seconds() > 86400
    ]
    for user_id in expired_users:
        del chat_memory.user_profiles[user_id]
    
    # Создаем или обновляем профиль
    if user.id in chat_memory.user_profiles:
        profile = chat_memory.user_profiles[user.id]
        profile.last_activity = now
    else:
        profile = UserProfile(user_id=user.id, chat_id=chat.id)
        chat_memory.user_profiles[user.id] = profile
    
    chat_memory.total_messages += 1
    profile.last_activity = now
    
    # Приветственное сообщение
    ai_status = "✅ (AI-режим)" if openai_service.is_available else "⚠️ (Базовый режим)"
    
    welcome_text = (
        f"👋 *Добро пожаловать в Бизнес-Навигатор 6.0!* {ai_status}\n\n"
        "🎯 *Что вас ждет:*\n"
        "• 18 вопросов для глубокого анализа личности\n"
        "• Психологический портрет от AI\n"
        "• 5 персонализированных бизнес-ниш\n"
        "• Детальные пошаговые планы\n\n"
        "⏱️ *Время прохождения:* 15-20 минут\n"
        "📊 *Глубина анализа:* профессиональный уровень"
    )
    
    welcome_text += get_memory_status()
    
    keyboard = [[InlineKeyboardButton("🚀 Начать анкету", callback_data='start_questionnaire')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    return BotState.DEMOGRAPHY

# ==================== HEALTH CHECK ====================
async def health_check(request):
    """Проверка здоровья сервиса"""
    status = {
        "status": "OK",
        "version": "6.0",
        "timestamp": datetime.now().isoformat(),
        "openai_available": openai_service.is_available,
        "statistics": {
            "active_users": len(chat_memory.user_profiles),
            "total_messages": chat_memory.total_messages,
            "memory_usage_percent": chat_memory.get_memory_usage_percentage()
        }
    }
    return web.Response(
        text=json.dumps(status, ensure_ascii=False, indent=2),
        content_type='application/json'
    )

async def run_health_server():
    """Запуск сервера для проверки здоровья"""
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
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        logger.error("❌ TELEGRAM_BOT_TOKEN не найден!")
        return
    
    logger.info(f"🚀 Запуск Бизнес-Навигатора v6.0")
    logger.info(f"🤖 OpenAI статус: {'✅ Доступен' if openai_service.is_available else '❌ Недоступен'}")
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем команду start
    application.add_handler(CommandHandler("start", start))
    
    # Запускаем health сервер
    health_server = await run_health_server()
    
    # Запускаем бота
    try:
        await application.initialize()
        await application.start()
        
        # ЗАПУСКАЕМ POLLING - как в твоем исходном коде!
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
        logger.info("✅ Бот готов к работе! (polling режим)")
        
        # Бесконечный цикл - ждем команды
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