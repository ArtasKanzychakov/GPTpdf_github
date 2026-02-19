#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурационные настройки бота (DEMO версия)
"""
import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional

from models.enums import NicheCategory, NicheDetails

@dataclass
class BotConfig:
    """Конфигурация бота"""
    
    # Токены и ключи
    telegram_token: str = field(default_factory=lambda: os.getenv('TELEGRAM_BOT_TOKEN', ''))
    openai_api_key: str = field(default_factory=lambda: os.getenv('OPENAI_API_KEY', ''))
    
    # Настройки сервера
    host: str = field(default_factory=lambda: os.getenv('HOST', '0.0.0.0'))
    port: int = field(default_factory=lambda: int(os.getenv('PORT', '10000')))
    
    # Настройки OpenAI
    openai_model: str = field(default_factory=lambda: os.getenv('OPENAI_MODEL', 'gpt-4-turbo-preview'))
    openai_temperature: float = field(default_factory=lambda: float(os.getenv('OPENAI_TEMPERATURE', '0.7')))
    openai_max_tokens: int = field(default_factory=lambda: int(os.getenv('OPENAI_MAX_TOKENS', '2000')))
    
    # Настройки бота
    bot_language: str = field(default_factory=lambda: os.getenv('BOT_LANGUAGE', 'ru'))
    cleanup_hours: int = field(default_factory=lambda: int(os.getenv('CLEANUP_HOURS', '24')))
    max_questions: int = field(default_factory=lambda: int(os.getenv('MAX_QUESTIONS', '7')))  # DEMO: 7 вопросов
    
    # Данные вопросов
    questions: List[Dict[str, Any]] = field(default_factory=list)
    question_categories: Dict[str, str] = field(default_factory=dict)
    niche_categories: List[NicheDetails] = field(default_factory=list)
    
    def __post_init__(self):
        """Загрузка вопросов после инициализации"""
        config_dir = Path(__file__).parent
        print("🔄 Загрузка конфигурации бота...")
        
        yaml_path = config_dir / 'questions_v2.yaml'
        
        if yaml_path.exists():
            try:
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    import yaml
                    data = yaml.safe_load(f)
                    self.questions = data if isinstance(data, dict) else []
                    print(f"✅ Загружено {len(self.questions)} вопросов из YAML (DEMO)")
                    self._create_default_niches()
                    return
            except Exception as e:
                print(f"❌ Ошибка загрузки YAML: {e}")
        
        print("⚠️ Создаю минимальный набор вопросов...")
        self._create_minimal_questions()
        self._create_default_niches()
    
    def _create_minimal_questions(self):
        """Создать минимальный набор вопросов для теста"""
        print("📝 Создаю минимальный набор вопросов...")
        self.questions = [
            {"id": "Q1", "text": "👋 Привет! Как тебя зовут?", "type": "text", "category": "start"},
            {"id": "Q2", "text": "📊 Сколько тебе лет?", "type": "text", "category": "demography"},
            {"id": "Q3", "text": "🎯 Что тебя мотивирует?", "type": "text", "category": "personality"}
        ]
        self.question_categories = {"start": "Старт", "demography": "Демография", "personality": "Личность"}
    
    def _create_default_niches(self):
        """Создать стандартные категории ниш"""
        print("🏢 Создаю стандартные категории ниш...")
        
        default_niches = [
            {
                "id": "QUICK_START",
                "name": "Быстрый старт",
                "category": "QUICK_START",
                "description": "Проекты с быстрой окупаемостью",
                "emoji": "🔥",
                "risk_level": 4,
                "time_to_profit": "1-3 месяца",
                "required_skills": ["Маркетинг", "Коммуникация"],
                "min_budget": 50000,
                "success_rate": 0.6,
                "examples": ["Дропшиппинг", "Консультации"]
            },
            {
                "id": "BALANCED",
                "name": "Сбалансированный",
                "category": "BALANCED",
                "description": "Оптимальное соотношение риска и доходности",
                "emoji": "🚀",
                "risk_level": 3,
                "time_to_profit": "3-6 месяцев",
                "required_skills": ["Планирование", "Управление"],
                "min_budget": 150000,
                "success_rate": 0.7,
                "examples": ["Интернет-магазин", "SMM-агентство"]
            }
        ]
        
        self.niche_categories = []
        category_map = {
            "QUICK_START": NicheCategory.QUICK_START,
            "BALANCED": NicheCategory.BALANCED,
            "LONG_TERM": NicheCategory.LONG_TERM,
            "RISKY": NicheCategory.RISKY,
            "HIDDEN": NicheCategory.HIDDEN
        }
        
        for niche_data in default_niches:
            try:
                niche_enum = category_map.get(niche_data['category'])
                if not niche_enum:
                    continue
                niche = NicheDetails(
                    id=niche_data['id'],
                    name=niche_data['name'],
                    category=niche_enum,
                    description=niche_data['description'],
                    emoji=niche_data['emoji'],
                    risk_level=niche_data['risk_level'],
                    time_to_profit=niche_data['time_to_profit'],
                    required_skills=niche_data['required_skills'],
                    min_budget=niche_data['min_budget'],
                    success_rate=niche_data['success_rate'],
                    examples=niche_data['examples']
                )
                self.niche_categories.append(niche)
            except Exception as e:
                print(f"⚠️ Ошибка создания ниши {niche_data.get('id')}: {e}")
        
        print(f"✅ Создано {len(self.niche_categories)} стандартных ниш")
    
    def validate(self) -> bool:
        """Проверка корректности конфигурации"""
        errors = []
        
        if not self.telegram_token:
            errors.append("❌ TELEGRAM_BOT_TOKEN не установлен")
            print("⚠️ ВНИМАНИЕ: Бот не сможет работать без TELEGRAM_BOT_TOKEN!")
        
        if len(self.questions) == 0:
            errors.append("❌ Не загружены вопросы анкеты")
        
        if errors:
            print("❌ Ошибки конфигурации:")
            for error in errors:
                print(f"   {error}")
            return False
        
        print("✅ Конфигурация прошла проверку")
        print(f"   📝 Вопросов: {len(self.questions)}")
        print(f"   🏢 Ниш: {len(self.niche_categories)}")
        print(f"   🤖 OpenAI модель: {self.openai_model}")
        print(f"   🌐 Язык: {self.bot_language}")
        return True
    
    def get_question_by_id(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Получить вопрос по ID"""
        for question in self.questions:
            if str(question.get('id')) == str(question_id):
                return question
        return None
    
    def get_question_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """Получить вопрос по индексу"""
        if 0 <= index < len(self.questions):
            return self.questions[index]
        return None
    
    def get_total_questions(self) -> int:
        """Получить общее количество вопросов"""
        return len(self.questions)

# Создаем глобальный экземпляр конфигурации
print("🚀 Инициализация конфигурации бота...")
try:
    config = BotConfig()
    if config.validate():
        print("✨ Конфигурация готова к работе!")
    else:
        print("⚠️ Конфигурация имеет ошибки, но бот попытается запуститься")
except Exception as e:
    print(f"💥 Критическая ошибка при инициализации конфигурации: {e}")
    import traceback
    traceback.print_exc()
    config = BotConfig()
    config.questions = []
    config.niche_categories = []
    print("⚠️ Создана минимальная конфигурация для запуска")
