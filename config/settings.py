"""
Конфигурация бота - получение переменных из окружения Render
"""
import os
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class BotConfig:
    """Конфигурация бота"""
    
    def __init__(self):
        # Пути
        self.base_dir = Path(__file__).parent.parent
        self.data_dir = self.base_dir / "data"
        self.data_dir.mkdir(exist_ok=True)
        
        # Токены и ключи ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ RENDER
        # Получаем токен из переменных окружения
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        
        # OpenAI ключ (опционально)
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
        
        # Настройки Telegram polling (важно для стабильности)
        self.polling_timeout = 30
        self.polling_connect_timeout = 30
        self.polling_read_timeout = 30
        self.polling_write_timeout = 30
        self.polling_poll_interval = 1.0
        
        # Настройки веб-сервера для health check (Render)
        # PORT переменная автоматически устанавливается Render
        self.port = int(os.getenv("PORT", "10000"))
        self.host = "0.0.0.0"  # Обязательно для Render
        
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
        
        # Логируем конфигурацию (без ключей!)
        logger.info("📋 Конфигурация загружена")
        logger.info(f"  • Python: {os.sys.version}")
        logger.info(f"  • Telegram Bot: {'✅' if self.telegram_token else '❌'}")
        logger.info(f"  • OpenAI: {'✅' if self.openai_api_key else '⚠️ (базовый режим)'}")
        logger.info(f"  • Port: {self.port}")
        logger.info(f"  • Host: {self.host}")
        logger.info(f"  • Data dir: {self.data_dir}")
    
    def validate(self) -> bool:
        """Валидация конфигурации"""
        errors = []
        
        if not self.telegram_token:
            errors.append("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        
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