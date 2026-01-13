#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enum классы
"""
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Optional

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

@dataclass
class NicheDetails:
    """Детальная информация о нише"""
    id: str
    name: str
    category: NicheCategory  # Это Enum
    description: str = ""
    emoji: str = "📊"
    risk_level: int = 3  # 1-5
    time_to_profit: str = ""  # "1-3 месяца", "6-12 месяцев"
    required_skills: List[str] = field(default_factory=list)
    min_budget: float = 0
    success_rate: float = 0.5
    examples: List[str] = field(default_factory=list)
    
    def __str__(self):
        return f"{self.emoji} {self.name} ({self.category.value})"
    
    @property
    def full_description(self) -> str:
        """Полное описание ниши"""
        desc = f"{self.emoji} *{self.name}*\n"
        desc += f"📊 Категория: {self.category.value}\n"
        
        if self.description:
            desc += f"📝 {self.description}\n\n"
        
        if self.time_to_profit:
            desc += f"⏱️ Срок выхода на прибыль: {self.time_to_profit}\n"
        
        risk_stars = "★" * self.risk_level + "☆" * (5 - self.risk_level)
        desc += f"🎯 Уровень риска: {risk_stars} ({self.risk_level}/5)\n"
        
        if self.min_budget > 0:
            desc += f"💰 Мин. бюджет: {self.min_budget:,.0f} руб\n"
        
        if self.success_rate > 0:
            desc += f"📈 Шанс успеха: {self.success_rate*100:.0f}%\n"
        
        if self.required_skills:
            desc += f"\n🔧 Требуемые навыки:\n"
            for skill in self.required_skills[:3]:
                desc += f"• {skill}\n"
            if len(self.required_skills) > 3:
                desc += f"• ... и ещё {len(self.required_skills) - 3}\n"
        
        if self.examples:
            desc += f"\n💡 Примеры бизнесов:\n"
            for example in self.examples[:2]:
                desc += f"• {example}\n"
            if len(self.examples) > 2:
                desc += f"• ... и ещё {len(self.examples) - 2}\n"
        
        return desc
    
    def to_dict(self) -> dict:
        """Конвертация в словарь для JSON"""
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category.name,
            'category_display': self.category.value,
            'description': self.description,
            'emoji': self.emoji,
            'risk_level': self.risk_level,
            'time_to_profit': self.time_to_profit,
            'required_skills': self.required_skills,
            'min_budget': self.min_budget,
            'success_rate': self.success_rate,
            'examples': self.examples
        }

# Дополнительные перечисления для аналитики
class AnalysisDepth(Enum):
    """Глубина анализа"""
    SURFACE = "поверхностный"
    STANDARD = "стандартный"
    DEEP = "глубокий"
    PROFESSIONAL = "профессиональный"

class PriorityLevel(Enum):
    """Уровень приоритета"""
    LOW = "низкий"
    MEDIUM = "средний"
    HIGH = "высокий"
    CRITICAL = "критический"