#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enum классы
"""
from enum import Enum, auto
from dataclasses import dataclass

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

# Дополнительный dataclass для деталей ниши (если нужно)
@dataclass
class NicheDetails:
    """Детальная информация о нише"""
    id: str
    name: str
    category: NicheCategory
    description: str = ""
    emoji: str = "📊"
    risk_level: int = 3  # 1-5
    time_to_profit: str = ""  # "1-3 месяца", "6-12 месяцев"
    
    def __str__(self):
        return f"{self.emoji} {self.name} ({self.category.value})"