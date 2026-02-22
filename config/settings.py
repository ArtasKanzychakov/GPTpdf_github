#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурационные настройки бота - DEMO VERSION
"""
import os
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class BotConfig:
    """Конфигурация бота"""
    telegram_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "10000")))
    demo_mode: bool = field(default_factory=lambda: os.getenv("DEMO_MODE", "true").lower() == "true")
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"))
    openai_temperature: float = 0.7
    openai_max_tokens: int = 1000
    bot_language: str = "ru"
    max_questions: int = 10

    questions: List[Dict[str, Any]] = field(default_factory=list)
    question_categories: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        print("🔄 Загрузка конфигурации бота (DEMO MODE)...")
        self._create_demo_questions()
        print(f"✅ Загружено {len(self.questions)} демонстрационных вопросов")

    def _create_demo_questions(self):
        self.questions = [
            {
                "id": "Q1",
                "text": "👋 Привет! Давайте познакомимся.\nКак вас зовут?",
                "type": "text",
                "category": "start",
                "validation": {"min_length": 2, "max_length": 50, "required": True}
            },
            {
                "id": "Q2",
                "text": "📊 Выберите ваш возраст:",
                "type": "quick_buttons",
                "category": "demographic",
                "options": [
                    {"value": "18-25", "label": "18-25 лет", "emoji": "🎓"},
                    {"value": "26-35", "label": "26-35 лет", "emoji": "💼"},
                    {"value": "36-45", "label": "36-45 лет", "emoji": "🏆"},
                    {"value": "46+", "label": "46+ лет", "emoji": "🎯"}
                ]
            },
            {
                "id": "Q3",
                "text": "🎯 Выберите сферы интересов (можно несколько):",
                "type": "multi_select",
                "category": "interests",
                "validation": {"min_choices": 1, "max_choices": 3},
                "options": [
                    {"value": "tech", "label": "Технологии", "emoji": "💻"},
                    {"value": "creative", "label": "Творчество", "emoji": "🎨"},
                    {"value": "business", "label": "Бизнес", "emoji": "💰"},
                    {"value": "education", "label": "Образование", "emoji": "📚"},
                    {"value": "health", "label": "Здоровье", "emoji": "💪"}
                ]
            },
            {
                "id": "Q4",
                "text": "⚡ Оцените ваш уровень энергии в течение дня:",
                "type": "energy_distribution",
                "category": "energy",
                "time_periods": [
                    {"period": "morning", "label": "🌅 Утро", "emoji": "🌅", "min": 1, "max": 7},
                    {"period": "day", "label": "☀️ День", "emoji": "☀️", "min": 1, "max": 7},
                    {"period": "evening", "label": "🌙 Вечер", "emoji": "🌙", "min": 1, "max": 7}
                ]
            },
            {
                "id": "Q5",
                "text": "💪 Оцените ваши навыки (1-5 звёзд):",
                "type": "skill_rating",
                "category": "skills",
                "rating_scale": {"max": 5, "star_emoji": "⭐", "empty_emoji": "☆"},
                "skills": [
                    {"id": "communication", "label": "Коммуникация", "emoji": "💬"},
                    {"id": "analytics", "label": "Аналитика", "emoji": "📈"},
                    {"id": "creativity", "label": "Креатив", "emoji": "🎨"},
                    {"id": "organization", "label": "Организация", "emoji": "📋"}
                ]
            },
            {
                "id": "Q6",
                "text": "📈 Распределите 10 баллов между форматами работы:",
                "type": "learning_allocation",
                "category": "work_style",
                "total_points": 10,
                "formats": [
                    {"id": "online", "label": "Онлайн", "emoji": "🌐"},
                    {"id": "offline", "label": "Офлайн", "emoji": "🏢"},
                    {"id": "hybrid", "label": "Гибрид", "emoji": "🔄"}
                ],
                "validation": {"sum_equals": 10}
            },
            {
                "id": "Q7",
                "text": "🎚️ Какой уровень риска вам комфортен?",
                "type": "slider_with_scenario",
                "category": "risk",
                "slider": {"min": 1, "max": 10, "label": "Уровень риска"},
                "options": [
                    {"value": "conservative", "label": "🐢 Консервативный (минимум риска)"},
                    {"value": "balanced", "label": "⚖️ Сбалансированный (средний риск)"},
                    {"value": "aggressive", "label": "🚀 Агрессивный (высокий риск)"}
                ]
            },
            {
                "id": "Q8",
                "text": "💎 Что для вас важнее всего в проекте?",
                "type": "scenario_test",
                "category": "values",
                "options": [
                    {"value": "money", "label": "💰 Высокий доход", "description": "Финансовая свобода и прибыль"},
                    {"value": "freedom", "label": "🕊️ Свобода времени", "description": "Гибкий график и независимость"},
                    {"value": "impact", "label": "🌍 Влияние на мир", "description": "Польза для общества"},
                    {"value": "growth", "label": "📈 Личный рост", "description": "Развитие навыков и опыта"}
                ]
            },
            {
                "id": "Q9",
                "text": "📝 Напишите коротко о вашей мечте (необязательно):",
                "type": "existential_text",
                "category": "dream",
                "text_input": {"prompt": "Расскажите о вашей мечте:", "min_length": 0, "max_length": 500},
                "validation": {"required": False}
            },
            {
                "id": "Q10",
                "text": "✅ Проверьте ваши ответы и подтвердите завершение:",
                "type": "confirmation",
                "category": "finish"
            }
        ]
        self.question_categories = {
            "start": "👋 Знакомство",
            "demographic": "📊 О вас",
            "interests": "🎯 Интересы",
            "energy": "⚡ Энергия",
            "skills": "💪 Навыки",
            "work_style": "💼 Стиль работы",
            "risk": "🎚️ Риск",
            "values": "💎 Ценности",
            "dream": "📝 Мечта",
            "finish": "✅ Завершение"
        }

    def get_question_by_id(self, question_id: str) -> Optional[Dict[str, Any]]:
        for question in self.questions:
            if question.get("id") == question_id:
                return question
        return None

    def get_total_questions(self) -> int:
        return len(self.questions)


config = BotConfig()
