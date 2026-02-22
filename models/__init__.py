"""
Модели данных для Business Navigator
"""
from .session import UserSession, SessionStatus, DemographicData, NicheDetails
from .enums import ConversationState, PaymentStatus, NicheCategory, UserRole
from .question_types import QuestionType, QuestionCategory, AnswerValidationRule

__all__ = [
    "UserSession",
    "SessionStatus",
    "DemographicData",
    "NicheDetails",
    "ConversationState",
    "PaymentStatus",
    "NicheCategory",
    "UserRole",
    "QuestionType",
    "QuestionCategory",
    "AnswerValidationRule"
]
