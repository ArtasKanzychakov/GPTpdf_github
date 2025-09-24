import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
import openai
from openai import OpenAI
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove

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

# Определяем состояния для ConversationHandler
GET_QUESTION_1, GET_QUESTION_2, GENERATE_NICHES = range(3)

# Тексты вопросов и кнопки
QUESTIONS = {
    GET_QUESTION_1: "Вопрос 1: Что вам больше нравится? Работа с людьми или работа с данными? (Ответьте: 'С людьми' или 'С данными')",
    GET_QUESTION_2: "Вопрос 2: Какими тремя словами вы бы описали свои основные интересы и увлечения? (Например: 'творчество, спорт, технологии')"
}

# Отвечать на эти вопросы с помощью кнопок
REPLY_KEYBOARD = [["С людьми", "С данными"]]
REPLY_MARKUP = ReplyKeyboardMarkup(REPLY_KEYBOARD, one_time_keyboard=True, resize_keyboard=True)

# Команды и обработчики
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает диалог с пользователем."""
    await update.message.reply_text(
        "Привет! Я помогу тебе найти нишу для бизнеса. Давай начнём анкету. "
        "Пожалуйста, ответь на первый вопрос, используя кнопки ниже:",
        reply_markup=REPLY_MARKUP
    )
    await update.message.reply_text(QUESTIONS[GET_QUESTION_1])
    context.user_data['answers'] = {}
    return GET_QUESTION_1

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет сообщение-помощь, когда пользователь отправляет команду /help."""
    help_text = (
        "Привет! Я бот для поиска бизнес-ниш.\n\n"
        "Доступные команды:\n"
        "/start - Начать анкету для подбора ниши.\n"
        "/cancel - Отменить текущую анкету.\n"
        "/reset - Сбросить анкету и начать заново.\n"
        "/help - Показать это сообщение."
    )
    await update.message.reply_text(help_text)

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбрасывает анкету."""
    await update.message.reply_text('Анкета сброшена. Чтобы начать заново, используйте команду /start.')
    return ConversationHandler.END

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет диалог."""
    await update.message.reply_text(
        "Диалог отменен. Чтобы начать заново, используйте команду /start."
    )
    return ConversationHandler.END

# Обработчики состояний ConversationHandler
async def get_q1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ответ на первый вопрос и задает второй."""
    user_answer = update.message.text
    context.user_data['answers']['q1'] = user_answer
    logger.info(f"Answer to Q1: {user_answer}")

    await update.message.reply_text(
        "Спасибо! Теперь ответьте на следующий вопрос.",
        reply_markup=ReplyKeyboardRemove()
    )
    await update.message.reply_text(QUESTIONS[GET_QUESTION_2])

    return GET_QUESTION_2

async def get_q2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ответ на второй вопрос и переходит к генерации."""
    user_answer = update.message.text
    context.user_data['answers']['q2'] = user_answer
    logger.info(f"Answer to Q2: {user_answer}")

    await update.message.reply_text("Отлично! Ваши ответы собраны. Сейчас я сгенерирую для вас 10 бизнес-ниш...")
    
    # Формируем промпт для OpenAI
    answers = context.user_data['answers']
    prompt = f"""
    На основе следующих ответов пользователя, предложи 10 креативных идей для бизнес-ниш:
    - Вопрос 1 (что нравится): {answers.get('q1')}
    - Вопрос 2 (основные интересы): {answers.get('q2')}
    
    Сформируй промпт для ChatGPT, который будет предлагать 10 ниш, учитывая наклонности пользователя.
    """
    
    try:
        completion = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Ты - опытный бизнес-консультант, специализирующийся на поиске уникальных ниш."},
                {"role": "user", "content": prompt}
            ]
        )
        bot_response = completion.choices[0].message.content
        await update.message.reply_text(bot_response)

    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        await update.message.reply_text("Произошла ошибка при обращении к AI. Попробуйте позже.")

    # Завершаем диалог
    return ConversationHandler.END

# Обработчик ошибок
async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Логирует ошибки."""
    logger.error(f'Update {update} caused error {context.error}')

def main():
    """Запускает бота."""
    logger.info('Starting bot...')
    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()

        # Создаем обработчик для диалога
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start_command)],
            states={
                GET_QUESTION_1: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, get_q1
                    )
                ],
                GET_QUESTION_2: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, get_q2
                    )
                ],
            },
            fallbacks=[CommandHandler('cancel', cancel_command), CommandHandler('reset', reset_command)],
        )

        app.add_handler(conv_handler)
        app.add_handler(CommandHandler('help', help_command))
        app.add_error_handler(error)

        logger.info('Polling...')
        app.run_polling()

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == '__main__':
    main()
