#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
БИЗНЕС-НАВИГАТОР v7.0: Глубокий психологический анализ для поиска уникальных ниш
Полная версия для Python 3.9.16 с OpenAI 0.28.1
"""

import os
import logging
import asyncio
import json
import re
import sys
import random
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from collections import defaultdict
import html
import hashlib
from pathlib import Path

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    PicklePersistence,
)

# Импорт для OpenAI 0.28.1 (совместим с Python 3.9)
import openai
from openai.error import OpenAIError, AuthenticationError, RateLimitError, APIError, ServiceUnavailableError

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== КОНСТАНТЫ И ПЕРЕЧИСЛЕНИЯ ====================
class BotState(Enum):
    """Состояния бота"""
    START = auto()
    DEMOGRAPHY = auto()
    PERSONALITY = auto()
    SKILLS = auto()
    VALUES = auto()
    LIMITATIONS = auto()
    ANALYZING = auto()
    NICHE_SELECTION = auto()
    DETAILED_PLAN = auto()
    PSYCH_ANALYSIS = auto()
    SAVING_DATA = auto()

class QuestionType(Enum):
    """Типы вопросов"""
    BUTTONS = auto()
    MULTISELECT = auto()
    SLIDER = auto()
    TEXT = auto()
    SCENARIO = auto()
    RATING = auto()

class NicheCategory(Enum):
    """Категории ниш"""
    QUICK_START = "🔥 БЫСТРЫЙ СТАРТ"
    BALANCED = "🚀 СБАЛАНСИРОВАННЫЙ"
    LONG_TERM = "🌱 ДОЛГОСРОЧНЫЙ"
    RISKY = "💎 РИСКОВАННЫЙ"
    HIDDEN = "🎯 СКРЫТАЯ НИША"

# ==================== МОДЕЛИ ДАННЫХ ====================
@dataclass
class UserSession:
    """Сессия пользователя"""
    user_id: int
    chat_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    
    # Часть 1: Демография (3 вопроса)
    age_group: Optional[str] = None
    education: Optional[str] = None
    location_type: Optional[str] = None
    location_custom: Optional[str] = None
    location: Optional[str] = None
    
    # Часть 2: Личность и мотивация (5 вопросов)
    motivations: List[str] = field(default_factory=list)
    decision_style: Optional[str] = None
    risk_tolerance: int = 5
    risk_scenario: Optional[str] = None
    energy_morning: int = 3
    energy_day: int = 3
    energy_evening: int = 3
    peak_analytical: Optional[str] = None
    peak_creative: Optional[str] = None
    peak_social: Optional[str] = None
    fears_selected: List[str] = field(default_factory=list)
    fear_custom: Optional[str] = None
    
    # Часть 3: Способности и навыки (4 вопроса)
    skills_analytics: int = 3
    skills_communication: int = 3
    skills_design: int = 3
    skills_organization: int = 3
    skills_manual: int = 3
    skills_eq: int = 3
    superpower: Optional[str] = None
    work_style: Optional[str] = None
    learning_preferences: str = ""
    
    # Часть 4: Ценности и интересы (3 вопроса)
    existential_answer: Optional[str] = None
    flow_experience_desc: Optional[str] = None
    flow_feelings: Optional[str] = None
    ideal_client_age: Optional[str] = None
    ideal_client_field: Optional[str] = None
    ideal_client_pain: Optional[str] = None
    ideal_client_details: Optional[str] = None
    
    # Часть 5: Практические ограничения (3 вопроса)
    budget: Optional[str] = None
    equipment: List[str] = field(default_factory=list)
    knowledge_assets: List[str] = field(default_factory=list)
    time_per_week: Optional[str] = None
    business_scale: Optional[str] = None
    business_format: Optional[str] = None
    
    # AI результаты
    psychological_analysis: Optional[str] = None
    generated_niches: List[Dict] = field(default_factory=list)
    detailed_plans: Dict[str, str] = field(default_factory=dict)
    selected_niche_index: int = 0
    
    # Состояние
    current_state: BotState = BotState.START
    current_question: int = 0
    questions_answered: int = 0
    total_questions: int = 18
    start_time: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    # Временные данные
    temp_multiselect: List[str] = field(default_factory=list)
    temp_energy_selection: Optional[str] = None
    
    def update_activity(self):
        """Обновить время последней активности"""
        self.last_activity = datetime.now()
    
    def get_progress_percentage(self) -> float:
        """Получить процент заполнения"""
        return min((self.questions_answered / self.total_questions) * 100, 100.0)
    
    def get_progress_bar(self) -> str:
        """Получить строку прогресса"""
        percent = self.get_progress_percentage()
        filled = int(percent / 5)
        bar = "🟩" * filled + "⬜" * (20 - filled)
        return f"{bar} {percent:.1f}%"
    
    def get_location(self) -> str:
        """Получить полную локацию"""
        if self.location_custom:
            return self.location_custom
        return self.location_type or "Не указано"
    
    def to_openai_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь для OpenAI"""
        return {
            "demographics": {
                "age_group": self.age_group,
                "education": self.education,
                "location": self.get_location()
            },
            "personality": {
                "motivations": self.motivations,
                "decision_style": self.decision_style,
                "risk_tolerance": self.risk_tolerance,
                "risk_scenario": self.risk_scenario,
                "energy_profile": {
                    "morning": self.energy_morning,
                    "day": self.energy_day,
                    "evening": self.energy_evening,
                    "peak_analytical": self.peak_analytical,
                    "peak_creative": self.peak_creative,
                    "peak_social": self.peak_social
                },
                "fears": self.fears_selected,
                "fear_custom": self.fear_custom
            },
            "skills": {
                "analytics": self.skills_analytics,
                "communication": self.skills_communication,
                "design": self.skills_design,
                "organization": self.skills_organization,
                "manual": self.skills_manual,
                "emotional_iq": self.skills_eq,
                "superpower": self.superpower,
                "work_style": self.work_style,
                "learning_preferences": self.learning_preferences
            },
            "values": {
                "existential_answer": self.existential_answer,
                "flow_experience": self.flow_experience_desc,
                "flow_feelings": self.flow_feelings,
                "ideal_client": {
                    "age": self.ideal_client_age,
                    "field": self.ideal_client_field,
                    "pain": self.ideal_client_pain,
                    "details": self.ideal_client_details
                }
            },
            "limitations": {
                "budget": self.budget,
                "equipment": self.equipment,
                "knowledge_assets": self.knowledge_assets,
                "time_per_week": self.time_per_week,
                "business_scale": self.business_scale,
                "business_format": self.business_format
            }
        }

