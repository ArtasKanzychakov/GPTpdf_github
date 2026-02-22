# ... в начале файла ...
from models.session import NicheDetails  # Было: from models.enums import NicheDetails
# ... остальной код без изменений ...
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
from models.session import UserSession, NicheDetails

logger = logging.getLogger(__name__)


def format_question_text(text: str, user_name: str, current_q: int, total_q: int) -> str:
    """Форматирование текста вопроса"""
    formatted_text = text.replace("{user_name}", user_name) if user_name else text
    
    if current_q > 0 and total_q > 0:
        from handlers.ui_components import UIComponents
        progress_bar = UIComponents.create_progress_bar(current_q, total_q)
        progress_text = f"\n📊 *Прогресс:* {current_q}/{total_q}\n{progress_bar}"
        formatted_text += progress_text
    
    return formatted_text


def format_niche_details(niche: NicheDetails, detailed: bool = False) -> str:
    """Форматирование информации о нише"""
    if not niche:
        return "❌ Информация о нише недоступна"
    
    try:
        formatted = f"{niche.emoji} *{niche.name}*\n"
        formatted += f"📊 Категория: {niche.category}\n"
        
        if niche.description:
            desc = niche.description[:200] + "..." if len(niche.description) > 200 else niche.description
            formatted += f"📝 {desc}\n"
        
        formatted += f"⏱️ Срок выхода на прибыль: {niche.time_to_profit}\n"
        risk_stars = "★" * niche.risk_level + "☆" * (5 - niche.risk_level)
        formatted += f"🎯 Уровень риска: {risk_stars} ({niche.risk_level}/5)\n"
        
        if niche.min_budget > 0:
            formatted += f"💰 Мин. бюджет: {niche.min_budget:,.0f} руб\n"
        
        if niche.success_rate > 0:
            formatted += f"📈 Шанс успеха: {niche.success_rate*100:.0f}%\n"
        
        return formatted
    except Exception as e:
        logger.error(f"Ошибка форматирования ниши: {e}")
        return f"📊 *{niche.name}*\n{niche.description[:100]}..."


def format_analysis_result(analysis_text: str) -> str:
    """Форматирование психологического анализа"""
    if not analysis_text:
        return "🧠 *Психологический анализ*\nАнализ пока не готов."
    
    if len(analysis_text) > 3000:
        analysis_text = analysis_text[:3000] + "\n... [текст сокращен]"
    
    return f"🧠 *Психологический анализ вашего профиля*\n{analysis_text}\n---"
