import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from openai import OpenAI
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io
import json
import asyncio
import threading
import time
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = "gpt-3.5-turbo"

# Проверка переменных окружения
if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    logger.critical("Не заданы TELEGRAM_BOT_TOKEN или OPENAI_API_KEY!")
    raise ValueError("TELEGRAM_BOT_TOKEN и OPENAI_API_KEY должны быть установлены")

# Инициализация OpenAI клиента
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Определяем состояния для ConversationHandler
NUM_QUESTIONS = 10
START, *QUESTIONS_STATES, GENERATE_NICHES = range(NUM_QUESTIONS + 1)

# Вопросы
QUIZ_QUESTIONS = [
    {
        "text": "💰 **Бюджет на старт**: Сколько денег вы готовы вложить прямо сейчас?",
        "options": [["0-50 тыс. ₽"], ["50-200 тыс. ₽"], ["200-500 тыс. ₽"], ["500+ тыс. ₽"]]
    },
    {
        "text": "⏰ **Время в неделю**: Сколько часов в неделю вы готовы уделять бизнесу?",
        "options": [["5-10 часов"], ["10-20 часов"], ["20-40 часов"], ["Полный день (40+ часов)"]]
    },
    {
        "text": "🎯 **Опыт**: В какой сфере у вас уже есть опыт или знания?",
        "options": [["IT/Технологии"], ["Маркетинг/Продажи"], ["Творчество/Дизайн"], ["Услуги/Консалтинг"], ["Торговля/Продукты"], ["Другое"]]
    },
    {
        "text": "👥 **Команда**: Вы будете работать один или есть команда/партнёр?",
        "options": [["Один/одна"], ["Есть партнёр"], ["Есть небольшая команда"]]
    },
    {
        "text": "🚀 **Скорость роста**: Что для вас важнее на старте?",
        "options": [["Быстрый рост и масштаб"], ["Стабильность и уверенность"], ["Тестирование без рисков"]]
    },
    {
        "text": "🌍 **География**: Где планируете работать?",
        "options": [["Только онлайн"], ["Мой город/регион"], ["По всей стране"], ["Международный рынок"]]
    },
    {
        "text": "🎨 **Тип бизнеса**: Что вам ближе?",
        "options": [["Товары (физические)"], ["Услуги"], ["Цифровые продукты"], ["Образование/Коучинг"]]
    },
    {
        "text": "📈 **Цель на год**: Какой доход планируете через 12 месяцев?",
        "options": [["Доп. доход 20-50к/мес"], ["Заменить текущий доход"], ["50-100к чистыми"], ["100-500к чистыми"], ["500к+ чистыми"]]
    },
    {
        "text": "🛠️ **Навыки**: Какие ваши сильные стороны?",
        "options": None
    },
    {
        "text": "🔥 **Страсть**: О чём вы можете говорить часами? Что вас зажигает?",
        "options": None
    }
]

# Хранилище данных
user_niches = {}

# Флаг для отслеживания запуска keep_alive
_keep_alive_started = False

def keep_alive_background():
    """Фоновая задача чтобы бот не засыпал."""
    while True:
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"🤖 Бот активен - {current_time}")
            time.sleep(300)  # Каждые 5 минут
        except Exception as e:
            logger.error(f"Keep alive error: {e}")
            time.sleep(60)

# Команды
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает опрос с предупреждения."""
    warning_text = (
        "⚠️ **Внимание!** ⚠️\n\n"
        "Качество идей напрямую зависит от ваших ответов.\n\n"
        "• **Чем конкретнее отвечаете** — тем полезнее будут идеи\n"
        "• **Честно оценивайте** свои возможности и ресурсы\n"
        "• **Думайте реалистично** о времени и бюджете\n\n"
        "Бот предложит 5 бизнес-ниш на основе ваших ответов.\n"
        "Вы сможете просмотреть любую из них в любое время!\n\n"
        "Готовы начать?"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, начать!", callback_data="start_quiz")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(warning_text, reply_markup=reply_markup, parse_mode='Markdown')
    return START

async def start_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка callback для начала опроса."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text(
            "Диалог отменен. Используйте /start чтобы начать заново.",
            reply_markup=None
        )
        return ConversationHandler.END
    
    await query.edit_message_text(
        "Отлично! Начинаем анкету из 10 вопросов.\n\n"
        "Отвечайте честно — это ключ к полезным результатам!",
        reply_markup=None
    )
    
    context.user_data['answers'] = {}
    context.user_data['question_index'] = 0
    context.user_data['chat_id'] = query.message.chat_id
    
    # Отправляем первый вопрос
    return await ask_question_callback(query, context)

async def ask_question_callback(query, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет текущий вопрос через callback."""
    q_index = context.user_data['question_index']
    question_data = QUIZ_QUESTIONS[q_index]

    keyboard = None
    if question_data["options"]:
        keyboard = ReplyKeyboardMarkup(question_data["options"], one_time_keyboard=True, resize_keyboard=True)
    
    await context.bot.send_message(
        chat_id=context.user_data['chat_id'],
        text=question_data["text"],
        reply_markup=keyboard
    )
    return q_index

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
        await update.message.reply_chat_action("typing")
        
        await update.message.reply_text(
            "✅ **Анкета завершена!**\n\n"
            "Сейчас проанализирую ваши ответы и предложу 5 конкретных бизнес-идей...",
            reply_markup=ReplyKeyboardRemove()
        )
        return await generate_niches(update, context)

