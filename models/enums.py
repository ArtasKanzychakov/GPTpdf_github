"""
Перечисления для Business Navigator
"""
from enum import Enum


class ConversationState(Enum):
    """Состояния диалога с ботом"""
    START = "start"
    MAIN_MENU = "main_menu"
    
    # Демо вопросы (Q1-Q10)
    DEMO_AGE = "demo_age"
    DEMO_EDUCATION = "demo_education"
    DEMO_CITY = "demo_city"
    PERSONALITY_MOTIVATION = "personality_motivation"
    PERSONALITY_TYPE = "personality_type"
    PERSONALITY_RISK = "personality_risk"
    PERSONALITY_ENERGY = "personality_energy"
    PERSONALITY_FEARS = "personality_fears"
    SKILLS_COGNITIVE = "skills_cognitive"
    
    # Анализ и результаты
    PROCESSING = "processing"
    SHOW_ANALYSIS = "show_analysis"
    SHOW_NICHES = "show_niches"
    SELECT_NICHE = "select_niche"
    
    # Завершение
    COMPLETED = "completed"
