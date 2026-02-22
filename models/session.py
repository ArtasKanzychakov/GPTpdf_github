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
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass
class UserSession:
    """Сессия пользователя"""
    user_id: int
    status: SessionStatus = SessionStatus.STARTED
    current_question: int = 1
    current_category: str = "start"
    answers: Dict[str, Any] = field(default_factory=dict)
    temp_data: Dict[str, Any] = field(default_factory=dict)
    navigation_history: List[tuple] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def update_timestamp(self):
        """Обновить временную метку"""
        self.updated_at = datetime.now()
    
    def add_answer(self, question_id: str, answer: Any):
        """Добавить ответ на вопрос"""
        self.answers[question_id] = answer
        self.update_timestamp()
    
    def add_to_navigation(self, category: str, question_num: int):
        """Добавить в историю навигации"""
        self.navigation_history.append((category, question_num))
        if len(self.navigation_history) > 20:
            self.navigation_history = self.navigation_history[-20:]
    
    def go_back(self) -> Optional[tuple]:
        """Вернуться на предыдущий вопрос"""
        if len(self.navigation_history) > 1:
            self.navigation_history.pop()
            return self.navigation_history[-1]
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь"""
        return {
            "user_id": self.user_id,
            "status": self.status.value,
            "current_question": self.current_question,
            "answers": self.answers,
            "temp_data": self.temp_data,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserSession":
        """Создать из словаря"""
        session = cls(
            user_id=data["user_id"],
            status=SessionStatus(data.get("status", "started")),
            current_question=data.get("current_question", 1),
            answers=data.get("answers", {}),
            temp_data=data.get("temp_data", {}),
        )
        if "created_at" in data:
            session.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            session.updated_at = datetime.fromisoformat(data["updated_at"])
        return session
