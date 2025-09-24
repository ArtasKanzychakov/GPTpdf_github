# app.py (обновленные части)
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
import openai
from openai import OpenAI
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io

# Настройка логирования
# ... (Оставить без изменений)

# Конфигурация
# ... (Оставить без изменений)

# Инициализация OpenAI клиента
# ... (Оставить без изменений)

# Определяем состояния для ConversationHandler
START, *QUESTIONS_STATES, GENERATE_NICHES, NICHE_SELECTION, GENERATE_PLAN = range(23)
# 20 вопросов + 3 дополнительных состояния

# Вопросы и кнопки-ответы
QUIZ_QUESTIONS = [
    {
        "text": "Вопрос 1: Как вы относитесь к риску?",
        "options": [["Высокий (готов на всё)", "Умеренный (взвешенный подход)", "Низкий (предпочитаю стабильность)"]]
    },
    {
        "text": "Вопрос 2: Какой тип работы вам ближе?",
        "options": [["С людьми", "С данными/информацией"], ["С товарами/продуктами", "С услугами"]]
    },
    {
        "text": "Вопрос 3: Вы работаете один или в команде?",
        "options": [["Один", "В команде"]]
    },
    # ... Добавьте остальные 17 вопросов по аналогии
    {
        "text": "Вопрос 4: Какое ваше хобби или увлечение?",
        "options": None # Текстовый ввод, без кнопок
    },
    # ...
]

# Команды
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает опрос и задает первый вопрос."""
    await update.message.reply_text("Привет! Я помогу тебе найти нишу для бизнеса. "
                                    "Давай начнём анкету из 20 вопросов.",
                                    reply_markup=ReplyKeyboardRemove())
    
    # Инициализация ответов и индекса вопроса
    context.user_data['answers'] = {}
    context.user_data['question_index'] = 0
    
    await ask_question(update, context)
    return START

async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет текущий вопрос пользователю."""
    q_index = context.user_data['question_index']
    question_data = QUIZ_QUESTIONS[q_index]
    
    keyboard = None
    if question_data["options"]:
        keyboard = ReplyKeyboardMarkup(question_data["options"], one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(question_data["text"], reply_markup=keyboard)
    
    return q_index + 1 # Переходим в следующее состояние

async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ответ на вопрос."""
    q_index = context.user_data['question_index']
    user_answer = update.message.text
    context.user_data['answers'][f'q{q_index + 1}'] = user_answer
    logger.info(f"Answer to Q{q_index + 1}: {user_answer}")
    
    context.user_data['question_index'] += 1
    
    if context.user_data['question_index'] < len(QUIZ_QUESTIONS):
        # Если есть еще вопросы, задаем следующий
        await ask_question(update, context)
        return context.user_data['question_index'] + 1
    else:
        # Анкета завершена, переходим к генерации ниш
        await update.message.reply_text("Спасибо! Анкета завершена. "
                                        "Сейчас я проанализирую ваши ответы и сгенерирую 10 бизнес-ниш...")
        return await generate_niches(update, context)

async def generate_niches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерирует 10 ниш на основе ответов."""
    answers = context.user_data['answers']
    # Формируем большой промпт
    prompt = f"""
    На основе 20 ответов пользователя, предложи 10 креативных идей для бизнес-ниш.
    Учти все аспекты: риски, предпочтения в работе, командность, хобби, время, навыки, ценности, доход, капитал.
    
    Вот ответы пользователя:
    {answers}
    
    Предложи 10 ниш в виде простого нумерованного списка, без лишнего текста. Каждая ниша должна быть короткой и емкой, например:
    1. Онлайн-платформа для любителей собак.
    2. Сервис по созданию кастомных настольных игр.
    ...
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
        
        keyboard_buttons = [ [n] for n in niches if n.strip() ]
        
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
    
    # Генерация подробного плана
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
        # Регистрируем шрифт для поддержки кириллицы
        pdfmetrics.registerFont(TTFont('Vera', 'Vera.ttf'))
        
        # Создаем буфер в памяти
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        c.setFont('Vera', 12)
        
        # Добавляем содержимое в PDF
        textobject = c.beginText()
        textobject.setTextOrigin(10, 800)
        
        # Добавляем заголовок
        textobject.setFont('Vera', 16)
        textobject.textLine(f"Бизнес-план: {context.user_data['selected_niche']}")
        textobject.textLine("") # Пустая строка
        
        # Добавляем текст плана
        c.drawString(10, 780, context.user_data['business_plan'])
        
        c.showPage()
        c.save()
        
        buffer.seek(0)
        
        # Отправляем файл
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

# ... (остальные функции: help, cancel, reset, error)

def main():
    """Запускает бота."""
    logger.info('Starting bot...')
    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Создаем массив обработчиков для 20 вопросов
        quiz_handlers = [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quiz_answer)] * 20
        
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start_command)],
            states={
                START: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quiz_answer)],
                **{i: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quiz_answer)] for i in range(1, 21)},
                GENERATE_NICHES: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_niches)],
                NICHE_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_niche_selection)],
                GENERATE_PLAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_niche_selection)],
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
    # ... (Оставить без изменений)

# app.py

# ... (ваш существующий код)

async def create_and_send_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создает PDF-файл и отправляет его пользователю."""
    try:
        # Регистрируем шрифт для поддержки кириллицы
        # Замените 'Vera' на 'DejaVuSans'
        pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
        
        # Создаем буфер в памяти
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        
        # Устанавливаем шрифт для всего документа
        c.setFont('DejaVuSans', 12)
        
        # Добавляем содержимое в PDF
        textobject = c.beginText()
        textobject.setTextOrigin(10, 800)
        
        # Устанавливаем шрифт для заголовка
        textobject.setFont('DejaVuSans', 16)
        textobject.textLine(f"Бизнес-план: {context.user_data['selected_niche']}")
        textobject.textLine("") # Пустая строка
        
        # Добавляем текст плана
        c.drawString(10, 780, context.user_data['business_plan'])
        
        c.showPage()
        c.save()
        
        buffer.seek(0)
        
        # Отправляем файл
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
