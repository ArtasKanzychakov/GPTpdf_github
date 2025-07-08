import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import openai

# Корректный импорт исключений OpenAI
from openai.error import (
    AuthenticationError,
    RateLimitError,
    APIError
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Проверка переменных окружения
if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    logger.critical("Не заданы TELEGRAM_BOT_TOKEN или OPENAI_API_KEY!")
    raise ValueError("TELEGRAM_BOT_TOKEN и OPENAI_API_KEY должны быть установлены")

# Инициализация OpenAI
openai.api_key = OPENAI_API_KEY

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Я бот с ChatGPT 3.5. Отправь мне сообщение, и я отвечу.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
    Доступные команды:
    /start - Начать диалог
    /help - Получить помощь
    Просто напиши сообщение, и я отвечу!
    """
    await update.message.reply_text(help_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    logger.info(f"User message: {user_message}")
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7
        )
        bot_response = response.choices[0].message['content']
    
    except AuthenticationError:
        bot_response = "Ошибка: неверный API-ключ OpenAI. Проверьте настройки бота."
        logger.error("Invalid OpenAI API key")
    
    except RateLimitError:
        bot_response = "Превышен лимит запросов. Попробуйте позже."
        logger.error("OpenAI rate limit exceeded")
    
    except APIError as e:
        bot_response = f"Ошибка API OpenAI: {e}"
        logger.error(f"OpenAI API error: {e}")
    
    except Exception as e:
        bot_response = "Произошла неизвестная ошибка."
        logger.error(f"Unexpected error: {e}")
    
    await update.message.
