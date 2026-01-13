"""
Движок вопросов - рендерит и обрабатывает все типы вопросов
"""
import logging
import yaml
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from models.enums import QuestionType, BotState
from models.session import UserSession
from config.settings import BotConfig

logger = logging.getLogger(__name__)

@dataclass
class QuestionOption:
    """Опция вопроса"""
    text: str
    value: str
    store_field: Optional[str] = None
    is_custom: bool = False
    custom_prompt: Optional[str] = None
    custom_field: Optional[str] = None
    location: Optional[str] = None
    next_question: Optional[int] = None

@dataclass
class Question:
    """Модель вопроса"""
    id: int
    part: int
    text: str
    type: str
    options: List[QuestionOption]
    min_selections: Optional[int] = None
    max_selections: Optional[int] = None
    next_question: Optional[int] = None
    store_field: Optional[str] = None
    is_custom: bool = False

class QuestionEngine:
    """Движок для работы с вопросами"""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.questions: Dict[int, Question] = {}
        self.question_states: Dict[int, BotState] = {}
        self._load_questions()
        self._setup_state_mapping()
    
    def _load_questions(self):
        """Загрузить вопросы из YAML"""
        try:
            questions_path = self.config.get_questions_path()
            
            with open(questions_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            for q_data in data.get('questions', []):
                options = []
                for opt_data in q_data.get('options', []):
                    option = QuestionOption(
                        text=opt_data.get('text'),
                        value=opt_data.get('value'),
                        store_field=opt_data.get('store_field'),
                        is_custom=opt_data.get('is_custom', False),
                        custom_prompt=opt_data.get('custom_prompt'),
                        custom_field=opt_data.get('custom_field'),
                        location=opt_data.get('location'),
                        next_question=opt_data.get('next_question')
                    )
                    options.append(option)
                
                question = Question(
                    id=q_data['id'],
                    part=q_data.get('part', 1),
                    text=q_data['text'],
                    type=q_data['type'],
                    options=options,
                    min_selections=q_data.get('min_selections'),
                    max_selections=q_data.get('max_selections'),
                    next_question=q_data.get('next_question'),
                    store_field=q_data.get('store_field'),
                    is_custom=q_data.get('is_custom', False)
                )
                
                self.questions[question.id] = question
            
            logger.info(f"✅ Загружено {len(self.questions)} вопросов")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки вопросов: {e}")
            raise
    
    def _setup_state_mapping(self):
        """Настроить соответствие вопросов состояниям"""
        # Соответствие части анкеты состоянию бота
        part_to_state = {
            1: BotState.DEMOGRAPHY,
            2: BotState.PERSONALITY,
            3: BotState.SKILLS,
            4: BotState.VALUES,
            5: BotState.LIMITATIONS
        }
        
        for question_id, question in self.questions.items():
            self.question_states[question_id] = part_to_state.get(question.part, BotState.START)
    
    def get_question(self, question_id: int) -> Optional[Question]:
        """Получить вопрос по ID"""
        return self.questions.get(question_id)
    
    def get_next_question_id(self, current_id: int) -> Optional[int]:
        """Получить ID следующего вопроса"""
        question = self.questions.get(current_id)
        if question and question.next_question:
            return question.next_question
        
        # Если next_question не указан, берем следующий по порядку
        sorted_ids = sorted(self.questions.keys())
        try:
            current_index = sorted_ids.index(current_id)
            if current_index + 1 < len(sorted_ids):
                return sorted_ids[current_index + 1]
        except ValueError:
            pass
        
        return None
    
    def get_state_for_question(self, question_id: int) -> BotState:
        """Получить состояние бота для вопроса"""
        return self.question_states.get(question_id, BotState.START)
    
    def render_question(self, question: Question, session: UserSession) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
        """Рендерить вопрос для Telegram"""
        # Добавляем прогресс
        progress_header = self._get_progress_header(session)
        full_text = f"{progress_header}{question.text}"
        
        # Создаем клавиатуру в зависимости от типа вопроса
        keyboard = None
        
        if question.type == "buttons":
            keyboard = self._render_buttons(question, session)
        elif question.type == "multiselect":
            keyboard = self._render_multiselect(question, session)
        elif question.type == "slider":
            keyboard = self._render_slider(question, session)
        elif question.type == "text":
            # Для текстовых вопросов клавиатура не нужна
            pass
        
        return full_text, keyboard
    
    def _get_progress_header(self, session: UserSession) -> str:
        """Сгенерировать заголовок с прогрессом"""
        progress_bar = session.get_progress_bar()
        question_num = session.current_question
        
        emojis = ["🔴", "🟠", "🟡", "🟢", "🔵", "🟣"]
        emoji = emojis[min(question_num - 1, len(emojis) - 1)] if question_num > 0 else "🟢"
        
        return f"{emoji} *Вопрос {question_num}/{session.total_questions}*\n{progress_bar}\n\n"
    
    def _render_buttons(self, question: Question, session: UserSession) -> InlineKeyboardMarkup:
        """Рендерить кнопки"""
        keyboard = []
        
        for option in question.options:
            callback_data = f"answer_{question.id}_{option.value}"
            keyboard.append([InlineKeyboardButton(option.text, callback_data=callback_data)])
        
        return InlineKeyboardMarkup(keyboard)
    
    def _render_multiselect(self, question: Question, session: UserSession) -> InlineKeyboardMarkup:
        """Рендерить мультиселект"""
        keyboard = []
        
        # Получаем уже выбранные опции для этого вопроса
        selected_values = session.temp_multiselect
        
        for option in question.options:
            # Проверяем, выбрана ли опция
            is_selected = option.value in selected_values
            prefix = "✅" if is_selected else "□"
            
            callback_data = f"multiselect_{question.id}_{option.value}"
            button_text = f"{prefix} {option.text}"
            
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Кнопка завершения выбора
        keyboard.append([
            InlineKeyboardButton("✅ Завершить выбор", callback_data=f"multiselect_done_{question.id}")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def _render_slider(self, question: Question, session: UserSession) -> InlineKeyboardMarkup:
        """Рендерить слайдер (шкалу)"""
        keyboard = []
        
        # Создаем строку с кнопками от 1 до 5 (или 1 до 10)
        max_value = 5  # По умолчанию 5-балльная шкала
        if question.id in [8, 15, 16, 17, 18, 19, 20]:  # Риск и навыки
            max_value = 10 if question.id == 8 else 5
        
        row = []
        for i in range(1, max_value + 1):
            callback_data = f"slider_{question.id}_{i}"
            row.append(InlineKeyboardButton(str(i), callback_data=callback_data))
        
        keyboard.append(row)
        
        # Кнопка подтверждения
        keyboard.append([
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"slider_confirm_{question.id}")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def process_answer(
        self, 
        question: Question, 
        answer_data: str, 
        session: UserSession
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Обработать ответ на вопрос
        
        Возвращает: (успех, сообщение об ошибке, следующий вопрос)
        """
        try:
            if question.type == "multiselect":
                return self._process_multiselect(question, answer_data, session)
            elif question.type == "slider":
                return self._process_slider(question, answer_data, session)
            elif question.type == "buttons":
                return self._process_button(question, answer_data, session)
            elif question.type == "text":
                return self._process_text(question, answer_data, session)
            else:
                return False, f"Неизвестный тип вопроса: {question.type}", None
        
        except Exception as e:
            logger.error(f"❌ Ошибка обработки ответа: {e}")
            return False, "Ошибка обработки ответа", None
    
    def _process_multiselect(
        self, 
        question: Question, 
        answer_data: str, 
        session: UserSession
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """Обработать мультиселект"""
        # Проверяем, завершен ли выбор
        if answer_data.startswith("done_"):
            # Проверяем минимальное количество выбранных опций
            selected_count = len(session.temp_multiselect)
            
            if question.min_selections and selected_count < question.min_selections:
                error_msg = f"Пожалуйста, выберите как минимум {question.min_selections} варианта"
                return False, error_msg, None
            
            if question.max_selections and selected_count > question.max_selections:
                error_msg = f"Пожалуйста, выберите не более {question.max_selections} вариантов"
                return False, error_msg, None
            
            # Сохраняем выбранные значения
            self._save_multiselection(question, session)
            
            # Очищаем временные данные
            session.temp_multiselect = []
            
            # Переходим к следующему вопросу
            next_id = self.get_next_question_id(question.id)
            return True, None, next_id
        
        else:
            # Добавляем/удаляем опцию
            option_value = answer_data.replace("select_", "")
            
            if option_value in session.temp_multiselect:
                session.temp_multiselect.remove(option_value)
            else:
                # Проверяем максимальное количество
                if question.max_selections and len(session.temp_multiselect) >= question.max_selections:
                    error_msg = f"Можно выбрать не более {question.max_selections} вариантов"
                    return False, error_msg, None
                session.temp_multiselect.append(option_value)
            
            # Остаемся на том же вопросе
            return True, None, question.id
    
    def _save_multiselection(self, question: Question, session: UserSession):
        """Сохранить выбранные значения мультиселекта"""
        # Находим опции по значениям
        selected_options = []
        for option in question.options:
            if option.value in session.temp_multiselect:
                selected_options.append(option)
        
        # Сохраняем в соответствующие поля
        for option in selected_options:
            if option.store_field:
                # Для мотиваций - добавляем в список
                if option.store_field == "motivations":
                    session.motivations.append(option.text)
                # Для страхов
                elif option.store_field == "fears_selected":
                    session.fears_selected.append(option.text)
                # Для оборудования
                elif option.store_field == "equipment":
                    session.equipment.append(option.text)
                # Для знаний
                elif option.store_field == "knowledge_assets":
                    session.knowledge_assets.append(option.text)
    
    def _process_slider(
        self, 
        question: Question, 
        answer_data: str, 
        session: UserSession
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """Обработать слайдер"""
        if answer_data.startswith("confirm_"):
            # Подтверждение выбранного значения
            next_id = self.get_next_question_id(question.id)
            return True, None, next_id
        
        else:
            # Выбор значения
            value = int(answer_data.split("_")[-1])
            
            # Сохраняем значение в зависимости от вопроса
            if question.id == 8:  # Уровень риска
                session.risk_tolerance = value
            elif question.id == 15:  # Аналитика
                session.skills_analytics = value
            elif question.id == 16:  # Коммуникация
                session.skills_communication = value
            elif question.id == 17:  # Дизайн
                session.skills_design = value
            elif question.id == 18:  # Организация
                session.skills_organization = value
            elif question.id == 19:  # Ручной труд
                session.skills_manual = value
            elif question.id == 20:  # Эмоциональный интеллект
                session.skills_eq = value
            
            # Остаемся на том же вопросе
            return True, None, question.id
    
    def _process_button(
        self, 
        question: Question, 
        answer_data: str, 
        session: UserSession
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """Обработать кнопку"""
        # Находим выбранную опцию
        selected_value = answer_data.split("_")[-1]
        selected_option = None
        
        for option in question.options:
            if option.value == selected_value:
                selected_option = option
                break
        
        if not selected_option:
            return False, "Выбран неверный вариант", None
        
        # Проверяем, нужен ли кастомный ввод
        if selected_option.is_custom and selected_option.custom_field:
            # Устанавливаем флаг кастомного ввода
            session.temp_energy_selection = selected_option.custom_field
            # Остаемся на том же вопросе для кастомного ввода
            return True, None, question.id
        
        # Сохраняем значение
        if selected_option.store_field:
            self._save_button_answer(selected_option, session)
        
        # Определяем следующий вопрос
        next_id = selected_option.next_question or self.get_next_question_id(question.id)
        
        return True, None, next_id
    
    def _save_button_answer(self, option: QuestionOption, session: UserSession):
        """Сохранить ответ на кнопку"""
        field_name = option.store_field
        
        if field_name == "age_group":
            session.age_group = option.text
        elif field_name == "education":
            session.education = option.text
        elif field_name == "location_type":
            session.location_type = option.text
            if option.location:
                session.location = option.location
        elif field_name == "decision_style":
            session.decision_style = option.text
        elif field_name == "risk_scenario":
            session.risk_scenario = option.text
        elif field_name == "peak_analytical":
            session.peak_analytical = option.text
        elif field_name == "peak_creative":
            session.peak_creative = option.text
        elif field_name == "peak_social":
            session.peak_social = option.text
        elif field_name == "superpower":
            session.superpower = option.text
        elif field_name == "work_style":
            session.work_style = option.text
        elif field_name == "ideal_client_age":
            session.ideal_client_age = option.text
        elif field_name == "ideal_client_field":
            session.ideal_client_field = option.text
        elif field_name == "ideal_client_pain":
            session.ideal_client_pain = option.text
        elif field_name == "budget":
            session.budget = option.text
        elif field_name == "time_per_week":
            session.time_per_week = option.text
        elif field_name == "business_scale":
            session.business_scale = option.text
        elif field_name == "business_format":
            session.business_format = option.text
    
    def _process_text(
        self, 
        question: Question, 
        answer_text: str, 
        session: UserSession
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """Обработать текстовый ответ"""
        # Сохраняем текст в зависимости от вопроса
        if question.id == 4:  # Кастомная локация
            session.location_custom = answer_text
            session.location = answer_text
        elif question.id == 9:  # Энергетический профиль
            # Парсим числа из текста
            import re
            numbers = re.findall(r'\d+', answer_text)
            if len(numbers) >= 3:
                try:
                    session.energy_morning = min(7, max(1, int(numbers[0])))
                    session.energy_day = min(7, max(1, int(numbers[1])))
                    session.energy_evening = min(7, max(1, int(numbers[2])))
                except:
                    pass
        elif question.id == 12:  # Кастомный страх
            session.fear_custom = answer_text
        elif question.id == 21:  # Стиль обучения
            session.learning_preferences = answer_text
        elif question.id == 22:  # Экзистенциальный вопрос
            session.existential_answer = answer_text
        elif question.id == 23:  # Состояние потока
            session.flow_experience_desc = answer_text
        elif question.id == 24:  # Ощущения в потоке
            session.flow_feelings = answer_text
        elif question.id == 28:  # Детали о клиенте
            session.ideal_client_details = answer_text
        
        next_id = self.get_next_question_id(question.id)
        return True, None, next_id