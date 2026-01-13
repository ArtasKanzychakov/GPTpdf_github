"""
Enum классы
"""
from enum import Enum, auto

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