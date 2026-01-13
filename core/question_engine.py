#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Движок вопросов для анкеты
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.constants import ParseMode

from models.enums import QuestionType, BotState
from models.session import UserSession
from utils.formatters import format_question_text

logger = logging.getLogger(__name__)

class QuestionEngine:
    """Движок для обработки и отправки вопросов анкеты"""
    
    def __init__(self, bot):
        """
        Инициализация движка вопросов
        
        Args:
            bot: Экземпляр BusinessNavigatorBot
        """
        self.bot = bot
        self.config = bot.config
        
    async def send_question(self, user_id: int, session: UserSession, question_data: Dict[str, Any]):
        """
        Отправить вопрос пользователю
        
        Args:
            user_id: ID пользователя
            session: Сессия пользователя
            question_data: Данные вопроса
        """
        try:
            question_id = question_data['id']
            question_type = question_data.get('type', QuestionType.TEXT.value)
            question_text = question_data['text']
            
            # Форматируем текст вопроса
            formatted_text = format_question_text(
                question_text,
                session.user_name,
                session.current_question_index + 1,
                len(self.config.questions)
            )
            
            # Отправляем вопрос в зависимости от типа
            if question_type == QuestionType.TEXT.value:
                await self._send_text_question(user_id, formatted_text, question_data)
                
            elif question_type == QuestionType.BUTTONS.value:
                await self._send_buttons_question(user_id, formatted_text, question_data)
                
            elif question_type == QuestionType.MULTISELECT.value:
                await self._send_multiselect_question(user_id, formatted_text, question_data)
                
            elif question_type == QuestionType.SLIDER.value:
                await self._send_slider_question(user_id, formatted_text, question_data)
                
            else:
                logger.error(f"❌ Неизвестный тип вопроса: {question_type}")
                await self._send_text_question(user_id, formatted_text, question_data)
            
            # Обновляем состояние сессии
            session.current_question_id = question_id
            session.current_question_type = question_type
            session.last_activity = datetime.now()
            self.bot.save_user_session(session)
            
            logger.info(f"📝 Отправлен вопрос {question_id} пользователю {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки вопроса: {e}", exc_info=True)
            await self.bot.send_message(
                chat_id=user_id,
                text="❌ Произошла ошибка при отправке вопроса. Попробуйте позже."
            )
    
    async def _send_text_question(self, user_id: int, text: str, question_data: Dict[str, Any]):
        """Отправить текстовый вопрос"""
        await self.bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
    
    async def _send_buttons_question(self, user_id: int, text: str, question_data: Dict[str, Any]):
        """Отправить вопрос с кнопками"""
        options = question_data.get('options', [])
        
        # Создаем кнопки
        keyboard = []
        for option in options:
            button_text = option.get('text', '')
            button_value = option.get('value', '')
            
            keyboard.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"answer_{question_data['id']}_{button_value}"
                )
            ])
        
        # Добавляем кнопку "Пропустить" если нужно
        if question_data.get('skippable', False):
            keyboard.append([
                InlineKeyboardButton(
                    text="⏭️ Пропустить",
                    callback_data=f"skip_{question_data['id']}"
                )
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def _send_multiselect_question(self, user_id: int, text: str, question_data: Dict[str, Any]):
        """Отправить вопрос с мультиселектом"""
        options = question_data.get('options', [])
        
        # Создаем кнопки для выбора
        keyboard = []
        for option in options:
            option_text = option.get('text', '')
            option_value = option.get('value', '')
            
            keyboard.append([
                InlineKeyboardButton(
                    text=f"□ {option_text}",
                    callback_data=f"multiselect_{question_data['id']}_{option_value}_toggle"
                )
            ])
        
        # Кнопка подтверждения выбора
        keyboard.append([
            InlineKeyboardButton(
                text="✅ Завершить выбор",
                callback_data=f"multiselect_{question_data['id']}_confirm"
            )
        ])
        
        # Кнопка "Пропустить" если нужно
        if question_data.get('skippable', False):
            keyboard.append([
                InlineKeyboardButton(
                    text="⏭️ Пропустить",
                    callback_data=f"skip_{question_data['id']}"
                )
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.bot.send_message(
            chat_id=user_id,
            text=f"{text}\n\n*Вы можете выбрать несколько вариантов.*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def _send_slider_question(self, user_id: int, text: str, question_data: Dict[str, Any]):
        """Отправить вопрос со слайдером"""
        min_val = question_data.get('min', 1)
        max_val = question_data.get('max', 10)
        step = question_data.get('step', 1)
        
        # ИЗМЕНЕНИЕ: Исправляем range для создания всех значений
        # Было: range(min_val, max_val + 1, 2)
        # Стало: range(min_val, max_val + 1, step)
        values = list(range(min_val, max_val + 1, step))
        
        # Создаем кнопки слайдера
        keyboard = []
        row = []
        
        for value in values:
            row.append(
                InlineKeyboardButton(
                    text=str(value),
                    callback_data=f"slider_{question_data['id']}_{value}"
                )
            )
            
            # Разбиваем на строки по 5 кнопок
            if len(row) >= 5:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        # Кнопка подтверждения
        keyboard.append([
            InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data=f"slider_{question_data['id']}_confirm"
            )
        ])
        
        # Кнопка "Пропустить" если нужно
        if question_data.get('skippable', False):
            keyboard.append([
                InlineKeyboardButton(
                    text="⏭️ Пропустить",
                    callback_data=f"skip_{question_data['id']}"
                )
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.bot.send_message(
            chat_id=user_id,
            text=f"{text}\n\n*Выберите значение от {min_val} до {max_val}:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def update_multiselect_view(self, user_id: int, question_id: str, selected_values: List[str]):
        """Обновить вид мультиселекта с выбранными значениями"""
        # Получаем данные вопроса
        question_data = self.config.get_question_by_id(question_id)
        if not question_data:
            logger.error(f"❌ Вопрос {question_id} не найден")
            return
        
        options = question_data.get('options', [])
        
        # Создаем обновленную клавиатуру
        keyboard = []
        for option in options:
            option_text = option.get('text', '')
            option_value = option.get('value', '')
            
            # Определяем, выбран ли вариант
            is_selected = option_value in selected_values
            prefix = "☑️" if is_selected else "□"
            
            keyboard.append([
                InlineKeyboardButton(
                    text=f"{prefix} {option_text}",
                    callback_data=f"multiselect_{question_id}_{option_value}_toggle"
                )
            ])
        
        # Кнопка подтверждения
        keyboard.append([
            InlineKeyboardButton(
                text="✅ Завершить выбор",
                callback_data=f"multiselect_{question_id}_confirm"
            )
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Обновляем сообщение
        try:
            await self.bot.application.bot.edit_message_reply_markup(
                chat_id=user_id,
                message_id=self._get_last_message_id(user_id),
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"❌ Ошибка обновления мультиселекта: {e}")
    
    def _get_last_message_id(self, user_id: int) -> Optional[int]:
        """Получить ID последнего сообщения для пользователя"""
        # В реальном проекте здесь должна быть логика получения ID
        # Для простоты возвращаем None - тогда нужно будет отправлять новое сообщение
        return None
    
    def validate_answer(self, question_data: Dict[str, Any], answer: Any) -> bool:
        """Проверить корректность ответа"""
        question_type = question_data.get('type', QuestionType.TEXT.value)
        
        if question_type == QuestionType.TEXT.value:
            # Проверка текстового ответа
            if not isinstance(answer, str):
                return False
            min_length = question_data.get('min_length', 1)
            max_length = question_data.get('max_length', 1000)
            return min_length <= len(answer) <= max_length
        
        elif question_type == QuestionType.BUTTONS.value:
            # Проверка ответа с кнопками
            options = [opt['value'] for opt in question_data.get('options', [])]
            return answer in options
        
        elif question_type == QuestionType.MULTISELECT.value:
            # Проверка мультиселекта
            if not isinstance(answer, list):
                return False
            options = [opt['value'] for opt in question_data.get('options', [])]
            min_select = question_data.get('min_select', 1)
            max_select = question_data.get('max_select', len(options))
            return all(item in options for item in answer) and min_select <= len(answer) <= max_select
        
        elif question_type == QuestionType.SLIDER.value:
            # Проверка слайдера
            if not isinstance(answer, (int, float)):
                return False
            min_val = question_data.get('min', 1)
            max_val = question_data.get('max', 10)
            return min_val <= answer <= max_val
        
        return False