@dataclass
class OpenAIUsage:
    """Использование OpenAI"""
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    estimated_cost_usd: float = 0.0
    
    def add_usage(self, usage: Dict):
        """Добавить использование"""
        self.total_tokens += usage.get("total_tokens", 0)
        self.prompt_tokens += usage.get("prompt_tokens", 0)
        self.completion_tokens += usage.get("completion_tokens", 0)
        self.total_requests += 1
        self.successful_requests += 1
        
        # Примерная стоимость (gpt-3.5-turbo)
        # Входные: $0.0015 / 1K, Выходные: $0.002 / 1K
        prompt_cost = (self.prompt_tokens * 0.0015) / 1000
        completion_cost = (self.completion_tokens * 0.002) / 1000
        self.estimated_cost_usd = prompt_cost + completion_cost
    
    def add_failure(self):
        """Добавить неудачный запрос"""
        self.total_requests += 1
        self.failed_requests += 1
    
    def get_stats_str(self) -> str:
        """Статистика в строке"""
        success_rate = (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0
        return (
            f"📊 *Статистика OpenAI:*\n"
            f"• Запросов: {self.total_requests}\n"
            f"• Успешных: {self.successful_requests} ({success_rate:.1f}%)\n"
            f"• Токенов: {self.total_tokens:,}\n"
            f"• Стоимость: ${self.estimated_cost_usd:.4f}"
        )

@dataclass
class BotStatistics:
    """Статистика бота"""
    total_users: int = 0
    active_sessions: int = 0
    completed_profiles: int = 0
    generated_niches: int = 0
    generated_plans: int = 0
    total_messages: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    
    def get_uptime(self) -> str:
        """Время работы"""
        delta = datetime.now() - self.start_time
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        return f"{hours}ч {minutes}м"
    
    def get_stats_str(self) -> str:
        """Статистика в строке"""
        return (
            f"🤖 *Статистика бота:*\n"
            f"• Пользователей: {self.total_users}\n"
            f"• Активных: {self.active_sessions}\n"
            f"• Завершено: {self.completed_profiles}\n"
            f"• Ниш сгенерировано: {self.generated_niches}\n"
            f"• Планов: {self.generated_plans}\n"
            f"• Сообщений: {self.total_messages}\n"
            f"• Работает: {self.get_uptime()}"
        )

# ==================== КОНФИГУРАЦИЯ ====================
class BotConfig:
    """Конфигурация бота"""
    
    def __init__(self):
        # Токены и ключи
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # Проверка
        if not self.telegram_token:
            logger.error("❌ TELEGRAM_BOT_TOKEN не найден!")
            raise ValueError("TELEGRAM_BOT_TOKEN не установлен")
        
        if not self.openai_api_key:
            logger.warning("⚠️ OPENAI_API_KEY не найден. AI функции отключены.")
        else:
            # Настройка OpenAI для версии 0.28.1
            openai.api_key = self.openai_api_key
        
        # Настройки OpenAI
        self.openai_model = "gpt-3.5-turbo"
        self.openai_max_tokens = 4000
        self.openai_temperature = 0.7
        
        # Лимиты
        self.max_niches_to_generate = 8
        self.max_plans_to_generate = 3
        
        # Время ожидания
        self.question_timeout = 300
        self.analysis_timeout = 120
        
        # Пути
        self.data_dir = Path("./data")
        self.data_dir.mkdir(exist_ok=True)
        
        # Фразы похвалы
        self.praise_phrases = [
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
        
        logger.info(f"✅ Конфигурация загружена. OpenAI: {'Доступен' if self.openai_api_key else 'Недоступен'}")

# ==================== OPENAI СЕРВИС (версия 0.28.1) ====================
class OpenAIService:
    """Сервис для работы с OpenAI (версия 0.28.1)"""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.is_available = bool(config.openai_api_key)
        
        if self.is_available:
            openai.api_key = config.openai_api_key
            logger.info("✅ OpenAI клиент инициализирован (v0.28.1)")
        else:
            logger.warning("⚠️ OpenAI API ключ не установлен")
    
    async def _call_openai(self, prompt: str, max_tokens: int = None, temperature: float = None) -> Optional[str]:
        """Вызов OpenAI API для версии 0.28.1"""
        if not self.is_available:
            logger.warning("OpenAI недоступен")
            return None
        
        try:
            response = openai.ChatCompletion.create(
                model=self.config.openai_model,
                messages=[
                    {"role": "system", "content": "Ты - опытный бизнес-консультант и психолог."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens or self.config.openai_max_tokens,
                temperature=temperature or self.config.openai_temperature,
                timeout=60
            )
            
            content = response.choices[0].message.content
            
            # Логируем использование токенов
            usage = response.usage.to_dict()
            logger.info(f"✅ OpenAI: использовано {usage.get('total_tokens', 0)} токенов")
            
            return content
            
        except AuthenticationError:
            logger.error("❌ Ошибка аутентификации OpenAI. Проверьте API ключ.")
            self.is_available = False
            return None
        except RateLimitError:
            logger.error("❌ Превышен лимит запросов к OpenAI")
            return None
        except APIError as e:
            logger.error(f"❌ Ошибка API OpenAI: {e}")
            return None
        except ServiceUnavailableError:
            logger.error("❌ Сервис OpenAI временно недоступен")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка вызова OpenAI: {e}")
            return None
    
    async def generate_psychological_analysis(self, session: UserSession) -> Optional[str]:
        """Генерация психологического анализа"""
        logger.info(f"🧠 Генерация психологического анализа для {session.user_id}")
        
        profile = session.to_openai_dict()
        
        prompt = f"""Ты - нейропсихолог и бизнес-стратег с 20-летним опытом. 
Проведи ГЛУБОКИЙ ПСИХОЛОГИЧЕСКИЙ АНАЛИЗ и составь бизнес-стратегию.

## ПОЛНЫЙ ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:

### 1. ДЕМОГРАФИЯ:
- Возрастная группа: {profile['demographics']['age_group']}
- Образование: {profile['demographics']['education']}
- Локация: {profile['demographics']['location']}

### 2. ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ:
- Ключевая мотивация: {', '.join(profile['personality']['motivations'])}
- Стиль принятия решений: {profile['personality']['decision_style']}
- Толерантность к риску: {profile['personality']['risk_tolerance']}/10 (сценарий: {profile['personality']['risk_scenario']})
- Энергетический профиль: Утро={profile['personality']['energy_profile']['morning']}/7, День={profile['personality']['energy_profile']['day']}/7, Вечер={profile['personality']['energy_profile']['evening']}/7
- Пиковая продуктивность: Аналитика={profile['personality']['energy_profile']['peak_analytical']}, Креатив={profile['personality']['energy_profile']['peak_creative']}, Общение={profile['personality']['energy_profile']['peak_social']}
- Глубинные страхи: {', '.join(profile['personality']['fears'])} + "{profile['personality']['fear_custom']}"

### 3. НАВЫКИ (оценка 1-5):
- Аналитика/логика: {profile['skills']['analytics']}/5
- Коммуникация/переговоры: {profile['skills']['communication']}/5
- Дизайн/креатив: {profile['skills']['design']}/5
- Организация/планирование: {profile['skills']['organization']}/5
- Ручной труд/мастерство: {profile['skills']['manual']}/5
- Эмоциональный интеллект: {profile['skills']['emotional_iq']}/5
- Суперсила: {profile['skills']['superpower']}
- Стиль работы: {profile['skills']['work_style']}

### 4. ЦЕННОСТИ И ИНТЕРЕСЫ:
- Экзистенциальный ответ: "{profile['values']['existential_answer'][:200]}..."
- Состояние потока: "{profile['values']['flow_experience']}" (ощущения: "{profile['values']['flow_feelings']}")
- Идеальный клиент: {profile['values']['ideal_client']['age']}, сфера: {profile['values']['ideal_client']['field']}, боль: {profile['values']['ideal_client']['pain']}, детали: "{profile['values']['ideal_client']['details']}"

### 5. ПРАКТИЧЕСКИЕ ОГРАНИЧЕНИЯ:
- Стартовый бюджет: {profile['limitations']['budget']}
- Оборудование: {', '.join(profile['limitations']['equipment'])}
- Знания/активы: {', '.join(profile['limitations']['knowledge_assets'])}
- Время в неделю: {profile['limitations']['time_per_week']}
- Масштаб бизнеса: {profile['limitations']['business_scale']}
- Формат работы: {profile['limitations']['business_format']}

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

        analysis = await self._call_openai(prompt, max_tokens=3000, temperature=0.5)
        
        if analysis:
            logger.info(f"✅ Психологический анализ сгенерирован ({len(analysis)} символов)")
        else:
            logger.warning("❌ Не удалось сгенерировать анализ")
            analysis = self._create_fallback_analysis(session)
        
        return analysis
    
    async def generate_business_niches(self, session: UserSession, analysis: str) -> List[Dict]:
        """Генерация бизнес-ниш"""
        logger.info(f"🎯 Генерация бизнес-ниш для {session.user_id}")
        
        profile = session.to_openai_dict()
        location = profile['demographics']['location']
        
        prompt = f"""Ты - бизнес-аналитик и предприниматель с опытом создания 50+ бизнесов.
На основе психологического анализа создай 8 КОНКРЕТНЫХ БИЗНЕС-НИШ.

## ПСИХОЛОГИЧЕСКИЙ АНАЛИЗ ПОЛЬЗОВАТЕЛЯ:
{analysis[:2000]}

## ПРАКТИЧЕСКИЕ ПАРАМЕТРЫ ПОЛЬЗОВАТЕЛЯ:
- Возраст: {profile['demographics']['age_group']}
- Образование: {profile['demographics']['education']}
- Локация: {location}
- Бюджет: {profile['limitations']['budget']}
- Время: {profile['limitations']['time_per_week']}
- Масштаб: {profile['limitations']['business_scale']}
- Формат: {profile['limitations']['business_format']}

## ТРЕБОВАНИЯ К НИШАМ:

### 1-2. 🔥 БЫСТРЫЙ СТАРТ (первые деньги за 1-2 месяца)
- Минимальные вложения
- Быстрый запуск
- Конкретные первые шаги
- Реальный рынок в локации пользователя

### 3-4. 🚀 СБАЛАНСИРОВАННЫЙ (стабильный доход за 3-6 месяцев)
- Умеренные вложения
- Стабильная клиентская база
- Возможность совмещения с работой
- Четкий план масштабирования

### 5-6. 🌱 ДОЛГОСРОЧНЫЙ (масштабирование за 1-2 года)
- Серьезные перспективы роста
- Высокий потолок доходов
- Возможность создания команды/бренда
- Учет трендов рынка

### 7. 💎 РИСКОВАННАЯ НИША (высокая маржа, требует смелости)
- Высокий потенциал доходности
- Соответствие уровню риска пользователя ({profile['personality']['risk_tolerance']}/10)
- Четкий план минимизации рисков
- Уникальное предложение

### 8. 🎯 СКРЫТАЯ НИША (мало конкурентов, требует экспертизы)
- Использование уникальных навыков пользователя
- Неочевидная монетизация
- Низкая конкуренция
- Требует глубокой экспертизы

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

ВЕРНИ ТОЛЬКО 8 НИШ В ЭТОМ ФОРМАТЕ. Без вступлений, без заключений."""

        niches_text = await self._call_openai(prompt, max_tokens=4000, temperature=0.8)
        
        if not niches_text:
            logger.warning("❌ Не удалось сгенерировать ниши")
            return self._create_fallback_niches(session)
        
        # Парсинг сгенерированных ниш
        niches = self._parse_niches_from_text(niches_text)
        
        if niches:
            logger.info(f"✅ Сгенерировано {len(niches)} ниш")
        else:
            logger.warning("❌ Не удалось распарсить ниши")
            niches = self._create_fallback_niches(session)
        
        return niches
    
    async def generate_detailed_plan(self, session: UserSession, niche: Dict) -> Optional[str]:
        """Генерация детального плана"""
        logger.info(f"📋 Генерация плана для ниши: {niche.get('name', '')}")
        
        profile = session.to_openai_dict()
        
        prompt = f"""Ты - опытный бизнес-консультант и коуч.
Создай ГИПЕРПЕРСОНАЛИЗИРОВАННЫЙ БИЗНЕС-ПЛАН.

## НИША ДЛЯ РАЗРАБОТКИ:
{niche.get('name', '')} ({niche.get('type', '')})
{niche.get('description', '')}

## ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ (ключевые параметры):
- Возраст: {profile['demographics']['age_group']}
- Образование: {profile['demographics']['education']}
- Локация: {profile['demographics']['location']}
- Мотивация: {', '.join(profile['personality']['motivations'])}
- Главные страхи: {', '.join(profile['personality']['fears'])}
- Бюджет: {profile['limitations']['budget']}
- Время в неделю: {profile['limitations']['time_per_week']}
- Суперсила: {profile['skills']['superpower']}
- Энергетический пик: Аналитика={profile['personality']['energy_profile']['peak_analytical']}, Креатив={profile['personality']['energy_profile']['peak_creative']}

## ОСОБЫЕ ТРЕБОВАНИЯ:
1. УЧЕСТЬ ВОЗРАСТ {profile['demographics']['age_group']} - предложить соответствующий темп и сложность
2. ИСПОЛЬЗОВАТЬ ОБРАЗОВАНИЕ {profile['demographics']['education']} - интегрировать в бизнес-модель
3. УЧЕСТЬ ЛОКАЦИЮ {profile['demographics']['location']} - предложить местные возможности
4. ОБОЙТИ СТРАХИ: {', '.join(profile['personality']['fears'])} - добавить психологические техники
5. УЛОЖИТЬСЯ В {profile['limitations']['time_per_week']} ЧАСОВ В НЕДЕЛЮ - реалистичное расписание
6. ИСПОЛЬЗОВАТЬ СУПЕРСИЛУ {profile['skills']['superpower']} - сделать конкурентным преимуществом

## СТРУКТУРА ПЛАНА:

### 1. 🧠 ПСИХОЛОГИЧЕСКАЯ ПОДГОТОВКА (день 1-7)
- Ментальная настройка для этой ниши
- Ежедневные ритуалы и привычки
- Техники работы со страхами
- Подготовка окружения

### 2. 🚀 ПОШАГОВЫЙ ЗАПУСК (30 дней, по дням)
#### Неделя 1: Подготовка (конкретные действия по дням)
#### Неделя 2: Создание активов (сайт, соцсети, материалы)
#### Неделя 3: Первые контакты и тестовые продажи
#### Неделя 4: Анализ результатов и корректировка

### 3. 💰 ФИНАНСОВАЯ ДОРОЖНАЯ КАРТА (12 месяцев)
#### Месяц 1-3: Выход в ноль (конкретные цифры доходов/расходов)
#### Месяц 4-6: Доход 50,000₽ в месяц (как достичь, конкретные шаги)
#### Месяц 7-12: Доход 100,000₽ в месяц (стратегия масштабирования)
#### Инвестиции по месяцам (детально)

### 4. 📊 МЕТРИКИ УСПЕХА И KPI
- Ежедневные метрики (3 конкретных показателя)
- Еженедельные метрики (3 показателя)
- Ежемесячные метрики (3 показателя)
- Критические точки контроля

### 5. ⚠️ ЧЕК-ЛИСТ ОШИБОК И РЕШЕНИЙ
- Типичные ошибки новичков в этой нише (5-7 ошибок)
- Как распознать их заранее
- Конкретные решения для каждой ошибки
- План Б на случай серьезных проблем

### 6. 📚 РЕСУРСЫ ДЛЯ РОСТА И РАЗВИТИЯ
- Книги (конкретные названия, почему подходят)
- Курсы (конкретные, с ссылками если возможно)
- Сообщества и нетворкинг (где искать)
- Инструменты и софт (список с описанием)

Сделай план МАКСИМАЛЬНО КОНКРЕТНЫМ, с цифрами, сроками, конкретными действиями.
Учитывай все особенности пользователя из профиля."""

        plan = await self._call_openai(prompt, max_tokens=4000, temperature=0.6)
        
        if not plan:
            logger.warning("❌ Не удалось сгенерировать план")
            plan = self._create_fallback_plan(session, niche)
        
        return plan
    
    def _parse_niches_from_text(self, text: str) -> List[Dict]:
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
        
        if current_niche:
            niches.append(current_niche)
        
        for niche in niches:
            if 'steps' not in niche or len(niche['steps']) < 3:
                niche['steps'] = [
                    'Провести анализ рынка и конкурентов',
                    'Создать MVP продукта или услуги',
                    'Найти первых 3 клиентов для тестирования'
                ]
        
        return niches
    
    def _create_fallback_analysis(self, session: UserSession) -> str:
        """Запасной психологический анализ"""
        return f"""# ПСИХОЛОГИЧЕСКИЙ АНАЛИЗ (базовый)

## 1. КЛЮЧЕВЫЕ ХАРАКТЕРИСТИКИ:
- **Тип личности:** Практичный аналитик с творческим потенциалом
- **Мотивация:** {', '.join(session.motivations)}
- **Сильные стороны:** Хорошие аналитические способности ({session.skills_analytics}/5), умение общаться ({session.skills_communication}/5)
- **Энергия:** Пик продуктивности - {session.peak_analytical or 'дневное'} время

## 2. СКРЫТЫЙ ПОТЕНЦИАЛ:
- Неиспользованная комбинация навыков: аналитика + {session.superpower or 'креативность'}
- Возможность монетизации образования: {session.education}
- Географическое преимущество: {session.get_location()}

## 3. ИДЕАЛЬНЫЕ УСЛОВИЯ:
- Формат: {session.business_format or 'гибрид'}
- Темп: Умеренный, с быстрым стартом
- Клиенты: {session.ideal_client_age or '30-40 лет'}, {session.ideal_client_field or 'бизнес'}

## 4. РЕКОМЕНДАЦИИ:
1. Начинать с небольших проектов для быстрого получения результата
2. Использовать сильные стороны для создания конкурентного преимущества
3. Постепенно расширять масштаб по мере роста уверенности"""
    
    def _create_fallback_niches(self, session: UserSession) -> List[Dict]:
        """Запасные бизнес-ниши"""
        location = session.get_location()
        
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
                    'Создать профессиональное портфолио и предложение',
                    'Найти 5 потенциальных клиентов через LinkedIn'
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
                'name': f'Автоматизация бизнес-процессов в {location}',
                'description': f'Разработка и внедрение систем автоматизации для малого бизнеса в {location}',
                'why': 'Использует аналитические навыки и интерес к технологиям',
                'format': 'Гибрид',
                'investment': '100,000-200,000₽',
                'roi': '6-8 месяцев',
                'steps': [
                    'Изучить популярные CRM системы',
                    'Разработать 3 пакета услуг автоматизации',
                    'Провести 10 пробных консультаций'
                ]
            },
            {
                'id': 4,
                'type': '💎 Рискованный',
                'name': 'Технологический стартап',
                'description': 'Создание SaaS-продукта для решения конкретной проблемы рынка',
                'why': 'Соответствует высокому уровню риска и техническим навыкам',
                'format': 'Онлайн',
                'investment': '300,000-500,000₽',
                'roi': '12-18 месяцев',
                'steps': [
                    'Провести исследование рынка',
                    'Найти технического сооснователя',
                    'Разработать прототип продукта'
                ]
            },
            {
                'id': 5,
                'type': '🎯 Скрытая ниша',
                'name': f'Нишевое консультирование в {location}',
                'description': f'Специализированные консультации для узкой отрасли в {location}',
                'why': 'Использует уникальное сочетание навыков и образования',
                'format': session.business_format or 'Гибрид',
                'investment': '20,000-80,000₽',
                'roi': '2-3 месяца',
                'steps': [
                    'Определить узкую целевую аудиторию',
                    'Разработать уникальное предложение',
                    'Найти первых клиентов через нетворкинг'
                ]
            }
        ]
    
    def _create_fallback_plan(self, session: UserSession, niche: Dict) -> str:
        """Запасной детальный план"""
        return f"""# 📋 ДЕТАЛЬНЫЙ БИЗНЕС-ПЛАН

## 🎯 НИША: {niche.get('name', 'Бизнес-услуги')}

### 1. 🧠 ПСИХОЛОГИЧЕСКАЯ ПОДГОТОВКА (неделя 1)
- **Ментальная настройка:** Ежедневно 15 минут на визуализацию успеха
- **Работа со страхами:** Разбивайте большие задачи на маленькие шаги по 30 минут
- **Ритуалы:** Утренний planning и вечерний review дня

### 2. 🚀 30-ДНЕВНЫЙ ЗАПУСК
**Неделя 1-2: Подготовка**
- Создать базовые материалы (визитка, сайт, соцсети)
- Определить целевую аудиторию и ценностное предложение
- Подготовить коммерческое предложение

**Неделя 3-4: Первые контакты**
- Найти 20 потенциальных клиентов
- Провести 5 пробных консультаций
- Заключить первые 2-3 договора

### 3. 💰 ФИНАНСОВАЯ ДОРОЖНАЯ КАРТА
**Стартовые инвестиции:** {niche.get('investment', '50,000-100,000₽')}

**Месяц 1-3:**
- Доход: 30,000-50,000₽
- Расходы: 20,000-30,000₽
- **Цель:** Выйти в ноль к концу 3 месяца

**Месяц 4-6:**
- Доход: 50,000-80,000₽
- **Цель:** Стабильный доход 50,000₽ в месяц

**Месяц 7-12:**
- Доход: 80,000-120,000₽
- **Цель:** Достичь 100,000₽ в месяц

### 4. 📊 МЕТРИКИ УСПЕХА
- **Ежедневно:** 3 новых контакта, 1 консультация
- **Еженедельно:** 2-3 закрытые сделки
- **Ежемесячно:** Доход от 50,000₽, 5 довольных клиентов

### 5. ⚠️ ТИПИЧНЫЕ ОШИБКИ
1. **Слишком широкий фокус:** Начинать нужно с узкой ниши
2. **Недооценка времени:** Учитывайте административную работу
3. **Отсутствие системы:** Создавайте процессы с первого дня

### 6. 📚 РЕСУРСЫ ДЛЯ РОСТА
- **Книги:** "От нуля к единице" Питер Тиль, "Бизнес с нуля" Эрик Рис
- **Сообщества:** Местные бизнес-клубы, Telegram-чаты по вашей теме
- **Инструменты:** Notion для планирования, Canva для дизайна, Tilda для сайта

💡 **Совет:** Начинайте с малого, быстро тестируйте гипотезы, собирайте обратную связь и масштабируйте то, что работает."""

# ==================== МЕНЕДЖЕР ДАННЫХ ====================
class DataManager:
    """Менеджер данных"""
    
    def __init__(self):
        self.user_sessions: Dict[int, UserSession] = {}
        self.openai_usage = OpenAIUsage()
        self.stats = BotStatistics()
        self.cache_dir = Path("./data")
        self.cache_dir.mkdir(exist_ok=True)
        self.last_cleanup = datetime.now()
        
        # Загружаем сохраненные сессии
        self._load_sessions()
    
    def _load_sessions(self):
        """Загрузить сохраненные сессии"""
        try:
            for file_path in self.cache_dir.glob("session_*.json"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Создаем сессию из данных
                    session = UserSession(**data)
                    self.user_sessions[session.user_id] = session
                    self.stats.active_sessions += 1
                    
                except Exception as e:
                    logger.error(f"Ошибка загрузки сессии из {file_path}: {e}")
        except Exception as e:
            logger.error(f"Ошибка загрузки сессий: {e}")
    
    def save_session(self, session: UserSession):
        """Сохранить сессию"""
        try:
            file_path = self.cache_dir / f"session_{session.user_id}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(session), f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"Ошибка сохранения сессии {session.user_id}: {e}")
    
    def get_or_create_session(self, user_id: int, chat_id: int, **kwargs) -> UserSession:
        """Получить или создать сессию"""
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            session.update_activity()
            return session
        else:
            session = UserSession(
                user_id=user_id,
                chat_id=chat_id,
                username=kwargs.get('username'),
                first_name=kwargs.get('first_name'),
                last_name=kwargs.get('last_name')
            )
            self.user_sessions[user_id] = session
            self.stats.total_users += 1
            self.stats.active_sessions += 1
            return session
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Очистить старые сессии"""
        now = datetime.now()
        if (now - self.last_cleanup).total_seconds() < 3600:
            return
        
        expired = []
        for user_id, session in self.user_sessions.items():
            if (now - session.last_activity).total_seconds() > max_age_hours * 3600:
                expired.append(user_id)
        
        for user_id in expired:
            if user_id in self.user_sessions:
                self.save_session(self.user_sessions[user_id])
                del self.user_sessions[user_id]
                self.stats.active_sessions -= 1
        
        if expired:
            logger.info(f"Очищено {len(expired)} неактивных сессий")
        
        self.last_cleanup = now
    
    def mark_profile_completed(self, user_id: int):
        """Пометить профиль как завершенный"""
        if user_id in self.user_sessions:
            self.stats.completed_profiles += 1
            self.save_session(self.user_sessions[user_id])
    
    def add_generated_niches(self, niches_count: int):
        """Добавить сгенерированные ниши"""
        self.stats.generated_niches += niches_count
    
    def add_generated_plan(self):
        """Добавить сгенерированный план"""
        self.stats.generated_plans += 1
    
    def increment_messages(self):
        """Увеличить счетчик сообщений"""
        self.stats.total_messages += 1

# ==================== UX МЕНЕДЖЕР ====================
class UXManager:
    """Менеджер пользовательского опыта"""
    
    def __init__(self, config: BotConfig):
        self.config = config
    
    def get_random_praise(self) -> str:
        """Получить случайную фразу похвалы"""
        return random.choice(self.config.praise_phrases)
    
    def get_progress_header(self, session: UserSession) -> str:
        """Получить заголовок с прогрессом"""
        progress_bar = session.get_progress_bar()
        question_num = session.current_question
        
        emojis = ["🔴", "🟠", "🟡", "🟢", "🔵", "🟣"]
        emoji = emojis[min(question_num - 1, len(emojis) - 1)] if question_num > 0 else "🟢"
        
        return f"{emoji} *Вопрос {question_num}/{session.total_questions}*\n{progress_bar}\n"
    
    def format_niche_for_display(self, niche: Dict, index: int, total: int) -> str:
        """Форматировать нишу для отображения"""
        steps_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(niche.get('steps', [])[:3])])
        
        return f"""🎯 *НИША {index} из {total}*

{niche.get('type', '🔥 Ниша')}

*{niche.get('name', 'Название')}*

📝 *Суть:*
{niche.get('description', 'Описание')}

✅ *Почему вам подходит:*
{niche.get('why', 'Соответствует вашему профилю')}

📊 *Детали:*
• Формат: {niche.get('format', 'Гибрид')}
• Инвестиции: {niche.get('investment', '50,000-100,000₽')}
• Окупаемость: {niche.get('roi', '3-6 месяцев')}

🚀 *Первые шаги:*
{steps_text}"""
    
    def format_analysis_for_display(self, analysis: str) -> str:
        """Форматировать анализ для отображения"""
        return f"""🧠 *ПСИХОЛОГИЧЕСКИЙ АНАЛИЗ*

{analysis[:3000]}..."""
    
    def create_niche_navigation(self, session: UserSession) -> InlineKeyboardMarkup:
        """Создать клавиатуру навигации по нишам"""
        keyboard = []
        
        if session.generated_niches:
            current_idx = session.selected_niche_index
            total = len(session.generated_niches)
            
            # Кнопки навигации
            nav_buttons = []
            if current_idx > 0:
                nav_buttons.append(InlineKeyboardButton("◀️ Предыдущая", callback_data="niche_prev"))
            
            nav_buttons.append(InlineKeyboardButton(f"{current_idx + 1}/{total}", callback_data="niche_current"))
            
            if current_idx < total - 1:
                nav_buttons.append(InlineKeyboardButton("Следующая ▶️", callback_data="niche_next"))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            # Кнопки действий
            current_niche = session.generated_niches[current_idx]
            niche_id = current_niche.get('id', current_idx + 1)
            
            keyboard.append([
                InlineKeyboardButton("📋 Детальный план", callback_data=f"plan_{niche_id}")
            ])
        
        # Общие кнопки
        keyboard.append([
            InlineKeyboardButton("🧠 Психологический анализ", callback_data="show_analysis"),
            InlineKeyboardButton("💾 Сохранить все", callback_data="save_all")
        ])
        
        keyboard.append([
            InlineKeyboardButton("🔄 Начать заново", callback_data="start_over"),
            InlineKeyboardButton("📊 Статистика", callback_data="show_stats")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def create_question_keyboard(self, question_type: QuestionType, options: List[Any] = None) -> Optional[InlineKeyboardMarkup]:
        """Создать клавиатуру для вопроса"""
        if not options:
            return None
        
        keyboard = []
        
        if question_type == QuestionType.BUTTONS:
            for option in options:
                if isinstance(option, tuple):
                    text, callback_data = option
                    keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])
                else:
                    keyboard.append([InlineKeyboardButton(option, callback_data=option)])
        
        elif question_type == QuestionType.MULTISELECT:
            for option in options:
                if isinstance(option, tuple):
                    text, callback_data = option
                    keyboard.append([InlineKeyboardButton(f"□ {text}", callback_data=f"select_{callback_data}")])
                else:
                    keyboard.append([InlineKeyboardButton(f"□ {option}", callback_data=f"select_{option}")])
            keyboard.append([InlineKeyboardButton("✅ Завершить выбор", callback_data="multiselect_done")])
        
        elif question_type == QuestionType.SLIDER:
            # Простой слайдер
            row = []
            for i in range(1, 6):
                row.append(InlineKeyboardButton(str(i), callback_data=f"slider_{i}"))
            keyboard.append(row)
            keyboard.append([InlineKeyboardButton("✅ Подтвердить", callback_data="slider_confirm")])
        
        return InlineKeyboardMarkup(keyboard) if keyboard else None

# ==================== ОСНОВНОЙ КЛАСС БОТА ====================
class BusinessNavigatorBot:
    """Основной класс бота"""
    
    def __init__(self):
        self.config = BotConfig()
        self.data_manager = DataManager()
        self.ux_manager = UXManager(self.config)
        self.openai_service = OpenAIService(self.config)
        
        # Инициализация приложения Telegram
        self.application = Application.builder() \
            .token(self.config.telegram_token) \
            .build()
        
        # Регистрация обработчиков
        self._register_handlers()
        
        logger.info("🤖 Бизнес-Навигатор инициализирован")
    
    def _register_handlers(self):
        """Регистрация всех обработчиков"""
        # Обработчики команд
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("restart", self.restart_command))
        
        # Обработчики callback-запросов
        self.application.add_handler(CallbackQueryHandler(self.handle_callback_query))
        
        # Обработчики текстовых сообщений
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            self.handle_text_message
        ))
        
        # Обработчик ошибок
        self.application.add_error_handler(self.error_handler)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        chat = update.effective_chat
        
        # Очищаем старые сессии
        self.data_manager.cleanup_old_sessions()
        
        # Создаем новую сессию
        session = self.data_manager.get_or_create_session(
            user_id=user.id,
            chat_id=chat.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        # Сбрасываем состояние
        session.current_state = BotState.START
        session.current_question = 0
        session.questions_answered = 0
        session.selected_niche_index = 0
        session.start_time = datetime.now()
        session.update_activity()
        
        # Приветственное сообщение
        ai_status = "✅ (AI-режим)" if self.openai_service.is_available else "⚠️ (Базовый режим)"
        
        welcome_text = f"""👋 *Добро пожаловать в Бизнес-Навигатор v7.0!* {ai_status}

🎯 *Что вас ждет:*
• 18 вопросов для глубокого анализа личности
• Психологический портрет от AI
• 8 персонализированных бизнес-ниш
• Детальные пошаговые планы

📊 *Статистика бота:*
{self.data_manager.stats.get_stats_str()}

👇 *Нажмите кнопку ниже, чтобы начать анализ:*"""
        
        keyboard = [[InlineKeyboardButton("🚀 Начать анкету", callback_data='start_questionnaire')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Сохраняем менеджеры в контексте
        context.bot_data['data_manager'] = self.data_manager
        context.bot_data['openai_service'] = self.openai_service
        context.bot_data['ux_manager'] = self.ux_manager
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """🤖 *ПОМОЩЬ ПО БОТУ*

*Команды:*
/start - Начать новый анализ
/restart - Начать заново (очистить текущую сессию)
/stats - Показать статистику бота
/help - Эта справка

*Процесс анализа:*
1. Заполните анкету (18 вопросов)
2. AI анализирует ваш профиль
3. Получите 8 персонализированных бизнес-ниш
4. Выберите нишу для детального плана

*Советы:*
• Будьте честны в ответах
• Не торопитесь, обдумайте каждый вопрос
• Отвечайте максимально подробно
• Используйте все возможности AI-анализа"""
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /stats"""
        stats_text = f"""📊 *СТАТИСТИКА БОТА*

{self.data_manager.stats.get_stats_str()}

{self.data_manager.openai_usage.get_stats_str() if self.data_manager.openai_usage.total_requests > 0 else ''}

*Активные сессии:* {len(self.data_manager.user_sessions)}"""
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    
    async def restart_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /restart"""
        user_id = update.effective_user.id
        
        if user_id in self.data_manager.user_sessions:
            # Сохраняем старую сессию
            self.data_manager.save_session(self.data_manager.user_sessions[user_id])
            # Удаляем из активных
            del self.data_manager.user_sessions[user_id]
            self.data_manager.stats.active_sessions -= 1
        
        await update.message.reply_text(
            "🔄 *Сессия сброшена!*\n\n"
            "Все данные вашей текущей сессии сохранены.\n"
            "Используйте /start для начала нового анализа.",
            parse_mode='Markdown'
        )
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback-запросов"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        callback_data = query.data
        
        # Получаем сессию
        session = self.data_manager.get_or_create_session(
            user_id=user_id,
            chat_id=query.message.chat_id,
            username=query.from_user.username,
            first_name=query.from_user.first_name,
            last_name=query.from_user.last_name
        )
        
        # Обработка callback в зависимости от состояния
        if session.current_state == BotState.START:
            await self._handle_start_state(query, session, callback_data)
        elif session.current_state in [BotState.DEMOGRAPHY, BotState.PERSONALITY, 
                                      BotState.SKILLS, BotState.VALUES, BotState.LIMITATIONS]:
            await self._handle_questionnaire_state(query, context, session, callback_data)
        elif session.current_state == BotState.NICHE_SELECTION:
            await self._handle_niche_selection_state(query, context, session, callback_data)
        elif session.current_state == BotState.DETAILED_PLAN:
            await self._handle_detailed_plan_state(query, context, session, callback_data)
        elif session.current_state == BotState.PSYCH_ANALYSIS:
            await self._handle_psych_analysis_state(query, context, session, callback_data)
    
    async def _handle_start_state(self, query, session, callback_data):
        """Обработка состояния START"""
        if callback_data == 'start_questionnaire':
            session.current_state = BotState.DEMOGRAPHY
            session.current_question = 1
            await self._ask_question(query, session, 1)
    
    async def _handle_questionnaire_state(self, query, context, session, callback_data):
        """Обработка состояний вопросника"""
        question_num = session.current_question
        
        if callback_data.startswith('select_'):
            # Мультиселект
            selected_id = callback_data.replace('select_', '')
            if selected_id in session.temp_multiselect:
                session.temp_multiselect.remove(selected_id)
            else:
                session.temp_multiselect.append(selected_id)
            
            await self._update_multiselect_message(query, session, question_num)
            
        elif callback_data == 'multiselect_done':
            await self._handle_multiselect_done(query, session, question_num)
            
        elif callback_data.startswith('slider_'):
            if callback_data == 'slider_confirm':
                await self._handle_slider_confirm(query, session, question_num)
            else:
                value = int(callback_data.split('_')[1])
                await self._handle_slider_value(query, session, question_num, value)
                
        elif callback_data.startswith('energy_'):
            await self._handle_energy_selection(query, session, callback_data)
            
        elif callback_data.startswith('peak_'):
            await self._handle_peak_selection(query, session, callback_data)
            
        else:
            # Обычная кнопка
            await self._handle_button_answer(query, context, session, question_num, callback_data)
    
    async def _handle_niche_selection_state(self, query, context, session, callback_data):
        """Обработка состояния NICHE_SELECTION"""
        if callback_data == 'niche_prev':
            if session.selected_niche_index > 0:
                session.selected_niche_index -= 1
                await self._show_current_niche(query, session)
                
        elif callback_data == 'niche_next':
            if session.selected_niche_index < len(session.generated_niches) - 1:
                session.selected_niche_index += 1
                await self._show_current_niche(query, session)
                
        elif callback_data.startswith('plan_'):
            await self._show_detailed_plan(query, context, session, callback_data)
            
        elif callback_data == 'show_analysis':
            await self._show_psych_analysis(query, context, session)
            
        elif callback_data == 'save_all':
            await self._save_all_data(query, context, session)
            
        elif callback_data == 'start_over':
            await self._start_over(query, session)
            
        elif callback_data == 'show_stats':
            await self._show_stats(query, context)
    
    async def _handle_detailed_plan_state(self, query, context, session, callback_data):
        """Обработка состояния DETAILED_PLAN"""
        if callback_data == 'back_to_niches':
            session.current_state = BotState.NICHE_SELECTION
            await self._show_current_niche(query, session)
            
        elif callback_data.startswith('save_plan_'):
            await query.answer("✅ План сохранен в истории чата!", show_alert=True)
    
    async def _handle_psych_analysis_state(self, query, context, session, callback_data):
        """Обработка состояния PSYCH_ANALYSIS"""
        if callback_data == 'back_to_niches':
            session.current_state = BotState.NICHE_SELECTION
            await self._show_current_niche(query, session)
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        # Увеличиваем счетчик сообщений
        self.data_manager.increment_messages()
        
        # Получаем сессию
        session = self.data_manager.get_or_create_session(
            user_id=user_id,
            chat_id=update.message.chat_id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name
        )
        
        # Обработка текстового ответа
        question_num = session.current_question
        
        if question_num == 4 and session.current_state == BotState.DEMOGRAPHY:
            # Кастомная локация
            session.location_custom = message_text
            session.location = message_text
            session.questions_answered += 1
            await self._ask_next_question(update, session, 5)
            
        elif question_num == 9 and session.current_state == BotState.PERSONALITY:
            # Энергетический профиль (текст)
            # Парсим числа из текста
            import re
            numbers = re.findall(r'\d+', message_text)
            if len(numbers) >= 3:
                try:
                    session.energy_morning = min(7, max(1, int(numbers[0])))
                    session.energy_day = min(7, max(1, int(numbers[1])))
                    session.energy_evening = min(7, max(1, int(numbers[2])))
                except:
                    pass
            session.questions_answered += 1
            await self._ask_next_question(update, session, 10)
            
        elif question_num == 12 and session.current_state == BotState.PERSONALITY:
            # Кастомный страх
            session.fear_custom = message_text
            session.questions_answered += 1
            await self._ask_next_question(update, session, 13)
            
        elif question_num == 21 and session.current_state == BotState.SKILLS:
            # Стиль обучения
            session.learning_preferences = message_text
            session.questions_answered += 1
            await self._ask_next_question(update, session, 22)
            
        elif question_num == 22 and session.current_state == BotState.VALUES:
            # Экзистенциальный вопрос
            session.existential_answer = message_text
            session.questions_answered += 1
            await self._ask_next_question(update, session, 23)
            
        elif question_num == 23 and session.current_state == BotState.VALUES:
            # Состояние потока
            session.flow_experience_desc = message_text
            session.questions_answered += 1
            await self._ask_next_question(update, session, 24)
            
        elif question_num == 24 and session.current_state == BotState.VALUES:
            # Ощущения в потоке
            session.flow_feelings = message_text
            session.questions_answered += 1
            await self._ask_next_question(update, session, 25)
            
        elif question_num == 28 and session.current_state == BotState.VALUES:
            # Детали о клиенте
            session.ideal_client_details = message_text
            session.questions_answered += 1
            await self._ask_next_question(update, session, 29)
            
        else:
            await update.message.reply_text(
                "Пожалуйста, используйте кнопки для ответа на текущий вопрос.",
                parse_mode='Markdown'
            )
    
    async def _ask_question(self, query, session, question_num):
        """Задать вопрос"""
        session.current_question = question_num
        
        header = self.ux_manager.get_progress_header(session)
        praise = self.ux_manager.get_random_praise()
        
        question_text, keyboard = self._get_question_data(question_num)
        full_text = f"{praise}\n\n{header}{question_text}"
        
        reply_markup = self.ux_manager.create_question_keyboard(keyboard[0], keyboard[1]) if keyboard[1] else None
        
        if query:
            await query.edit_message_text(
                full_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    async def _ask_next_question(self, update, session, next_question_num):
        """Задать следующий вопрос"""
        session.current_question = next_question_num
        
        if next_question_num > session.total_questions:
            # Все вопросы отвечены
            await self._finish_questionnaire(update, session)
            return
        
        header = self.ux_manager.get_progress_header(session)
        praise = self.ux_manager.get_random_praise()
        
        question_text, keyboard = self._get_question_data(next_question_num)
        full_text = f"{praise}\n\n{header}{question_text}"
        
        reply_markup = self.ux_manager.create_question_keyboard(keyboard[0], keyboard[1]) if keyboard[1] else None
        
        if isinstance(update, Update) and update.message:
            await update.message.reply_text(
                full_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        elif hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(
                full_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    def _get_question_data(self, question_num: int) -> Tuple[str, Tuple[QuestionType, List]]:
        """Получить данные вопроса"""
        questions = {
            1: (
                "🔢 *ВОПРОС 1/18: ВАШ ВОЗРАСТ*\n\nВыберите вашу возрастную группу:",
                (QuestionType.BUTTONS, [
                    ("18-25 лет", "age_18-25"),
                    ("26-35 лет", "age_26-35"),
                    ("36-45 лет", "age_36-45"),
                    ("46+ лет", "age_46+")
                ])
            ),
            2: (
                "🎓 *ВОПРОС 2/18: ВАШЕ ОБРАЗОВАНИЕ*\n\nВыберите ваш образовательный уровень:",
                (QuestionType.BUTTONS, [
                    ("Среднее", "edu_school"),
                    ("Среднее специальное", "edu_college"),
                    ("Неоконченное высшее", "edu_incomplete"),
                    ("Высшее (бакалавр)", "edu_bachelor"),
                    ("Высшее (магистр/специалист)", "edu_master"),
                    ("Два и более высших", "edu_multiple"),
                    ("MBA/аспирантура", "edu_mba"),
                    ("Самообразование", "edu_self")
                ])
            ),
            3: (
                "🏙️ *ВОПРОС 3/18: ВАШ ГОРОД/РЕГИОН*\n\nВыберите тип вашего населенного пункта:",
                (QuestionType.BUTTONS, [
                    ("Москва", "loc_moscow"),
                    ("Санкт-Петербург", "loc_spb"),
                    ("Город-миллионник", "loc_million"),
                    ("Областной центр", "loc_region"),
                    ("Малый город", "loc_small"),
                    ("Село/деревня", "loc_village"),
                    ("Другое (напишу)", "loc_custom")
                ])
            ),
            4: (
                "🏙️ *ВОПРОС 3/18 (продолжение): НАЗВАНИЕ ВАШЕГО ГОРОДА*\n\nНапишите название вашего города или региона:",
                (QuestionType.TEXT, [])
            ),
            5: (
                "🎯 *ВОПРОС 4/18: КЛЮЧЕВАЯ МОТИВАЦИЯ*\n\nЧто для вас ВАЖНЕЕ ВСЕГО в бизнесе?\nВыберите 2-3 самых важных пункта:",
                (QuestionType.MULTISELECT, [
                    ("Свобода и независимость", "mot_freedom"),
                    ("Стабильный высокий доход", "mot_money"),
                    ("Помощь людям", "mot_help"),
                    ("Творческая реализация", "mot_creative"),
                    ("Решение сложных вызовов", "mot_challenge"),
                    ("Признание, статус", "mot_status"),
                    ("Баланс работы и жизни", "mot_balance"),
                    ("Наследие, долгосрочный проект", "mot_legacy")
                ])
            ),
            6: (
                "🧩 *ВОПРОС 5/18: СТИЛЬ ПРИНЯТИЯ РЕШЕНИЙ*\n\n*Ситуация:* Нужно выбрать между двумя проектами.\n\nКакой подход вам ближе?",
                (QuestionType.BUTTONS, [
                    ("💖 Проект А - нравится интуитивно", "dec_feelings"),
                    ("📊 Проект Б - больше цифр и аналитики", "dec_logic"),
                    ("🤝 Посоветуюсь с близкими/экспертами", "dec_advice"),
                    ("⚖️ Составлю таблицу плюсов/минусов", "dec_table"),
                    ("🎯 Выберу то, что быстрее принесет результат", "dec_fast")
                ])
            ),
            7: (
                "🎲 *ВОПРОС 6/18: ОТНОШЕНИЕ К РИСКУ*\n\n*Ситуация:* У вас есть 100,000₽ свободных денег.\n\nНа что готовы их использовать?",
                (QuestionType.BUTTONS, [
                    ("🔒 Только на проверенные инвестиции", "risk_safe"),
                    ("🎓 На обучение/развитие навыков", "risk_learning"),
                    ("🚀 На запуск своего дела", "risk_business"),
                    ("🎰 На рискованный стартап", "risk_startup")
                ])
            ),
            8: (
                "🎲 *ВОПРОС 6/18 (продолжение): УРОВЕНЬ РИСКА*\n\nОцените ваш общий уровень толерантности к риску:\n1 - максимальная осторожность, 10 - готов к высоким рискам",
                (QuestionType.SLIDER, [])
            ),
            9: (
                "⚡ *ВОПРОС 7/18: ЭНЕРГЕТИЧЕСКИЙ ПРОФИЛЬ*\n\nКак распределяется ваша ЭНЕРГИЯ в течение дня?\n(1 - минимальная энергия, 7 - максимальная)\n\nНапишите три числа через пробел (утро день вечер):",
                (QuestionType.TEXT, [])
            ),
            10: (
                "⚡ *ВОПРОС 7/18 (продолжение): ПИКОВАЯ ПРОДУКТИВНОСТЬ*\n\nКогда вы наиболее продуктивны для АНАЛИТИЧЕСКОЙ работы?",
                (QuestionType.BUTTONS, [
                    ("🌅 Утро", "peak_analytical_morning"),
                    ("☀️ День", "peak_analytical_day"),
                    ("🌙 Вечер", "peak_analytical_evening")
                ])
            ),
            11: (
                "⚡ *ВОПРОС 7/18 (продолжение): ПИКОВАЯ ПРОДУКТИВНОСТЬ*\n\nКогда вы наиболее продуктивны для ТВОРЧЕСКОЙ работы?",
                (QuestionType.BUTTONS, [
                    ("🌅 Утро", "peak_creative_morning"),
                    ("☀️ День", "peak_creative_day"),
                    ("🌙 Вечер", "peak_creative_evening")
                ])
            ),
            12: (
                "⚡ *ВОПРОС 7/18 (продолжение): ПИКОВАЯ ПРОДУКТИВНОСТЬ*\n\nКогда вы наиболее продуктивны для ОБЩЕНИЯ С ЛЮДЬМИ?",
                (QuestionType.BUTTONS, [
                    ("🌅 Утро", "peak_social_morning"),
                    ("☀️ День", "peak_social_day"),
                    ("🌙 Вечер", "peak_social_evening")
                ])
            ),
            13: (
                "👻 *ВОПРОС 8/18: ГЛУБИННЫЕ СТРАХИ*\n\nЧего вы БОЛЬШЕ ВСЕГО БОИТЕСЬ в бизнесе?\nВыберите 1-2 главных страха:",
                (QuestionType.MULTISELECT, [
                    ("Финансовая нестабильность", "fear_financial"),
                    ("Не справиться технически", "fear_technical"),
                    ("Провал, осуждение близких", "fear_failure"),
                    ("Выгорание, потеря интереса", "fear_burnout"),
                    ("Юридические проблемы", "fear_legal"),
                    ("Не найти клиентов", "fear_clients"),
                    ("Конкуренция", "fear_competition")
                ])
            ),
            14: (
                "👻 *ВОПРОС 8/18 (продолжение): ОПИШИТЕ ВАШ СТРАХ*\n\nА теперь опишите СВОИМИ СЛОВАМИ:\n\"Мой самый большой страх в бизнесе - это...\"",
                (QuestionType.TEXT, [])
            ),
            15: (
                "🧠 *ВОПРОС 9/18: АНАЛИТИЧЕСКИЕ НАВЫКИ*\n\nОцените ваш уровень аналитики и работы с цифрами:\n(1 - начинающий, 5 - эксперт)",
                (QuestionType.SLIDER, [])
            ),
            16: (
                "💬 *ВОПРОС 10/18: КОММУНИКАЦИОННЫЕ НАВЫКИ*\n\nОцените ваши навыки общения и переговоров:",
                (QuestionType.SLIDER, [])
            ),
            17: (
                "🎨 *ВОПРОС 11/18: ТВОРЧЕСКИЕ НАВЫКИ*\n\nОцените ваши навыки дизайна и креативности:",
                (QuestionType.SLIDER, [])
            ),
            18: (
                "📊 *ВОПРОС 12/18: ОРГАНИЗАЦИОННЫЕ НАВЫКИ*\n\nОцените ваши навыки планирования и организации:",
                (QuestionType.SLIDER, [])
            ),
            19: (
                "🔧 *ВОПРОС 13/18: НАВЫКИ РУЧНОГО ТРУДА*\n\nОцените ваши навыки работы руками:",
                (QuestionType.SLIDER, [])
            ),
            20: (
                "❤️ *ВОПРОС 14/18: ЭМОЦИОНАЛЬНЫЙ ИНТЕЛЛЕКТ*\n\nОцените ваш эмоциональный интеллект:",
                (QuestionType.SLIDER, [])
            ),
            21: (
                "🌟 *ВОПРОС 15/18: ВАША СУПЕРСИЛА*\n\nЕСЛИ БЫ ВЫ БЫЛИ СУПЕРГЕРОЕМ, ваша суперсила была бы:",
                (QuestionType.BUTTONS, [
                    ("🔮 ПРЕДВИДЕНИЕ - вижу тренды", "power_vision"),
                    ("💬 УБЕЖДЕНИЕ - договариваюсь", "power_persuasion"),
                    ("🔧 ИНЖЕНЕРИЯ - решаю задачи", "power_engineering"),
                    ("🎨 СОЗИДАНИЕ - создаю красивое", "power_creation"),
                    ("👁️ ПРОНИКНОВЕНИЕ - понимаю мотивы", "power_insight"),
                    ("⚡ ЭНЕРГИЯ - работаю на энтузиазме", "power_energy")
                ])
            ),
            22: (
                "🔄 *ВОПРОС 16/18: РЕЖИМ РАБОТЫ*\n\nКак вы ЛУЧШЕ ВСЕГО РАБОТАЕТЕ?\nВыберите вашу идеальную рабочую среду:",
                (QuestionType.BUTTONS, [
                    ("👤 В одиночку", "work_alone"),
                    ("👥 В паре", "work_pair"),
                    ("👨‍👩‍👧‍👦 В команде 3-5 человек", "work_team"),
                    ("🏢 В структуре с ролями", "work_structure"),
                    ("🌐 Удаленно", "work_remote"),
                    ("🤸 Гибко - меняю форматы", "work_flexible")
                ])
            ),
            23: (
                "📚 *ВОПРОС 17/18: СТИЛЬ ОБУЧЕНИЯ*\n\nКак вы лучше всего учитесь новому?\nОпишите одним-двумя предложениями:",
                (QuestionType.TEXT, [])
            ),
            24: (
                "🌍 *ВОПРОС 18/18: ЭКЗИСТЕНЦИАЛЬНЫЙ ВОПРОС*\n\n*Задание на 2 минуты размышления:*\n\n\"Если бы вам не нужно было зарабатывать деньги и все базовые потребности были бы удовлетворены...\"\n\nЧЕМ БЫ ВЫ ЗАНИМАЛИСЬ?\n(опишите подробно, 3-5 предложений)",
                (QuestionType.TEXT, [])
            ),
            25: (
                "⏳ *ВОПРОС 18/18 (продолжение): СОСТОЯНИЕ ПОТОКА*\n\nВспомните момент, когда вы полностью погружались в дело и теряли чувство времени:\n\nКакое это было дело? Опишите одним предложением.",
                (QuestionType.TEXT, [])
            ),
            26: (
                "⏳ *ВОПРОС 18/18 (продолжение): ОЩУЩЕНИЯ В ПОТОКЕ*\n\nТеперь опишите свои ОЩУЩЕНИЯ в тот момент:\n\"Я чувствовал(а)...\" (2-3 предложения)",
                (QuestionType.TEXT, [])
            ),
            27: (
                "👥 *ВОПРОС 18/18 (продолжение): ИДЕАЛЬНЫЙ КЛИЕНТ*\n\nОпишите человека, с которым вам было бы ИНТЕРЕСНО и ПРИЯТНО работать:\n\nВыберите возрастную группу:",
                (QuestionType.BUTTONS, [
                    ("20-30 лет", "client_20-30"),
                    ("30-40 лет", "client_30-40"),
                    ("40-50 лет", "client_40-50"),
                    ("50+ лет", "client_50+")
                ])
            ),
            28: (
                "👥 *ВОПРОС 18/18 (продолжение): СФЕРА ДЕЯТЕЛЬНОСТИ КЛИЕНТА*\n\nВыберите сферу деятельности вашего идеального клиента:",
                (QuestionType.BUTTONS, [
                    ("💻 IT/Технологии", "field_it"),
                    ("🎨 Творчество/Дизайн", "field_creative"),
                    ("💼 Бизнес/Предпринимательство", "field_business"),
                    ("📚 Образование", "field_education"),
                    ("🏥 Здоровье/Красота", "field_health"),
                    ("🌿 Другое", "field_other")
                ])
            ),
            29: (
                "👥 *ВОПРОС 18/18 (продолжение): ГЛАВНАЯ \"БОЛЬ\" КЛИЕНТА*\n\nКакая главная \"боль\" у вашего идеального клиента?",
                (QuestionType.BUTTONS, [
                    ("⏰ Не хватает времени", "pain_time"),
                    ("📊 Нет системности", "pain_system"),
                    ("🎓 Нет экспертизы", "pain_expertise"),
                    ("👥 Нет клиентов", "pain_clients"),
                    ("💰 Не хватает денег", "pain_money")
                ])
            ),
            30: (
                "👥 *ВОПРОС 18/18 (продолжение): ДЕТАЛИ О КЛИЕНТЕ*\n\nДобавьте деталей одним-двумя предложениями:\n\"Мне нравится работать с людьми, которые...\"",
                (QuestionType.TEXT, [])
            ),
            31: (
                "🛠️ *ВОПРОС 18/18 (продолжение): РЕСУРСНАЯ КАРТА*\n\nЧто у вас уже есть для старта?\n\n1. ДЕНЬГИ для инвестиций:",
                (QuestionType.BUTTONS, [
                    ("< 50,000₽", "budget_50k"),
                    ("50,000-200,000₽", "budget_200k"),
                    ("200,000-500,000₽", "budget_500k"),
                    ("> 500,000₽", "budget_more")
                ])
            ),
            32: (
                "🛠️ *ВОПРОС 18/18 (продолжение): ОБОРУДОВАНИЕ*\n\nКакое оборудование у вас уже есть?\n(можно выбрать несколько)",
                (QuestionType.MULTISELECT, [
                    ("💻 Компьютер/ноутбук", "equip_computer"),
                    ("📷 Камера/фотоаппарат", "equip_camera"),
                    ("🔧 Специнструменты", "equip_tools"),
                    ("🏠 Помещение/мастерская", "equip_space")
                ])
            ),
            33: (
                "🛠️ *ВОПРОС 18/18 (продолжение): ЗНАНИЯ И ДОСТУП*\n\nКакие нематериальные активы у вас есть?\n(можно выбрать несколько)",
                (QuestionType.MULTISELECT, [
                    ("🤝 Профессиональные связи", "know_connections"),
                    ("🎓 Уникальная экспертиза", "know_expertise"),
                    ("📊 Доступ к информации", "know_info"),
                    ("🌟 Личный бренд/аудитория", "know_brand")
                ])
            ),
            34: (
                "⏰ *ВОПРОС 18/18 (продолжение): ВРЕМЕННОЙ БЮДЖЕТ*\n\nСколько часов в неделю вы реально можете уделить бизнесу на старте?",
                (QuestionType.BUTTONS, [
                    ("5-10 часов", "time_5-10"),
                    ("10-20 часов", "time_10-20"),
                    ("20-30 часов", "time_20-30"),
                    ("30-40 часов", "time_30-40"),
                    ("40+ часов", "time_40+")
                ])
            ),
            35: (
                "📍 *ВОПРОС 18/18 (продолжение): МАСШТАБ БИЗНЕСА*\n\nКакой масштаб бизнеса вас привлекает?",
                (QuestionType.BUTTONS, [
                    ("📍 Локальный (район/город)", "scale_local"),
                    ("🗺️ Региональный (область)", "scale_region"),
                    ("🇷🇺 Национальный (Россия)", "scale_national"),
                    ("🌍 Международный", "scale_international"),
                    ("🌐 Онлайн-глобальный", "scale_online")
                ])
            ),
            36: (
                "📍 *ВОПРОС 18/18 (продолжение): ФОРМАТ РАБОТЫ*\n\nКакие у вас предпочтения по формату работы?",
                (QuestionType.BUTTONS, [
                    ("🌐 Только онлайн", "format_online"),
                    ("🏪 Только офлайн", "format_offline"),
                    ("🔄 Гибрид", "format_hybrid")
                ])
            )
        }
        
        return questions.get(question_num, ("Вопрос не найден", (QuestionType.BUTTONS, [])))
    
    async def _update_multiselect_message(self, query, session, question_num):
        """Обновить сообщение с мультиселектом"""
        question_text, keyboard_data = self._get_question_data(question_num)
        header = self.ux_manager.get_progress_header(session)
        praise = self.ux_manager.get_random_praise()
        
        selected_count = len(session.temp_multiselect)
        full_text = f"{praise}\n\n{header}{question_text}\n\n✅ Выбрано: {selected_count}"
        
        # Создаем обновленную клавиатуру
        question_type, options = keyboard_data
        keyboard = []
        
        for option in options:
            if isinstance(option, tuple):
                text, callback_data = option
                if callback_data in session.temp_multiselect:
                    keyboard.append([InlineKeyboardButton(f"✅ {text}", callback_data=f"select_{callback_data}")])
                else:
                    keyboard.append([InlineKeyboardButton(f"□ {text}", callback_data=f"select_{callback_data}")])
        
        keyboard.append([InlineKeyboardButton("✅ Завершить выбор", callback_data="multiselect_done")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            full_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _handle_multiselect_done(self, query, session, question_num):
        """Обработка завершения мультиселекта"""
        question_text, keyboard_data = self._get_question_data(question_num)
        
        # Проверяем количество выбранных вариантов
        selected = session.temp_multiselect
        min_selections = 2 if question_num == 5 else 1  # Для мотивации нужно 2-3, для остального 1-2
        
        if len(selected) < min_selections:
            await query.answer(f"❌ Пожалуйста, выберите как минимум {min_selections} варианта", show_alert=True)
            return
        
        # Сохраняем выбранные варианты
        if question_num == 5:  # Мотивация
            mot_map = {
                'mot_freedom': 'Свобода и независимость',
                'mot_money': 'Стабильный высокий доход',
                'mot_help': 'Помощь людям, социальная значимость',
                'mot_creative': 'Творческая реализация, самовыражение',
                'mot_challenge': 'Решение интересных вызовов, азарт',
                'mot_status': 'Признание, статус',
                'mot_balance': 'Баланс работы и жизни',
                'mot_legacy': 'Наследие, долгосрочный проект'
            }
            session.motivations = [mot_map.get(m, m) for m in selected]
            
        elif question_num == 13:  # Страхи
            fear_map = {
                'fear_financial': 'Финансовая нестабильность',
                'fear_technical': 'Не справиться технически',
                'fear_failure': 'Провал, осуждение близких',
                'fear_burnout': 'Выгорание, потеря интереса',
                'fear_legal': 'Юридические проблемы',
                'fear_clients': 'Не найти клиентов',
                'fear_competition': 'Конкуренция'
            }
            session.fears_selected = [fear_map.get(f, f) for f in selected]
            
        elif question_num == 32:  # Оборудование
            equip_map = {
                'equip_computer': 'Компьютер/ноутбук',
                'equip_camera': 'Камера/фотоаппарат',
                'equip_tools': 'Специнструменты',
                'equip_space': 'Помещение/мастерская'
            }
            session.equipment = [equip_map.get(e, e) for e in selected]
            
        elif question_num == 33:  # Знания
            know_map = {
                'know_connections': 'Профессиональные связи',
                'know_expertise': 'Уникальная экспертиза',
                'know_info': 'Доступ к информации',
                'know_brand': 'Личный бренд/аудитория'
            }
            session.knowledge_assets = [know_map.get(k, k) for k in selected]
        
        session.temp_multiselect = []
        session.questions_answered += 1
        await self._ask_next_question(query, session, question_num + 1)
    
    async def _handle_slider_value(self, query, session, question_num, value):
        """Обработка значения слайдера"""
        # Сохраняем значение в зависимости от вопроса
        if question_num == 8:  # Уровень риска
            session.risk_tolerance = value
        elif question_num == 15:  # Аналитика
            session.skills_analytics = value
        elif question_num == 16:  # Коммуникация
            session.skills_communication = value
        elif question_num == 17:  # Дизайн
            session.skills_design = value
        elif question_num == 18:  # Организация
            session.skills_organization = value
        elif question_num == 19:  # Ручной труд
            session.skills_manual = value
        elif question_num == 20:  # Эмоциональный интеллект
            session.skills_eq = value
        
        # Показываем текущее значение
        await query.answer(f"Выбрано: {value}", show_alert=False)
    
    async def _handle_slider_confirm(self, query, session, question_num):
        """Обработка подтверждения слайдера"""
        session.questions_answered += 1
        await self._ask_next_question(query, session, question_num + 1)
    
    async def _handle_energy_selection(self, query, session, callback_data):
        """Обработка выбора энергии"""
        # Для упрощения пропускаем детальную обработку
        session.questions_answered += 1
        await self._ask_next_question(query, session, session.current_question + 1)
    
    async def _handle_peak_selection(self, query, session, callback_data):
        """Обработка выбора пиковых часов"""
        if callback_data.startswith('peak_analytical_'):
            session.peak_analytical = callback_data.replace('peak_analytical_', '').capitalize()
        elif callback_data.startswith('peak_creative_'):
            session.peak_creative = callback_data.replace('peak_creative_', '').capitalize()
        elif callback_data.startswith('peak_social_'):
            session.peak_social = callback_data.replace('peak_social_', '').capitalize()
        
        # Переходим к следующему вопросу
        next_question = session.current_question + 1
        if next_question == 13:  # После всех пиковых часов
            session.questions_answered += 1
        
        await self._ask_next_question(query, session, next_question)
    
    async def _handle_button_answer(self, query, context, session, question_num, callback_data):
        """Обработка ответа на кнопку"""
        # Обработка ответов в зависимости от вопроса
        if question_num == 1:  # Возраст
            age_map = {
                'age_18-25': '18-25 лет',
                'age_26-35': '26-35 лет',
                'age_36-45': '36-45 лет',
                'age_46+': '46+ лет'
            }
            session.age_group = age_map.get(callback_data, 'Не указано')
            session.questions_answered += 1
            await self._ask_next_question(query, session, 2)
            
        elif question_num == 2:  # Образование
            edu_map = {
                'edu_school': 'Среднее',
                'edu_college': 'Среднее специальное',
                'edu_incomplete': 'Неоконченное высшее',
                'edu_bachelor': 'Высшее (бакалавр)',
                'edu_master': 'Высшее (магистр/специалист)',
                'edu_multiple': 'Два и более высших',
                'edu_mba': 'MBA/аспирантура',
                'edu_self': 'Самообразование (курсы, самоучка)'
            }
            session.education = edu_map.get(callback_data, 'Не указано')
            session.questions_answered += 1
            await self._ask_next_question(query, session, 3)
            
        elif question_num == 3:  # Локация
            if callback_data == 'loc_custom':
                # Пользователь напишет сам
                await query.edit_message_text(
                    "🏙️ *ВОПРОС 3/18 (продолжение): НАЗВАНИЕ ВАШЕГО ГОРОДА*\n\nНапишите название вашего города или региона:",
                    parse_mode='Markdown'
                )
                return
            
            loc_map = {
                'loc_moscow': 'Москва',
                'loc_spb': 'Санкт-Петербург',
                'loc_million': 'Город-миллионник',
                'loc_region': 'Областной центр',
                'loc_small': 'Малый город',
                'loc_village': 'Село/деревня'
            }
            session.location_type = loc_map.get(callback_data, 'Не указано')
            session.location = session.location_type
            session.questions_answered += 1
            await self._ask_next_question(query, session, 4)
            
        elif question_num == 6:  # Стиль решений
            dec_map = {
                'dec_feelings': 'Сначала чувства и эмоции, потом логика',
                'dec_logic': 'Сначала логика и факты, потом чувства',
                'dec_advice': 'Советуюсь с близкими/экспертами',
                'dec_table': 'Составляю таблицу плюсов/минусов',
                'dec_fast': 'Выбираю то, что быстрее принесет результат'
            }
            session.decision_style = dec_map.get(callback_data, 'Не указано')
            session.questions_answered += 1
            await self._ask_next_question(query, session, 7)
            
        elif question_num == 7:  # Риск сценарий
            risk_map = {
                'risk_safe': 'Только на проверенные инвестиции (<10% годовых)',
                'risk_learning': 'На обучение/развитие навыков',
                'risk_business': 'На запуск своего небольшого дела',
                'risk_startup': 'На рискованный, но перспективный стартап'
            }
            session.risk_scenario = risk_map.get(callback_data, 'Не указано')
            # Не увеличиваем счетчик - следующий вопрос часть того же
            await self._ask_next_question(query, session, 8)
            
        elif question_num == 21:  # Суперсила
            power_map = {
                'power_vision': 'Предвидение трендов и возможностей',
                'power_persuasion': 'Умение убеждать и вдохновлять',
                'power_engineering': 'Решение сложных технических проблем',
                'power_creation': 'Создание красивых и функциональных вещей',
                'power_insight': 'Понимание скрытых мотивов людей',
                'power_energy': 'Могу работать сутками на энтузиазме'
            }
            session.superpower = power_map.get(callback_data, 'Не указано')
            session.questions_answered += 1
            await self._ask_next_question(query, session, 22)
            
        elif question_num == 22:  # Режим работы
            work_map = {
                'work_alone': 'В одиночку - полный контроль',
                'work_pair': 'В паре - взаимодополнение',
                'work_team': 'В команде 3-5 человек',
                'work_structure': 'В структуре с четкими ролями',
                'work_remote': 'Удаленно, с периодическими встречами',
                'work_flexible': 'Гибко - меняю форматы под задачи'
            }
            session.work_style = work_map.get(callback_data, 'Не указано')
            session.questions_answered += 1
            await self._ask_next_question(query, session, 23)
            
        elif question_num == 27:  # Возраст клиента
            age_map = {
                'client_20-30': '20-30 лет',
                'client_30-40': '30-40 лет',
                'client_40-50': '40-50 лет',
                'client_50+': '50+ лет'
            }
            session.ideal_client_age = age_map.get(callback_data, 'Не указано')
            session.questions_answered += 1
            await self._ask_next_question(query, session, 28)
            
        elif question_num == 28:  # Сфера клиента
            field_map = {
                'field_it': 'IT/Технологии',
                'field_creative': 'Творчество/Дизайн',
                'field_business': 'Бизнес/Предпринимательство',
                'field_education': 'Образование',
                'field_health': 'Здоровье/Красота',
                'field_other': 'Другое'
            }
            session.ideal_client_field = field_map.get(callback_data, 'Не указано')
            session.questions_answered += 1
            await self._ask_next_question(query, session, 29)
            
        elif question_num == 29:  # Боль клиента
            pain_map = {
                'pain_time': 'Не хватает времени',
                'pain_system': 'Нет системности',
                'pain_expertise': 'Нет экспертизы',
                'pain_clients': 'Нет клиентов',
                'pain_money': 'Не хватает денег'
            }
            session.ideal_client_pain = pain_map.get(callback_data, 'Не указано')
            session.questions_answered += 1
            await self._ask_next_question(query, session, 30)
            
        elif question_num == 31:  # Бюджет
            budget_map = {
                'budget_50k': '< 50,000₽',
                'budget_200k': '50,000-200,000₽',
                'budget_500k': '200,000-500,000₽',
                'budget_more': '> 500,000₽'
            }
            session.budget = budget_map.get(callback_data, 'Не указано')
            session.questions_answered += 1
            await self._ask_next_question(query, session, 32)
            
        elif question_num == 34:  # Время
            time_map = {
                'time_5-10': '5-10 часов (параллельно с работой)',
                'time_10-20': '10-20 часов (серьезный side-project)',
                'time_20-30': '20-30 часов (почти полный день)',
                'time_30-40': '30-40 часов (можно погрузиться)',
                'time_40+': '40+ часов (готов(а) работать сутками)'
            }
            session.time_per_week = time_map.get(callback_data, 'Не указано')
            session.questions_answered += 1
            await self._ask_next_question(query, session, 35)
            
        elif question_num == 35:  # Масштаб
            scale_map = {
                'scale_local': 'Локальный (район/город)',
                'scale_region': 'Региональный (область)',
                'scale_national': 'Национальный (Россия)',
                'scale_international': 'Международный',
                'scale_online': 'Онлайн-глобальный'
            }
            session.business_scale = scale_map.get(callback_data, 'Не указано')
            session.questions_answered += 1
            await self._ask_next_question(query, session, 36)
            
        elif question_num == 36:  # Формат
            format_map = {
                'format_online': 'Только онлайн',
                'format_offline': 'Только офлайн',
                'format_hybrid': 'Гибрид (онлайн + офлайн)'
            }
            session.business_format = format_map.get(callback_data, 'Не указано')
            session.questions_answered += 1
            # Все вопросы отвечены
            await self._finish_questionnaire(query, session)
    
    async def _finish_questionnaire(self, update, session):
        """Завершить вопросник"""
        session.current_state = BotState.ANALYZING
        
        praise = self.ux_manager.get_random_praise()
        
        finish_text = f"""🎉 *БРАВО! АНКЕТА ЗАВЕРШЕНА!*

{praise}

✅ Отвечено: {session.questions_answered} вопросов
⏱️ Время заполнения: ~{(datetime.now() - session.start_time).seconds // 60} минут
🎯 Глубина анализа: профессиональный уровень

🤖 *Запускаю AI-анализ...*
1. Анализирую психологический профиль
2. Ищу скрытый потенциал  
3. Подбираю уникальные ниши
4. Готовлю персонализированные планы

⏳ *Это займет 1-2 минуты*
Пока AI работает, можете отдохнуть ☕"""
        
        if isinstance(update, Update) and update.message:
            await update.message.reply_text(finish_text, parse_mode='Markdown')
        elif hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text(finish_text, parse_mode='Markdown')
        
        # Сохраняем сессию
        self.data_manager.save_session(session)
        self.data_manager.mark_profile_completed(session.user_id)
        
        # Запускаем AI анализ асинхронно
        asyncio.create_task(self._start_ai_analysis(update, session))
    
    async def _start_ai_analysis(self, update, session):
        """Запустить AI анализ"""
        try:
            # Генерация психологического анализа
            analysis = await self.openai_service.generate_psychological_analysis(session)
            session.psychological_analysis = analysis
            
            # Генерация бизнес-ниш
            niches = await self.openai_service.generate_business_niches(session, analysis)
            session.generated_niches = niches
            self.data_manager.add_generated_niches(len(niches))
            
            # Генерация планов для первых 3 ниш
            plans_generated = 0
            for i, niche in enumerate(session.generated_niches[:3]):
                plan = await self.openai_service.generate_detailed_plan(session, niche)
                if plan:
                    session.detailed_plans[str(niche.get('id', i))] = plan
                    plans_generated += 1
                    self.data_manager.add_generated_plan()
            
            # Показываем результат
            stats = self.data_manager.openai_usage
            stats_text = stats.get_stats_str() if stats.total_requests > 0 else ""
            
            result_text = f"""🎉 *АНАЛИЗ ЗАВЕРШЕН!*

✅ Создано: {len(session.generated_niches)} уникальных бизнес-ниш
📊 Психологический портрет: готов
📋 Детальные планы: {plans_generated} шт

{stats_text}

👇 *Выберите первую нишу для изучения:*"""
            
            if hasattr(update, 'callback_query'):
                chat_id = update.callback_query.message.chat_id
            elif isinstance(update, Update) and update.message:
                chat_id = update.message.chat_id
            else:
                chat_id = session.chat_id
            
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=result_text,
                parse_mode='Markdown'
            )
            
            session.current_state = BotState.NICHE_SELECTION
            await self._show_current_niche(None, session, chat_id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка AI анализа: {e}")
            
            # Используем запасные данные
            await self._use_fallback_data(update, session)
    
    async def _use_fallback_data(self, update, session):
        """Использовать запасные данные"""
        session.psychological_analysis = self.openai_service._create_fallback_analysis(session)
        session.generated_niches = self.openai_service._create_fallback_niches(session)
        
        result_text = f"""🎉 *АНАЛИЗ ЗАВЕРШЕН (базовый режим)*

✅ Создано: {len(session.generated_niches)} бизнес-ниш
📊 Использованы стандартные шаблоны
⚠️ AI временно недоступен

👇 *Выберите первую нишу для изучения:*"""
        
        if hasattr(update, 'callback_query'):
            chat_id = update.callback_query.message.chat_id
            await update.callback_query.edit_message_text(result_text, parse_mode='Markdown')
        elif isinstance(update, Update) and update.message:
            chat_id = update.message.chat_id
            await update.message.reply_text(result_text, parse_mode='Markdown')
        else:
            chat_id = session.chat_id
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=result_text,
                parse_mode='Markdown'
            )
        
        session.current_state = BotState.NICHE_SELECTION
        await self._show_current_niche(None, session, chat_id)
    
    async def _show_current_niche(self, query, session, chat_id=None):
        """Показать текущую нишу"""
        if not session.generated_niches:
            error_text = "❌ Ниши не сгенерированы. Попробуйте начать заново /start"
            if query:
                await query.edit_message_text(error_text, parse_mode='Markdown')
            elif chat_id:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=error_text,
                    parse_mode='Markdown'
            )
            return
        
        niche = session.generated_niches[session.selected_niche_index]
        niche_text = self.ux_manager.format_niche_for_display(
            niche, 
            session.selected_niche_index + 1, 
            len(session.generated_niches)
        )
        
        keyboard = self.ux_manager.create_niche_navigation(session)
        
        if query:
            await query.edit_message_text(
                niche_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        elif chat_id:
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=niche_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
    
    async def _show_detailed_plan(self, query, context, session, callback_data):
        """Показать детальный план"""
        try:
            niche_id = callback_data.split('_')[1]
            plan = session.detailed_plans.get(niche_id)
            
            if plan:
                plan_text = f"""📋 *ДЕТАЛЬНЫЙ БИЗНЕС-ПЛАН*

{plan[:3500]}..."""
                
                keyboard = [[
                    InlineKeyboardButton("◀️ Назад к нишам", callback_data="back_to_niches"),
                    InlineKeyboardButton("💾 Сохранить план", callback_data=f"save_plan_{niche_id}")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    plan_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
                session.current_state = BotState.DETAILED_PLAN
            else:
                await query.answer("❌ План для этой ниши еще не сгенерирован", show_alert=True)
                
        except Exception as e:
            logger.error(f"Ошибка показа плана: {e}")
            await query.answer("❌ Ошибка загрузки плана", show_alert=True)
    
    async def _show_psych_analysis(self, query, context, session):
        """Показать психологический анализ"""
        if session.psychological_analysis:
            analysis_text = self.ux_manager.format_analysis_for_display(session.psychological_analysis)
            
            keyboard = [[InlineKeyboardButton("◀️ Назад к нишам", callback_data="back_to_niches")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                analysis_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            session.current_state = BotState.PSYCH_ANALYSIS
        else:
            await query.answer("❌ Анализ не сгенерирован", show_alert=True)
    
    async def _save_all_data(self, query, context, session):
        """Сохранить все данные"""
        await query.answer("💾 Сохраняю все данные...", show_alert=True)
        
        # Сохраняем сессию
        self.data_manager.save_session(session)
        
        # Отправляем все ниши
        for i, niche in enumerate(session.generated_niches):
            niche_text = self.ux_manager.format_niche_for_display(
                niche, i + 1, len(session.generated_niches)
            )
            
            await context.bot.send_message(
                chat_id=session.chat_id,
                text=niche_text,
                parse_mode='Markdown'
            )
            await asyncio.sleep(0.5)
        
        # Отправляем анализ если есть
        if session.psychological_analysis:
            analysis_text = self.ux_manager.format_analysis_for_display(session.psychological_analysis)
            await context.bot.send_message(
                chat_id=session.chat_id,
                text=analysis_text,
                parse_mode='Markdown'
            )
        
        await query.answer("✅ Все данные сохранены в истории чата!", show_alert=True)
    
    async def _start_over(self, query, session):
        """Начать заново"""
        # Сохраняем текущую сессию
        self.data_manager.save_session(session)
        
        # Удаляем из активных
        if session.user_id in self.data_manager.user_sessions:
            del self.data_manager.user_sessions[session.user_id]
            self.data_manager.stats.active_sessions -= 1
        
        keyboard = [[InlineKeyboardButton("🚀 Начать новую анкету", callback_data='start_questionnaire')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🔄 *Сессия сброшена!*\n\n"
            "Все данные вашей текущей сессии сохранены.\n"
            "Готовы начать новую анкету с чистого листа?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def _show_stats(self, query, context):
        """Показать статистику"""
        stats_text = f"""📊 *СТАТИСТИКА БОТА*

{self.data_manager.stats.get_stats_str()}

{self.data_manager.openai_usage.get_stats_str() if self.data_manager.openai_usage.total_requests > 0 else ''}

*Активные сессии:* {len(self.data_manager.user_sessions)}"""
        
        await query.edit_message_text(stats_text, parse_mode='Markdown')
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"Ошибка: {context.error}", exc_info=context.error)
        
        try:
            error_text = "❌ *Произошла ошибка*\n\nПожалуйста, попробуйте начать заново /start"
            
            if update and update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=error_text,
                    parse_mode='Markdown'
                )
        except:
            pass
    
    async def run(self):
        """Запустить бота"""
        logger.info("🚀 Запуск Бизнес-Навигатора...")
        
        # Запускаем поллинг
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
        logger.info("✅ Бот запущен и готов к работе!")
        
        # Бесконечный цикл
        try:
            while True:
                # Очистка старых сессий каждые 30 минут
                self.data_manager.cleanup_old_sessions()
                
                await asyncio.sleep(300)  # 5 минут
                
        except KeyboardInterrupt:
            logger.info("⏹ Остановка бота...")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
        finally:
            # Сохраняем все сессии
            for session in self.data_manager.user_sessions.values():
                self.data_manager.save_session(session)
            
            # Останавливаем бота
            if self.application.updater:
                await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("✅ Бот остановлен")

# ==================== ТОЧКА ВХОДА ====================
async def main():
    """Основная функция"""
    try:
        # Создаем и запускаем бота
        bot = BusinessNavigatorBot()
        await bot.run()
    except Exception as e:
        logger.critical(f"❌ Не удалось запустить бота: {e}")
        sys.exit(1)

if __name__ == '__main__':
    # Запускаем асинхронно
    asyncio.run(main())