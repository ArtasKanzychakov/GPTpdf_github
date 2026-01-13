"""
Конфигурация бота
"""
import os
import logging
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class BotConfig:
    """Конфигурация бота"""
    
    def __init__(self):
        # Загружаем .env файл
        load_dotenv()
        
        # Пути
        self.base_dir = Path(__file__).parent.parent
        self.data_dir = self.base_dir / "data"
        self.data_dir.mkdir(exist_ok=True)
        
        # Токены и ключи
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # Настройки OpenAI
        self.openai_model = "gpt-3.5-turbo"
        self.openai_max_tokens = 4000
        self.openai_temperature = 0.7
        
        # Лимиты
        self.max_niches_to_generate = 8
        self.max_plans_to_generate = 3
        self.session_timeout_hours = 24  # Сессии живут 24 часа
        
        # Время ожидания
        self.question_timeout = 300
        self.analysis_timeout = 120
        
        # Настройки Telegram
        self.polling_timeout = 30
        self.polling_connect_timeout = 30
        self.polling_read_timeout = 30
        self.polling_write_timeout = 30
        
        # Настройки веб-сервера (для health check)
        self.port = int(os.getenv("PORT", "10000"))
        self.host = "0.0.0.0"
        
        # Фразы похвалы
        self.praise_phrases = [
            "Отлично! Вижу, вы подходите к делу серьезно 👏",
            "Прекрасный ответ! Это многое проясняет 💡",
            "Замечательно! Вы раскрываетесь с каждой минутой 🌟",
            "Восхитительно! Такие ответы делают анализ максимально точным 🎯",
            "Браво! Вы мыслите нестандартно, это ценно 🚀",
            "Потрясающе! Чувствуется глубина мышления 🧠",
            "Великолепно! Вы делаете эту анкету лучше с каждым ответом 💎",
            "Изумительно! Такой анализ будет максимально персонализированным ✨",
            "Превосходно! Вижу системный подход к самоанализу 📊",
            "Блестяще! Ваши ответы - золотая жила для подбора ниши 🏆",
        ]
        
        logger.info("📋 Конфигурация загружена")
    
    def validate(self) -> bool:
        """Валидация конфигурации"""
        errors = []
        
        if not self.telegram_token:
            errors.append("TELEGRAM_BOT_TOKEN не установлен")
        
        if not self.openai_api_key:
            logger.warning("⚠️ OPENAI_API_KEY не установлен. AI функции отключены.")
        
        if errors:
            for error in errors:
                logger.error(f"❌ {error}")
            return False
        
        logger.info("✅ Конфигурация валидна")
        return True
    
    def get_questions_path(self) -> Path:
        """Получить путь к файлу вопросов"""
        return self.base_dir / "config" / "questions.yaml"
    
    def get_prompts_dir(self) -> Path:
        """Получить путь к папке с промтами"""
        return self.base_dir / "config" / "prompts"