#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Перечисления для Business Navigator
"""
from enum import Enum


class ConversationState(Enum):
    """Состояния диалога с ботом"""
    START = "start"
    MAIN_MENU = "main_menu"
    DEMO_AGE = "demo_age"
    DEMO_EDUCATION = "demo_education"
    DEMO_CITY = "demo_city"
    PERSONALITY_MOTIVATION = "personality_motivation"
    PERSONALITY_TYPE = "personality_type"
    PERSONALITY_RISK = "personality_risk"
    PERSONALITY_ENERGY = "personality_energy"
    PERSONALITY_FEARS = "personality_fears"
    SKILLS_COGNITIVE = "skills_cognitive"
    PROCESSING = "processing"
    SHOW_ANALYSIS = "show_analysis"
    SHOW_NICHES = "show_niches"
    SELECT_NICHE = "select_niche"
    COMPLETED = "completed"


class PaymentStatus(Enum):
    """Статусы оплаты"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NicheCategory(Enum):
    """Категории ниш"""
    QUICK_START = "quick_start"
    BALANCED = "balanced"
    LONG_TERM = "long_term"
    RISKY = "risky"
    HIDDEN = "hidden"


class UserRole(Enum):
    """Роли пользователей"""
    USER = "user"
    PREMIUM = "premium"
    ADMIN = "admin"
