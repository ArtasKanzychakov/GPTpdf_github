import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
from requests.exceptions import RequestException

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# Проверка переменных окружения
if not TELEGRAM_TOKEN or not DEEPSEEK_API_KEY:
    logger.critical("Не заданы TELEGRAM_BOT_TOKEN или DEEPSEEK_API_KEY!")
    raise ValueError("TELEGRAM_BOT_TOKEN и DEEPSEEK_API_KEY должны быть установлены")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Я бот с DeepSeek AI. Отправь мне сообщение, и я отвечу.')

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
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.7
        }
        
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data)
        response.raise_for_status()
        
        bot_response = response.json()['choices'][0]['message']['content']
    
    except RequestException as e:
        if response.status_code == 401:
            bot_response = "Ошибка: неверный API-ключ DeepSeek. Проверьте настройки бота."
            logger.error("Invalid DeepSeek API key")
        elif response.status_code == 429:
            bot_response = "Превышен лимит запросов. Попробуйте позже."
            logger.error("DeepSeek rate limit exceeded")
        else:
            bot_response = f"Ошибка API DeepSeek: {str(e)}"
            logger.error(f"DeepSeek API error: {e}")
    
    except Exception as e:
        bot_response = "Произошла неизвестная ошибка."
        logger.error(f"Unexpected error: {e}")
    
    await update.message.reply_text(bot_response)

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f'Update {update} caused error {context.error}')

if __name__ == '__main__':
    logger.info('Starting bot...')
    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()
        
        app.add_handler(CommandHandler('start', start_command))
        app.add_handler(CommandHandler('help', help_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_error_handler(error)
        
        logger.info('Polling...')
        app.run_polling()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
