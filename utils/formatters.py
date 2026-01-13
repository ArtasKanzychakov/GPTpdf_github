"""
Форматирование текста для вывода
"""
import random
from typing import Dict, List

def get_random_praise() -> str:
    """Получить случайную фразу похвалы"""
    praise_phrases = [
        "Отлично! Вижу, вы подходите к делу серьезно 👏",
        "Прекрасный ответ! Это многое проясняет 💡",
        "Замечательно! Вы раскрываетесь с каждой минутой 🌟",
        "Восхитительно! Такие ответы делают анализ максимально точным 🎯",
        "Браво! Вы мыслите нестандартно, это ценно 🚀",
        "Потрясающе! Чувствуется глубина мышления 🧠",
        "Великолепно! Вы делаете эту анкету лучше с каждым ответом 💎",
        "Изумительно! Такой анализ будет максимально персонализированным ✨",
    ]
    return random.choice(praise_phrases)

def format_progress_header(session) -> str:
    """Форматировать заголовок с прогрессом"""
    progress_bar = session.get_progress_bar()
    question_num = session.current_question
    
    emojis = ["🔴", "🟠", "🟡", "🟢", "🔵", "🟣"]
    emoji = emojis[min(question_num - 1, len(emojis) - 1)] if question_num > 0 else "🟢"
    
    return f"{emoji} *Вопрос {question_num}/{session.total_questions}*\n{progress_bar}\n\n"

def format_niche(niche: Dict, index: int, total: int) -> str:
    """Форматировать нишу для отображения"""
    steps_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(niche.get('steps', [])[:3])])
    
    return f"""🎯 *НИША {index} из {total}*

{niche.get('type', '🔥 Ниша')}

*{niche.get('name', 'Название')}*

📝 *Суть:*
{niche.get('description', 'Описание')}

✅ *Почему вам подходит:*
{niche.get('why', 'Соответствует вашему профилю')}

📊 *Детали:*
• Формат: {niche.get('format', 'Гибрид')}
• Инвестиции: {niche.get('investment', '50,000-100,000₽')}
• Окупаемость: {niche.get('roi', '3-6 месяцев')}

🚀 *Первые шаги:*
{steps_text}"""

def format_analysis(analysis: str) -> str:
    """Форматировать анализ для отображения"""
    # Ограничиваем длину для Telegram
    max_length = 4000
    
    if len(analysis) > max_length:
        analysis = analysis[:max_length] + "...\n\n📝 *Анализ продолжается в сохраненных файлах*"
    
    return f"""🧠 *ПСИХОЛОГИЧЕСКИЙ АНАЛИЗ*

{analysis}"""

def create_niche_navigation(session) -> InlineKeyboardMarkup:
    """Создать клавиатуру навигации по нишам"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    keyboard = []
    
    if session.generated_niches:
        current_idx = session.selected_niche_index
        total = len(session.generated_niches)
        
        # Кнопки навигации
        nav_buttons = []
        if current_idx > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ Предыдущая", callback_data="niche_prev"))
        
        nav_buttons.append(InlineKeyboardButton(f"{current_idx + 1}/{total}", callback_data="niche_current"))
        
        if current_idx < total - 1:
            nav_buttons.append(InlineKeyboardButton("Следующая ▶️", callback_data="niche_next"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        # Кнопки действий
        current_niche = session.generated_niches[current_idx]
        niche_id = current_niche.get('id', current_idx + 1)
        
        keyboard.append([
            InlineKeyboardButton("📋 Детальный план", callback_data=f"plan_{niche_id}")
        ])
    
    # Общие кнопки
    keyboard.append([
        InlineKeyboardButton("🧠 Психологический анализ", callback_data="show_analysis"),
        InlineKeyboardButton("💾 Сохранить все", callback_data="save_all")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🔄 Начать заново", callback_data="start_over"),
        InlineKeyboardButton("📊 Статистика", callback_data="show_stats")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def split_message(text: str, max_length: int = 4000) -> List[str]:
    """Разделить длинное сообщение на части"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break
        
        # Ищем последний перенос строки перед max_length
        split_pos = text.rfind('\n', 0, max_length)
        if split_pos == -1:
            # Ищем последний пробел
            split_pos = text.rfind(' ', 0, max_length)
            if split_pos == -1:
                split_pos = max_length
        
        parts.append(text[:split_pos].strip())
        text = text[split_pos:].strip()
    
    return parts