"""
Перечисления для Business Navigator
"""
from enum import Enum


class ConversationState(Enum):
    """Состояния диалога с ботом"""
    # Начальные состояния
    START = "start"
    MAIN_MENU = "main_menu"
    
    # Демография (Q1-Q3)
    DEMO_AGE = "demo_age"
    DEMO_EDUCATION = "demo_education"
    DEMO_CITY = "demo_city"
    
    # Личность и мотивация (Q4-Q8)
    PERSONALITY_MOTIVATION = "personality_motivation"
    PERSONALITY_TYPE = "personality_type"
    PERSONALITY_RISK = "personality_risk"
    PERSONALITY_ENERGY = "personality_energy"
    PERSONALITY_FEARS = "personality_fears"
    
    # Способности и навыки (Q9-Q12)
    SKILLS_COGNITIVE = "skills_cognitive"
    SKILLS_SUPERPOWER = "skills_superpower"
    SKILLS_WORK_MODE = "skills_work_mode"
    SKILLS_LEARNING = "skills_learning"
    
    # Ценности и интересы (Q13-Q15)
    VALUES_EXISTENTIAL = "values_existential"
    VALUES_FLOW = "values_flow"
    VALUES_CLIENT = "values_client"
    
    # Практические ограничения (Q16-Q18)
    RESOURCES_MAP = "resources_map"
    RESOURCES_TIME = "resources_time"
    RESOURCES_GEOGRAPHY = "resources_geography"
    
    # Анализ и результаты
    PROCESSING = "processing"
    SHOW_ANALYSIS = "show_analysis"
    SHOW_NICHES = "show_niches"
    SELECT_NICHE = "select_niche"
    SHOW_PLAN = "show_plan"
    
    # Оплата
    PAYMENT = "payment"
    WAITING_PAYMENT = "waiting_payment"
    
    # Завершение
    COMPLETED = "completed"
    FEEDBACK = "feedback"


class PaymentStatus(Enum):
    """Статусы оплаты"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NicheCategory(Enum):
    """Категории ниш"""
    QUICK_START = "quick_start"  # Быстрый старт (1-2 месяца)
    BALANCED = "balanced"  # Баланс (3-6 месяцев)
    LONG_TERM = "long_term"  # Долгосрок (1-2 года)
    RISKY = "risky"  # Рискованная ниша
    HIDDEN = "hidden"  # Скрытая ниша


class UserRole(Enum):
    """Роли пользователей"""
    USER = "user"
    PREMIUM = "premium"
    ADMIN = "admin"