#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Движок вопросов для бизнес-навигатора
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from models.enums import BotState, QuestionType
from models.session import UserSession
from config.settings import config
from utils.formatters import format_question_text

logger = logging.getLogger(__name__)

class QuestionEngine:
    """Движок для управления вопросами анкеты"""
    
    def __init__(self):
        self.total_questions = len(config.questions)
        logger.info(f"QuestionEngine инициализирован с {self.total_questions} вопросами")
    
    def get_question_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """Получить вопрос по индексу"""
        if 0 <= index < self.total_questions:
            question = config.questions[index]
            
            # Добавляем метаданные для отладки
            question['question_number'] = index + 1
            question['total_questions'] = self.total_questions
            
            return question
        return None
    
    def get_next_question_index(self, current_index: int) -> Optional[int]:
        """Получить индекс следующего вопроса"""
        if current_index < self.total_questions - 1:
            return current_index + 1
        return None
    
    def get_question_text(self, question: Dict[str, Any], session: UserSession) -> str:
        """Форматировать текст вопроса"""
        text = question.get('text', '')
        
        # Добавляем номер вопроса
        q_num = question.get('question_number', 0)
        total = question.get('total_questions', self.total_questions)
        
        if q_num > 0:
            # Находим начало текста (после эмодзи)
            lines = text.split('\n')
            if lines:
                # Добавляем номер вопроса к первой строке
                first_line = lines[0]
                if 'ВОПРОС' in first_line:
                    # Уже есть форматирование
                    return text
                else:
                    # Добавляем форматирование
                    lines[0] = f"📋 *ВОПРОС {q_num}/{total}:*\n\n{first_line}"
                    text = '\n'.join(lines)
        
        # Заменяем плейсхолдеры
        if '{user_name}' in text and session.full_name:
            text = text.replace('{user_name}', session.full_name)
        
        return text
    
    def create_keyboard_for_question(self, question: Dict[str, Any]) -> Optional[InlineKeyboardMarkup]:
        """Создать клавиатуру для вопроса"""
        question_type = question.get('type', 'text')
        options = question.get('options', [])
        
        if question_type == 'buttons' and options:
            keyboard = []
            for option in options:
                button_text = option.get('text', '')
                button_data = option.get('value', '')
                keyboard.append([InlineKeyboardButton(button_text, callback_data=button_data)])
            return InlineKeyboardMarkup(keyboard)
        
        elif question_type == 'multiselect' and options:
            # Для мультиселекта - кнопки с флажками
            keyboard = []
            for option in options:
                button_text = f"□ {option.get('text', '')}"
                button_data = f"select_{option.get('value', '')}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=button_data)])
            
            # Кнопка подтверждения выбора
            keyboard.append([InlineKeyboardButton("✅ Завершить выбор", callback_data="multiselect_done")])
            return InlineKeyboardMarkup(keyboard)
        
        return None
    
    def validate_answer(self, question: Dict[str, Any], answer: Any) -> Tuple[bool, str]:
        """Проверить валидность ответа"""
        question_type = question.get('type', 'text')
        
        if question_type == 'text':
            min_length = question.get('min_length', 0)
            max_length = question.get('max_length', 1000)
            
            if not isinstance(answer, str):
                return False, "Ответ должен быть текстом"
            
            answer_len = len(answer.strip())
            if answer_len < min_length:
                return False, f"Ответ слишком короткий. Минимум {min_length} символов."
            if answer_len > max_length:
                return False, f"Ответ слишком длинный. Максимум {max_length} символов."
            
            return True, ""
        
        elif question_type == 'slider':
            try:
                value = int(answer)
                min_val = question.get('min', 1)
                max_val = question.get('max', 10)
                
                if min_val <= value <= max_val:
                    return True, ""
                else:
                    return False, f"Значение должно быть от {min_val} до {max_val}"
            except:
                return False, "Неверный формат числа"
        
        elif question_type == 'multiselect':
            if not isinstance(answer, list):
                answer = [answer] if answer else []
            
            min_select = question.get('min_selections', 1)
            max_select = question.get('max_selections', 10)
            
            if len(answer) < min_select:
                return False, f"Выберите хотя бы {min_select} вариант(а)"
            if len(answer) > max_select:
                return False, f"Выберите не более {max_select} вариантов"
            
            return True, ""
        
        return True, ""
    
    def process_answer(self, session: UserSession, question: Dict[str, Any], answer: Any) -> bool:
        """Обработать ответ пользователя"""
        try:
            question_id = question.get('id')
            question_index = session.current_question_index
            
            # Валидация ответа
            is_valid, error_message = self.validate_answer(question, answer)
            if not is_valid:
                logger.warning(f"Невалидный ответ: {error_message}")
                return False
            
            # Сохраняем ответ в сессию
            if session.save_answer(question_index + 1, answer):
                logger.info(f"Ответ сохранен для вопроса {question_id}")
                
                # Если это последний вопрос, помечаем как завершенный
                if question_index >= self.total_questions - 1:
                    session.mark_completed()
                    logger.info(f"Анкета пользователя {session.user_id} завершена")
                else:
                    # Переходим к следующему вопросу
                    session.current_question_index += 1
                    session.current_state = self._get_state_for_question(session.current_question_index)
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка обработки ответа: {e}")
            return False
    
    def get_help_text(self, question: Dict[str, Any]) -> str:
        """Получить текст подсказки для вопроса"""
        help_text = question.get('help_text', '')
        
        # Добавляем специфичные подсказки по типу вопроса
        question_type = question.get('type', 'text')
        
        if question_type == 'slider':
            min_val = question.get('min', 1)
            max_val = question.get('max', 10)
            default = question.get('default_value', min_val)
            labels = question.get('labels', {})
            
            help_parts = []
            if help_text:
                help_parts.append(help_text)
            
            help_parts.append(f"📏 Диапазон: от {min_val} до {max_val}")
            
            if labels:
                labels_text = " | ".join([f"{k}: {v}" for k, v in labels.items()])
                help_parts.append(f"🏷️ Значения: {labels_text}")
            
            if default:
                help_parts.append(f"⚙️ По умолчанию: {default}")
            
            return "\n".join(help_parts)
        
        elif question_type == 'multiselect':
            min_select = question.get('min_selections', 1)
            max_select = question.get('max_selections', 10)
            
            help_parts = []
            if help_text:
                help_parts.append(help_text)
            
            if min_select == max_select:
                help_parts.append(f"📌 Выберите ровно {min_select} вариант(а)")
            else:
                help_parts.append(f"📌 Выберите от {min_select} до {max_select} вариантов")
            
            help_parts.append("ℹ️ Нажмите на вариант, чтобы выбрать/снять выбор")
            help_parts.append("✅ Нажмите 'Завершить выбор', когда закончите")
            
            return "\n".join(help_parts)
        
        return help_text if help_text else "Введите ваш ответ"
    
    def _get_state_for_question(self, question_index: int) -> BotState:
        """Получить состояние бота для вопроса"""
        # Простая логика - по индексам вопросов
        if question_index < 3:  # Вопросы 1-3
            return BotState.DEMOGRAPHY
        elif question_index < 12:  # Вопросы 4-12
            return BotState.PERSONALITY
        elif question_index < 22:  # Вопросы 13-22
            return BotState.SKILLS
        elif question_index < 29:  # Вопросы 23-29
            return BotState.VALUES
        elif question_index < 35:  # Вопросы 30-35
            return BotState.LIMITATIONS
        else:
            return BotState.ANALYZING
    
    def format_slider_value(self, value: int, question: Dict[str, Any]) -> str:
        """Форматировать значение ползунка"""
        min_val = question.get('min', 1)
        max_val = question.get('max', 10)
        unit = question.get('unit', '')
        labels = question.get('labels', {})
        
        # Ищем ближайшую метку
        if labels:
            # Преобразуем ключи в int
            label_keys = []
            for k in labels.keys():
                try:
                    label_keys.append(int(k))
                except:
                    pass
            
            if label_keys:
                # Находим ближайшую метку
                closest_key = min(label_keys, key=lambda x: abs(x - value))
                label = labels.get(str(closest_key), '')
                if label:
                    return f"{value} {unit} ({label})".strip()
        
        return f"{value} {unit}".strip()
    
    def get_next_question_id(self, question: Dict[str, Any]) -> Optional[int]:
        """Получить ID следующего вопроса"""
        next_q = question.get('next_question')
        if next_q is not None:
            # next_question может быть null для последнего вопроса
            if next_q is None:
                return None
            return int(next_q) - 1  # Преобразуем в 0-based индекс
        return None

# Глобальный экземпляр движка
question_engine = QuestionEngine()