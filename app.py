import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import openai
from openai import OpenAIError

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
    logger.error("Не заданы TELEGRAM_BOT_TOKEN или OPENAI_API_KEY!")
    exit(1)

# Инициализация OpenAI
openai.api_key = OPENAI_API_KEY

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text('Привет! Я бот с ChatGPT 3.5. Отправь мне сообщение, и я отвечу.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
    Доступные команды:
    /start - Начать диалог
    /help - Получить помощь
    Просто напиши сообщение, и я отвечу!
    """
    await update.message.reply_text(help_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
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
    
    except openai.error.AuthenticationError:
        bot_response = "Ошибка: неверный API-ключ OpenAI. Проверьте настройки бота."
        logger.error("Invalid OpenAI API key")
    
    except openai.error.RateLimitError:
        bot_response = "Превышен лимит запросов. Попробуйте позже."
        logger.error("OpenAI rate limit exceeded")
    
    except openai.error.APIError as e:
        bot_response = f"Ошибка API OpenAI: {e}"
        logger.error(f"OpenAI API error: {e}")
    
    except Exception as e:
        bot_response = "Произошла неизвестная ошибка."
        logger.error(f"Unexpected error: {e}")
    
    await update.message.reply_text(bot_response)

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f'Update {update} caused error {context.error}')

if __name__ == '__main__':
    logger.info('Starting bot...')
    
    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Команды
        app.add_handler(CommandHandler('start', start_command))
        app.add_handler(CommandHandler('help', help_command))
        
        # Сообщения
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Ошибки
        app.add_error_handler(error)
        
        logger.info('Polling...')
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            timeout=30,
            connect_timeout=10,
            pool_timeout=10
        )
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
