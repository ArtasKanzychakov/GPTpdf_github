from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime

from models.analysis import AnalysisResult


@dataclass
class UserSession:
    user_id: int
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Все ответы пользователя (ID вопроса -> ответ)
    answers: Dict[str, Any] = field(default_factory=dict)

    # Текущий вопрос анкеты
    current_question_id: Optional[int] = None

    # Финальный результат анализа
    analysis_result: Optional[AnalysisResult] = None

    def add_answer(self, question_id: str, answer: Any) -> None:
        self.answers[question_id] = answer

    def get_answer(self, question_id: str) -> Any:
        return self.answers.get(question_id)

    def get_all_answers(self) -> Dict[str, Any]:
        return self.answers