async def generate_niches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерирует 5 ниш на основе ответов."""
    user_id = update.effective_user.id
    answers = context.user_data['answers']
    
    prompt = f"""
    На основе следующих ответов пользователя, предложи 5 КОНКРЕТНЫХ и РЕАЛИСТИЧНЫХ бизнес-идей:
    {json.dumps(answers, indent=2, ensure_ascii=False)}
    
    Требования к ответу:
    1. Только 5 идей, пронумерованных от 1 до 5
    2. Каждая идея должна быть ОЧЕНЬ конкретной
    3. Учитывай бюджет, время и опыт из ответов
    4. Формат: "1. [Название идеи] - [Краткое описание]"
    5. Без лишнего текста, только список
    """
    
    try:
        await update.message.reply_chat_action("typing")
        
        completion = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Ты - практикующий бизнес-консультант. Предлагаешь только реалистичные идеи."},
                {"role": "user", "content": prompt}
            ]
        )
        bot_response = completion.choices[0].message.content
        
        # Сохраняем идеи для пользователя
        niches = []
        for line in bot_response.split('\n'):
            if line.strip() and line[0].isdigit():
                niches.append(line.strip())
        
        user_niches[user_id] = niches
        context.user_data['niches'] = niches
        
        # Создаем инлайн-клавиатуру
        keyboard = []
        for i, niche in enumerate(niches[:5], 1):
            button_text = niche[:3] + "..." if len(niche) > 30 else niche
            keyboard.append([InlineKeyboardButton(f"{i}. {button_text}", callback_data=f"niche_{i}")])
        
        keyboard.append([
            InlineKeyboardButton("🔄 Новые идеи", callback_data="regenerate"),
            InlineKeyboardButton("📋 Все идеи", callback_data="show_all")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🎯 **Вот 5 бизнес-идей специально для вас:**\n\n"
            "Нажмите на любую идею, чтобы получить подробный план.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return GENERATE_NICHES

    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        await update.message.reply_text(
            "Произошла ошибка при генерации идей. Попробуйте позже.",
            reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
        )
        return ConversationHandler.END

async def handle_niche_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор ниши через inline-кнопки."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data.startswith("niche_"):
        niche_index = int(query.data.split("_")[1]) - 1
        
        if user_id in user_niches and niche_index < len(user_niches[user_id]):
            selected_niche = user_niches[user_id][niche_index]
            context.user_data['selected_niche'] = selected_niche
            
            await query.edit_message_text(
                f"⏳ **Готовлю план для:**\n\n"
                f"**{selected_niche}**\n\n"
                f"Это займет 20-30 секунд...",
                parse_mode='Markdown'
            )
            
            # Генерируем бизнес-план
            plan_prompt = f"""
            Создай бизнес-план для идеи: "{selected_niche}"
            
            Структура:
            1. **Суть проекта**
            2. **Стартовые инвестиции**
            3. **План запуска на 30 дней**
            4. **Целевая аудитория**
            5. **Монетизация**
            6. **Риски и решения**
            7. **Первые 3 шага**
            
            Будь конкретным и практичным!
            """
            
            try:
                completion = openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "Ты - бизнес-аналитик. Даешь конкретные рекомендации."},
                        {"role": "user", "content": plan_prompt}
                    ]
                )
                business_plan = completion.choices[0].message.content
                context.user_data['business_plan'] = business_plan
                
                # Клавиатура с кнопками
                keyboard = [
                    [InlineKeyboardButton("📥 Скачать PDF", callback_data="download_pdf")],
                    [InlineKeyboardButton("← Назад к идеям", callback_data="back_to_niches"),
                     InlineKeyboardButton("🔄 Новые идеи", callback_data="regenerate")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"**📋 Бизнес-план:** {selected_niche}\n\n"
                    f"{business_plan}\n\n"
                    f"---\n"
                    f"💡 *Сохраните этот план или скачайте в PDF*",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
            except Exception as e:
                logger.error(f"Error generating business plan: {e}")
                await query.edit_message_text(
                    "Ошибка при создании плана.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="back_to_niches")]])
                )
    
    elif query.data == "show_all":
        if user_id in user_niches:
            all_niches = "\n".join(user_niches[user_id])
            
            keyboard = []
            for i in range(1, 6):
                keyboard.append([InlineKeyboardButton(f"Идея {i}", callback_data=f"niche_{i}")])
            
            keyboard.append([
                InlineKeyboardButton("← Назад", callback_data="back_main"),
                InlineKeyboardButton("🔄 Новые", callback_data="regenerate")
            ])
            
            await query.edit_message_text(
                f"📋 **Все 5 идей:**\n\n{all_niches}\n\n"
                f"Выберите идею для детального плана:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    elif query.data == "regenerate":
        await query.edit_message_text("🔄 Генерирую новые идеи...")
        
        if 'answers' in context.user_data:
            new_prompt = f"""
            На основе этих же ответов предложи 5 ДРУГИХ бизнес-идей:
            {json.dumps(context.user_data['answers'], indent=2, ensure_ascii=False)}
            
            Идеи должны быть другими.
            Формат: "1. [Название] - [Описание]"
            """
            
            try:
                completion = openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "Придумываешь неочевидные бизнес-идеи."},
                        {"role": "user", "content": new_prompt}
                    ]
                )
                new_niches = []
                for line in completion.choices[0].message.content.split('\n'):
                    if line.strip() and line[0].isdigit():
                        new_niches.append(line.strip())
                
                user_niches[user_id] = new_niches
                
                keyboard = []
                for i, niche in enumerate(new_niches[:5], 1):
                    button_text = niche[:30] + "..." if len(niche) > 30 else niche
                    keyboard.append([InlineKeyboardButton(f"{i}. {button_text}", callback_data=f"niche_{i}")])
                
                keyboard.append([
                    InlineKeyboardButton("📋 Все идеи", callback_data="show_all"),
                    InlineKeyboardButton("🔄 Ещё раз", callback_data="regenerate")
                ])
                
                await query.edit_message_text(
                    "🆕 **Новые 5 идей:**\n\n"
                    "Выберите идею для детального плана:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                
            except Exception as e:
                logger.error(f"Error regenerating niches: {e}")
                await query.edit_message_text(
                    "Ошибка генерации.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("/start", callback_data="start")]])
                )
    
    elif query.data == "back_to_niches":
        if user_id in user_niches:
            keyboard = []
            for i, niche in enumerate(user_niches[user_id][:5], 1):
                button_text = niche[:30] + "..." if len(niche) > 30 else niche
                keyboard.append([InlineKeyboardButton(f"{i}. {button_text}", callback_data=f"niche_{i}")])
            
            keyboard.append([
                InlineKeyboardButton("📋 Все идеи", callback_data="show_all"),
                InlineKeyboardButton("🔄 Новые", callback_data="regenerate")
            ])
            
            await query.edit_message_text(
                "🎯 **Ваши бизнес-идеи:**\n\n"
                "Выберите идею для подробного плана:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    elif query.data == "download_pdf":
        await create_and_send_pdf_callback(query, context)
    
    elif query.data == "back_main":
        await query.edit_message_text(
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Мои идеи", callback_data="back_to_niches")],
                [InlineKeyboardButton("🔄 Новые идеи", callback_data="regenerate")],
                [InlineKeyboardButton("/start", callback_data="start")]
            ])
        )
    
    elif query.data == "start":
        await query.edit_message_text(
            "Используйте команду /start",
            reply_markup=None
        )
    
    return GENERATE_NICHES

async def create_and_send_pdf_callback(query, context: ContextTypes.DEFAULT_TYPE):
    """Создает PDF и отправляет через callback."""
    try:
        await query.answer("Создаю PDF...")
        
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        c.setFont("Helvetica", 12)
        
        title = context.user_data.get('selected_niche', 'Бизнес-план')
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 800, "БИЗНЕС-ПЛАН")
        c.setFont("Helvetica", 14)
        c.drawString(50, 775, title[:80])
        
        c.line(50, 765, 550, 765)
        
        business_plan = context.user_data.get('business_plan', '')
        c.setFont("Helvetica", 12)
        
        lines = []
        for line in business_plan.split('\n'):
            clean_line = line.replace('**', '').replace('__', '').strip()
            if clean_line:
                lines.append(clean_line)
        
        y_position = 740
        
        for line in lines:
            if y_position < 50:
                c.showPage()
                c.setFont("Helvetica", 12)
                y_position = 800
            
            if len(line) > 80:
                words = line.split(' ')
                current_line = ""
                for word in words:
                    if len(current_line + word) < 80:
                        current_line += word + " "
                    else:
                        c.drawString(50, y_position, current_line)
                        y_position -= 16
                        current_line = word + " "
                        if y_position < 50:
                            c.showPage()
                            c.setFont("Helvetica", 12)
                            y_position = 800
                if current_line:
                    c.drawString(50, y_position, current_line)
                    y_position -= 16
            else:
                c.drawString(50, y_position, line)
                y_position -= 16
            
            y_position -= 2
        
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(50, 30, "Сгенерировано Business Idea Bot")
        c.drawString(50, 15, datetime.now().strftime("%d.%m.%Y"))
        
        c.save()
        buffer.seek(0)
        
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=buffer,
            filename=f"business_plan_{query.from_user.id}.pdf",
            caption=f"📄 Ваш бизнес-план!\n\n{title[:50]}..."
        )
        
        buffer.close()
        
        keyboard = [
            [InlineKeyboardButton("← К идеям", callback_data="back_to_niches")],
            [InlineKeyboardButton("🔄 Новые идеи", callback_data="regenerate")]
        ]
        
        await query.edit_message_text(
            f"✅ **PDF отправлен!**\n\n"
            f"Проверьте документы в чате ↑",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error creating PDF: {e}")
        await query.edit_message_text(
            "Ошибка при создании файла.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="back_to_niches")]])
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет сообщение-помощь."""
    help_text = (
        "🤖 **Бизнес-генератор идей**\n\n"
        "Я помогу найти бизнес-нишу и создам пошаговый план!\n\n"
        "📋 **Как это работает:**\n"
        "1. Отвечаете на 10 вопросов о себе\n"
        "2. Получаете 5 персональных бизнес-идей\n"
        "3. Выбираете идею и получаете детальный план\n"
        "4. Скачиваете план в PDF\n\n"
        "📝 **Команды:**\n"
        "/start - Начать анкету\n"
        "/help - Эта справка\n"
        "/cancel - Отменить диалог"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет диалог."""
    await update.message.reply_text(
        "Диалог отменен. Используйте /start чтобы начать заново.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбрасывает анкету."""
    user_id = update.effective_user.id
    if user_id in user_niches:
        del user_niches[user_id]
    
    await update.message.reply_text(
        '✅ Данные сброшены. Используйте /start.',
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Логирует ошибки."""
    logger.error(f'Update {update} caused error {context.error}')

def main() -> None:
    """Запускает бота."""
    PORT = int(os.environ.get('PORT', 8443))
    
    # Создаем Application БЕЗ job_queue
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Запускаем фоновый поток для keep-alive
    global _keep_alive_started
    if not _keep_alive_started:
        keep_alive_thread = threading.Thread(target=keep_alive_background, daemon=True)
        keep_alive_thread.start()
        _keep_alive_started = True
        logger.info("Keep-alive thread started")
    
    # Определяем состояния
    quiz_states_dict = {i: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quiz_answer)] for i in range(NUM_QUESTIONS)}
    
    # ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start_command),
            CallbackQueryHandler(start_quiz_callback, pattern="^(start_quiz|cancel)$")
        ],
        states={
            START: [
                CallbackQueryHandler(start_quiz_callback, pattern="^(start_quiz|cancel)$")
            ],
            **quiz_states_dict,
            GENERATE_NICHES: [
                CallbackQueryHandler(handle_niche_selection, pattern="^(niche_|show_all|regenerate|back_|download_|start|cancel)$"),
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel_command),
            CommandHandler('reset', reset_command),
            CommandHandler('start', start_command),
        ],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('reset', reset_command))
    app.add_error_handler(error)
    
    # Запускаем вебхук
    logger.info("Starting bot...")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://gptpdf-github-vybor-nishy.onrender.com/{TELEGRAM_TOKEN}"
    )

if __name__ == '__main__':
    main()
