"""
UI компоненты для визуализации интерактивных элементов
"""
from typing import List, Dict, Any, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class UIComponents:
    """Вспомогательные компоненты для создания UI"""
    
    @staticmethod
    def create_progress_bar(current: int, total: int, length: int = 10) -> str:
        """
        Создать прогресс-бар
        
        Args:
            current: Текущее значение
            total: Максимальное значение
            length: Длина бара
        
        Returns:
            Строка с прогресс-баром
        """
        filled = int((current / total) * length)
        bar = "█" * filled + "░" * (length - filled)
        percentage = int((current / total) * 100)
        return f"{bar} {percentage}%"
    
    @staticmethod
    def create_star_rating(current: int, max_stars: int = 5) -> str:
        """
        Создать визуализацию звездного рейтинга
        
        Args:
            current: Текущий рейтинг
            max_stars: Максимальное количество звезд
        
        Returns:
            Строка со звездами
        """
        filled = "⭐" * current
        empty = "☆" * (max_stars - current)
        return f"{filled}{empty}"
    
    @staticmethod
    def create_slider_visual(
        current: int, 
        min_val: int, 
        max_val: int,
        width: int = 10,
        filled_char: str = "█",
        empty_char: str = "░"
    ) -> str:
        """
        Создать визуализацию слайдера
        
        Args:
            current: Текущее значение
            min_val: Минимум
            max_val: Максимум
            width: Ширина слайдера
            filled_char: Символ заполненной части
            empty_char: Символ пустой части
        
        Returns:
            Строка со слайдером
        """
        normalized = (current - min_val) / (max_val - min_val)
        filled_width = int(normalized * width)
        
        filled = filled_char * filled_width
        empty = empty_char * (width - filled_width)
        
        return f"{min_val} {filled}{empty} {max_val}"
    
    @staticmethod
    def create_energy_bars(energy_data: Dict[str, int]) -> str:
        """
        Создать визуализацию энергетических уровней
        
        Args:
            energy_data: Словарь {период: уровень}
        
        Returns:
            Форматированный текст
        """
        bars = []
        emojis = {
            'morning': '🌅',
            'day': '☀️',
            'evening': '🌙'
        }
        
        for period, level in energy_data.items():
            emoji = emojis.get(period, '⚡')
            bar = "▇" * level + "▁" * (7 - level)
            bars.append(f"{emoji} {bar} ({level}/7)")
        
        return "\n".join(bars)
    
    @staticmethod
    def create_allocation_display(allocation: Dict[str, int], total: int) -> str:
        """
        Создать отображение распределения баллов
        
        Args:
            allocation: Словарь {категория: баллы}
            total: Общее количество баллов
        
        Returns:
            Форматированный текст
        """
        lines = []
        used = sum(allocation.values())
        
        for category, points in allocation.items():
            if points > 0:
                bar = "█" * points + "░" * (total - points)
                lines.append(f"{category}: {bar} ({points})")
        
        remaining = total - used
        lines.append(f"\n📊 Использовано: {used}/{total}")
        lines.append(f"💡 Осталось: {remaining}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_multiselect_status(
        selected: List[str], 
        min_choices: int, 
        max_choices: int
    ) -> str:
        """
        Форматировать статус множественного выбора
        
        Args:
            selected: Список выбранных элементов
            min_choices: Минимум выборов
            max_choices: Максимум выборов
        
        Returns:
            Строка статуса
        """
        count = len(selected)
        
        if count < min_choices:
            return f"❌ Выбрано {count} из минимум {min_choices}"
        elif count > max_choices:
            return f"⚠️ Выбрано {count}, максимум {max_choices}"
        else:
            return f"✅ Выбрано {count} (мин: {min_choices}, макс: {max_choices})"
    
    @staticmethod
    def create_completion_summary(answers_count: int, total_questions: int = 18) -> str:
        """
        Создать сводку о заполнении анкеты
        
        Args:
            answers_count: Количество ответов
            total_questions: Всего вопросов
        
        Returns:
            Форматированный текст
        """
        percentage = int((answers_count / total_questions) * 100)
        bar = UIComponents.create_progress_bar(answers_count, total_questions)
        
        return f"""
📋 Прогресс анкеты:
{bar}

Отвечено на {answers_count} из {total_questions} вопросов
"""
    
    @staticmethod
    def create_navigation_buttons(
        show_back: bool = True,
        show_skip: bool = False,
        show_submit: bool = False
    ) -> List[List[InlineKeyboardButton]]:
        """
        Создать кнопки навигации
        
        Args:
            show_back: Показать кнопку "Назад"
            show_skip: Показать кнопку "Пропустить"
            show_submit: Показать кнопку "Продолжить"
        
        Returns:
            Список рядов кнопок
        """
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
    def format_demographic_summary(demographic_data: Dict[str, Any]) -> str:
        """
        Форматировать сводку демографических данных
        
        Args:
            demographic_data: Демографические данные
        
        Returns:
            Форматированный текст
        """
        age = demographic_data.get('age_group', 'не указано')
        education = demographic_data.get('education', 'не указано')
        city = demographic_data.get('city', 'не указано')
        
        return f"""
👤 Ваши данные:
• Возраст: {age}
• Образование: {education}
• Город: {city}
"""
    
    @staticmethod
    def create_category_header(category_name: str, emoji: str = "📌") -> str:
        """
        Создать заголовок категории
        
        Args:
            category_name: Название категории
            emoji: Эмодзи категории
        
        Returns:
            Форматированный заголовок
        """
        separator = "═" * 30
        return f"""
{separator}
{emoji} {category_name.upper()}
{separator}
"""


