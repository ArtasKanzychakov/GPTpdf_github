import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from openai import OpenAI
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import json

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
START, *QUESTIONS_STATES, GENERATE_NICHES, NICHE_SELECTION, GENERATE_PLAN = range(23)

# Вопросы и кнопки-ответы
QUIZ_QUESTIONS = [
    {
        "text": "Вопрос 1: Как вы относитесь к риску?",
        "options": [["Высокий (готов на всё)"], ["Умеренный (взвешенный подход)"], ["Низкий (предпочитаю стабильность)"]]
    },
    {
        "text": "Вопрос 2: Какой тип работы вам ближе?",
        "options": [["С людьми", "С данными/информацией"], ["С товарами/продуктами", "С услугами"]]
    },
    {
        "text": "Вопрос 3: Вы работаете один или в команде?",
        "options": [["Один", "В команде"]]
    },
    {
        "text": "Вопрос 4: Какое ваше хобби или увлечение?",
        "options": None
    },
    {
        "text": "Вопрос 5: Насколько вы готовы инвестировать личное время?",
        "options": [["1-5 часов в неделю"], ["5-15 часов в неделю"], ["Более 15 часов в неделю"]]
    },
    {
        "text": "Вопрос 6: Готовы ли вы обучаться новому?",
        "options": [["Да, всегда"], ["Да, если нужно"], ["Нет, предпочитаю использовать то, что уже знаю"]]
    },
    {
        "text": "Вопрос 7: Какой уровень дохода вы ожидаете в первый год?",
        "options": [["Дополнительный доход"], ["Средний доход"], ["Основной доход"]]
    },
    {
        "text": "Вопрос 8: Какими уникальными навыками вы обладаете?",
        "options": None
    },
    {
        "text": "Вопрос 9: Какие сферы вас вдохновляют?",
        "options": None
    },
    {
        "text": "Вопрос 10: Какая ваша самая сильная черта характера?",
        "options": None
    },
    {
        "text": "Вопрос 11: Готовы ли вы работать по выходным?",
        "options": [["Да"], ["Нет"]]
    },
    {
        "text": "Вопрос 12: Как вы относитесь к конкуренции?",
        "options": [["Конкуренция — это хорошо"], ["Предпочитаю избегать"]]
    },
    {
        "text": "Вопрос 13: Что для вас важнее: инновации или проверенные методы?",
        "options": [["Инновации"], ["Проверенные методы"]]
    },
    {
        "text": "Вопрос 14: Какой у вас стартовый капитал?",
        "options": [["< 50 000 руб."], ["50 000 - 200 000 руб."], ["200 000 - 1 000 000 руб."], ["> 1 000 000 руб."]]
    },
    {
        "text": "Вопрос 15: Вы работаете в найме или на себя?",
        "options": [["На себя"], ["В найме"]]
    },
    {
        "text": "Вопрос 16: Какая ваша самая большая неудача в карьере?",
        "options": None
    },
    {
        "text": "Вопрос 17: Какие ваши основные ценности в жизни?",
        "options": None
    },
    {
        "text": "Вопрос 18: Что для вас означает успех?",
        "options": None
    },
    {
        "text": "Вопрос 19: Какую проблему вы бы хотели решить для других людей?",
        "options": None
    },
    {
        "text": "Вопрос 20: Что вас больше мотивирует: деньги, признание, или влияние?",
        "options": [["Деньги"], ["Признание"], ["Влияние"]]
    }
]

# Команды
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает опрос и задает первый вопрос."""
    await update.message.reply_text("Привет! Я помогу тебе найти нишу для бизнеса. "
                                    "Давай начнём анкету из 20 вопросов.",
                                    reply_markup=ReplyKeyboardRemove())

    context.user_data['answers'] = {}
    context.user_data['question_index'] = 0

    return await ask_question(update, context)

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
    await update.message.reply_text(help_text, reply_markup=ReplyKeyboardRemove())

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбрасывает анкету."""
    await update.message.reply_text('Анкета сброшена. Чтобы начать заново, используйте команду /start.', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет диалог."""
    await update.message.reply_text(
        "Диалог отменен. Чтобы начать заново, используйте команду /start."
    )
    return ConversationHandler.END

# Обработчики состояний ConversationHandler
async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет текущий вопрос пользователю."""
    q_index = context.user_data['question_index']
    question_data = QUIZ_QUESTIONS[q_index]

    keyboard = None
    if question_data["options"]:
        keyboard = ReplyKeyboardMarkup(question_data["options"], one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(question_data["text"], reply_markup=keyboard)

    return q_index

async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ответ на вопрос."""
    q_index = context.user_data['question_index']
    user_answer = update.message.text
    context.user_data['answers'][f'q{q_index + 1}'] = user_answer
    logger.info(f"Answer to Q{q_index + 1}: {user_answer}")

    context.user_data['question_index'] += 1

    if context.user_data['question_index'] < len(QUIZ_QUESTIONS):
        return await ask_question(update, context)
    else:
        await update.message.reply_text("Спасибо! Анкета завершена. "
                                        "Сейчас я проанализирую ваши ответы и сгенерирую 10 бизнес-ниш...",
                                        reply_markup=ReplyKeyboardRemove())
        return await generate_niches(update, context)

async def generate_niches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерирует 10 ниш на основе ответов."""
    answers = context.user_data['answers']
    prompt = f"""
    На основе следующих ответов пользователя, предложи 10 креативных идей для бизнес-ниш:
    {json.dumps(answers, indent=2, ensure_ascii=False)}
    
    Сформируй 10 ниш в виде простого нумерованного списка, без лишнего текста. Каждая ниша должна быть короткой и емкой.
    """
    
    try:
        completion = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Ты - эксперт по поиску уникальных идей для бизнеса. Твоя задача — предложить 10 ниш, которые идеально подходят пользователю, исходя из его ответов на 20 вопросов."},
                {"role": "user", "content": prompt}
            ]
        )
        bot_response = completion.choices[0].message.content
        
        niches = bot_response.split('\n')
        
        keyboard_buttons = [[n] for n in niches if n.strip() and n[0].isdigit()]
        
        await update.message.reply_text(
            "Вот 10 ниш, которые могут вам подойти:",
            reply_markup=ReplyKeyboardMarkup(keyboard_buttons, one_time_keyboard=True, resize_keyboard=True)
        )
        return NICHE_SELECTION

    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        await update.message.reply_text("Произошла ошибка при генерации идей. Пожалуйста, попробуйте позже.")
        return ConversationHandler.END

