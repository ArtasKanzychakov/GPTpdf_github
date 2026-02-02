"""Модели данных"""
from .enums import (
    ConversationState,
    BotState,  # ← ДОБАВЬ ЭТО
    PaymentStatus,
    NicheCategory,
    UserRole,
    NicheDetails
)
from .session import UserSession, SessionStatus, DemographicData

__all__ = [
    'ConversationState',
    'BotState',  # ← И ЭТО
    'PaymentStatus',
    'NicheCategory',
    'UserRole',
    'NicheDetails',
    'UserSession',
    'SessionStatus',
    'DemographicData'
]
