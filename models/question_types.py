"""
Типы вопросов для анкеты Business Navigator v7.0
"""
from enum import Enum

class QuestionType(Enum):
    """Типы вопросов в анкете"""
    # Простые типы
    TEXT = "text"
    CHOICE = "choice"
    MULTIPLE_CHOICE = "multiple_choice"
    
    # Интерактивные типы (новые)
    QUICK_BUTTONS = "quick_buttons"
    MULTI_SELECT = "multi_select"
    SCENARIO_TEST = "scenario_test"
    SLIDER_WITH_SCENARIO = "slider_with_scenario"
    ENERGY_DISTRIBUTION = "energy_distribution"
    SKILL_RATING = "skill_rating"
    SUPERHERO_METAPHOR = "superhero_metaphor"
    LEARNING_ALLOCATION = "learning_allocation"
    EXISTENTIAL_TEXT = "existential_text"
    FLOW_EXPERIENCE = "flow_experience"
    CLIENT_PORTRAIT = "client_portrait"

class QuestionCategory(Enum):
    """Категории вопросов"""
    DEMOGRAPHIC = "demographic"
    PERSONALITY = "personality"
    SKILLS = "skills"
    VALUES = "values"
    RESOURCES = "resources"

class AnswerValidationRule(Enum):
    """Правила валидации ответов"""
    REQUIRED = "required"
    MIN_LENGTH = "min_length"
    MAX_LENGTH = "max_length"
    MIN_CHOICES = "min_choices"
    MAX_CHOICES = "max_choices"
    RANGE = "range"
    SUM_EQUALS = "sum_equals"