async def handle_niche_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор ниши и генерирует бизнес-план."""
    selected_niche = update.message.text
    context.user_data['selected_niche'] = selected_niche
    
    await update.message.reply_text(f"Отлично! Вы выбрали: **{selected_niche}**\n\n"
                                    "Готовлю подробный бизнес-план. Это займет некоторое время...",
                                    reply_markup=ReplyKeyboardRemove())
    
    plan_prompt = f"""
    Напиши подробный бизнес-план для ниши "{selected_niche}".
    Включи следующие разделы:
    1. **Цель и миссия**
    2. **Описание продукта/услуги**
    3. **Целевая аудитория**
    4. **Анализ рынка и конкурентов**
    5. **Маркетинговая стратегия**
    6. **Финансовый план (расходы, доходы, выход в прибыль)** - укажи примерные цифры
    7. **План действий (что сделать уже сегодня, завтра и на следующей неделе)**
    
    Отвечай в формате, удобном для чтения, с использованием заголовков и списков.
    """
    
    try:
        completion = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Ты - опытный бизнес-консультант, который создает понятные и практичные бизнес-планы."},
                {"role": "user", "content": plan_prompt}
            ]
        )
        business_plan = completion.choices[0].message.content
        context.user_data['business_plan'] = business_plan
        
        await update.message.reply_text(business_plan)
        
        await create_and_send_pdf(update, context)
        
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error generating business plan: {e}")
        await update.message.reply_text("Произошла ошибка при генерации бизнес-плана. Попробуйте снова.")
        return ConversationHandler.END

async def create_and_send_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создает PDF-файл и отправляет его пользователю."""
    try:
        pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
        
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        c.setFont('DejaVuSans', 12)
        
        lines = context.user_data['business_plan'].split('\n')
        y_position = 800
        for line in lines:
            c.drawString(10, y_position, line)
            y_position -= 14
            if y_position < 50:
                c.showPage()
                y_position = 800
                c.setFont('DejaVuSans', 12)
        
        c.save()
        
        buffer.seek(0)
        
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=buffer,
            filename=f"Бизнес-план_{context.user_data['selected_niche']}.pdf",
            caption="Ваш подробный бизнес-план готов! Вы можете скачать его в формате PDF."
        )
        
        buffer.close()
        
    except Exception as e:
        logger.error(f"Error creating/sending PDF: {e}")
        await update.message.reply_text("Произошла ошибка при создании PDF-файла.")

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Логирует ошибки."""
    logger.error(f'Update {update} caused error {context.error}')

def main():
    """Запускает бота."""
    logger.info('Starting bot...')
    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Определяем состояния для каждого вопроса
        quiz_states_dict = {i: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quiz_answer)] for i in range(len(QUIZ_QUESTIONS))}
        
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start_command)],
            states={
                # Начальное состояние для первого вопроса
                0: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quiz_answer)],
                # Остальные состояния для вопросов (от 1 до 19)
                **quiz_states_dict,
                # Состояние для выбора ниши
                len(QUIZ_QUESTIONS): [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_niche_selection)],
            },
            fallbacks=[CommandHandler('cancel', cancel_command), CommandHandler('reset', reset_command)],
        )

        app.add_handler(conv_handler)
        app.add_handler(CommandHandler('help', help_command))
        app.add_error_handler(error)
        app.add_handler(CommandHandler('reset', reset_command))

        logger.info('Polling...')
        app.run_polling()

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == '__main__':
    main()
