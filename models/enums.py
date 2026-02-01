"""
Перечисления для Business Navigator
"""
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional


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


@dataclass
class NicheDetails:
    """Детальная информация о бизнес-нише"""
    id: str
    name: str
    category: NicheCategory
    description: str
    emoji: str = "💼"
    risk_level: int = 3  # 1-5
    time_to_profit: str = "3-6 месяцев"
    required_skills: List[str] = None
    min_budget: int = 0
    success_rate: float = 0.5
    examples: List[str] = None
    
    def __post_init__(self):
        """Инициализация после создания"""
        if self.required_skills is None:
            self.required_skills = []
        if self.examples is None:
            self.examples = []
        
        # Конвертируем category в enum если это строка
        if isinstance(self.category, str):
            self.category = NicheCategory(self.category)
    
    @property
    def full_description(self) -> str:
        """Полное описание ниши"""
        risk_stars = "★" * self.risk_level + "☆" * (5 - self.risk_level)
        
        text = f"{self.emoji} *{self.name}*\n"
        text += f"📊 Категория: {self.category.value}\n"
        text += f"📝 {self.description}\n\n"
        text += f"⏱️ Срок выхода на прибыль: {self.time_to_profit}\n"
        text += f"🎯 Уровень риска: {risk_stars} ({self.risk_level}/5)\n"
        
        if self.min_budget > 0:
            text += f"💰 Мин. бюджет: {self.min_budget:,.0f} руб\n"
        
        if self.success_rate > 0:
            text += f"📈 Шанс успеха: {self.success_rate*100:.0f}%\n"
        
        if self.required_skills:
            text += f"\n🔧 Требуемые навыки:\n"
            for skill in self.required_skills[:3]:
                text += f"• {skill}\n"
        
        if self.examples:
            text += f"\n💡 Примеры:\n"
            for example in self.examples[:2]:
                text += f"• {example}\n"
        
        return text
    
    def to_dict(self):
        """Конвертация в словарь"""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "emoji": self.emoji,
            "risk_level": self.risk_level,
            "time_to_profit": self.time_to_profit,
            "required_skills": self.required_skills,
            "min_budget": self.min_budget,
            "success_rate": self.success_rate,
            "examples": self.examples
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Создание из словаря"""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            category=data.get("category", "balanced"),
            description=data.get("description", ""),
            emoji=data.get("emoji", "💼"),
            risk_level=data.get("risk_level", 3),
            time_to_profit=data.get("time_to_profit", "3-6 месяцев"),
            required_skills=data.get("required_skills", []),
            min_budget=data.get("min_budget", 0),
            success_rate=data.get("success_rate", 0.5),
            examples=data.get("examples", [])
        )
