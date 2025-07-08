import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import openai

# Конфигурация
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Инициализация OpenAI
import openai
from openai import OpenAIError

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
    print(f'Update {update} caused error {context.error}')

if __name__ == '__main__':
    print('Starting bot...')
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    
    # Сообщения
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    
    # Ошибки
    app.add_error_handler(error)
    
    # Опрос сервера Telegram
    print('Polling...')
    app.run_polling()
