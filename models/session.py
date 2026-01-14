#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модели данных для бота
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import json

from models.enums import BotState, QuestionType, NicheCategory, NicheDetails

@dataclass
class UserSession:
    """Сессия пользователя для бизнес-навигатора (35 вопросов)"""
    
    # Основные данные пользователя
    user_id: int
    username: str = ""
    full_name: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Текущее состояние опроса
    current_state: BotState = BotState.START
    current_question_index: int = 0
    is_completed: bool = False
    completion_date: Optional[datetime] = None
    
    # === ОТВЕТЫ НА 35 ВОПРОСОВ (по частям из YAML) ===
    
    # Часть 1: Демография (3 вопроса)
    age_group: str = ""  # q1
    education: str = ""  # q2
    location_type: str = ""  # q3
    location_custom: str = ""  # q3_custom
    
    # Часть 2: Личность (8 вопросов + подвопросы)
    motivations: List[str] = field(default_factory=list)  # q4
    decision_style: str = ""  # q5
    risk_scenario: str = ""  # q6
    risk_tolerance: int = 0  # q7
    energy_profile: str = ""  # q8 - "3 5 2"
    peak_analytical: str = ""  # q9
    peak_creative: str = ""  # q10
    peak_social: str = ""  # q11
    fears_selected: List[str] = field(default_factory=list)  # q12
    fear_custom: str = ""  # q13
    
    # Часть 3: Навыки (8 вопросов)
    analytical_skills: int = 0  # q14
    communication_skills: int = 0  # q15
    design_skills: int = 0  # q16
    organizational_skills: int = 0  # q17
    manual_skills: int = 0  # q18
    emotional_iq: int = 0  # q19
    superpower: str = ""  # q20
    work_style: str = ""  # q21
    learning_style: str = ""  # q22
    
    # Часть 4: Ценности (8 вопросов + подвопросы)
    existential_answer: str = ""  # q23
    flow_experience: str = ""  # q24
    flow_feelings: str = ""  # q25
    ideal_client_age: str = ""  # q26
    ideal_client_field: str = ""  # q27
    ideal_client_pain: str = ""  # q28
    ideal_client_details: str = ""  # q29
    
    # Часть 5: Ограничения (7 вопросов)
    budget: str = ""  # q30
    equipment: List[str] = field(default_factory=list)  # q31
    knowledge_assets: List[str] = field(default_factory=list)  # q32
    time_per_week: str = ""  # q33
    business_scale: str = ""  # q34
    business_format: str = ""  # q35
    
    # Результаты анализа
    analysis_result: str = ""
    suggested_niches: List[NicheDetails] = field(default_factory=list)
    selected_niche: Optional[NicheDetails] = None
    detailed_plan: str = ""
    
    # Технические метрики
    messages_sent: int = 0
    last_interaction: datetime = field(default_factory=datetime.now)
    
    def update_timestamp(self):
        """Обновить время последнего обновления"""
        self.updated_at = datetime.now()
        self.last_interaction = datetime.now()
        self.messages_sent += 1
    
    def get_progress_percentage(self) -> float:
        """Получить процент заполнения анкеты"""
        total_questions = 35  # В YAML версии
        if total_questions == 0:
            return 0.0
        return (self.current_question_index / total_questions) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать сессию в словарь"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'full_name': self.full_name,
            'current_state': self.current_state.name,
            'current_question_index': self.current_question_index,
            'progress_percentage': self.get_progress_percentage(),
            'is_completed': self.is_completed,
            'answers': self.get_all_answers(),
            'suggested_niches_count': len(self.suggested_niches),
            'has_selected_niche': self.selected_niche is not None
        }
    
    def get_all_answers(self) -> Dict[str, Any]:
        """Получить все ответы в структурированном виде"""
        return {
            'demographics': {
                'age_group': self.age_group,
                'education': self.education,
                'location': self.location_custom or self.location_type
            },
            'personality': {
                'motivations': self.motivations,
                'decision_style': self.decision_style,
                'risk_tolerance': self.risk_tolerance,
                'risk_scenario': self.risk_scenario,
                'energy_profile': {
                    'morning': self._get_energy_part(0),
                    'day': self._get_energy_part(1),
                    'evening': self._get_energy_part(2),
                    'peak_analytical': self.peak_analytical,
                    'peak_creative': self.peak_creative,
                    'peak_social': self.peak_social
                },
                'fears': self.fears_selected,
                'fear_custom': self.fear_custom
            },
            'skills': {
                'analytics': self.analytical_skills,
                'communication': self.communication_skills,
                'design': self.design_skills,
                'organization': self.organizational_skills,
                'manual': self.manual_skills,
                'emotional_iq': self.emotional_iq,
                'superpower': self.superpower,
                'work_style': self.work_style,
                'learning_style': self.learning_style
            },
            'values': {
                'existential_answer': self.existential_answer,
                'flow_experience': self.flow_experience,
                'flow_feelings': self.flow_feelings,
                'ideal_client': {
                    'age': self.ideal_client_age,
                    'field': self.ideal_client_field,
                    'pain': self.ideal_client_pain,
                    'details': self.ideal_client_details
                }
            },
            'limitations': {
                'budget': self.budget,
                'equipment': self.equipment,
                'knowledge_assets': self.knowledge_assets,
                'time_per_week': self.time_per_week,
                'business_scale': self.business_scale,
                'business_format': self.business_format
            }
        }
    
    def _get_energy_part(self, index: int) -> int:
        """Получить часть энергетического профиля"""
        if not self.energy_profile:
            return 0
        parts = self.energy_profile.split()
        if index < len(parts):
            try:
                return int(parts[index])
            except:
                return 0
        return 0
    
    def is_answer_complete(self, question_id: int) -> bool:
        """Проверить, заполнен ли ответ на вопрос"""
        # Маппинг вопросов на поля (упрощенно)
        field_map = {
            1: lambda: bool(self.age_group),
            2: lambda: bool(self.education),
            3: lambda: bool(self.location_type),
            4: lambda: bool(self.motivations),
            5: lambda: bool(self.decision_style),
            6: lambda: bool(self.risk_scenario),
            7: lambda: self.risk_tolerance > 0,
            8: lambda: bool(self.energy_profile),
            9: lambda: bool(self.peak_analytical),
            10: lambda: bool(self.peak_creative),
            11: lambda: bool(self.peak_social),
            12: lambda: bool(self.fears_selected),
            13: lambda: bool(self.fear_custom),
            14: lambda: self.analytical_skills > 0,
            15: lambda: self.communication_skills > 0,
            16: lambda: self.design_skills > 0,
            17: lambda: self.organizational_skills > 0,
            18: lambda: self.manual_skills > 0,
            19: lambda: self.emotional_iq > 0,
            20: lambda: bool(self.superpower),
            21: lambda: bool(self.work_style),
            22: lambda: bool(self.learning_style),
            23: lambda: bool(self.existential_answer),
            24: lambda: bool(self.flow_experience),
            25: lambda: bool(self.flow_feelings),
            26: lambda: bool(self.ideal_client_age),
            27: lambda: bool(self.ideal_client_field),
            28: lambda: bool(self.ideal_client_pain),
            29: lambda: bool(self.ideal_client_details),
            30: lambda: bool(self.budget),
            31: lambda: bool(self.equipment),
            32: lambda: bool(self.knowledge_assets),
            33: lambda: bool(self.time_per_week),
            34: lambda: bool(self.business_scale),
            35: lambda: bool(self.business_format)
        }
        
        if question_id in field_map:
            return field_map[question_id]()
        return False
    
    def save_answer(self, question_id: int, answer: Any) -> bool:
        """Сохранить ответ на вопрос"""
        try:
            # Маппинг ID вопросов на поля сессии
            answer_map = {
                1: ('age_group', str(answer)),
                2: ('education', str(answer)),
                3: ('location_type', str(answer)),
                4: ('motivations', answer if isinstance(answer, list) else [str(answer)]),
                5: ('decision_style', str(answer)),
                6: ('risk_scenario', str(answer)),
                7: ('risk_tolerance', int(answer) if str(answer).isdigit() else 0),
                8: ('energy_profile', str(answer)),
                9: ('peak_analytical', str(answer)),
                10: ('peak_creative', str(answer)),
                11: ('peak_social', str(answer)),
                12: ('fears_selected', answer if isinstance(answer, list) else [str(answer)]),
                13: ('fear_custom', str(answer)),
                14: ('analytical_skills', int(answer) if str(answer).isdigit() else 0),
                15: ('communication_skills', int(answer) if str(answer).isdigit() else 0),
                16: ('design_skills', int(answer) if str(answer).isdigit() else 0),
                17: ('organizational_skills', int(answer) if str(answer).isdigit() else 0),
                18: ('manual_skills', int(answer) if str(answer).isdigit() else 0),
                19: ('emotional_iq', int(answer) if str(answer).isdigit() else 0),
                20: ('superpower', str(answer)),
                21: ('work_style', str(answer)),
                22: ('learning_style', str(answer)),
                23: ('existential_answer', str(answer)),
                24: ('flow_experience', str(answer)),
                25: ('flow_feelings', str(answer)),
                26: ('ideal_client_age', str(answer)),
                27: ('ideal_client_field', str(answer)),
                28: ('ideal_client_pain', str(answer)),
                29: ('ideal_client_details', str(answer)),
                30: ('budget', str(answer)),
                31: ('equipment', answer if isinstance(answer, list) else [str(answer)]),
                32: ('knowledge_assets', answer if isinstance(answer, list) else [str(answer)]),
                33: ('time_per_week', str(answer)),
                34: ('business_scale', str(answer)),
                35: ('business_format', str(answer))
            }
            
            if question_id in answer_map:
                field_name, value = answer_map[question_id]
                setattr(self, field_name, value)
                self.update_timestamp()
                return True
            
            return False
            
        except Exception as e:
            print(f"Ошибка сохранения ответа на вопрос {question_id}: {e}")
            return False
    
    def mark_completed(self):
        """Пометить анкету как завершенную"""
        self.is_completed = True
        self.completion_date = datetime.now()
        self.current_state = BotState.ANALYZING
        self.update_timestamp()

# Дополнительные классы
@dataclass
class QuestionnaireAnswer:
    """Ответ на вопрос анкеты"""
    question_id: int
    question_text: str
    answer: Any
    timestamp: datetime = field(default_factory=datetime.now)
    answer_type: str = ""  # text, button, multiselect, slider

@dataclass
class AnalysisResult:
    """Результат анализа пользователя"""
    psychological_profile: str = ""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    opportunities: List[str] = field(default_factory=list)
    threats: List[str] = field(default_factory=list)
    recommended_niches: List[Dict[str, Any]] = field(default_factory=list)
    ideal_working_conditions: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)