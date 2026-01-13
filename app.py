#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
БИЗНЕС-НАВИГАТОР v7.0: Глубокий психологический анализ для поиска уникальных ниш
Полная версия с OpenAI, polling и всеми улучшениями
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

import openai
from openai import AsyncOpenAI

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
    FEEDBACK = auto()

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
    LOCAL = "📍 ЛОКАЛЬНЫЙ"
    ONLINE = "🌐 ОНЛАЙН"

# ==================== МОДЕЛИ ДАННЫХ ====================
@dataclass
class EnergyProfile:
    """Энергетический профиль"""
    morning: int = 3  # 1-7
    day: int = 3      # 1-7
    evening: int = 3  # 1-7
    peak_analytical: Optional[str] = None
    peak_creative: Optional[str] = None
    peak_social: Optional[str] = None

@dataclass
class SkillsProfile:
    """Профиль навыков"""
    analytics: int = 3  # 1-5
    communication: int = 3
    design: int = 3
    organization: int = 3
    manual: int = 3
    emotional_iq: int = 3
    superpower: Optional[str] = None
    work_style: Optional[str] = None
    learning_preferences: Dict[str, int] = field(default_factory=dict)

@dataclass
class Demographics:
    """Демографические данные"""
    age_group: Optional[str] = None
    education: Optional[str] = None
    location_type: Optional[str] = None
    location_custom: Optional[str] = None
    location: Optional[str] = None  # Комбинированное
    
    def get_full_location(self):
        """Получить полную локацию"""
        if self.location_custom:
            return self.location_custom
        return self.location_type or "Не указано"

@dataclass
class PersonalityProfile:
    """Профиль личности"""
    motivations: List[str] = field(default_factory=list)
    decision_style: Optional[str] = None
    risk_tolerance: int = 5  # 1-10
    risk_scenario: Optional[str] = None
    energy_profile: EnergyProfile = field(default_factory=EnergyProfile)
    fears_selected: List[str] = field(default_factory=list)
    fear_custom: Optional[str] = None

@dataclass
class ValuesProfile:
    """Ценности и интересы"""
    existential_answer: Optional[str] = None
    flow_experience_type: Optional[str] = None
    flow_experience_desc: Optional[str] = None
    flow_feelings: Optional[str] = None
    ideal_client_age: Optional[str] = None
    ideal_client_field: Optional[str] = None
    ideal_client_pain: Optional[str] = None
    ideal_client_details: Optional[str] = None

@dataclass
class LimitationsProfile:
    """Ограничения и ресурсы"""
    budget: Optional[str] = None
    equipment: List[str] = field(default_factory=list)
    equipment_custom: Optional[str] = None
    knowledge_assets: List[str] = field(default_factory=list)
    time_per_week: Optional[str] = None
    business_scale: Optional[str] = None
    business_format: Optional[str] = None

@dataclass
class BusinessNiche:
    """Бизнес-ниша"""
    id: int
    category: str
    name: str
    description: str
    why_suitable: str
    format: str
    investment_range: str
    roi_timeframe: str
    steps: List[str]
    risks: List[str]
    age_specific: Optional[str] = None
    location_specific: Optional[str] = None
    education_utilization: Optional[str] = None
    
    def to_dict(self):
        return {
            "id": self.id,
            "category": self.category,
            "name": self.name,
            "description": self.description,
            "why_suitable": self.why_suitable,
            "format": self.format,
            "investment_range": self.investment_range,
            "roi_timeframe": self.roi_timeframe,
            "steps": self.steps,
            "risks": self.risks
        }

@dataclass
class DetailedPlan:
    """Детальный план"""
    niche_id: int
    niche_name: str
    psychological_prep: str
    day_by_day_launch: str
    financial_roadmap: str
    success_metrics: str
    common_mistakes: str
    resources: str
    age_adapted: str
    location_adapted: str
    
    def to_dict(self):
        return {
            "niche_id": self.niche_id,
            "niche_name": self.niche_name,
            "psychological_prep": self.psychological_prep,
            "day_by_day_launch": self.day_by_day_launch,
            "financial_roadmap": self.financial_roadmap,
            "success_metrics": self.success_metrics,
            "common_mistakes": self.common_mistakes,
            "resources": self.resources
        }

@dataclass
class PsychologicalAnalysis:
    """Психологический анализ"""
    demographic_insights: str
    personality_profile: str
    hidden_potential: str
    ideal_conditions: str
    age_specific_recommendations: str
    location_opportunities: str
    
    def to_dict(self):
        return {
            "demographic_insights": self.demographic_insights,
            "personality_profile": self.personality_profile,
            "hidden_potential": self.hidden_potential,
            "ideal_conditions": self.ideal_conditions
        }

