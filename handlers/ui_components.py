#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI компоненты для визуализации - DEMO VERSION
"""
from typing import List, Dict, Any, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class UIComponents:
    """Вспомогательные компоненты для создания UI"""
    
    @staticmethod
    def create_progress_bar(current: int, total: int, length: int = 10) -> str:
        """Создать прогресс-бар"""
        filled = int((current / total) * length)
        bar = "█" * filled + "░" * (length - filled)
        percentage = int((current / total) * 100)
        return f"`{bar}` {percentage}%"
    
    @staticmethod
    def create_star_rating(current: int, max_stars: int = 5) -> str:
        """Создать визуализацию звездного рейтинга"""
        filled = "⭐" * current
        empty = "☆" * (max_stars - current)
        return f"{filled}{empty}"
    
    @staticmethod
    def create_slider_visual(current: int, min_val: int, max_val: int, width: int = 10) -> str:
        """Создать визуализацию слайдера"""
        normalized = (current - min_val) / (max_val - min_val)
        filled_width = int(normalized * width)
        filled = "█" * filled_width
        empty = "░" * (width - filled_width)
        return f"`{min_val} {filled}{empty} {max_val}`"
    
    @staticmethod
    def create_energy_bars(energy_data: Dict[str, int]) -> str:
        """Создать визуализацию энергетических уровней"""
        bars = []
        emojis = {'morning': '🌅', 'day': '☀️', 'evening': '🌙'}
        
        for period, level in energy_data.items():
            emoji = emojis.get(period, '⚡')
            bar = "▇" * level + "▁" * (7 - level)
            bars.append(f"{emoji} `{bar}` ({level}/7)")
        
        return "\n".join(bars)
    
    @staticmethod
    def create_allocation_display(allocation: Dict[str, int], total: int) -> str:
        """Создать отображение распределения баллов"""
        lines = []
        used = sum(allocation.values())
        
        for category, points in allocation.items():
            if points > 0:
                bar = "█" * points + "░" * (total - points)
                lines.append(f"`{category}: {bar} ({points})`")
        
        remaining = total - used
        lines.append(f"\n📊 Использовано: `{used}/{total}`")
        lines.append(f"💡 Осталось: `{remaining}`")
        
        return "\n".join(lines)
    
    @staticmethod
    def create_copyable_text(text: str, label: str = "📋") -> str:
        """Создать копируемый блок текста"""
        return f"{label}\n```\n{text}\n```"
    
    @staticmethod
    def create_stats_table(data: Dict[str, Any]) -> str:
        """Создать таблицу статистики"""
        lines = ["📊 *Статистика:*"]
        for key, value in data.items():
            lines.append(f"• `{key}`: {value}")
        return "\n".join(lines)
    
    @staticmethod
    def create_demo_badge() -> str:
        """Создать бейдж демо-режима"""
        return "⚠️ *DEMO MODE*\n_Бот работает в демонстрационном режиме_"
    
    @staticmethod
    def format_multiselect_status(selected: List[str], min_choices: int, max_choices: int) -> str:
        """Форматировать статус множественного выбора"""
        count = len(selected)
        if count < min_choices:
            return f"❌ Выбрано `{count}` из минимум `{min_choices}`"
        elif count > max_choices:
            return f"⚠️ Выбрано `{count}`, максимум `{max_choices}`"
        else:
            return f"✅ Выбрано `{count}` (мин: `{min_choices}`, макс: `{max_choices}`)"
    
    @staticmethod
    def create_completion_summary(answers_count: int, total_questions: int = 10) -> str:
        """Создать сводку о заполнении анкеты"""
        percentage = int((answers_count / total_questions) * 100)
        bar = UIComponents.create_progress_bar(answers_count, total_questions)
        
        return f"""
📋 Прогресс анкеты:
{bar}
Отвечено на `{answers_count}` из `{total_questions}` вопросов
"""
    
    @staticmethod
    def create_navigation_buttons(show_back: bool = True, show_skip: bool = False, show_submit: bool = False) -> List[List[InlineKeyboardButton]]:
        """Создать кнопки навигации"""
        buttons = []
        row = []
        
        if show_back:
            row.append(InlineKeyboardButton("⬅️ Назад", callback_data="back"))
        if show_skip:
            row.append(InlineKeyboardButton("⏭️ Пропустить", callback_data="skip"))
        if row:
            buttons.append(row)
        
        if show_submit:
            buttons.append([InlineKeyboardButton("✅ Продолжить", callback_data="submit")])
        
        return buttons
    
    @staticmethod
    def create_category_header(category_name: str, emoji: str = "📌") -> str:
        """Создать заголовок категории"""
        separator = "═" * 25
        return f"\n{separator}\n{emoji} *{category_name.upper()}*\n{separator}\n"
    
    @staticmethod
    def create_info_box(title: str, content: str, emoji: str = "ℹ️") -> str:
        """Создать информационный блок"""
        return f"{emoji} *{title}*\n```\n{content}\n```"


class QuestionFormatter:
    """Форматирование вопросов для отображения"""
    
    @staticmethod
    def format_with_context(question_text: str, question_num: int, total_questions: int = 10, category_emoji: str = "📝") -> str:
        """Форматировать вопрос с контекстом"""
        progress = UIComponents.create_progress_bar(question_num, total_questions, length=10)
        
        return f"""
{progress}
Вопрос {question_num} из {total_questions}
{category_emoji} {question_text}
"""
    
    @staticmethod
    def add_hint(text: str, hint: str) -> str:
        """Добавить подсказку к тексту"""
        return f"{text}\n\n💡 `{hint}`"
    
    @staticmethod
    def add_example(text: str, example: str) -> str:
        """Добавить пример к тексту"""
        return f"{text}\n\n📖 *Пример:*\n```\n{example}\n```"


class LoadingMessages:
    """Сообщения о загрузке"""
    ANALYZING = """
⏳ Анализирую ваши ответы...
Пожалуйста, подождите 2-3 секунды.
Бот работает в демонстрационном режиме"""
    
    GENERATING_NICHES = """
🔄 Генерирую персональные ниши...
Это займёт около 2 секунд.
"""
    
    CREATING_PLAN = """
📝 Создаю детальный план...
Секундочку...
"""
    
    @staticmethod
    def create_animated_loader(step: int = 0) -> str:
        """Создать анимированный загрузчик"""
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        return frames[step % len(frames)]


class SuccessMessages:
    """Сообщения об успехе"""
    QUESTIONNAIRE_COMPLETED = """
🎊 Поздравляем! Анкета заполнена!
Сейчас я проанализирую ваши ответы...
⏳ Это займёт около 5-10 секунд...
⚠️ Бот работает в демонстрационном режиме"""
