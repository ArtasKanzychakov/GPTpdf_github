"""
Модели данных для сессий пользователей
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum


class SessionStatus(Enum):
    """Статусы сессии"""
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    QUESTIONNAIRE_COMPLETED = "questionnaire_completed"
    ANALYSIS_GENERATED = "analysis_generated"
    NICHE_SELECTED = "niche_selected"
    PLAN_GENERATED = "plan_generated"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass
class DemographicData:
    """Демографические данные пользователя"""
    age_group: Optional[str] = None  # "18-25", "26-35", etc.
    education: Optional[str] = None
    city: Optional[str] = None
    region_type: Optional[str] = None  # "moscow", "spb", "million", etc.


@dataclass
class UserSession:
    """Сессия пользователя"""
    user_id: int
    status: SessionStatus = SessionStatus.STARTED
    current_question: int = 1
    current_category: str = "demographic"
    
    # Расширенное хранилище ответов (теперь поддерживает любые типы)
    answers: Dict[str, Any] = field(default_factory=dict)
    
    # Демографические данные отдельно для быстрого доступа
    demographic_data: DemographicData = field(default_factory=DemographicData)
    
    # Временные данные для многошаговых вопросов
    temp_data: Dict[str, Any] = field(default_factory=dict)
    
    # История навигации (для кнопки "Назад")
    navigation_history: List[tuple] = field(default_factory=list)  # [(category, question_num)]
    
    # Результаты анализа
    psychological_analysis: Optional[str] = None
    generated_niches: Optional[List[Dict[str, Any]]] = None
    selected_niche: Optional[str] = None
    detailed_plan: Optional[str] = None
    
    # Метаданные
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    # Оплата
    payment_id: Optional[str] = None
    is_paid: bool = False
    
    def update_timestamp(self):
        """Обновить временную метку"""
        self.updated_at = datetime.now()
    
    def add_answer(self, question_id: str, answer: Any):
        """
        Добавить ответ на вопрос
        
        Args:
            question_id: ID вопроса (например, "Q1", "Q4", "Q7")
            answer: Ответ (может быть str, int, list, dict)
        """
        self.answers[question_id] = answer
        self.update_timestamp()
        
        # Обновляем демографические данные если это Q1-Q3
        if question_id == "Q1":
            self.demographic_data.age_group = answer
        elif question_id == "Q2":
            self.demographic_data.education = answer
        elif question_id == "Q3":
            if isinstance(answer, dict):
                self.demographic_data.city = answer.get("city")
                self.demographic_data.region_type = answer.get("region_type")
            else:
                self.demographic_data.city = answer
    
    def get_answer(self, question_id: str, default: Any = None) -> Any:
        """Получить ответ на вопрос"""
        return self.answers.get(question_id, default)
    
    def add_to_navigation(self, category: str, question_num: int):
        """Добавить в историю навигации"""
        self.navigation_history.append((category, question_num))
        if len(self.navigation_history) > 20:  # Храним только последние 20 шагов
            self.navigation_history = self.navigation_history[-20:]
    
    def go_back(self) -> Optional[tuple]:
        """
        Вернуться на предыдущий вопрос
        
        Returns:
            Tuple (category, question_num) или None
        """
        if len(self.navigation_history) > 1:
            self.navigation_history.pop()  # Удаляем текущий
            return self.navigation_history[-1]  # Возвращаем предыдущий
        return None
    
    def get_completion_percentage(self) -> float:
        """Получить процент заполнения анкеты"""
        total_questions = 18
        answered = len(self.answers)
        return (answered / total_questions) * 100
    
    def is_questionnaire_complete(self) -> bool:
        """Проверить, завершена ли анкета"""
        return len(self.answers) >= 18
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь для сериализации"""
        return {
            "user_id": self.user_id,
            "status": self.status.value,
            "current_question": self.current_question,
            "current_category": self.current_category,
            "answers": self.answers,
            "demographic_data": {
                "age_group": self.demographic_data.age_group,
                "education": self.demographic_data.education,
                "city": self.demographic_data.city,
                "region_type": self.demographic_data.region_type,
            },
            "temp_data": self.temp_data,
            "navigation_history": self.navigation_history,
            "psychological_analysis": self.psychological_analysis,
            "generated_niches": self.generated_niches,
            "selected_niche": self.selected_niche,
            "detailed_plan": self.detailed_plan,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "payment_id": self.payment_id,
            "is_paid": self.is_paid,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserSession":
        """Создать из словаря"""
        demo_data = data.get("demographic_data", {})
        
        session = cls(
            user_id=data["user_id"],
            status=SessionStatus(data.get("status", "started")),
            current_question=data.get("current_question", 1),
            current_category=data.get("current_category", "demographic"),
            answers=data.get("answers", {}),
            demographic_data=DemographicData(
                age_group=demo_data.get("age_group"),
                education=demo_data.get("education"),
                city=demo_data.get("city"),
                region_type=demo_data.get("region_type"),
            ),
            temp_data=data.get("temp_data", {}),
            navigation_history=data.get("navigation_history", []),
            psychological_analysis=data.get("psychological_analysis"),
            generated_niches=data.get("generated_niches"),
            selected_niche=data.get("selected_niche"),
            detailed_plan=data.get("detailed_plan"),
            payment_id=data.get("payment_id"),
            is_paid=data.get("is_paid", False),
        )
        
        # Восстанавливаем временные метки
        if "created_at" in data:
            session.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            session.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("completed_at"):
            session.completed_at = datetime.fromisoformat(data["completed_at"])
        
        return session