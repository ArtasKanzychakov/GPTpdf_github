import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import openai
from openai import OpenAI
import httpx # Рекомендуется для асинхронных запросов в `python-telegram-bot`

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = "gpt-3.5-turbo" # Или "gpt-4", если у вас есть доступ

# Проверка переменных окружения
if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    logger.critical("Не заданы TELEGRAM_BOT_TOKEN или OPENAI_API_KEY!")
    raise ValueError("TELEGRAM_BOT_TOKEN и OPENAI_API_KEY должны быть установлены")

# Инициализация OpenAI клиента
openai_client = OpenAI(api_key=OPENAI_API_KEY)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет приветственное сообщение и начинает анкету."""
    await update.message.reply_text('Привет! Я помогу тебе найти нишу для бизнеса. Давай начнём анкету. Напиши "Начать", чтобы продолжить.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет справочное сообщение."""
    help_text = """
    Доступные команды:
    /start - Начать анкету
    /help - Получить помощь
    /reset - Сбросить анкету
    """
    await update.message.reply_text(help_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения пользователя."""
    user_message = update.message.text
    logger.info(f"User message: {user_message}")

    # В этой части будет логика анкеты
    # Сейчас она просто отправляет сообщение в OpenAI
    await update.message.reply_text("Спасибо за ваше сообщение! Я пока не готов отвечать, но скоро эта функция появится. Пока вы можете пообщаться со мной.")

    try:
        completion = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message}
            ]
        )
        bot_response = completion.choices[0].message.content

    except openai.APIError as e:
        logger.error(f"OpenAI API error: {e}")
        bot_response = "Произошла ошибка при обращении к OpenAI API. Пожалуйста, попробуйте позже."
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error with OpenAI API: {e}")
        if e.response.status_code == 401:
            bot_response = "Ошибка: неверный API-ключ OpenAI. Проверьте настройки бота."
        else:
            bot_response = "Произошла ошибка при обращении к API. Пожалуйста, попробуйте позже."
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        bot_response = "Произошла неизвестная ошибка."

    await update.message.reply_text(bot_response)

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Логирует ошибки, вызванные обновлениями."""
    logger.error(f'Update {update} caused error {context.error}')

def main():
    """Запускает бота."""
    logger.info('Starting bot...')
    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()

        # Добавляем обработчики
        app.add_handler(CommandHandler('start', start_command))
        app.add_handler(CommandHandler('help', help_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_error_handler(error)

        logger.info('Polling...')
        app.run_polling(poll_interval=1.0)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == '__main__':
    main()
