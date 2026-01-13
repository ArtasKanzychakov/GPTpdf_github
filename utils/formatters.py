#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утилиты для форматирования текста и клавиатур
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

# КРИТИЧЕСКИ ВАЖНЫЙ ИМПОРТ: добавляем классы Telegram
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode

from models.session import UserSession
from models.enums import NicheCategory

logger = logging.getLogger(__name__)

def format_question_text(text: str, user_name: str, current_q: int, total_q: int) -> str:
    """
    Форматирование текста вопроса
    
    Args:
        text: Текст вопроса
        user_name: Имя пользователя
        current_q: Номер текущего вопроса
        total_q: Общее количество вопросов
    
    Returns:
        Отформатированный текст
    """
    # Заменяем плейсхолдеры
    formatted_text = text.replace("{user_name}", user_name)
    
    # Добавляем прогресс
    progress_bar = create_progress_bar(current_q, total_q)
    progress_text = f"\n\n📊 *Прогресс:* {current_q}/{total_q}\n{progress_bar}"
    
    return formatted_text + progress_text

def create_progress_bar(current: int, total: int, length: int = 10) -> str:
    """
    Создание текстового прогресс-бара
    
    Args:
        current: Текущая позиция
        total: Всего шагов
        length: Длина прогресс-бара в символах
    
    Returns:
        Строка прогресс-бара
    """
    filled = int((current / total) * length)
    empty = length - filled
    return "▓" * filled + "░" * empty

def format_recommendations(recommendations: str, user_name: str) -> str:
    """
    Форматирование рекомендаций
    
    Args:
        recommendations: Текст рекомендаций
        user_name: Имя пользователя
    
    Returns:
        Отформатированные рекомендации
    """
    header = f"🎯 *Персонализированные рекомендации для {user_name}*\n\n"
    footer = "\n\n---\n🤖 *Создано Бизнес-Навигатором v7.0*"
    
    return header + recommendations + footer

def format_session_summary(session: UserSession) -> str:
    """
    Форматирование сводки сессии
    
    Args:
        session: Сессия пользователя
    
    Returns:
        Текст сводки
    """
    summary = [
        f"👤 *Пользователь:* {session.user_name}",
        f"🆔 *ID:* {session.user_id}",
        f"📅 *Создана:* {session.created_at.strftime('%Y-%m-%d %H:%M')}",
        f"📝 *Вопросов пройдено:* {session.current_question_index}/18",
        f"🔄 *Состояние:* {session.current_state.value}"
    ]
    
    if session.completed_at:
        summary.append(f"✅ *Завершена:* {session.completed_at.strftime('%Y-%m-%d %H:%M')}")
    
    return "\n".join(summary)

def create_niche_navigation(session: UserSession) -> InlineKeyboardMarkup:
    """
    Создание навигационной клавиатуры для выбора ниши
    
    Args:
        session: Сессия пользователя
    
    Returns:
        InlineKeyboardMarkup для навигации
    """
    # Это заглушка - в реальном проекте здесь будет логика создания кнопок
    # на основе категорий ниш из конфига
    
    keyboard = [
        [InlineKeyboardButton("🏢 IT и технологии", callback_data="niche_it")],
        [InlineKeyboardButton("🛍️ Электронная коммерция", callback_data="niche_ecommerce")],
        [InlineKeyboardButton("📱 Мобильные приложения", callback_data="niche_mobile")],
        [InlineKeyboardButton("🎨 Креативные услуги", callback_data="niche_creative")],
        [InlineKeyboardButton("📊 Консалтинг", callback_data="niche_consulting")],
    ]
    
    return InlineKeyboardMarkup(keyboard)

def format_answer_summary(answers: Dict[str, Any]) -> str:
    """
    Форматирование сводки ответов
    
    Args:
        answers: Словарь с ответами пользователя
    
    Returns:
        Отформатированная сводка
    """
    if not answers:
        return "📭 Ответы пока не получены"
    
    summary_lines = ["📋 *Сводка ответов:*"]
    
    for i, (question_id, answer) in enumerate(answers.items(), 1):
        # Обрезаем длинные ответы
        if isinstance(answer, str) and len(answer) > 50:
            answer_display = answer[:50] + "..."
        elif isinstance(answer, list):
            answer_display = ", ".join(map(str, answer[:3]))
            if len(answer) > 3:
                answer_display += f" и ещё {len(answer) - 3}"
        else:
            answer_display = str(answer)
        
        summary_lines.append(f"{i}. *Вопрос {question_id}:* {answer_display}")
    
    return "\n".join(summary_lines)

def create_restart_keyboard() -> InlineKeyboardMarkup:
    """
    Создание клавиатуры для перезапуска
    
    Returns:
        InlineKeyboardMarkup с кнопкой перезапуска
    """
    keyboard = [
        [InlineKeyboardButton("🔄 Начать заново", callback_data="restart_confirm")],
        [InlineKeyboardButton("❌ Отмена", callback_data="restart_cancel")]
    ]
    
    return InlineKeyboardMarkup(keyboard)

def format_openai_usage(usage: Dict[str, Any]) -> str:
    """
    Форматирование информации об использовании OpenAI
    
    Args:
        usage: Словарь с данными использования
    
    Returns:
        Отформатированная информация
    """
    if not usage:
        return "📊 *Использование OpenAI:* данные недоступны"
    
    return (
        f"📊 *Использование OpenAI:*\n"
        f"• Запросов: {usage.get('requests', 0)}\n"
        f"• Токены: {usage.get('tokens', 0)}\n"
        f"• Стоимость: ${usage.get('cost', 0):.4f}"
    )

# Если нужно, добавьте другие функции форматирования