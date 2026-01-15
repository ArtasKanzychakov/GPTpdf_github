#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утилиты для форматирования текста и клавиатур
"""

import logging
import random
from typing import Dict, Any, List, Optional
from datetime import datetime

from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from models.session import UserSession
from models.enums import NicheDetails, NicheCategory

logger = logging.getLogger(__name__)

def format_question_text(text: str, user_name: str, current_q: int, total_q: int) -> str:
    """
    Форматирование текста вопроса
    """
    # Заменяем плейсхолдеры
    formatted_text = text.replace("{user_name}", user_name) if user_name else text

    # Добавляем прогресс (только если это не первый вопрос)
    if current_q > 0 and total_q > 0:
        progress_bar = create_progress_bar(current_q, total_q)
        progress_text = f"\n\n📊 *Прогресс:* {current_q}/{total_q}\n{progress_bar}"
        formatted_text += progress_text

    return formatted_text

def create_progress_bar(current: int, total: int, length: int = 10) -> str:
    """
    Создание текстового прогресс-бара
    """
    if total == 0:
        return ""
    
    filled = int((current / total) * length)
    empty = length - filled
    return "▓" * filled + "░" * empty

def format_recommendations(recommendations: str, user_name: str) -> str:
    """
    Форматирование рекомендаций
    """
    header = f"🎯 *Персонализированные рекомендации для {user_name}*\n\n" if user_name else "🎯 *Персонализированные рекомендации*\n\n"
    footer = "\n\n---\n🤖 *Создано Бизнес-Навигатором v7.0*"

    return header + recommendations + footer

def format_session_summary(session: UserSession) -> str:
    """
    Форматирование сводки сессии
    """
    summary = [
        f"👤 *Пользователь:* {session.full_name or 'Не указано'}",
        f"🆔 *ID:* {session.user_id}",
        f"📅 *Создана:* {session.created_at.strftime('%Y-%m-%d %H:%M')}",
        f"📝 *Вопросов пройдено:* {session.current_question_index}/35",
        f"🔄 *Состояние:* {session.current_state.name}"
    ]

    if session.completion_date:
        summary.append(f"✅ *Завершена:* {session.completion_date.strftime('%Y-%m-%d %H:%M')}")

    return "\n".join(summary)

def create_niche_selection_keyboard(niches: List[NicheDetails]) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры для выбора ниши
    """
    keyboard = []
    
    for i, niche in enumerate(niches[:5], 1):  # Не более 5 ниш
        button_text = f"{i}. {niche.emoji} {niche.name}"
        callback_data = f"select_niche_{niche.id}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # Добавляем кнопки управления
    keyboard.append([
        InlineKeyboardButton("🔄 Пройти заново", callback_data="restart_questionnaire"),
        InlineKeyboardButton("📊 Мой профиль", callback_data="show_profile")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def format_answer_summary(answers: Dict[str, Any]) -> str:
    """
    Форматирование сводки ответов
    """
    if not answers:
        return "📭 Ответы пока не получены"

    summary_lines = ["📋 *Сводка ответов:*"]

    # Упрощенная версия для 35 вопросов
    for category, data in answers.items():
        if category == 'demographics':
            summary_lines.append("\n📊 *Демография:*")
            for key, value in data.items():
                summary_lines.append(f"  • {key}: {value}")
        
        elif category == 'personality':
            summary_lines.append("\n🧠 *Личность:*")
            if 'motivations' in data:
                summary_lines.append(f"  • Мотивации: {', '.join(data['motivations'][:3])}")
            if 'risk_tolerance' in data:
                summary_lines.append(f"  • Толерантность к риску: {data['risk_tolerance']}/10")
        
        elif category == 'skills':
            summary_lines.append("\n🔧 *Навыки:*")
            # Показываем только оценки > 3
            for key, value in data.items():
                if isinstance(value, int) and value > 3:
                    summary_lines.append(f"  • {key}: {value}/5")

    return "\n".join(summary_lines)

def format_niche_details(niche: NicheDetails, detailed: bool = False) -> str:
    """
    Форматирование информации о нише
    """
    if not niche:
        return "❌ Информация о нише недоступна"

    try:
        # Используем встроенный метод, если есть
        if hasattr(niche, 'full_description'):
            formatted = niche.full_description
        else:
            # Форматируем вручную
            formatted = f"{niche.emoji} *{niche.name}*\n"
            formatted += f"📊 Категория: {niche.category.value}\n"
            
            if niche.description:
                desc = niche.description[:200] + "..." if len(niche.description) > 200 else niche.description
                formatted += f"📝 {desc}\n\n"
            
            formatted += f"⏱️ Срок выхода на прибыль: {niche.time_to_profit}\n"
            
            risk_stars = "★" * niche.risk_level + "☆" * (5 - niche.risk_level)
            formatted += f"🎯 Уровень риска: {risk_stars} ({niche.risk_level}/5)\n"
            
            if niche.min_budget > 0:
                formatted += f"💰 Мин. бюджет: {niche.min_budget:,.0f} руб\n"
            
            if niche.success_rate > 0:
                formatted += f"📈 Шанс успеха: {niche.success_rate*100:.0f}%\n"
        
        # Добавляем требуемые навыки если нужно
        if detailed and hasattr(niche, 'required_skills') and niche.required_skills:
            formatted += f"\n🔧 *Требуемые навыки:*\n"
            for skill in niche.required_skills[:3]:
                formatted += f"• {skill}\n"
            if len(niche.required_skills) > 3:
                formatted += f"• ... и ещё {len(niche.required_skills) - 3}\n"
        
        # Добавляем примеры если есть
        if hasattr(niche, 'examples') and niche.examples:
            formatted += f"\n💡 *Примеры бизнесов:*\n"
            for i, example in enumerate(niche.examples[:2], 1):
                formatted += f"{i}. {example}\n"
            if len(niche.examples) > 2:
                formatted += f"• ... и ещё {len(niche.examples) - 2}\n"

        return formatted

    except Exception as e:
        logger.error(f"Ошибка форматирования ниши: {e}")
        return f"📊 *{niche.name}*\n{niche.description[:100]}..."

def format_analysis_result(analysis_text: str) -> str:
    """
    Форматирование психологического анализа
    """
    if not analysis_text:
        return "🧠 *Психологический анализ*\n\nАнализ пока не готов."

    # Ограничиваем длину и добавляем заголовок
    if len(analysis_text) > 3000:
        analysis_text = analysis_text[:3000] + "\n\n... [текст сокращен]"

    return f"🧠 *Психологический анализ вашего профиля*\n\n{analysis_text}\n\n---"

def format_openai_usage(usage_data: Dict[str, Any]) -> str:
    """
    Форматирование информации об использовании OpenAI
    
    Args:
        usage_data: Словарь с данными использования
    
    Returns:
        Отформатированная информация
    """
    if not usage_data:
        return "📊 *Использование OpenAI:* данные недоступны"
    
    try:
        # Получаем данные из объекта или словаря
        if hasattr(usage_data, 'total_requests'):
            requests = usage_data.total_requests
            tokens = usage_data.total_tokens
            cost = usage_data.total_cost
        else:
            requests = usage_data.get('total_requests', 0)
            tokens = usage_data.get('total_tokens', 0)
            cost = usage_data.get('total_cost', 0.0)
        
        # Форматируем числа
        tokens_formatted = f"{tokens:,}".replace(",", " ")
        cost_formatted = f"{cost:.4f}"
        
        return (
            f"📊 *Использование OpenAI:*\n"
            f"• Запросов: {requests}\n"
            f"• Токенов: {tokens_formatted}\n"
            f"• Стоимость: ${cost_formatted}"
        )
    except Exception as e:
        logger.error(f"Ошибка форматирования OpenAI usage: {e}")
        return "📊 *Использование OpenAI:* ошибка форматирования"

def get_random_praise() -> str:
    """
    Получить случайную похвалу
    """
    praises = [
        "🎉 Отлично!", "👏 Прекрасный ответ!", "🌟 Здорово!", "🚀 Отличная работа!",
        "💪 Мощно!", "🧠 Умно!", "🤩 Восхитительно!", "👍 Супер!", "💎 Бриллиантово!",
        "🔥 Огонь!", "✨ Блестяще!", "🏆 Победно!", "💡 Гениально!", "🎯 Точно в цель!",
        "📈 Прогресс налицо!", "🤝 Отличное понимание!", "🌱 Здоровый рост!"
    ]
    return random.choice(praises)

def get_random_encouragement() -> str:
    """
    Получить случайное ободрение
    """
    encouragements = [
        "Продолжайте в том же духе! 💪", "Вы на правильном пути! 🚀",
        "Следующий вопрос будет ещё интереснее! 🔍", "Отлично справляетесь! ⭐",
        "Так держать! 🏆", "У вас отлично получается! 👌", "Ещё чуть-чуть! 🎯",
        "Ваши ответы очень ценны! 💎", "Вы делаете важную работу! 🌟"
    ]
    return random.choice(encouragements)

def create_restart_keyboard() -> InlineKeyboardMarkup:
    """
    Создание клавиатуры для перезапуска
    """
    keyboard = [
        [InlineKeyboardButton("🔄 Начать анкету заново", callback_data="restart_questionnaire")],
        [InlineKeyboardButton("📊 Посмотреть профиль", callback_data="show_profile")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def format_user_profile(session: UserSession) -> str:
    """
    Форматирование профиля пользователя
    """
    profile = [
        "👤 *ВАШ ПРОФИЛЬ*\n",
        f"🆔 ID: {session.user_id}",
        f"📅 Дата создания: {session.created_at.strftime('%d.%m.%Y')}",
        f"🔄 Статус: {'✅ Завершено' if session.is_completed else '⏳ В процессе'}",
        f"📝 Прогресс: {session.current_question_index}/35 вопросов",
    ]
    
    if session.is_completed:
        profile.append(f"🎯 Подобрано ниш: {len(session.suggested_niches)}")
        if session.selected_niche:
            profile.append(f"📌 Выбранная ниша: {session.selected_niche.name}")
    
    return "\n".join(profile)

def format_slider_display(value: int, min_val: int, max_val: int) -> str:
    """
    Форматирование отображения ползунка
    """
    bar_length = 10
    position = int((value - min_val) / (max_val - min_val) * bar_length)
    
    bar = "[" + "█" * position + "○" + "░" * (bar_length - position - 1) + "]"
    return f"{bar} {value}/{max_val}"