class QuestionFormatter:
    """Форматирование вопросов для отображения"""
    
    @staticmethod
    def format_with_context(
        question_text: str,
        question_num: int,
        total_questions: int = 18,
        category_emoji: str = "📝"
    ) -> str:
        """
        Форматировать вопрос с контекстом
        
        Args:
            question_text: Текст вопроса
            question_num: Номер вопроса
            total_questions: Всего вопросов
            category_emoji: Эмодзи категории
        
        Returns:
            Форматированный текст
        """
        progress = UIComponents.create_progress_bar(question_num, total_questions, length=18)
        
        return f"""
{progress}
Вопрос {question_num} из {total_questions}

{category_emoji} {question_text}
"""
    
    @staticmethod
    def add_hint(text: str, hint: str) -> str:
        """
        Добавить подсказку к тексту
        
        Args:
            text: Основной текст
            hint: Текст подсказки
        
        Returns:
            Текст с подсказкой
        """
        return f"{text}\n\n💡 {hint}"
    
    @staticmethod
    def add_example(text: str, example: str) -> str:
        """
        Добавить пример к тексту
        
        Args:
            text: Основной текст
            example: Текст примера
        
        Returns:
            Текст с примером
        """
        return f"{text}\n\n📖 Пример:\n{example}"


class ErrorMessages:
    """Стандартные сообщения об ошибках"""
    
    REQUIRED_FIELD = "❌ Это обязательный вопрос. Пожалуйста, выберите вариант ответа."
    MIN_LENGTH = "❌ Ответ слишком короткий. Минимум: {} символов."
    MAX_LENGTH = "❌ Ответ слишком длинный. Максимум: {} символов."
    MIN_CHOICES = "❌ Выберите минимум {} вариант(ов)."
    MAX_CHOICES = "❌ Максимум {} вариант(ов)."
    INVALID_NUMBER = "❌ Введите корректное число."
    SUM_MISMATCH = "❌ Сумма должна быть равна {}. Текущая сумма: {}."
    
    @staticmethod
    def format_validation_error(error_type: str, **kwargs) -> str:
        """
        Форматировать сообщение об ошибке валидации
        
        Args:
            error_type: Тип ошибки
            **kwargs: Параметры для форматирования
        
        Returns:
            Форматированное сообщение
        """
        messages = {
            'required': ErrorMessages.REQUIRED_FIELD,
            'min_length': ErrorMessages.MIN_LENGTH,
            'max_length': ErrorMessages.MAX_LENGTH,
            'min_choices': ErrorMessages.MIN_CHOICES,
            'max_choices': ErrorMessages.MAX_CHOICES,
            'invalid_number': ErrorMessages.INVALID_NUMBER,
            'sum_mismatch': ErrorMessages.SUM_MISMATCH,
        }
        
        message = messages.get(error_type, "❌ Ошибка валидации.")
        
        try:
            return message.format(**kwargs)
        except:
            return message


class SuccessMessages:
    """Стандартные сообщения об успехе"""
    
    ANSWER_SAVED = "✅ Ответ сохранен!"
    CATEGORY_COMPLETED = "🎉 Раздел '{}' завершен!"
    QUESTIONNAIRE_COMPLETED = """
🎊 Поздравляем! Анкета заполнена!

Сейчас я проанализирую ваши ответы и подготовлю персональные рекомендации.

⏳ Это займет около 30-60 секунд...
"""
    
    @staticmethod
    def format_category_completion(category_name: str, next_category: str) -> str:
        """
        Форматировать сообщение о завершении категории
        
        Args:
            category_name: Название завершенной категории
            next_category: Название следующей категории
        
        Returns:
            Форматированное сообщение
        """
        return f"""
✅ Раздел "{category_name}" завершен!

➡️ Переходим к разделу "{next_category}"
"""


class LoadingMessages:
    """Сообщения о загрузке"""
    
    ANALYZING = """
⏳ Анализирую ваши ответы...

Пожалуйста, подождите 30-60 секунд.
"""
    
    GENERATING_NICHES = """
🔄 Генерирую персональные бизнес-ниши...

Это может занять до минуты.
"""
    
    CREATING_PLAN = """
📝 Создаю детальный 90-дневный план...

Секундочку...
"""
    
    GENERATING_PDF = """
📄 Генерирую PDF-отчет...

Почти готово!
"""
    
    @staticmethod
    def create_animated_loader(step: int = 0) -> str:
        """
        Создать анимированный загрузчик
        
        Args:
            step: Шаг анимации (0-3)
        
        Returns:
            Строка с анимацией
        """
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        return frames[step % len(frames)]