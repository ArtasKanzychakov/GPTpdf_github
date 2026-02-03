from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime


class SessionStatus(str, Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ANALYSIS_GENERATED = "analysis_generated"
    ERROR = "error"


class ConversationState(str, Enum):
    START = "start"
    QUESTIONNAIRE = "questionnaire"
    ANALYSIS = "analysis"
    RESULT = "result"
    FINISHED = "finished"


@dataclass
class NavigationStep:
    question_id: int
    category: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class NicheDetails:
    niche_id: str
    name: str
    description: str
    score: float
    advantages: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    psychological_profile: str
    strengths: List[str]
    weaknesses: List[str]
    motivations: List[str]
    constraints: List[str]
    raw_response: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class UserSession:
    user_id: int

    # lifecycle
    status: SessionStatus = SessionStatus.NEW
    state: ConversationState = ConversationState.START

    # questionnaire progress
    current_question: int = 0
    current_category: Optional[str] = None

    # answers & temp data
    answers: Dict[int, Any] = field(default_factory=dict)
    temp_data: Dict[str, Any] = field(default_factory=dict)

    # navigation
    navigation_stack: List[NavigationStep] = field(default_factory=list)

    # analysis & result
    psychological_analysis: Optional[AnalysisResult] = None
    niches: List[NicheDetails] = field(default_factory=list)

    # meta
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # -------------------------
    # lifecycle helpers
    # -------------------------
    def touch(self) -> None:
        self.updated_at = datetime.utcnow()

    def start(self) -> None:
        self.status = SessionStatus.IN_PROGRESS
        self.state = ConversationState.QUESTIONNAIRE
        self.touch()

    def complete_questionnaire(self) -> None:
        self.state = ConversationState.ANALYSIS
        self.touch()

    def mark_analysis_generated(self) -> None:
        self.status = SessionStatus.ANALYSIS_GENERATED
        self.state = ConversationState.RESULT
        self.touch()

    def finish(self) -> None:
        self.status = SessionStatus.COMPLETED
        self.state = ConversationState.FINISHED
        self.touch()

    # -------------------------
    # answers
    # -------------------------
    def save_answer(self, question_id: int, answer: Any) -> None:
        self.answers[question_id] = answer
        self.current_question = question_id
        self.touch()

    def get_answer(self, question_id: int) -> Any:
        return self.answers.get(question_id)

    # -------------------------
    # navigation
    # -------------------------
    def add_to_navigation(self, question_id: int, category: Optional[str] = None) -> None:
        self.navigation_stack.append(
            NavigationStep(
                question_id=question_id,
                category=category or self.current_category,
            )
        )
        self.touch()

    def can_go_back(self) -> bool:
        return len(self.navigation_stack) > 0

    def go_back(self) -> Optional[NavigationStep]:
        if not self.navigation_stack:
            return None
        step = self.navigation_stack.pop()
        self.current_question = step.question_id
        self.current_category = step.category
        self.touch()
        return step

    # -------------------------
    # analysis
    # -------------------------
    def set_analysis(self, analysis: AnalysisResult) -> None:
        self.psychological_analysis = analysis
        self.mark_analysis_generated()

    def add_niche(self, niche: NicheDetails) -> None:
        self.niches.append(niche)
        self.touch()

    def clear_niches(self) -> None:
        self.niches.clear()
        self.touch()

    # -------------------------
    # serialization helpers
    # -------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "status": self.status.value,
            "state": self.state.value,
            "current_question": self.current_question,
            "current_category": self.current_category,
            "answers": self.answers,
            "temp_data": self.temp_data,
            "analysis": self.psychological_analysis.psychological_profile
            if self.psychological_analysis
            else None,
            "niches": [n.__dict__ for n in self.niches],
        }