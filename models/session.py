"""
Модели данных
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from models.enums import BotState

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
# models/session.py - добавить в конец файла

class NicheDetails(BaseModel):
    """Детали выбранной ниши"""
    title: str
    description: str
    steps: List[str]
    investment: str
    roi: str
    risks: str
    format: str
    why_suitable: str