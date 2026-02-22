"""
Модели данных для Business Navigator
"""
from .session import UserSession, SessionStatus, DemographicData
from .enums import ConversationState, PaymentStatus, NicheCategory, UserRole
from .question_types import QuestionType, QuestionCategory, AnswerValidationRule

__all__ = [
    "UserSession",
    "SessionStatus", 
    "DemographicData",
    "ConversationState",
    "PaymentStatus",
    "NicheCategory",
    "UserRole",
    "QuestionType",
    "QuestionCategory",
    "AnswerValidationRule"
]