@dataclass
class UserSession:
    """Сессия пользователя"""
    user_id: int
    chat_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    
    # Данные профиля
    demographics: Demographics = field(default_factory=Demographics)
    personality: PersonalityProfile = field(default_factory=PersonalityProfile)
    skills: SkillsProfile = field(default_factory=SkillsProfile)
    values: ValuesProfile = field(default_factory=ValuesProfile)
    limitations: LimitationsProfile = field(default_factory=LimitationsProfile)
    
    # AI результаты
    psychological_analysis: Optional[PsychologicalAnalysis] = None
    generated_niches: List[BusinessNiche] = field(default_factory=list)
    detailed_plans: Dict[int, DetailedPlan] = field(default_factory=dict)
    
    # Текущее состояние
    current_state: BotState = BotState.START
    current_question: int = 0
    questions_answered: int = 0
    total_questions: int = 23
    start_time: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    # Временные данные
    temp_multiselect: List[str] = field(default_factory=list)
    temp_ratings: Dict[str, int] = field(default_factory=dict)
    temp_learning_prefs: Dict[str, int] = field(default_factory=dict)
    
    def update_activity(self):
        """Обновить время последней активности"""
        self.last_activity = datetime.now()
    
    def get_progress_percentage(self) -> float:
        """Получить процент заполнения"""
        return min((self.questions_answered / self.total_questions) * 100, 100.0)
    
    def get_progress_bar(self) -> str:
        """Получить строку прогресса"""
        percent = self.get_progress_percentage()
        filled = int(percent / 5)  # 20 символов
        bar = "🟩" * filled + "⬜" * (20 - filled)
        return f"{bar} {percent:.1f}%"
    
    def to_openai_profile(self) -> Dict[str, Any]:
        """Конвертировать в формат для OpenAI"""
        return {
            "demographics": {
                "age_group": self.demographics.age_group,
                "education": self.demographics.education,
                "location": self.demographics.get_full_location()
            },
            "personality": {
                "motivations": self.personality.motivations,
                "decision_style": self.personality.decision_style,
                "risk_tolerance": self.personality.risk_tolerance,
                "risk_scenario": self.personality.risk_scenario,
                "energy_profile": {
                    "morning": self.personality.energy_profile.morning,
                    "day": self.personality.energy_profile.day,
                    "evening": self.personality.energy_profile.evening,
                    "peak_analytical": self.personality.energy_profile.peak_analytical,
                    "peak_creative": self.personality.energy_profile.peak_creative,
                    "peak_social": self.personality.energy_profile.peak_social
                },
                "fears": self.personality.fears_selected,
                "fear_custom": self.personality.fear_custom
            },
            "skills": {
                "analytics": self.skills.analytics,
                "communication": self.skills.communication,
                "design": self.skills.design,
                "organization": self.skills.organization,
                "manual": self.skills.manual,
                "emotional_iq": self.skills.emotional_iq,
                "superpower": self.skills.superpower,
                "work_style": self.skills.work_style,
                "learning_preferences": self.skills.learning_preferences
            },
            "values": {
                "existential_answer": self.values.existential_answer,
                "flow_experience": {
                    "type": self.values.flow_experience_type,
                    "description": self.values.flow_experience_desc,
                    "feelings": self.values.flow_feelings
                },
                "ideal_client": {
                    "age": self.values.ideal_client_age,
                    "field": self.values.ideal_client_field,
                    "pain": self.values.ideal_client_pain,
                    "details": self.values.ideal_client_details
                }
            },
            "limitations": {
                "budget": self.limitations.budget,
                "equipment": self.limitations.equipment,
                "knowledge_assets": self.limitations.knowledge_assets,
                "time_per_week": self.limitations.time_per_week,
                "business_scale": self.limitations.business_scale,
                "business_format": self.limitations.business_format
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
    
    def add_usage(self, prompt_tokens: int, completion_tokens: int, cost_usd: float = 0.0):
        """Добавить использование"""
        self.total_tokens += prompt_tokens + completion_tokens
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_requests += 1
        self.successful_requests += 1
        self.estimated_cost_usd += cost_usd
    
    def add_failure(self):
        """Добавить неудачный запрос"""
        self.total_requests += 1
        self.failed_requests += 1
    
    def get_cost_per_request(self) -> float:
        """Средняя стоимость запроса"""
        if self.successful_requests == 0:
            return 0.0
        return self.estimated_cost_usd / self.successful_requests
    
    def get_stats_str(self) -> str:
        """Статистика в строке"""
        success_rate = (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0
        return (
            f"📊 Статистика OpenAI:\n"
            f"• Запросов: {self.total_requests}\n"
            f"• Успешных: {self.successful_requests} ({success_rate:.1f}%)\n"
            f"• Токенов: {self.total_tokens:,}\n"
            f"• Стоимость: ${self.estimated_cost_usd:.4f}\n"
            f"• Средний запрос: ${self.get_cost_per_request():.6f}"
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
            f"🤖 Статистика бота:\n"
            f"• Пользователей: {self.total_users}\n"
            f"• Активных: {self.active_sessions}\n"
            f"• Завершено: {self.completed_profiles}\n"
            f"• Ниш сгенерировано: {self.generated_niches}\n"
            f"• Планов: {self.generated_plans}\n"
            f"• Сообщений: {self.total_messages}\n"
            f"• Работает: {self.get_uptime()}"
        )

class BotDataManager:
    """Менеджер данных бота"""
    
    def __init__(self):
        self.user_sessions: Dict[int, UserSession] = {}
        self.openai_usage = OpenAIUsage()
        self.stats = BotStatistics()
        self.cache_dir = Path("./cache")
        self.cache_dir.mkdir(exist_ok=True)
        
        # Кэш для быстрого доступа
        self.user_cache = {}
        self.last_cleanup = datetime.now()
        
    def get_or_create_session(self, user_id: int, chat_id: int, **kwargs) -> UserSession:
        """Получить или создать сессию"""
        if user_id not in self.user_sessions:
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
        else:
            session = self.user_sessions[user_id]
            session.update_activity()
        
        return session
    
    def save_session(self, user_id: int):
        """Сохранить сессию"""
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            cache_file = self.cache_dir / f"user_{user_id}.json"
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "session": asdict(session),
                        "last_activity": session.last_activity.isoformat()
                    }, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Ошибка сохранения сессии {user_id}: {e}")
    
    def load_session(self, user_id: int) -> Optional[UserSession]:
        """Загрузить сессию"""
        cache_file = self.cache_dir / f"user_{user_id}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Восстанавливаем сессию
                session_data = data["session"]
                session = UserSession(**session_data)
                
                # Восстанавливаем вложенные объекты
                if 'demographics' in session_data:
                    session.demographics = Demographics(**session_data['demographics'])
                if 'personality' in session_data:
                    personality_data = session_data['personality']
                    energy_data = personality_data.get('energy_profile', {})
                    session.personality = PersonalityProfile(
                        motivations=personality_data.get('motivations', []),
                        decision_style=personality_data.get('decision_style'),
                        risk_tolerance=personality_data.get('risk_tolerance', 5),
                        risk_scenario=personality_data.get('risk_scenario'),
                        energy_profile=EnergyProfile(**energy_data),
                        fears_selected=personality_data.get('fears_selected', []),
                        fear_custom=personality_data.get('fear_custom')
                    )
                
                self.user_sessions[user_id] = session
                return session
            except Exception as e:
                logger.error(f"Ошибка загрузки сессии {user_id}: {e}")
        
        return None
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Очистить старые сессии"""
        now = datetime.now()
        if (now - self.last_cleanup).total_seconds() < 3600:  # Раз в час
            return
        
        expired = []
        for user_id, session in self.user_sessions.items():
            if (now - session.last_activity).total_seconds() > max_age_hours * 3600:
                expired.append(user_id)
        
        for user_id in expired:
            self.save_session(user_id)
            del self.user_sessions[user_id]
            self.stats.active_sessions -= 1
        
        if expired:
            logger.info(f"Очищено {len(expired)} неактивных сессий")
        
        self.last_cleanup = now
    
    def mark_profile_completed(self, user_id: int):
        """Пометить профиль как завершенный"""
        if user_id in self.user_sessions:
            self.stats.completed_profiles += 1
            self.save_session(user_id)
    
    def add_generated_niches(self, niches_count: int):
        """Добавить сгенерированные ниши"""
        self.stats.generated_niches += niches_count
    
    def add_generated_plan(self):
        """Добавить сгенерированный план"""
        self.stats.generated_plans += 1
    
    def increment_messages(self):
        """Увеличить счетчик сообщений"""
        self.stats.total_messages += 1

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
        
        # Настройки OpenAI
        self.openai_model = "gpt-3.5-turbo-1106"  # Дешевле и достаточно
        self.openai_max_tokens = 4000
        self.openai_temperature = 0.7
        
        # Лимиты
        self.max_niches_to_generate = 8
        self.max_plans_to_generate = 3
        
        # Время ожидания
        self.question_timeout = 300  # 5 минут
        self.analysis_timeout = 120  # 2 минуты на анализ
        
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
        
        # Эмодзи для прогресса
        self.progress_emojis = ["🔴", "🟠", "🟡", "🟢", "🔵", "🟣", "🟤", "⚫", "⚪"]
        
        logger.info(f"✅ Конфигурация загружена. OpenAI: {'Доступен' if self.openai_api_key else 'Недоступен'}")

# ==================== OPENAI СЕРВИС ====================
class OpenAIService:
    """Сервис для работы с OpenAI"""
    
    def __init__(self, config: BotConfig, data_manager: BotDataManager):
        self.config = config
        self.data_manager = data_manager
        self.client = None
        self.is_available = False
        
        if config.openai_api_key:
            try:
                self.client = AsyncOpenAI(api_key=config.openai_api_key)
                self.is_available = True
                logger.info("✅ OpenAI клиент инициализирован")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации OpenAI: {e}")
                self.is_available = False
        else:
            logger.warning("⚠️ OpenAI API ключ не установлен")
    
    async def _call_openai(self, messages: List[Dict], max_tokens: int = None, temperature: float = None) -> Optional[Dict]:
        """Вызов OpenAI API"""
        if not self.is_available or not self.client:
            logger.warning("OpenAI недоступен")
            return None
        
        try:
            response = await self.client.chat.completions.create(
                model=self.config.openai_model,
                messages=messages,
                max_tokens=max_tokens or self.config.openai_max_tokens,
                temperature=temperature or self.config.openai_temperature,
                timeout=60.0
            )
            
            # Логируем использование
            usage = response.usage
            total_tokens = usage.total_tokens
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            
            # Примерная стоимость (gpt-3.5-turbo)
            # Входные токены: $0.0010 / 1K токенов
            # Выходные токены: $0.0020 / 1K токенов
            cost = (prompt_tokens * 0.001 + completion_tokens * 0.002) / 1000
            
            self.data_manager.openai_usage.add_usage(prompt_tokens, completion_tokens, cost)
            
            logger.info(f"✅ OpenAI: использовано {total_tokens} токенов (стоимость: ${cost:.6f})")
            
            return {
                "content": response.choices[0].message.content,
                "tokens": total_tokens,
                "cost": cost
            }
            
        except Exception as e:
            self.data_manager.openai_usage.add_failure()
            logger.error(f"❌ Ошибка вызова OpenAI: {e}")
            return None
    
    def _create_system_prompt(self, role: str = "business_psychologist") -> str:
        """Создать системный промпт"""
        prompts = {
            "business_psychologist": (
                "Ты - нейропсихолог и бизнес-стратег с 20-летним опытом. "
                "Твоя задача - проводить глубокий психологический анализ и создавать персонализированные бизнес-стратегии. "
                "Будь конкретным, практичным и структурированным в ответах. "
                "Учитывай возраст, образование и локацию пользователя. "
                "Предлагай реалистичные решения с учетом ограничений. "
                "Используй русский язык для ответов."
            ),
            "niche_generator": (
                "Ты - опытный бизнес-аналитик и предприниматель. "
                "Твоя задача - создавать уникальные бизнес-ниши на основе психологического профиля. "
                "Предлагай конкретные, реалистичные идеи с четкими шагами запуска. "
                "Учитывай бюджет, временные ограничения и географию пользователя. "
                "Будь креативным, но практичным. "
                "Используй русский язык для ответов."
            ),
            "plan_creator": (
                "Ты - бизнес-консультант и коуч с опытом запуска 50+ бизнесов. "
                "Твоя задача - создавать гиперперсонализированные бизнес-планы. "
                "Учитывай все особенности пользователя: возраст, страхи, навыки, ограничения. "
                "Создавай детальные пошаговые планы с конкретными действиями и сроками. "
                "Предусматривай риски и способы их минимизации. "
                "Используй русский язык для ответов."
            )
        }
        
        return prompts.get(role, prompts["business_psychologist"])
    
    async def generate_psychological_analysis(self, session: UserSession) -> Optional[PsychologicalAnalysis]:
        """Генерация психологического анализа"""
        logger.info(f"🧠 Генерация психологического анализа для {session.user_id}")
        
        profile = session.to_openai_profile()
        
        prompt = f"""Проведи МНОГОУРОВНЕВЫЙ ПСИХОЛОГИЧЕСКИЙ АНАЛИЗ на основе данных пользователя:

## ДЕМОГРАФИЯ:
• Возраст: {profile['demographics']['age_group']}
• Образование: {profile['demographics']['education']}
• Локация: {profile['demographics']['location']}

## ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ:
• Мотивация: {', '.join(profile['personality']['motivations'])}
• Стиль решений: {profile['personality']['decision_style']}
• Риск: {profile['personality']['risk_tolerance']}/10 ({profile['personality']['risk_scenario']})
• Энергия: Утро={profile['personality']['energy_profile']['morning']}/7, День={profile['personality']['energy_profile']['day']}/7, Вечер={profile['personality']['energy_profile']['evening']}/7
• Пиковая продуктивность: Аналитика={profile['personality']['energy_profile']['peak_analytical']}, Креатив={profile['personality']['energy_profile']['peak_creative']}, Общение={profile['personality']['energy_profile']['peak_social']}
• Страхи: {', '.join(profile['personality']['fears'])} + "{profile['personality']['fear_custom']}"

## НАВЫКИ (1-5):
• Аналитика: {profile['skills']['analytics']}
• Коммуникация: {profile['skills']['communication']}
• Дизайн: {profile['skills']['design']}
• Организация: {profile['skills']['organization']}
• Ручной труд: {profile['skills']['manual']}
• Эмоциональный интеллект: {profile['skills']['emotional_iq']}
• Суперсила: {profile['skills']['superpower']}
• Стиль работы: {profile['skills']['work_style']}

## ЦЕННОСТИ:
• Экзистенциальный ответ: "{profile['values']['existential_answer'][:200]}..."
• Состояние потока: {profile['values']['flow_experience']['type']} - "{profile['values']['flow_experience']['feelings']}"
• Идеальный клиент: {profile['values']['ideal_client']['age']}, {profile['values']['ideal_client']['field']}, боль: {profile['values']['ideal_client']['pain']}

## ОГРАНИЧЕНИЯ:
• Бюджет: {profile['limitations']['budget']}
• Время: {profile['limitations']['time_per_week']}
• Оборудование: {', '.join(profile['limitations']['equipment'])}
• Масштаб: {profile['limitations']['business_scale']}
• Формат: {profile['limitations']['business_format']}

---

## АНАЛИТИЧЕСКОЕ ЗАДАНИЕ:

### 1. ДЕМОГРАФИЧЕСКИЕ ВОЗМОЖНОСТИ
Проанализируй возрастные преимущества и ограничения, использование образования, географические возможности.

### 2. ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ
Опиши основные черты характера, сильные и слабые стороны, когнитивные стили.

### 3. СКРЫТЫЙ ПОТЕНЦИАЛ
Какие неиспользованные комбинации навыков есть? Что человек умеет, но не ценит?

### 4. ИДЕАЛЬНЫЕ УСЛОВИЯ ДЛЯ СТАРТА
Какой формат работы, темп роста, тип клиентов оптимальны?

### 5. ВОЗРАСТНЫЕ ОСОБЕННОСТИ
Какие стратегии подходят для этого возраста?

### 6. ЛОКАЛЬНЫЕ ВОЗМОЖНОСТИ
Какие возможности дает эта локация?

Верни структурированный ответ в формате JSON:
{{
  "demographic_insights": "текст",
  "personality_profile": "текст", 
  "hidden_potential": "текст",
  "ideal_conditions": "текст",
  "age_specific_recommendations": "текст",
  "location_opportunities": "текст"
}}"""

        messages = [
            {"role": "system", "content": self._create_system_prompt("business_psychologist")},
            {"role": "user", "content": prompt}
        ]
        
        response = await self._call_openai(messages, max_tokens=3000, temperature=0.5)
        
        if response:
            try:
                content = response["content"]
                # Пытаемся извлечь JSON
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    analysis_data = json.loads(json_match.group())
                    analysis = PsychologicalAnalysis(**analysis_data)
                    return analysis
                else:
                    # Если не JSON, создаем структурированный анализ
                    analysis = PsychologicalAnalysis(
                        demographic_insights=content[:500],
                        personality_profile=content[500:1000] if len(content) > 500 else "",
                        hidden_potential=content[1000:1500] if len(content) > 1000 else "",
                        ideal_conditions=content[1500:2000] if len(content) > 1500 else "",
                        age_specific_recommendations="",
                        location_opportunities=""
                    )
                    return analysis
            except Exception as e:
                logger.error(f"Ошибка парсинга анализа: {e}")
                return None
        
        return None
    
    async def generate_business_niches(self, session: UserSession, analysis: PsychologicalAnalysis) -> List[BusinessNiche]:
        """Генерация бизнес-ниш"""
        logger.info(f"🎯 Генерация бизнес-ниш для {session.user_id}")
        
        profile = session.to_openai_profile()
        
        prompt = f"""На основе психологического анализа создай 8 КОНКРЕТНЫХ БИЗНЕС-НИШ:

## ПСИХОЛОГИЧЕСКИЙ АНАЛИЗ:
{analysis.personality_profile[:1000]}

## ДЕМОГРАФИЯ:
• Возраст: {profile['demographics']['age_group']}
• Образование: {profile['demographics']['education']} 
• Локация: {profile['demographics']['location']}
• Бюджет: {profile['limitations']['budget']}
• Время: {profile['limitations']['time_per_week']}
• Масштаб: {profile['limitations']['business_scale']}
• Формат: {profile['limitations']['business_format']}

## ТРЕБОВАНИЯ К НИШАМ:

### 1-2. 🔥 БЫСТРЫЙ СТАРТ (первые деньги за 1-2 месяца)
• Минимальные вложения
• Быстрый запуск
• Реальный рынок в локации пользователя

### 3-4. 🚀 СБАЛАНСИРОВАННЫЙ (стабильный доход за 3-6 месяцев)
• Умеренные вложения
• Стабильная клиентская база
• Возможность совмещения с работой

### 5-6. 🌱 ДОЛГОСРОЧНЫЙ (масштабирование за 1-2 года)
• Серьезные перспективы роста
• Высокий потолок доходов
• Возможность создания бренда

### 7. 💎 РИСКОВАННАЯ НИША (высокая маржа, требует смелости)
• Высокий потенциал доходности
• Соответствие уровню риска пользователя ({profile['personality']['risk_tolerance']}/10)
• Четкий план минимизации рисков

### 8. 🎯 СКРЫТАЯ НИША (мало конкурентов, требует экспертизы)
• Использование уникальных навыков пользователя
• Неочевидная монетизация
• Низкая конкуренция

## ФОРМАТ ДЛЯ КАЖДОЙ НИШИ:

НИША [1-8]: [ТИП]
НАЗВАНИЕ: [Краткое название, 3-5 слов]
СУТЬ: [Что конкретно делать, 2-3 предложения]
ПОЧЕМУ ПОДХОДИТ: [Связь с профилем, 1 предложение]
ФОРМАТ: [онлайн/офлайн/гибрид]
ИНВЕСТИЦИИ: [Диапазон в рублях]
СРОК ОКУПАЕМОСТИ: [Реалистичный срок]
РИСКИ: [3 главных риска, через запятую]
ПЕРВЫЕ 3 ШАГА: 
1. [Конкретное действие]
2. [Конкретное действие] 
3. [Конкретное действие]

Верни ТОЛЬКО 8 ниш в этом формате. Каждая ниша начинается с "НИША X:"."""

        messages = [
            {"role": "system", "content": self._create_system_prompt("niche_generator")},
            {"role": "user", "content": prompt}
        ]
        
        response = await self._call_openai(messages, max_tokens=4000, temperature=0.8)
        
        niches = []
        
        if response:
            content = response["content"]
            niches = self._parse_niches_from_text(content, session)
        
        # Если не удалось сгенерировать или мало ниш, добавляем запасные
        if len(niches) < 5:
            niches.extend(self._create_fallback_niches(session))
        
        # Ограничиваем количество
        niches = niches[:self.config.max_niches_to_generate]
        
        self.data_manager.add_generated_niches(len(niches))
        logger.info(f"✅ Сгенерировано {len(niches)} ниш для {session.user_id}")
        
        return niches
    
    def _parse_niches_from_text(self, text: str, session: UserSession) -> List[BusinessNiche]:
        """Парсинг ниш из текста OpenAI"""
        niches = []
        current_niche = {}
        lines = text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('НИША') and ':' in line:
                if current_niche:
                    try:
                        niche = self._create_niche_from_dict(current_niche, len(niches) + 1)
                        if niche:
                            niches.append(niche)
                    except Exception as e:
                        logger.error(f"Ошибка создания ниши: {e}")
                
                current_niche = {}
                parts = line.split(':', 1)
                if len(parts) > 1:
                    current_niche['type'] = parts[1].strip()
            
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
            
            elif line.startswith('РИСКИ:'):
                risks_text = line.replace('РИСКИ:', '').strip()
                current_niche['risks'] = [r.strip() for r in risks_text.split(',')]
            
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
            try:
                niche = self._create_niche_from_dict(current_niche, len(niches) + 1)
                if niche:
                    niches.append(niche)
            except Exception as e:
                logger.error(f"Ошибка создания последней ниши: {e}")
        
        return niches
    
    def _create_niche_from_dict(self, data: Dict, niche_id: int) -> Optional[BusinessNiche]:
        """Создать объект ниши из словаря"""
        try:
            # Определяем категорию по типу
            type_str = data.get('type', '').lower()
            category = NicheCategory.BALANCED.value
            
            if 'быстр' in type_str:
                category = NicheCategory.QUICK_START.value
            elif 'сбаланс' in type_str:
                category = NicheCategory.BALANCED.value
            elif 'долгосроч' in type_str:
                category = NicheCategory.LONG_TERM.value
            elif 'риск' in type_str:
                category = NicheCategory.RISKY.value
            elif 'скрыт' in type_str:
                category = NicheCategory.HIDDEN.value
            
            niche = BusinessNiche(
                id=niche_id,
                category=category,
                name=data.get('name', f'Ниша {niche_id}'),
                description=data.get('description', 'Описание отсутствует'),
                why_suitable=data.get('why', 'Соответствует вашему профилю'),
                format=data.get('format', 'Гибрид'),
                investment_range=data.get('investment', '50,000-100,000₽'),
                roi_timeframe=data.get('roi', '3-6 месяцев'),
                steps=data.get('steps', [
                    'Провести анализ рынка',
                    'Создать MVP',
                    'Найти первых клиентов'
                ]),
                risks=data.get('risks', [
                    'Конкуренция',
                    'Нехватка клиентов',
                    'Сезонность спроса'
                ])
            )
            
            return niche
            
        except Exception as e:
            logger.error(f"Ошибка создания ниши: {e}")
            return None
    
    def _create_fallback_niches(self, session: UserSession) -> List[BusinessNiche]:
        """Создать запасные ниши"""
        location = session.demographics.get_full_location()
        age = session.demographics.age_group or "не указан"
        
        fallback_niches = [
            BusinessNiche(
                id=9991,
                category=NicheCategory.QUICK_START.value,
                name=f"Консультации в {location}",
                description=f"Предоставление профессиональных консультаций в вашей сфере знаний бизнесам в {location}",
                why_suitable="Использует ваши профессиональные навыки и образование",
                format="Гибрид",
                investment_range="10,000-50,000₽",
                roi_timeframe="1-2 месяца",
                steps=[
                    f"Изучить рынок консультационных услуг в {location}",
                    "Создать пакет услуг и ценообразование",
                    "Найти 5 первых клиентов через LinkedIn"
                ],
                risks=["Низкая платежеспособность клиентов", "Сезонность спроса", "Конкуренция"]
            ),
            BusinessNiche(
                id=9992,
                category=NicheCategory.BALANCED.value,
                name="Онлайн-курс по вашей экспертизе",
                description="Создание и продажа онлайн-курсов по вашей профессиональной области",
                why_suitable="Сочетает ваше образование и желание делиться знаниями",
                format="Онлайн",
                investment_range="50,000-150,000₽",
                roi_timeframe="3-4 месяца",
                steps=[
                    "Определить целевую аудиторию и их боли",
                    "Создать программу и контент мини-курса",
                    "Запустить предзаказ через соцсети"
                ],
                risks=["Низкая конверсия", "Высокая конкуренция", "Сложность создания качественного контента"]
            ),
            BusinessNiche(
                id=9993,
                category=NicheCategory.LONG_TERM.value,
                name=f"Автоматизация для бизнеса в {location}",
                description=f"Разработка и внедрение систем автоматизации для малого бизнеса в {location}",
                why_suitable="Использует аналитические навыки и интерес к технологиям",
                format="Гибрид",
                investment_range="100,000-300,000₽",
                roi_timeframe="6-8 месяцев",
                steps=[
                    "Изучить популярные CRM и системы автоматизации",
                    "Разработать 3 пакета услуг для разных сегментов",
                    "Провести 10 пробных консультаций"
                ],
                risks=["Высокий порог входа", "Долгая окупаемость", "Сложность продаж"]
            )
        ]
        
        return fallback_niches
    
    async def generate_detailed_plan(self, session: UserSession, niche: BusinessNiche) -> Optional[DetailedPlan]:
        """Генерация детального плана"""
        logger.info(f"📋 Генерация плана для ниши: {niche.name}")
        
        profile = session.to_openai_profile()
        
        prompt = f"""Создай ГИПЕРПЕРСОНАЛИЗИРОВАННЫЙ БИЗНЕС-ПЛАН для ниши:

## НИША:
{niche.name} ({niche.category})
{niche.description}

## ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:
• Возраст: {profile['demographics']['age_group']}
• Образование: {profile['demographics']['education']}
• Локация: {profile['demographics']['location']}
• Мотивация: {', '.join(profile['personality']['motivations'])}
• Страхи: {', '.join(profile['personality']['fears'])}
• Бюджет: {profile['limitations']['budget']}
• Время: {profile['limitations']['time_per_week']}
• Суперсила: {profile['skills']['superpower']}
• Пик продуктивности: Аналитика={profile['personality']['energy_profile']['peak_analytical']}, Креатив={profile['personality']['energy_profile']['peak_creative']}

## ОСОБЫЕ ТРЕБОВАНИЯ:
1. УЧЕСТЬ ВОЗРАСТ {profile['demographics']['age_group']} - предложить соответствующий темп
2. ИСПОЛЬЗОВАТЬ ОБРАЗОВАНИЕ {profile['demographics']['education']}
3. УЧЕСТЬ ЛОКАЦИЮ {profile['demographics']['location']}
4. ОБОЙТИ СТРАХИ: {', '.join(profile['personality']['fears'])}
5. УЛОЖИТЬСЯ В {profile['limitations']['time_per_week']} ЧАСОВ В НЕДЕЛЮ
6. ИСПОЛЬЗОВАТЬ СУПЕРСИЛУ {profile['skills']['superpower']}

## СТРУКТУРА ПЛАНА:

### 1. ПСИХОЛОГИЧЕСКАЯ ПОДГОТОВКА (день 1-7)
- Ментальная настройка для этой ниши
- Ежедневные ритуалы и привычки
- Техники работы со страхами
- Подготовка окружения

### 2. ПОШАГОВЫЙ ЗАПУСК (30 дней, по дням)
#### Неделя 1: Подготовка (конкретные действия по дням)
#### Неделя 2: Создание активов (сайт, соцсети, материалы)
#### Неделя 3: Первые контакты и тестовые продажи
#### Неделя 4: Анализ результатов и корректировка

### 3. ФИНАНСОВАЯ ДОРОЖНАЯ КАРТА (12 месяцев)
#### Месяц 1-3: Выход в ноль (конкретные цифры доходов/расходов)
#### Месяц 4-6: Доход 50,000₽ в месяц (как достичь, конкретные шаги)
#### Месяц 7-12: Доход 100,000₽ в месяц (стратегия масштабирования)
#### Инвестиции по месяцам (детально)

### 4. МЕТРИКИ УСПЕХА И KPI
- Ежедневные метрики (3 конкретных показателя)
- Еженедельные метрики (3 показателя)
- Ежемесячные метрики (3 показателя)
- Критические точки контроля

### 5. ЧЕК-ЛИСТ ОШИБОК И РЕШЕНИЙ
- Типичные ошибки новичков в этой нише (5-7 ошибок)
- Как распознать их заранее
- Конкретные решения для каждой ошибки
- План Б на случай серьезных проблем

### 6. РЕСУРСЫ ДЛЯ РОСТА И РАЗВИТИЯ
- Книги (конкретные названия, почему подходят)
- Курсы (конкретные, с ссылками если возможно)
- Сообщества и нетворкинг (где искать)
- Инструменты и софт (список с описанием)

Верни ответ в формате JSON:
{{
  "psychological_prep": "текст",
  "day_by_day_launch": "текст",
  "financial_roadmap": "текст",
  "success_metrics": "текст",
  "common_mistakes": "текст",
  "resources": "текст",
  "age_adapted": "как адаптировано под возраст",
  "location_adapted": "как адаптировано под локацию"
}}"""

        messages = [
            {"role": "system", "content": self._create_system_prompt("plan_creator")},
            {"role": "user", "content": prompt}
        ]
        
        response = await self._call_openai(messages, max_tokens=4000, temperature=0.6)
        
        if response:
            try:
                content = response["content"]
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    plan_data = json.loads(json_match.group())
                    plan = DetailedPlan(
                        niche_id=niche.id,
                        niche_name=niche.name,
                        **plan_data
                    )
                    self.data_manager.add_generated_plan()
                    return plan
                else:
                    # Создаем простой план
                    plan = DetailedPlan(
                        niche_id=niche.id,
                        niche_name=niche.name,
                        psychological_prep=content[:800] if len(content) > 800 else content,
                        day_by_day_launch=content[800:1600] if len(content) > 1600 else "",
                        financial_roadmap=content[1600:2400] if len(content) > 2400 else "",
                        success_metrics="Ежедневные: 3 новых контакта\nЕженедельные: 2 сделки\nЕжемесячные: 50,000₽ дохода",
                        common_mistakes="1. Слишком широкий фокус\n2. Недооценка времени\n3. Отсутствие системы",
                        resources="Книги: 'От нуля к единице'\nКурсы: основы маркетинга\nИнструменты: Notion, Canva, Tilda",
                        age_adapted=f"Адаптировано под {profile['demographics']['age_group']}",
                        location_adapted=f"Адаптировано под {profile['demographics']['location']}"
                    )
                    self.data_manager.add_generated_plan()
                    return plan
            except Exception as e:
                logger.error(f"Ошибка парсинга плана: {e}")
                return None
        
        return None

# ==================== UX/UI КОМПОНЕНТЫ ====================
class UXManager:
    """Менеджер пользовательского опыта"""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.progress_emojis = config.progress_emojis
    
    def get_random_praise(self) -> str:
        """Получить случайную фразу похвалы"""
        return random.choice(self.config.praise_phrases)
    
    def get_progress_header(self, session: UserSession) -> str:
        """Получить заголовок с прогрессом"""
        progress_bar = session.get_progress_bar()
        question_num = session.current_question
        
        emoji = self.progress_emojis[min(question_num - 1, len(self.progress_emojis) - 1)]
        
        return f"{emoji} *Вопрос {question_num}/{session.total_questions}*\n{progress_bar}\n"
    
    def format_niche_for_display(self, niche: BusinessNiche, index: int, total: int) -> str:
        """Форматировать нишу для отображения"""
        steps_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(niche.steps[:3])])
        risks_text = "\n".join([f"• {risk}" for risk in niche.risks[:3]])
        
        return f"""🎯 *НИША {index} из {total}*

{niche.category}

*{niche.name}*

📝 *Суть:*
{niche.description}

✅ *Почему вам подходит:*
{niche.why_suitable}

📊 *Детали:*
• Формат: {niche.format}
• Инвестиции: {niche.investment_range}
• Окупаемость: {niche.roi_timeframe}

⚠️ *Основные риски:*
{risks_text}

🚀 *Первые шаги:*
{steps_text}"""
    
    def format_analysis_for_display(self, analysis: PsychologicalAnalysis) -> str:
        """Форматировать анализ для отображения"""
        return f"""🧠 *ПСИХОЛОГИЧЕСКИЙ АНАЛИЗ*

*Демографические возможности:*
{analysis.demographic_insights[:500]}...

*Психологический портрет:*
{analysis.personality_profile[:500]}...

*Скрытый потенциал:*
{analysis.hidden_potential[:500]}...

*Идеальные условия:*
{analysis.ideal_conditions[:500]}..."""
    
    def format_plan_for_display(self, plan: DetailedPlan) -> str:
        """Форматировать план для отображения"""
        return f"""📋 *ДЕТАЛЬНЫЙ БИЗНЕС-ПЛАН*

*{plan.niche_name}*

🧠 *Психологическая подготовка:*
{plan.psychological_prep[:800]}...

🚀 *30-дневный запуск:*
{plan.day_by_day_launch[:800]}...

💰 *Финансовая дорожная карта:*
{plan.financial_roadmap[:800]}...

📊 *Метрики успеха:*
{plan.success_metrics}"""
    
    def create_navigation_keyboard(self, session: UserSession) -> InlineKeyboardMarkup:
        """Создать клавиатуру навигации"""
        keyboard = []
        
        # Навигация по нишам
        if session.generated_niches:
            current_idx = session.current_question - session.total_questions - 1
            if current_idx < 0:
                current_idx = 0
            
            nav_buttons = []
            if current_idx > 0:
                nav_buttons.append(InlineKeyboardButton("◀️ Предыдущая", callback_data=f"niche_prev"))
            
            nav_buttons.append(InlineKeyboardButton(
                f"{current_idx + 1}/{len(session.generated_niches)}", 
                callback_data="niche_current"
            ))
            
            if current_idx < len(session.generated_niches) - 1:
                nav_buttons.append(InlineKeyboardButton("Следующая ▶️", callback_data=f"niche_next"))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            # Кнопки действий для текущей ниши
            if 0 <= current_idx < len(session.generated_niches):
                niche = session.generated_niches[current_idx]
                keyboard.append([
                    InlineKeyboardButton("📋 Полный план", callback_data=f"plan_{niche.id}")
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
        if question_type == QuestionType.BUTTONS and options:
            keyboard = []
            for option in options:
                if isinstance(option, tuple):
                    text, callback_data = option
                    keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])
                else:
                    keyboard.append([InlineKeyboardButton(option, callback_data=option)])
            return InlineKeyboardMarkup(keyboard)
        
        elif question_type == QuestionType.MULTISELECT and options:
            keyboard = []
            for option in options:
                if isinstance(option, tuple):
                    text, callback_data = option
                    keyboard.append([InlineKeyboardButton(f"□ {text}", callback_data=f"select_{callback_data}")])
                else:
                    keyboard.append([InlineKeyboardButton(f"□ {option}", callback_data=f"select_{option}")])
            keyboard.append([InlineKeyboardButton("✅ Завершить выбор", callback_data="multiselect_done")])
            return InlineKeyboardMarkup(keyboard)
        
        elif question_type == QuestionType.SLIDER:
            # Простой слайдер для демонстрации
            keyboard = []
            row = []
            for i in range(1, 6):
                row.append(InlineKeyboardButton(str(i), callback_data=f"slider_{i}"))
            keyboard.append(row)
            keyboard.append([InlineKeyboardButton("✅ Подтвердить", callback_data="slider_confirm")])
            return InlineKeyboardMarkup(keyboard)
        
        return None

# ==================== ВОПРОСНИК ====================
class QuestionnaireManager:
    """Менеджер вопросника"""
    
    def __init__(self, ux_manager: UXManager):
        self.ux = ux_manager
        self.questions = self._load_questions()
    
    def _load_questions(self) -> List[Dict]:
        """Загрузить все вопросы"""
        return [
            # Часть 1: Демография
            {
                "id": 1,
                "text": "🔢 *ВАШ ВОЗРАСТ*\n\nВыберите вашу возрастную группу:",
                "type": QuestionType.BUTTONS,
                "options": [
                    ("18-25 лет", "age_18-25"),
                    ("26-35 лет", "age_26-35"),
                    ("36-45 лет", "age_36-45"),
                    ("46+ лет", "age_46+")
                ],
                "part": "ДЕМОГРАФИЯ",
                "handler": "_handle_age"
            },
            {
                "id": 2,
                "text": "🎓 *ВАШЕ ОБРАЗОВАНИЕ*\n\nВыберите ваш образовательный уровень:",
                "type": QuestionType.BUTTONS,
                "options": [
                    ("Среднее", "edu_school"),
                    ("Среднее специальное", "edu_college"),
                    ("Неоконченное высшее", "edu_incomplete"),
                    ("Высшее (бакалавр)", "edu_bachelor"),
                    ("Высшее (магистр/специалист)", "edu_master"),
                    ("Два и более высших", "edu_multiple"),
                    ("MBA/аспирантура", "edu_mba"),
                    ("Самообразование", "edu_self")
                ],
                "part": "ДЕМОГРАФИЯ",
                "handler": "_handle_education"
            },
            {
                "id": 3,
                "text": "🏙️ *ВАШ ГОРОД/РЕГИОН*\n\nВыберите тип вашего населенного пункта:",
                "type": QuestionType.BUTTONS,
                "options": [
                    ("Москва", "loc_moscow"),
                    ("Санкт-Петербург", "loc_spb"),
                    ("Город-миллионник", "loc_million"),
                    ("Областной центр", "loc_region"),
                    ("Малый город", "loc_small"),
                    ("Село/деревня", "loc_village"),
                    ("Другое (напишу)", "loc_custom")
                ],
                "part": "ДЕМОГРАФИЯ",
                "handler": "_handle_location_type"
            },
            {
                "id": 4,
                "text": "🏙️ *НАЗВАНИЕ ВАШЕГО ГОРОДА/РЕГИОНА*\n\nНапишите название вашего города или региона:",
                "type": QuestionType.TEXT,
                "part": "ДЕМОГРАФИЯ",
                "handler": "_handle_location_custom"
            },
            
            # Часть 2: Личность и мотивация
            {
                "id": 5,
                "text": "🎯 *КЛЮЧЕВАЯ МОТИВАЦИЯ*\n\nЧто для вас ВАЖНЕЕ ВСЕГО в бизнесе?\nВыберите 2-3 самых важных пункта:",
                "type": QuestionType.MULTISELECT,
                "options": [
                    ("Свобода и независимость", "mot_freedom"),
                    ("Стабильный высокий доход", "mot_money"),
                    ("Помощь людям", "mot_help"),
                    ("Творческая реализация", "mot_creative"),
                    ("Решение сложных вызовов", "mot_challenge"),
                    ("Признание, статус", "mot_status"),
                    ("Баланс работы и жизни", "mot_balance"),
                    ("Наследие, долгосрочный проект", "mot_legacy")
                ],
                "part": "ЛИЧНОСТЬ",
                "min_selections": 2,
                "max_selections": 3,
                "handler": "_handle_motivation"
            },
            {
                "id": 6,
                "text": "🧩 *СТИЛЬ ПРИНЯТИЯ РЕШЕНИЙ*\n\n*Ситуация:* Нужно выбрать между двумя проектами.\n\nКакой подход вам ближе?",
                "type": QuestionType.BUTTONS,
                "options": [
                    ("💖 Проект А - нравится интуитивно", "dec_feelings"),
                    ("📊 Проект Б - больше цифр и аналитики", "dec_logic"),
                    ("🤝 Посоветуюсь с близкими/экспертами", "dec_advice"),
                    ("⚖️ Составлю таблицу плюсов/минусов", "dec_table"),
                    ("🎯 Выберу то, что быстрее принесет результат", "dec_fast")
                ],
                "part": "ЛИЧНОСТЬ",
                "handler": "_handle_decision_style"
            },
            {
                "id": 7,
                "text": "🎲 *ОТНОШЕНИЕ К РИСКУ*\n\n*Ситуация:* У вас есть 100,000₽ свободных денег.\n\nНа что готовы их использовать?",
                "type": QuestionType.BUTTONS,
                "options": [
                    ("🔒 Только на проверенные инвестиции", "risk_safe"),
                    ("🎓 На обучение/развитие навыков", "risk_learning"),
                    ("🚀 На запуск своего дела", "risk_business"),
                    ("🎰 На рискованный стартап", "risk_startup")
                ],
                "part": "ЛИЧНОСТЬ",
                "handler": "_handle_risk_scenario"
            },
            {
                "id": 8,
                "text": "🎲 *УРОВЕНЬ РИСКА*\n\nОцените ваш общий уровень толерантности к риску:\n1 - максимальная осторожность, 10 - готов к высоким рискам",
                "type": QuestionType.SLIDER,
                "part": "ЛИЧНОСТЬ",
                "min_value": 1,
                "max_value": 10,
                "default_value": 5,
                "handler": "_handle_risk_level"
            },
            {
                "id": 9,
                "text": "⚡ *ЭНЕРГЕТИЧЕСКИЙ ПРОФИЛЬ*\n\nКак распределяется ваша ЭНЕРГИЯ в течение дня?\n(1 - минимальная энергия, 7 - максимальная)",
                "type": QuestionType.TEXT,
                "part": "ЛИЧНОСТЬ",
                "subquestions": [
                    ("УТРО (6:00-12:00):", "energy_morning"),
                    ("ДЕНЬ (12:00-18:00):", "energy_day"),
                    ("ВЕЧЕР (18:00-24:00):", "energy_evening")
                ],
                "handler": "_handle_energy_profile"
            },
            {
                "id": 10,
                "text": "⚡ *ПИКОВАЯ ПРОДУКТИВНОСТЬ*\n\nКогда вы наиболее продуктивны для разных типов задач?\n\nВыберите для каждого типа:",
                "type": QuestionType.BUTTONS,
                "options": [
                    ("🌅 Утро", "peak_morning"),
                    ("☀️ День", "peak_day"),
                    ("🌙 Вечер", "peak_evening")
                ],
                "part": "ЛИЧНОСТЬ",
                "subquestions": [
                    ("Аналитическая работа", "peak_analytical"),
                    ("Творческая работа", "peak_creative"),
                    ("Общение с людьми", "peak_social")
                ],
                "handler": "_handle_peak_hours"
            },
            {
                "id": 11,
                "text": "👻 *ГЛУБИННЫЕ СТРАХИ*\n\nЧего вы БОЛЬШЕ ВСЕГО БОИТЕСЬ в бизнесе?\nВыберите 1-2 главных страха:",
                "type": QuestionType.MULTISELECT,
                "options": [
                    ("Финансовая нестабильность", "fear_financial"),
                    ("Не справиться технически", "fear_technical"),
                    ("Провал, осуждение близких", "fear_failure"),
                    ("Выгорание, потеря интереса", "fear_burnout"),
                    ("Юридические проблемы", "fear_legal"),
                    ("Не найти клиентов", "fear_clients"),
                    ("Конкуренция", "fear_competition")
                ],
                "part": "ЛИЧНОСТЬ",
                "min_selections": 1,
                "max_selections": 2,
                "handler": "_handle_fears_select"
            },
            {
                "id": 12,
                "text": "👻 *ОПИШИТЕ ВАШ СТРАХ*\n\nА теперь опишите СВОИМИ СЛОВАМИ:\n\"Мой самый большой страх в бизнесе - это...\"",
                "type": QuestionType.TEXT,
                "part": "ЛИЧНОСТЬ",
                "handler": "_handle_fear_custom"
            },
            
            # Часть 3: Навыки
            {
                "id": 13,
                "text": "🧠 *АНАЛИТИЧЕСКИЕ НАВЫКИ*\n\nОцените ваш уровень аналитики и работы с цифрами:\n(1 - начинающий, 5 - эксперт)",
                "type": QuestionType.RATING,
                "part": "НАВЫКИ",
                "skill": "analytics",
                "min_value": 1,
                "max_value": 5,
                "handler": "_handle_skill_rating"
            },
            {
                "id": 14,
                "text": "💬 *КОММУНИКАЦИОННЫЕ НАВЫКИ*\n\nОцените ваши навыки общения и переговоров:",
                "type": QuestionType.RATING,
                "part": "НАВЫКИ",
                "skill": "communication",
                "min_value": 1,
                "max_value": 5,
                "handler": "_handle_skill_rating"
            },
            {
                "id": 15,
                "text": "🎨 *ТВОРЧЕСКИЕ НАВЫКИ*\n\nОцените ваши навыки дизайна и креативности:",
                "type": QuestionType.RATING,
                "part": "НАВЫКИ",
                "skill": "design",
                "min_value": 1,
                "max_value": 5,
                "handler": "_handle_skill_rating"
            },
            {
                "id": 16,
                "text": "📊 *ОРГАНИЗАЦИОННЫЕ НАВЫКИ*\n\nОцените ваши навыки планирования и организации:",
                "type": QuestionType.RATING,
                "part": "НАВЫКИ",
                "skill": "organization",
                "min_value": 1,
                "max_value": 5,
                "handler": "_handle_skill_rating"
            },
            {
                "id": 17,
                "text": "🔧 *НАВЫКИ РУЧНОГО ТРУДА*\n\nОцените ваши навыки работы руками:",
                "type": QuestionType.RATING,
                "part": "НАВЫКИ",
                "skill": "manual",
                "min_value": 1,
                "max_value": 5,
                "handler": "_handle_skill_rating"
            },
            {
                "id": 18,
                "text": "❤️ *ЭМОЦИОНАЛЬНЫЙ ИНТЕЛЛЕКТ*\n\nОцените ваш эмоциональный интеллект:",
                "type": QuestionType.RATING,
                "part": "НАВЫКИ",
                "skill": "emotional_iq",
                "min_value": 1,
                "max_value": 5,
                "handler": "_handle_skill_rating"
            },
            {
                "id": 19,
                "text": "🌟 *ВАША СУПЕРСИЛА*\n\nЕСЛИ БЫ ВЫ БЫЛИ СУПЕРГЕРОЕМ, ваша суперсила была бы:",
                "type": QuestionType.BUTTONS,
                "options": [
                    ("🔮 ПРЕДВИДЕНИЕ - вижу тренды", "power_vision"),
                    ("💬 УБЕЖДЕНИЕ - договариваюсь", "power_persuasion"),
                    ("🔧 ИНЖЕНЕРИЯ - решаю задачи", "power_engineering"),
                    ("🎨 СОЗИДАНИЕ - создаю красивое", "power_creation"),
                    ("👁️ ПРОНИКНОВЕНИЕ - понимаю мотивы", "power_insight"),
                    ("⚡ ЭНЕРГИЯ - работаю на энтузиазме", "power_energy")
                ],
                "part": "НАВЫКИ",
                "handler": "_handle_superpower"
            },
            {
                "id": 20,
                "text": "🔄 *РЕЖИМ РАБОТЫ*\n\nКак вы ЛУЧШЕ ВСЕГО РАБОТАЕТЕ?\nВыберите вашу идеальную рабочую среду:",
                "type": QuestionType.BUTTONS,
                "options": [
                    ("👤 В одиночку", "work_alone"),
                    ("👥 В паре", "work_pair"),
                    ("👨‍👩‍👧‍👦 В команде 3-5 человек", "work_team"),
                    ("🏢 В структуре с ролями", "work_structure"),
                    ("🌐 Удаленно", "work_remote"),
                    ("🤸 Гибко - меняю форматы", "work_flexible")
                ],
                "part": "НАВЫКИ",
                "handler": "_handle_work_style"
            },
            {
                "id": 21,
                "text": "📚 *СТИЛЬ ОБУЧЕНИЯ*\n\nКак вы лучше всего учитесь новому?\nРаспределите 10 баллов между форматами:",
                "type": QuestionType.TEXT,
                "part": "НАВЫКИ",
                "handler": "_handle_learning_style"
            },
            
            # Часть 4: Ценности
            {
                "id": 22,
                "text": "🌍 *ЭКЗИСТЕНЦИАЛЬНЫЙ ВОПРОС*\n\n*Задание на 2 минуты размышления:*\n\n\"Если бы вам не нужно было зарабатывать деньги и все базовые потребности были бы удовлетворены...\"\n\nЧЕМ БЫ ВЫ ЗАНИМАЛИСЬ?\n(опишите подробно, 3-5 предложений)",
                "type": QuestionType.TEXT,
                "part": "ЦЕННОСТИ",
                "handler": "_handle_existential"
            },
            {
                "id": 23,
                "text": "⏳ *СОСТОЯНИЕ ПОТОКА*\n\nВспомните момент, когда вы полностью погружались в дело и теряли чувство времени:\n\nКакое это было дело? Опишите одним предложением.",
                "type": QuestionType.TEXT,
                "part": "ЦЕННОСТИ",
                "handler": "_handle_flow_experience"
            },
            {
                "id": 24,
                "text": "⏳ *ОЩУЩЕНИЯ В ПОТОКЕ*\n\nТеперь опишите свои ОЩУЩЕНИЯ в тот момент:\n\"Я чувствовал(а)...\" (2-3 предложения)",
                "type": QuestionType.TEXT,
                "part": "ЦЕННОСТИ",
                "handler": "_handle_flow_feelings"
            },
            {
                "id": 25,
                "text": "👥 *ИДЕАЛЬНЫЙ КЛИЕНТ*\n\nОпишите человека, с которым вам было бы ИНТЕРЕСНО и ПРИЯТНО работать:\n\nВыберите возрастную группу:",
                "type": QuestionType.BUTTONS,
                "options": [
                    ("20-30 лет", "client_20-30"),
                    ("30-40 лет", "client_30-40"),
                    ("40-50 лет", "client_40-50"),
                    ("50+ лет", "client_50+")
                ],
                "part": "ЦЕННОСТИ",
                "handler": "_handle_client_age"
            },
            {
                "id": 26,
                "text": "👥 *СФЕРА ДЕЯТЕЛЬНОСТИ КЛИЕНТА*\n\nВыберите сферу деятельности вашего идеального клиента:",
                "type": QuestionType.BUTTONS,
                "options": [
                    ("💻 IT/Технологии", "field_it"),
                    ("🎨 Творчество/Дизайн", "field_creative"),
                    ("💼 Бизнес/Предпринимательство", "field_business"),
                    ("📚 Образование", "field_education"),
                    ("🏥 Здоровье/Красота", "field_health"),
                    ("🌿 Другое", "field_other")
                ],
                "part": "ЦЕННОСТИ",
                "handler": "_handle_client_field"
            },
            {
                "id": 27,
                "text": "👥 *ГЛАВНАЯ \"БОЛЬ\" КЛИЕНТА*\n\nКакая главная \"боль\" у вашего идеального клиента?",
                "type": QuestionType.BUTTONS,
                "options": [
                    ("⏰ Не хватает времени", "pain_time"),
                    ("📊 Нет системности", "pain_system"),
                    ("🎓 Нет экспертизы", "pain_expertise"),
                    ("👥 Нет клиентов", "pain_clients"),
                    ("💰 Не хватает денег", "pain_money")
                ],
                "part": "ЦЕННОСТИ",
                "handler": "_handle_client_pain"
            },
            {
                "id": 28,
                "text": "👥 *ДЕТАЛИ О КЛИЕНТЕ*\n\nДобавьте деталей одним-двумя предложениями:\n\"Мне нравится работать с людьми, которые...\"",
                "type": QuestionType.TEXT,
                "part": "ЦЕННОСТИ",
                "handler": "_handle_client_details"
            },
            
            # Часть 5: Ограничения
            {
                "id": 29,
                "text": "🛠️ *РЕСУРСНАЯ КАРТА*\n\nЧто у вас уже есть для старта?\n\n1. ДЕНЬГИ для инвестиций:",
                "type": QuestionType.BUTTONS,
                "options": [
                    ("< 50,000₽", "budget_50k"),
                    ("50,000-200,000₽", "budget_200k"),
                    ("200,000-500,000₽", "budget_500k"),
                    ("> 500,000₽", "budget_more")
                ],
                "part": "ОГРАНИЧЕНИЯ",
                "handler": "_handle_budget"
            },
            {
                "id": 30,
                "text": "🛠️ *ОБОРУДОВАНИЕ*\n\nКакое оборудование у вас уже есть?\n(можно выбрать несколько)",
                "type": QuestionType.MULTISELECT,
                "options": [
                    ("💻 Компьютер/ноутбук", "equip_computer"),
                    ("📷 Камера/фотоаппарат", "equip_camera"),
                    ("🔧 Специнструменты", "equip_tools"),
                    ("🏠 Помещение/мастерская", "equip_space")
                ],
                "part": "ОГРАНИЧЕНИЯ",
                "handler": "_handle_equipment"
            },
            {
                "id": 31,
                "text": "🛠️ *ЗНАНИЯ И ДОСТУП*\n\nКакие нематериальные активы у вас есть?\n(можно выбрать несколько)",
                "type": QuestionType.MULTISELECT,
                "options": [
                    ("🤝 Профессиональные связи", "know_connections"),
                    ("🎓 Уникальная экспертиза", "know_expertise"),
                    ("📊 Доступ к информации", "know_info"),
                    ("🌟 Личный бренд/аудитория", "know_brand")
                ],
                "part": "ОГРАНИЧЕНИЯ",
                "handler": "_handle_knowledge"
            },
            {
                "id": 32,
                "text": "⏰ *ВРЕМЕННОЙ БЮДЖЕТ*\n\nСколько часов в неделю вы реально можете уделить бизнесу на старте?",
                "type": QuestionType.BUTTONS,
                "options": [
                    ("5-10 часов", "time_5-10"),
                    ("10-20 часов", "time_10-20"),
                    ("20-30 часов", "time_20-30"),
                    ("30-40 часов", "time_30-40"),
                    ("40+ часов", "time_40+")
                ],
                "part": "ОГРАНИЧЕНИЯ",
                "handler": "_handle_time"
            },
            {
                "id": 33,
                "text": "📍 *МАСШТАБ БИЗНЕСА*\n\nКакой масштаб бизнеса вас привлекает?",
                "type": QuestionType.BUTTONS,
                "options": [
                    ("📍 Локальный (район/город)", "scale_local"),
                    ("🗺️ Региональный (область)", "scale_region"),
                    ("🇷🇺 Национальный (Россия)", "scale_national"),
                    ("🌍 Международный", "scale_international"),
                    ("🌐 Онлайн-глобальный", "scale_online")
                ],
                "part": "ОГРАНИЧЕНИЯ",
                "handler": "_handle_scale"
            },
            {
                "id": 34,
                "text": "📍 *ФОРМАТ РАБОТЫ*\n\nКакие у вас предпочтения по формату работы?",
                "type": QuestionType.BUTTONS,
                "options": [
                    ("🌐 Только онлайн", "format_online"),
                    ("🏪 Только офлайн", "format_offline"),
                    ("🔄 Гибрид", "format_hybrid")
                ],
                "part": "ОГРАНИЧЕНИЯ",
                "handler": "_handle_format"
            }
        ]
    
    def get_question(self, question_id: int) -> Optional[Dict]:
        """Получить вопрос по ID"""
        for question in self.questions:
            if question["id"] == question_id:
                return question
        return None
    
    def get_next_question(self, current_id: int) -> Optional[Dict]:
        """Получить следующий вопрос"""
        for question in self.questions:
            if question["id"] > current_id:
                return question
        return None
    
    async def ask_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession):
        """Задать следующий вопрос"""
        question = self.get_next_question(session.current_question)
        
        if not question:
            # Вопросы закончились
            await self._finish_questionnaire(update, context, session)
            return
        
        session.current_question = question["id"]
        
        # Формируем текст вопроса
        header = self.ux.get_progress_header(session)
        praise = self.ux.get_random_praise()
        question_text = f"{praise}\n\n{header}{question['text']}"
        
        # Создаем клавиатуру
        reply_markup = None
        if question["type"] != QuestionType.TEXT:
            reply_markup = self.ux.create_question_keyboard(
                question["type"], 
                question.get("options")
            )
        
        # Отправляем вопрос
        if update.callback_query:
            await update.callback_query.edit_message_text(
                question_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                question_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    async def _finish_questionnaire(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession):
        """Завершить вопросник и начать анализ"""
        session.current_state = BotState.ANALYZING
        
        praise = self.ux.get_random_praise()
        
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
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                finish_text,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                finish_text,
                parse_mode='Markdown'
            )
        
        # Сохраняем сессию
        context.bot_data['data_manager'].save_session(session.user_id)
        context.bot_data['data_manager'].mark_profile_completed(session.user_id)
        
        # Запускаем AI анализ
        await self._start_ai_analysis(update, context, session)
    
    async def _start_ai_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession):
        """Запустить AI анализ"""
        openai_service = context.bot_data['openai_service']
        
        # Показываем прогресс
        progress_msg = await context.bot.send_message(
            chat_id=session.chat_id,
            text="🧠 *AI АНАЛИЗ: 1/3 - Психологический профиль*\n\n"
                 "Анализирую ваши ответы...\n"
                 "⏱️ *Примерное время:* 30-45 секунд\n\n"
                 "🔍 *Что анализирую:*\n"
                 "• Личностные характеристики\n"
                 "• Скрытый потенциал\n"
                 "• Идеальные условия для бизнеса",
            parse_mode='Markdown'
        )
        
        try:
            # 1. Генерация психологического анализа
            analysis = await openai_service.generate_psychological_analysis(session)
            
            if analysis:
                session.psychological_analysis = analysis
                
                # Обновляем прогресс
                await progress_msg.edit_text(
                    "🧠 *AI АНАЛИЗ: 2/3 - Поиск бизнес-ниш*\n\n"
                    "Подбираю персонализированные ниши...\n"
                    "⏱️ *Примерное время:* 45-60 секунд\n\n"
                    "🎯 *Что ищу:*\n"
                    "• Быстрый старт (первые деньги за 1-2 месяца)\n"
                    "• Сбалансированные варианты\n"
                    "• Долгосрочные проекты\n"
                    "• Рискованные и скрытые ниши",
                    parse_mode='Markdown'
                )
                
                # 2. Генерация бизнес-ниш
                niches = await openai_service.generate_business_niches(session, analysis)
                session.generated_niches = niches
                
                # 3. Генерация планов для первых 3 ниш
                await progress_msg.edit_text(
                    "🧠 *AI АНАЛИЗ: 3/3 - Детальные планы*\n\n"
                    "Разрабатываю пошаговые стратегии...\n"
                    "⏱️ *Примерное время:* 60-90 секунд\n\n"
                    "📋 *Что создаю:*\n"
                    "• Психологическую подготовку\n"
                    "• 30-дневный план запуска\n"
                    "• Финансовую дорожную карту\n"
                    "• Метрики успеха и ресурсы",
                    parse_mode='Markdown'
                )
                
                # Генерируем планы для первых 3 ниш
                plans_generated = 0
                for i, niche in enumerate(session.generated_niches[:3]):
                    plan = await openai_service.generate_detailed_plan(session, niche)
                    if plan:
                        session.detailed_plans[niche.id] = plan
                        plans_generated += 1
                    
                    # Обновляем прогресс
                    if i < 2:
                        await progress_msg.edit_text(
                            f"🧠 *AI АНАЛИЗ: 3/3 - Детальные планы*\n\n"
                            f"Создаю план {i+1}/3...\n"
                            f"⏱️ *Примерное время:* {(i+1)*30} секунд",
                            parse_mode='Markdown'
                        )
                
                # Удаляем сообщение о прогрессе
                await progress_msg.delete()
                
                # Показываем результат
                stats = context.bot_data['data_manager'].openai_usage
                stats_text = stats.get_stats_str() if stats.total_requests > 0 else ""
                
                result_text = f"""🎉 *АНАЛИЗ ЗАВЕРШЕН!*

✅ Создано: {len(session.generated_niches)} уникальных бизнес-ниш
📊 Психологический портрет: готов
📋 Детальные планы: {plans_generated} шт

{stats_text}

👇 *Выберите первую нишу для изучения:*"""
                
                await context.bot.send_message(
                    chat_id=session.chat_id,
                    text=result_text,
                    parse_mode='Markdown'
                )
                
                session.current_state = BotState.NICHE_SELECTION
                await self._show_first_niche(update, context, session)
                
            else:
                # Ошибка генерации анализа
                await progress_msg.delete()
                await context.bot.send_message(
                    chat_id=session.chat_id,
                    text="❌ *Ошибка генерации анализа*\n\n"
                         "Не удалось сгенерировать психологический анализ. "
                         "Пожалуйста, попробуйте начать заново /start",
                    parse_mode='Markdown'
                )
                session.current_state = BotState.START
                
        except Exception as e:
            logger.error(f"❌ Ошибка AI анализа: {e}")
            await progress_msg.delete()
            
            # Пробуем использовать запасные данные
            await self._use_fallback_data(update, context, session)
    
    async def _use_fallback_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession):
        """Использовать запасные данные"""
        openai_service = context.bot_data['openai_service']
        
        # Создаем запасной анализ
        session.psychological_analysis = PsychologicalAnalysis(
            demographic_insights="Базовый анализ на основе ваших ответов.",
            personality_profile="Практичный подход с творческим потенциалом.",
            hidden_potential="Комбинация аналитических и коммуникативных навыков.",
            ideal_conditions="Гибридный формат работы с умеренным темпом роста.",
            age_specific_recommendations="",
            location_opportunities=""
        )
        
        # Создаем запасные ниши
        session.generated_niches = openai_service._create_fallback_niches(session)
        
        result_text = f"""🎉 *АНАЛИЗ ЗАВЕРШЕН (базовый режим)*

✅ Создано: {len(session.generated_niches)} бизнес-ниш
📊 Использованы стандартные шаблоны
⚠️ AI временно недоступен

👇 *Выберите первую нишу для изучения:*"""
        
        await context.bot.send_message(
            chat_id=session.chat_id,
            text=result_text,
            parse_mode='Markdown'
        )
        
        session.current_state = BotState.NICHE_SELECTION
        await self._show_first_niche(update, context, session)
    
    async def _show_first_niche(self, update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession):
        """Показать первую нишу"""
        if not session.generated_niches:
            await context.bot.send_message(
                chat_id=session.chat_id,
                text="❌ Ниши не сгенерированы. Попробуйте начать заново /start",
                parse_mode='Markdown'
            )
            return
        
        # Сбрасываем индекс для навигации
        session.current_question = len(self.questions) + 1
        
        niche = session.generated_niches[0]
        niche_text = self.ux.format_niche_for_display(niche, 1, len(session.generated_niches))
        
        keyboard = self.ux.create_navigation_keyboard(session)
        
        await context.bot.send_message(
            chat_id=session.chat_id,
            text=niche_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def handle_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           session: UserSession, question_id: int, answer_data: Any):
        """Обработать ответ на вопрос"""
        question = self.get_question(question_id)
        if not question:
            logger.error(f"Вопрос {question_id} не найден")
            return
        
        handler_name = question.get("handler")
        if not handler_name:
            logger.error(f"Хендлер для вопроса {question_id} не указан")
            return
        
        # Вызываем соответствующий обработчик
        handler = getattr(self, handler_name, None)
        if handler:
            await handler(update, context, session, answer_data)
        else:
            logger.error(f"Хендлер {handler_name} не найден")
        
        # Переходим к следующему вопросу
        await self.ask_question(update, context, session)
    
    # Обработчики ответов
    async def _handle_age(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                         session: UserSession, answer_data: str):
        """Обработка возраста"""
        age_map = {
            'age_18-25': '18-25 лет',
            'age_26-35': '26-35 лет',
            'age_36-45': '36-45 лет',
            'age_46+': '46+ лет'
        }
        
        session.demographics.age_group = age_map.get(answer_data, 'Не указано')
        session.questions_answered += 1
    
    async def _handle_education(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                              session: UserSession, answer_data: str):
        """Обработка образования"""
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
        
        session.demographics.education = edu_map.get(answer_data, 'Не указано')
        session.questions_answered += 1
    
    async def _handle_location_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                  session: UserSession, answer_data: str):
        """Обработка типа локации"""
        if answer_data == 'loc_custom':
            # Пользователь напишет сам
            session.current_question = 3  # Остаемся на том же вопросе
            return
        
        loc_map = {
            'loc_moscow': 'Москва',
            'loc_spb': 'Санкт-Петербург',
            'loc_million': 'Город-миллионник',
            'loc_region': 'Областной центр',
            'loc_small': 'Малый город',
            'loc_village': 'Село/деревня'
        }
        
        session.demographics.location_type = loc_map.get(answer_data, 'Не указано')
        session.demographics.location = session.demographics.location_type
        session.questions_answered += 1
    
    async def _handle_location_custom(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                    session: UserSession, answer_data: str):
        """Обработка кастомной локации"""
        session.demographics.location_custom = answer_data
        session.demographics.location = answer_data
        session.questions_answered += 1
    
    async def _handle_motivation(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                               session: UserSession, answer_data: str):
        """Обработка мотивации"""
        if answer_data == 'multiselect_done':
            # Проверяем количество выбранных вариантов
            selected = session.temp_multiselect
            question = self.get_question(session.current_question)
            
            min_sel = question.get('min_selections', 0)
            max_sel = question.get('max_selections', 999)
            
            if min_sel <= len(selected) <= max_sel:
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
                
                session.personality.motivations = [mot_map.get(m, m) for m in selected]
                session.temp_multiselect = []
                session.questions_answered += 1
            else:
                # Сообщаем об ошибке
                if update.callback_query:
                    await update.callback_query.answer(
                        f"❌ Пожалуйста, выберите {min_sel}-{max_sel} вариантов",
                        show_alert=True
                    )
                return
        else:
            # Добавляем или удаляем выбранный вариант
            mot_id = answer_data.replace('select_', '')
            if mot_id in session.temp_multiselect:
                session.temp_multiselect.remove(mot_id)
            else:
                session.temp_multiselect.append(mot_id)
            
            # Обновляем сообщение
            await self._update_multiselect_message(update, session)
    
    async def _update_multiselect_message(self, update: Update, session: UserSession):
        """Обновить сообщение с мультиселектом"""
        question = self.get_question(session.current_question)
        if not question:
            return
        
        header = self.ux.get_progress_header(session)
        praise = self.ux.get_random_praise()
        question_text = f"{praise}\n\n{header}{question['text']}"
        
        # Добавляем информацию о выбранных
        selected_count = len(session.temp_multiselect)
        question_text += f"\n\n✅ Выбрано: {selected_count}"
        
        # Создаем обновленную клавиатуру
        keyboard = []
        for option in question.get('options', []):
            if isinstance(option, tuple):
                text, callback_data = option
                if callback_data in session.temp_multiselect:
                    keyboard.append([InlineKeyboardButton(f"✅ {text}", callback_data=f"select_{callback_data}")])
                else:
                    keyboard.append([InlineKeyboardButton(f"□ {text}", callback_data=f"select_{callback_data}")])
        
        keyboard.append([InlineKeyboardButton("✅ Завершить выбор", callback_data="multiselect_done")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                question_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    async def _handle_decision_style(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   session: UserSession, answer_data: str):
        """Обработка стиля решений"""
        dec_map = {
            'dec_feelings': 'Сначала чувства и эмоции, потом логика',
            'dec_logic': 'Сначала логика и факты, потом чувства',
            'dec_advice': 'Советуюсь с близкими/экспертами',
            'dec_table': 'Составляю таблицу плюсов/минусов',
            'dec_fast': 'Выбираю то, что быстрее принесет результат'
        }
        
        session.personality.decision_style = dec_map.get(answer_data, 'Не указано')
        session.questions_answered += 1
    
    async def _handle_risk_scenario(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                  session: UserSession, answer_data: str):
        """Обработка сценария риска"""
        risk_map = {
            'risk_safe': 'Только на проверенные инвестиции (<10% годовых)',
            'risk_learning': 'На обучение/развитие навыков',
            'risk_business': 'На запуск своего небольшого дела',
            'risk_startup': 'На рискованный, но перспективный стартап'
        }
        
        session.personality.risk_scenario = risk_map.get(answer_data, 'Не указано')
        # Не увеличиваем счетчик - следующий вопрос часть того же
        # session.questions_answered += 1
    
    async def _handle_risk_level(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                               session: UserSession, answer_data: str):
        """Обработка уровня риска"""
        if answer_data.startswith('slider_'):
            if answer_data == 'slider_confirm':
                session.questions_answered += 1
            else:
                try:
                    level = int(answer_data.split('_')[1])
                    session.personality.risk_tolerance = level
                except:
                    pass
        else:
            session.questions_answered += 1
    
    async def _handle_energy_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   session: UserSession, answer_data: str):
        """Обработка энергетического профиля"""
        # Для простоты берем первое число из текста
        import re
        numbers = re.findall(r'\d+', answer_data)
        if len(numbers) >= 3:
            try:
                session.personality.energy_profile.morning = min(7, max(1, int(numbers[0])))
                session.personality.energy_profile.day = min(7, max(1, int(numbers[1])))
                session.personality.energy_profile.evening = min(7, max(1, int(numbers[2])))
                session.questions_answered += 1
            except:
                session.questions_answered += 1
        else:
            session.questions_answered += 1
    
    async def _handle_peak_hours(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                               session: UserSession, answer_data: str):
        """Обработка пиковых часов"""
        # Этот обработчик сложнее, требует контекста
        # Для упрощения пропускаем
        session.questions_answered += 1
    
    async def _handle_fears_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 session: UserSession, answer_data: str):
        """Обработка выбора страхов"""
        if answer_data == 'multiselect_done':
            selected = session.temp_multiselect
            question = self.get_question(session.current_question)
            
            min_sel = question.get('min_selections', 0)
            max_sel = question.get('max_selections', 999)
            
            if min_sel <= len(selected) <= max_sel:
                fear_map = {
                    'fear_financial': 'Финансовая нестабильность',
                    'fear_technical': 'Не справиться технически',
                    'fear_failure': 'Провал, осуждение близких',
                    'fear_burnout': 'Выгорание, потеря интереса',
                    'fear_legal': 'Юридические проблемы',
                    'fear_clients': 'Не найти клиентов',
                    'fear_competition': 'Конкуренция'
                }
                
                session.personality.fears_selected = [fear_map.get(f, f) for f in selected]
                session.temp_multiselect = []
                session.questions_answered += 1
            else:
                if update.callback_query:
                    await update.callback_query.answer(
                        f"❌ Пожалуйста, выберите {min_sel}-{max_sel} вариантов",
                        show_alert=True
                    )
                return
        else:
            fear_id = answer_data.replace('select_', '')
            if fear_id in session.temp_multiselect:
                session.temp_multiselect.remove(fear_id)
            else:
                session.temp_multiselect.append(fear_id)
            
            await self._update_multiselect_message(update, session)
    
    async def _handle_fear_custom(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                session: UserSession, answer_data: str):
        """Обработка кастомного страха"""
        session.personality.fear_custom = answer_data
        session.questions_answered += 1
    
    async def _handle_skill_rating(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 session: UserSession, answer_data: str):
        """Обработка оценки навыка"""
        question = self.get_question(session.current_question)
        skill_name = question.get('skill')
        
        if answer_data.startswith('slider_'):
            if answer_data == 'slider_confirm':
                session.questions_answered += 1
            else:
                try:
                    level = int(answer_data.split('_')[1])
                    if skill_name:
                        setattr(session.skills, skill_name, level)
                except:
                    pass
        else:
            session.questions_answered += 1
    
    async def _handle_superpower(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                               session: UserSession, answer_data: str):
        """Обработка суперсилы"""
        power_map = {
            'power_vision': 'Предвидение трендов и возможностей',
            'power_persuasion': 'Умение убеждать и вдохновлять',
            'power_engineering': 'Решение сложных технических проблем',
            'power_creation': 'Создание красивых и функциональных вещей',
            'power_insight': 'Понимание скрытых мотивов людей',
            'power_energy': 'Могу работать сутками на энтузиазме'
        }
        
        session.skills.superpower = power_map.get(answer_data, 'Не указано')
        session.questions_answered += 1
    
    async def _handle_work_style(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                               session: UserSession, answer_data: str):
        """Обработка стиля работы"""
        work_map = {
            'work_alone': 'В одиночку - полный контроль',
            'work_pair': 'В паре - взаимодополнение',
            'work_team': 'В команде 3-5 человек',
            'work_structure': 'В структуре с четкими ролями',
            'work_remote': 'Удаленно, с периодическими встречами',
            'work_flexible': 'Гибко - меняю форматы под задачи'
        }
        
        session.skills.work_style = work_map.get(answer_data, 'Не указано')
        session.questions_answered += 1
    
    async def _handle_learning_style(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   session: UserSession, answer_data: str):
        """Обработка стиля обучения"""
        # Для простоты сохраняем как текст
        session.skills.learning_preferences['custom'] = answer_data
        session.questions_answered += 1
    
    async def _handle_existential(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                session: UserSession, answer_data: str):
        """Обработка экзистенциального вопроса"""
        session.values.existential_answer = answer_data
        session.questions_answered += 1
    
    async def _handle_flow_experience(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                    session: UserSession, answer_data: str):
        """Обработка опыта потока"""
        session.values.flow_experience_desc = answer_data
        session.questions_answered += 1
    
    async def _handle_flow_feelings(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                  session: UserSession, answer_data: str):
        """Обработка ощущений в потоке"""
        session.values.flow_feelings = answer_data
        session.questions_answered += 1
    
    async def _handle_client_age(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                               session: UserSession, answer_data: str):
        """Обработка возраста клиента"""
        age_map = {
            'client_20-30': '20-30 лет',
            'client_30-40': '30-40 лет',
            'client_40-50': '40-50 лет',
            'client_50+': '50+ лет'
        }
        
        session.values.ideal_client_age = age_map.get(answer_data, 'Не указано')
        session.questions_answered += 1
    
    async def _handle_client_field(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 session: UserSession, answer_data: str):
        """Обработка сферы клиента"""
        field_map = {
            'field_it': 'IT/Технологии',
            'field_creative': 'Творчество/Дизайн',
            'field_business': 'Бизнес/Предпринимательство',
            'field_education': 'Образование',
            'field_health': 'Здоровье/Красота',
            'field_other': 'Другое'
        }
        
        session.values.ideal_client_field = field_map.get(answer_data, 'Не указано')
        session.questions_answered += 1
    
    async def _handle_client_pain(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                session: UserSession, answer_data: str):
        """Обработка боли клиента"""
        pain_map = {
            'pain_time': 'Не хватает времени',
            'pain_system': 'Нет системности',
            'pain_expertise': 'Нет экспертизы',
            'pain_clients': 'Нет клиентов',
            'pain_money': 'Не хватает денег'
        }
        
        session.values.ideal_client_pain = pain_map.get(answer_data, 'Не указано')
        session.questions_answered += 1
    
    async def _handle_client_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   session: UserSession, answer_data: str):
        """Обработка деталей о клиенте"""
        session.values.ideal_client_details = answer_data
        session.questions_answered += 1
    
    async def _handle_budget(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                           session: UserSession, answer_data: str):
        """Обработка бюджета"""
        budget_map = {
            'budget_50k': '< 50,000₽',
            'budget_200k': '50,000-200,000₽',
            'budget_500k': '200,000-500,000₽',
            'budget_more': '> 500,000₽'
        }
        
        session.limitations.budget = budget_map.get(answer_data, 'Не указано')
        session.questions_answered += 1
    
    async def _handle_equipment(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                              session: UserSession, answer_data: str):
        """Обработка оборудования"""
        if answer_data == 'multiselect_done':
            selected = session.temp_multiselect
            equip_map = {
                'equip_computer': 'Компьютер/ноутбук',
                'equip_camera': 'Камера/фотоаппарат',
                'equip_tools': 'Специнструменты',
                'equip_space': 'Помещение/мастерская'
            }
            
            session.limitations.equipment = [equip_map.get(e, e) for e in selected]
            session.temp_multiselect = []
            session.questions_answered += 1
        else:
            equip_id = answer_data.replace('select_', '')
            if equip_id in session.temp_multiselect:
                session.temp_multiselect.remove(equip_id)
            else:
                session.temp_multiselect.append(equip_id)
            
            await self._update_multiselect_message(update, session)
    
    async def _handle_knowledge(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                              session: UserSession, answer_data: str):
        """Обработка знаний"""
        if answer_data == 'multiselect_done':
            selected = session.temp_multiselect
            know_map = {
                'know_connections': 'Профессиональные связи',
                'know_expertise': 'Уникальная экспертиза',
                'know_info': 'Доступ к информации',
                'know_brand': 'Личный бренд/аудитория'
            }
            
            session.limitations.knowledge_assets = [know_map.get(k, k) for k in selected]
            session.temp_multiselect = []
            session.questions_answered += 1
        else:
            know_id = answer_data.replace('select_', '')
            if know_id in session.temp_multiselect:
                session.temp_multiselect.remove(know_id)
            else:
                session.temp_multiselect.append(know_id)
            
            await self._update_multiselect_message(update, session)
    
    async def _handle_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                         session: UserSession, answer_data: str):
        """Обработка времени"""
        time_map = {
            'time_5-10': '5-10 часов (параллельно с работой)',
            'time_10-20': '10-20 часов (серьезный side-project)',
            'time_20-30': '20-30 часов (почти полный день)',
            'time_30-40': '30-40 часов (можно погрузиться)',
            'time_40+': '40+ часов (готов(а) работать сутками)'
        }
        
        session.limitations.time_per_week = time_map.get(answer_data, 'Не указано')
        session.questions_answered += 1
    
    async def _handle_scale(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                          session: UserSession, answer_data: str):
        """Обработка масштаба"""
        scale_map = {
            'scale_local': 'Локальный (район/город)',
            'scale_region': 'Региональный (область)',
            'scale_national': 'Национальный (Россия)',
            'scale_international': 'Международный',
            'scale_online': 'Онлайн-глобальный'
        }
        
        session.limitations.business_scale = scale_map.get(answer_data, 'Не указано')
        session.questions_answered += 1
    
    async def _handle_format(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                           session: UserSession, answer_data: str):
        """Обработка формата"""
        format_map = {
            'format_online': 'Только онлайн',
            'format_offline': 'Только офлайн',
            'format_hybrid': 'Гибрид (онлайн + офлайн)'
        }
        
        session.limitations.business_format = format_map.get(answer_data, 'Не указано')
        session.questions_answered += 1

# ==================== ОСНОВНОЙ КЛАСС БОТА ====================
class BusinessNavigatorBot:
    """Основной класс бота"""
    
    def __init__(self):
        self.config = BotConfig()
        self.data_manager = BotDataManager()
        self.ux_manager = UXManager(self.config)
        self.questionnaire = QuestionnaireManager(self.ux_manager)
        self.openai_service = OpenAIService(self.config, self.data_manager)
        
        # Инициализация приложения Telegram
        self.application = Application.builder() \
            .token(self.config.telegram_token) \
            .persistence(PicklePersistence(filepath="bot_data.pickle")) \
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
        self.application.add_handler(CallbackQueryHandler(self.handle_callback_query, pattern=None))
        
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
        session.start_time = datetime.now()
        session.update_activity()
        
        # Приветственное сообщение
        ai_status = "✅ (AI-режим)" if self.openai_service.is_available else "⚠️ (Базовый режим)"
        
        welcome_text = f"""👋 *Добро пожаловать в Бизнес-Навигатор v7.0!* {ai_status}

🎯 *Что вас ждет:*
• 34 вопроса для глубокого анализа личности
• Психологический портрет от AI
• 8 персонализированных бизнес-ниш
• Детальные пошаговые планы

📊 *Статистика бота:*
{self.data_manager.stats.get_stats_str()}

{self.data_manager.openai_usage.get_stats_str() if self.data_manager.openai_usage.total_requests > 0 else ''}

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
        context.bot_data['questionnaire'] = self.questionnaire
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
1. Заполните анкету (34 вопроса)
2. AI анализирует ваш профиль
3. Получите 8 персонализированных бизнес-ниш
4. Выберите нишу для детального плана

*Советы:*
• Будьте честны в ответах
• Не торопитесь, обдумайте каждый вопрос
• Отвечайте максимально подробно
• Используйте все возможности AI-анализа

*Техническая поддержка:*
Если возникли проблемы, попробуйте:
1. Перезапустить бота /restart
2. Проверить подключение к интернету
3. Подождать несколько минут"""
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /stats"""
        stats_text = f"""📊 *СТАТИСТИКА БОТА*

{self.data_manager.stats.get_stats_str()}

{self.data_manager.openai_usage.get_stats_str() if self.data_manager.openai_usage.total_requests > 0 else ''}

*Активные сессии:* {len(self.data_manager.user_sessions)}
*Кэшировано сессий:* {len(list(self.data_manager.cache_dir.glob('user_*.json')))}"""
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    
    async def restart_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /restart"""
        user_id = update.effective_user.id
        
        if user_id in self.data_manager.user_sessions:
            # Сохраняем старую сессию
            self.data_manager.save_session(user_id)
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
        
        # Получаем или создаем сессию
        session = self.data_manager.get_or_create_session(
            user_id=user_id,
            chat_id=query.message.chat_id,
            username=query.from_user.username,
            first_name=query.from_user.first_name,
            last_name=query.from_user.last_name
        )
        
        # Обрабатываем callback
        if callback_data == 'start_questionnaire':
            await self._start_questionnaire(query, session)
        
        elif callback_data.startswith('niche_'):
            await self._handle_niche_navigation(query, context, session, callback_data)
        
        elif callback_data.startswith('plan_'):
            await self._handle_plan_request(query, context, session, callback_data)
        
        elif callback_data == 'show_analysis':
            await self._show_analysis(query, context, session)
        
        elif callback_data == 'save_all':
            await self._save_all_data(query, context, session)
        
        elif callback_data == 'start_over':
            await self._start_over(query, context, session)
        
        elif callback_data == 'show_stats':
            await self._show_stats(query, context)
        
        else:
            # Обработка ответов на вопросы
            await self._handle_question_answer(query, context, session, callback_data)
    
    async def _start_questionnaire(self, query, session):
        """Начать вопросник"""
        session.current_state = BotState.DEMOGRAPHY
        session.current_question = 0
        session.questions_answered = 0
        
        await self.questionnaire.ask_question(None, query, session)
    
    async def _handle_niche_navigation(self, query, context, session, callback_data):
        """Навигация по нишам"""
        if not session.generated_niches:
            await query.answer("❌ Ниши не сгенерированы", show_alert=True)
            return
        
        current_idx = session.current_question - len(self.questionnaire.questions) - 1
        if current_idx < 0:
            current_idx = 0
        
        if callback_data == 'niche_prev' and current_idx > 0:
            current_idx -= 1
        elif callback_data == 'niche_next' and current_idx < len(session.generated_niches) - 1:
            current_idx += 1
        
        session.current_question = len(self.questionnaire.questions) + current_idx + 1
        
        niche = session.generated_niches[current_idx]
        niche_text = self.ux_manager.format_niche_for_display(
            niche, current_idx + 1, len(session.generated_niches)
        )
        
        keyboard = self.ux_manager.create_navigation_keyboard(session)
        
        await query.edit_message_text(
            niche_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def _handle_plan_request(self, query, context, session, callback_data):
        """Запрос детального плана"""
        try:
            niche_id = int(callback_data.split('_')[1])
            
            if niche_id in session.detailed_plans:
                plan = session.detailed_plans[niche_id]
                plan_text = self.ux_manager.format_plan_for_display(plan)
                
                keyboard = [[
                    InlineKeyboardButton("◀️ Назад к нишам", callback_data="back_to_niches"),
                    InlineKeyboardButton("💾 Сохранить план", callback_data=f"save_plan_{niche_id}")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    plan_text[:4000],  # Ограничение Telegram
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
                # Если план длинный, отправляем остальное
                if len(plan_text) > 4000:
                    remaining = plan_text[4000:]
                    parts = [remaining[i:i+4000] for i in range(0, len(remaining), 4000)]
                    for part in parts:
                        await context.bot.send_message(
                            chat_id=session.chat_id,
                            text=part,
                            parse_mode='Markdown'
                        )
            else:
                await query.answer("❌ План для этой ниши еще не сгенерирован", show_alert=True)
                
        except Exception as e:
            logger.error(f"Ошибка показа плана: {e}")
            await query.answer("❌ Ошибка загрузки плана", show_alert=True)
    
    async def _show_analysis(self, query, context, session):
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
        else:
            await query.answer("❌ Анализ не сгенерирован", show_alert=True)
    
    async def _save_all_data(self, query, context, session):
        """Сохранить все данные"""
        await query.answer("💾 Сохраняю все данные...", show_alert=True)
        
        # Сохраняем сессию
        self.data_manager.save_session(session.user_id)
        
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
    
    async def _start_over(self, query, context, session):
        """Начать заново"""
        # Сохраняем текущую сессию
        self.data_manager.save_session(session.user_id)
        
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

{self.data_manager.openai_usage.get_stats_str() if self.data_manager.openai_usage.total_requests > 0 else ''}"""
        
        await query.edit_message_text(stats_text, parse_mode='Markdown')
    
    async def _handle_question_answer(self, query, context, session, callback_data):
        """Обработка ответа на вопрос"""
        await self.questionnaire.handle_answer(
            query, context, session, session.current_question, callback_data
        )
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        # Получаем сессию
        session = self.data_manager.get_or_create_session(
            user_id=user_id,
            chat_id=update.message.chat_id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name
        )
        
        # Увеличиваем счетчик сообщений
        self.data_manager.increment_messages()
        
        # Обрабатываем текстовый ответ
        await self.questionnaire.handle_answer(
            update, context, session, session.current_question, message_text
        )
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"Ошибка: {context.error}", exc_info=context.error)
        
        try:
            # Пытаемся отправить сообщение об ошибке
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
        # Сохраняем менеджеры в application.bot_data
        self.application.bot_data['data_manager'] = self.data_manager
        self.application.bot_data['openai_service'] = self.openai_service
        self.application.bot_data['questionnaire'] = self.questionnaire
        self.application.bot_data['ux_manager'] = self.ux_manager
        
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
                
                # Логируем статистику каждые 10 минут
                if datetime.now().minute % 10 == 0:
                    logger.info(f"📊 Статистика: {self.data_manager.stats.get_stats_str()}")
                
                await asyncio.sleep(300)  # 5 минут
                
        except KeyboardInterrupt:
            logger.info("⏹ Остановка бота...")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
        finally:
            # Сохраняем все сессии
            for user_id in list(self.data_manager.user_sessions.keys()):
                self.data_manager.save_session(user_id)
            
            # Останавливаем бота
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