"""
Типы вопросов для анкеты Business Navigator v7.0
"""
from enum import Enum


class QuestionType(Enum):
    """Типы вопросов в анкете"""
    
    # Простые типы
    TEXT = "text"  # Текстовый ответ
    CHOICE = "choice"  # Одиночный выбор (кнопки)
    MULTIPLE_CHOICE = "multiple_choice"  # Множественный выбор
    
    # Интерактивные типы (новые)
    QUICK_BUTTONS = "quick_buttons"  # Быстрые кнопки (Q1, Q2, Q3)
    MULTI_SELECT = "multi_select"  # Мультиселект с лимитом
    SCENARIO_TEST = "scenario_test"  # Интерактивный сценарий (Q5)
    SLIDER_WITH_SCENARIO = "slider_with_scenario"  # Сценарий + ползунок (Q6)
    ENERGY_DISTRIBUTION = "energy_distribution"  # 3 ползунка (Q7)
    SKILL_RATING = "skill_rating"  # Рейтинг по звездам (Q9)
    SUPERHERO_METAPHOR = "superhero_metaphor"  # Метафорический выбор (Q10)
    LEARNING_ALLOCATION = "learning_allocation"  # Распределение баллов (Q12)
    EXISTENTIAL_TEXT = "existential_text"  # Развернутый ответ (Q13)
    FLOW_EXPERIENCE = "flow_experience"  # Пример + описание (Q14)
    CLIENT_PORTRAIT = "client_portrait"  # Портрет клиента (Q15)


class QuestionCategory(Enum):
    """Категории вопросов"""
    DEMOGRAPHIC = "demographic"  # Q1-Q3
    PERSONALITY = "personality"  # Q4-Q8
    SKILLS = "skills"  # Q9-Q12
    VALUES = "values"  # Q13-Q15
    RESOURCES = "resources"  # Q16-Q18


class AnswerValidationRule(Enum):
    """Правила валидации ответов"""
    REQUIRED = "required"
    MIN_LENGTH = "min_length"
    MAX_LENGTH = "max_length"
    MIN_CHOICES = "min_choices"
    MAX_CHOICES = "max_choices"
    RANGE = "range"  # Для чисел/слайдеров
    SUM_EQUALS = "sum_equals"  # Для распределения баллов