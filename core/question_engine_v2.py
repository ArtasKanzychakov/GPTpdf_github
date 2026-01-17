---

## ФАЙЛ 5: `core/question_engine_v2.py` (НОВЫЙ ФАЙЛ)

```python
"""
Движок вопросов v2.0 для Business Navigator
Поддержка всех типов интерактивных вопросов
"""
import yaml
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging

from models.question_types import QuestionType, QuestionCategory
from models.session import UserSession

logger = logging.getLogger(__name__)


class QuestionEngineV2:
    """Движок обработки вопросов анкеты v2.0"""
    
    def __init__(self, questions_file: str = "config/questions_v2.yaml"):
        """
        Инициализация движка
        
        Args:
            questions_file: Путь к YAML файлу с вопросами
        """
        self.questions_file = Path(questions_file)
        self.questions: Dict[str, Any] = {}
        self.load_questions()
    
    def load_questions(self):
        """Загрузить вопросы из YAML файла"""
        try:
            with open(self.questions_file, 'r', encoding='utf-8') as f:
                self.questions = yaml.safe_load(f)
            logger.info(f"Загружено {len(self.questions)} вопросов из {self.questions_file}")
        except Exception as e:
            logger.error(f"Ошибка загрузки вопросов: {e}")
            raise
    
    def get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        """
        Получить вопрос по ID
        
        Args:
            question_id: ID вопроса (например, "Q1", "Q5")
        
        Returns:
            Словарь с данными вопроса или None
        """
        return self.questions.get(question_id)
    
    def get_next_question_id(self, current_id: str) -> Optional[str]:
        """
        Получить ID следующего вопроса
        
        Args:
            current_id: Текущий ID вопроса
        
        Returns:
            ID следующего вопроса или None
        """
        current_question = self.get_question(current_id)
        if not current_question:
            return None
        
        next_id = current_question.get('next')
        if next_id == 'processing':
            return None  # Анкета завершена
        
        return next_id
    
    def format_question_text(self, question_data: Dict[str, Any]) -> str:
        """
        Форматировать текст вопроса
        
        Args:
            question_data: Данные вопроса
        
        Returns:
            Отформатированный текст
        """
        text = question_data.get('question', '')
        
        if 'description' in question_data:
            desc = question_data['description']
            if isinstance(desc, str):
                text += f"\n\n{desc}"
            elif isinstance(desc, dict):
                text += f"\n\n{desc}"
        
        if 'scenario' in question_data:
            text += f"\n\n📖 {question_data['scenario']}"
        
        if 'hint' in question_data:
            text += f"\n\n💡 {question_data['hint']}"
        
        return text
    
    def create_keyboard(
        self, 
        question_data: Dict[str, Any], 
        session: Optional[UserSession] = None
    ) -> Optional[InlineKeyboardMarkup]:
        """
        Создать клавиатуру для вопроса
        
        Args:
            question_data: Данные вопроса
            session: Сессия пользователя (для отображения выбранных вариантов)
        
        Returns:
            InlineKeyboardMarkup или None
        """
        question_type = question_data.get('type')
        
        if question_type in ['text', 'existential_text']:
            return None  # Текстовый ввод без кнопок
        
        if question_type in ['quick_buttons', 'choice', 'superhero_metaphor']:
            return self._create_simple_keyboard(question_data)
        
        if question_type == 'multi_select':
            return self._create_multiselect_keyboard(question_data, session)
        
        if question_type == 'scenario_test':
            return self._create_scenario_keyboard(question_data)
        
        if question_type == 'slider_with_scenario':
            return self._create_slider_keyboard(question_data, session)
        
        if question_type == 'skill_rating':
            return self._create_rating_keyboard(question_data, session)
        
        if question_type == 'learning_allocation':
            return self._create_allocation_keyboard(question_data, session)
        
        if question_type == 'energy_distribution':
            return self._create_energy_keyboard(question_data, session)
        
        if question_type == 'flow_experience':
            return self._create_flow_keyboard(question_data)
        
        if question_type == 'client_portrait':
            return self._create_portrait_keyboard(question_data, session)
        
        return None
    
    def _create_simple_keyboard(self, question_data: Dict[str, Any]) -> InlineKeyboardMarkup:
        """Создать простую клавиатуру с кнопками"""
        keyboard = []
        options = question_data.get('options', [])
        
        for option in options:
            value = option.get('value')
            label = option.get('label')
            emoji = option.get('emoji', '')
            
            button_text = f"{emoji} {label}" if emoji else label
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"answer:{value}")])
        
        # Добавить кнопку "Назад" если это не первый вопрос
        if question_data.get('category') != 'demographic' or 'Q1' not in str(question_data):
            keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def _create_multiselect_keyboard(
        self, 
        question_data: Dict[str, Any], 
        session: Optional[UserSession]
    ) -> InlineKeyboardMarkup:
        """Создать клавиатуру для множественного выбора"""
        keyboard = []
        options = question_data.get('options', [])
        
        # Получить уже выбранные варианты
        question_id = self._get_question_id(question_data)
        selected = []
        if session:
            temp_key = f"{question_id}_selected"
            selected = session.temp_data.get(temp_key, [])
        
        for option in options:
            value = option.get('value')
            label = option.get('label')
            emoji = option.get('emoji', '')
            
            # Добавить галочку если выбрано
            checkmark = "✅ " if value in selected else ""
            button_text = f"{checkmark}{emoji} {label}" if emoji else f"{checkmark}{label}"
            
            keyboard.append([InlineKeyboardButton(
                button_text, 
                callback_data=f"multiselect:{value}"
            )])
        
        # Кнопки управления
        validation = question_data.get('validation', {})
        min_choices = validation.get('min_choices', 1)
        max_choices = validation.get('max_choices', 10)
        
        info_text = f"📊 Выбрано: {len(selected)} (мин: {min_choices}, макс: {max_choices})"
        keyboard.append([InlineKeyboardButton(info_text, callback_data="info")])
        
        if len(selected) >= min_choices:
            keyboard.append([InlineKeyboardButton("✅ Продолжить", callback_data="submit")])
        
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def _create_scenario_keyboard(self, question_data: Dict[str, Any]) -> InlineKeyboardMarkup:
        """Создать клавиатуру для сценарного вопроса"""
        keyboard = []
        options = question_data.get('options', [])
        
        for option in options:
            value = option.get('value')
            label = option.get('label')
            description = option.get('description', '')
            
            button_text = label
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"scenario:{value}")])
            
            # Добавить описание как отдельную строку (неактивная кнопка)
            if description:
                keyboard.append([InlineKeyboardButton(
                    f"    └─ {description}", 
                    callback_data="info"
                )])
        
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def _create_slider_keyboard(
        self, 
        question_data: Dict[str, Any], 
        session: Optional[UserSession]
    ) -> InlineKeyboardMarkup:
        """Создать клавиатуру со слайдером"""
        keyboard = []
        
        # Сначала показываем варианты сценария
        options = question_data.get('options', [])
        question_id = self._get_question_id(question_data)
        
        # Проверяем, выбран ли вариант сценария
        selected_option = None
        if session:
            selected_option = session.temp_data.get(f"{question_id}_option")
        
        if not selected_option:
            # Показываем варианты сценария
            for option in options:
                value = option.get('value')
                label = option.get('label')
                keyboard.append([InlineKeyboardButton(label, callback_data=f"slider_option:{value}")])
        else:
            # Показываем слайдер
            slider_data = question_data.get('slider', {})
            min_val = slider_data.get('min', 1)
            max_val = slider_data.get('max', 10)
            current_val = session.temp_data.get(f"{question_id}_value", 5) if session else 5
            
            # Визуализация слайдера
            slider_text = f"{slider_data.get('label', 'Уровень:')} {current_val}/{max_val}"
            keyboard.append([InlineKeyboardButton(slider_text, callback_data="info")])
            
            # Кнопки управления
            row = []
            if current_val > min_val:
                row.append(InlineKeyboardButton("➖", callback_data="slider_dec"))
            row.append(InlineKeyboardButton(f"{current_val}", callback_data="info"))
            if current_val < max_val:
                row.append(InlineKeyboardButton("➕", callback_data="slider_inc"))
            keyboard.append(row)
            
            # Визуальная шкала
            scale = self._create_visual_scale(current_val, min_val, max_val)
            keyboard.append([InlineKeyboardButton(scale, callback_data="info")])
            
            keyboard.append([InlineKeyboardButton("✅ Продолжить", callback_data="submit")])
        
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def _create_rating_keyboard(
        self, 
        question_data: Dict[str, Any], 
        session: Optional[UserSession]
    ) -> InlineKeyboardMarkup:
        """Создать клавиатуру для рейтинга навыков"""
        keyboard = []
        skills = question_data.get('skills', [])
        question_id = self._get_question_id(question_data)
        
        # Получить текущие рейтинги
        ratings = {}
        if session:
            ratings = session.temp_data.get(f"{question_id}_ratings", {})
        
        rating_scale = question_data.get('rating_scale', {})
        max_stars = rating_scale.get('max', 5)
        star_emoji = rating_scale.get('star_emoji', '⭐')
        empty_emoji = rating_scale.get('empty_emoji', '☆')
        
        for skill in skills:
            skill_id = skill.get('id')
            label = skill.get('label')
            emoji = skill.get('emoji', '')
            
            current_rating = ratings.get(skill_id, 0)
            
            # Визуализация звезд
            stars = star_emoji * current_rating + empty_emoji * (max_stars - current_rating)
            button_text = f"{emoji} {label}"
            
            keyboard.append([InlineKeyboardButton(button_text, callback_data="info")])
            
            # Кнопки рейтинга
            rating_row = []
            for i in range(1, max_stars + 1):
                rating_row.append(InlineKeyboardButton(
                    f"{i}⭐" if i == current_rating else str(i),
                    callback_data=f"rating:{skill_id}:{i}"
                ))
            keyboard.append(rating_row)
        
        # Проверка заполненности
        all_rated = len(ratings) == len(skills) and all(r > 0 for r in ratings.values())
        
        if all_rated:
            keyboard.append([InlineKeyboardButton("✅ Продолжить", callback_data="submit")])
        else:
            keyboard.append([InlineKeyboardButton(
                f"📊 Оценено: {len([r for r in ratings.values() if r > 0])}/{len(skills)}", 
                callback_data="info"
            )])
        
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def _create_allocation_keyboard(
        self, 
        question_data: Dict[str, Any], 
        session: Optional[UserSession]
    ) -> InlineKeyboardMarkup:
        """Создать клавиатуру для распределения баллов"""
        keyboard = []
        formats = question_data.get('formats', [])
        total_points = question_data.get('total_points', 10)
        question_id = self._get_question_id(question_data)
        
        # Получить текущее распределение
        allocation = {}
        if session:
            allocation = session.temp_data.get(f"{question_id}_allocation", {})
        
        # Вычислить использованные баллы
        used_points = sum(allocation.values())
        remaining = total_points - used_points
        
        # Показать каждый формат
        for fmt in formats:
            fmt_id = fmt.get('id')
            label = fmt.get('label')
            emoji = fmt.get('emoji', '')
            
            current_value = allocation.get(fmt_id, 0)
            
            button_text = f"{emoji} {label}: {current_value}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data="info")])
            
            # Кнопки +/-
            row = []
            if current_value > 0:
                row.append(InlineKeyboardButton("➖", callback_data=f"alloc_dec:{fmt_id}"))
            row.append(InlineKeyboardButton(f"{current_value}", callback_data="info"))
            if remaining > 0:
                row.append(InlineKeyboardButton("➕", callback_data=f"alloc_inc:{fmt_id}"))
            keyboard.append(row)
        
        # Показать остаток
        keyboard.append([InlineKeyboardButton(
            f"📊 Осталось баллов: {remaining}/{total_points}", 
            callback_data="info"
        )])
        
        # Кнопка продолжить только если распределены все баллы
        if remaining == 0:
            keyboard.append([InlineKeyboardButton("✅ Продолжить", callback_data="submit")])
        
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def _create_energy_keyboard(
        self, 
        question_data: Dict[str, Any], 
        session: Optional[UserSession]
    ) -> InlineKeyboardMarkup:
        """Создать клавиатуру для распределения энергии"""
        keyboard = []
        question_id = self._get_question_id(question_data)
        
        # Получить текущее состояние
        step = session.temp_data.get(f"{question_id}_step", 'periods') if session else 'periods'
        
        if step == 'periods':
            # Шаг 1: Оценка энергии по периодам дня
            time_periods = question_data.get('time_periods', [])
            energy_levels = {}
            if session:
                energy_levels = session.temp_data.get(f"{question_id}_energy", {})
            
            for period_data in time_periods:
                period = period_data.get('period')
                label = period_data.get('label')
                emoji = period_data.get('emoji', '')
                min_val = period_data.get('min', 1)
                max_val = period_data.get('max', 7)
                
                current = energy_levels.get(period, 4)
                
                keyboard.append([InlineKeyboardButton(
                    f"{emoji} {label}", 
                    callback_data="info"
                )])
                
                # Визуальная шкала
                scale = self._create_visual_scale(current, min_val, max_val, "▁▂▃▄▅▆▇")
                keyboard.append([InlineKeyboardButton(scale, callback_data="info")])
                
                # Кнопки управления
                row = []
                if current > min_val:
                    row.append(InlineKeyboardButton("➖", callback_data=f"energy_dec:{period}"))
                row.append(InlineKeyboardButton(f"{current}", callback_data="info"))
                if current < max_val:
                    row.append(InlineKeyboardButton("➕", callback_data=f"energy_inc:{period}"))
                keyboard.append(row)
            
            # Проверка заполненности
            all_set = len(energy_levels) == len(time_periods)
            if all_set:
                keyboard.append([InlineKeyboardButton(
                    "➡️ Далее (выбор времени для активностей)", 
                    callback_data="energy_next"
                )])
        
        else:
            # Шаг 2: Выбор оптимального времени для активностей
            activity_types = question_data.get('activity_types', [])
            activity_times = {}
            if session:
                activity_times = session.temp_data.get(f"{question_id}_activities", {})
            
            for activity in activity_types:
                act_type = activity.get('type')
                label = activity.get('label')
                options = activity.get('options', [])
                
                selected = activity_times.get(act_type)
                
                keyboard.append([InlineKeyboardButton(f"📌 {label}", callback_data="info")])
                
                row = []
                for opt in options:
                    checkmark = "✅ " if selected == opt else ""
                    row.append(InlineKeyboardButton(
                        f"{checkmark}{opt}", 
                        callback_data=f"activity:{act_type}:{opt}"
                    ))
                keyboard.append(row)
            
            # Кнопка продолжить
            all_selected = len(activity_times) == len(activity_types)
            if all_selected:
                keyboard.append([InlineKeyboardButton("✅ Продолжить", callback_data="submit")])
        
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def _create_flow_keyboard(self, question_data: Dict[str, Any]) -> InlineKeyboardMarkup:
        """Создать клавиатуру для вопроса о состоянии потока"""
        keyboard = []
        examples = question_data.get('examples', [])
        
        for example in examples:
            value = example.get('value')
            label = example.get('label')
            keyboard.append([InlineKeyboardButton(label, callback_data=f"flow:{value}")])
        
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def _create_portrait_keyboard(
        self, 
        question_data: Dict[str, Any], 
        session: Optional[UserSession]
    ) -> InlineKeyboardMarkup:
        """Создать клавиатуру для портрета клиента"""
        keyboard = []
        question_id = self._get_question_id(question_data)
        
        # Проверяем текущий шаг
        current_field = None
        if session:
            current_field = session.temp_data.get(f"{question_id}_current_field")
        
        demographics = question_data.get('demographics', {})
        
        if not current_field:
            # Начинаем с первого поля
            first_field = list(demographics.keys())[0]
            current_field = first_field
        
        # Получаем данные текущего поля
        field_data = demographics.get(current_field, {})
        label = field_data.get('label', current_field)
        options = field_data.get('options', [])
        
        keyboard.append([InlineKeyboardButton(f"📋 {label}", callback_data="info")])
        
        for option in options:
            keyboard.append([InlineKeyboardButton(
                option, 
                callback_data=f"portrait:{current_field}:{option}"
            )])
        
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def _create_visual_scale(
        self, 
        current: int, 
        min_val: int, 
        max_val: int, 
        chars: str = "▁▂▃▄▅▆▇█"
    ) -> str:
        """
        Создать визуальную шкалу
        
        Args:
            current: Текущее значение
            min_val: Минимум
            max_val: Максимум
            chars: Символы для отображения
        
        Returns:
            Строка со шкалой
        """
        total_steps = len(chars)
        normalized = (current - min_val) / (max_val - min_val)
        step = int(normalized * (total_steps - 1))
        
        filled = chars[-1] * step
        empty = chars[0] * (total_steps - step - 1)
        current_char = chars[step]
        
        return f"{filled}{current_char}{empty}"
    
    def _get_question_id(self, question_data: Dict[str, Any]) -> str:
        """Получить ID вопроса из данных"""
        # Поиск ID по обратной связи
        for qid, data in self.questions.items():
            if data == question_data:
                return qid
        return "unknown"
    
    def validate_answer(
        self, 
        question_id: str, 
        answer: Any, 
        session: Optional[UserSession] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Валидировать ответ на вопрос
        
        Args:
            question_id: ID вопроса
            answer: Ответ пользователя
            session: Сессия (для сложных валидаций)
        
        Returns:
            Tuple (is_valid, error_message)
        """
        question = self.get_question(question_id)
        if not question:
            return False, "Вопрос не найден"
        
        validation = question.get('validation', {})
        
        # Required check
        if validation.get('required') and not answer:
            return False, "Это обязательный вопрос"
        
        # Text length checks
        if isinstance(answer, str):
            min_length = validation.get('min_length')
            max_length = validation.get('max_length')
            
            if min_length and len(answer) < min_length:
                return False, f"Минимальная длина ответа: {min_length} символов"
            
            if max_length and len(answer) > max_length:
                return False, f"Максимальная длина ответа: {max_length} символов"
        
        # Multi-select checks
        if isinstance(answer, list):
            min_choices = validation.get('min_choices')
            max_choices = validation.get('max_choices')
            
            if min_choices and len(answer) < min_choices:
                return False, f"Выберите минимум {min_choices} вариант(ов)"
            
            if max_choices and len(answer) > max_choices:
                return False, f"Максимум {max_choices} вариант(ов)"
        
        # Sum equals check (для распределения баллов)
        if validation.get('sum_equals') and isinstance(answer, dict):
            expected_sum = validation['sum_equals']
            actual_sum = sum(answer.values())
            
            if actual_sum != expected_sum:
                return False, f"Сумма должна быть {expected_sum}, текущая: {actual_sum}"
        
        return True, None
```

---
