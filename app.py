import os
import logging
import asyncio
import json
import io
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

import aiohttp
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters
)
from openai import AsyncOpenAI
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# ==================== КОНФИГУРАЦИЯ ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
PORT = int(os.environ.get('PORT', 8443))
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_MODEL = "gpt-3.5-turbo"
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', '')

# Проверка конфигурации
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не установлен!")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY не установлен!")

# Инициализация OpenAI
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Состояния ConversationHandler
NUM_QUESTIONS = 10
START, *QUESTIONS_STATES, GENERATE_NICHES = range(NUM_QUESTIONS + 1)

# Вопросы анкеты
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

# Хранилище данных в памяти
user_data_store: Dict[int, Dict] = {}
user_niches_store: Dict[int, List[str]] = {}

# ==================== HEALTH CHECK СЕРВЕР ====================
async def health_handler(request):
    """Обработчик health check запросов."""
    return web.Response(text="OK", status=200)

async def start_http_server():
    """Запуск HTTP сервера для health check."""
    app = web.Application()
    app.router.add_get('/health', health_handler)
    app.router.add_get('/', health_handler)  # Корневой путь тоже отвечает
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Используем порт из переменной окружения
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"✅ Health check сервер запущен на порту {PORT}")
    logger.info(f"✅ URL для проверки: http://0.0.0.0:{PORT}/health")
    
    if RENDER_EXTERNAL_URL:
        logger.info(f"✅ Внешний URL Render: {RENDER_EXTERNAL_URL}")
    
    return runner

# ==================== SELF-PING СИСТЕМА ====================
async def self_ping():
    """Пингует свой же сервис чтобы не заснуть на Render."""
    if not RENDER_EXTERNAL_URL:
        logger.warning("RENDER_EXTERNAL_URL не установлен, self-ping отключен")
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{RENDER_EXTERNAL_URL}/health", timeout=10) as response:
                if response.status == 200:
                    logger.info(f"✅ Self-ping успешен: {RENDER_EXTERNAL_URL}")
                else:
                    logger.warning(f"⚠️ Self-ping получил статус {response.status}")
    except Exception as e:
        logger.error(f"❌ Ошибка self-ping: {e}")

async def start_self_ping():
    """Запускает периодический self-ping."""
    import aioschedule as schedule
    import asyncio
    
    # Пингуем каждые 4 минуты (не 5!)
    schedule.every(4).minutes.do(self_ping)
    
    logger.info("🔄 Self-ping система запущена (каждые 4 минуты)")
    
    while True:
        await schedule.run_pending()
        await asyncio.sleep(60)  # Проверяем каждую минуту

# ==================== КОМАНДЫ БОТА ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает опрос с предупреждением."""
    user_id = update.effective_user.id
    
    # Очищаем старые данные пользователя
    if user_id in user_data_store:
        del user_data_store[user_id]
    if user_id in user_niches_store:
        del user_niches_store[user_id]
    
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

    user_id = query.from_user.id
    user_data_store[user_id] = {
        'answers': {},
        'question_index': 0,
        'chat_id': query.message.chat_id
    }

    # Отправляем первый вопрос
    return await send_question(query, context, user_id)

async def send_question(query, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Отправляет текущий вопрос пользователю."""
    user_data = user_data_store[user_id]
    q_index = user_data['question_index']
    
    if q_index >= len(QUIZ_QUESTIONS):
        return await complete_quiz(context, user_id)
    
    question_data = QUIZ_QUESTIONS[q_index]

    keyboard = None
    if question_data["options"]:
        keyboard = ReplyKeyboardMarkup(
            question_data["options"], 
            one_time_keyboard=True, 
            resize_keyboard=True
        )

    await context.bot.send_message(
        chat_id=user_data['chat_id'],
        text=question_data["text"],
        reply_markup=keyboard
    )
    return q_index

async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ответ на вопрос."""
    user_id = update.effective_user.id
    
    if user_id not in user_data_store:
        await update.message.reply_text(
            "Сессия устарела. Пожалуйста, начните заново с /start",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    user_data = user_data_store[user_id]
    q_index = user_data['question_index']
    user_answer = update.message.text
    
    # Сохраняем ответ
    user_data['answers'][f'q{q_index + 1}'] = user_answer
    logger.info(f"Пользователь {user_id}: ответ на Q{q_index + 1}: {user_answer}")
    
    # Переходим к следующему вопросу
    user_data['question_index'] += 1
    
    if user_data['question_index'] < len(QUIZ_QUESTIONS):
        # Отправляем следующий вопрос
        question_data = QUIZ_QUESTIONS[user_data['question_index']]
        
        keyboard = None
        if question_data["options"]:
            keyboard = ReplyKeyboardMarkup(
                question_data["options"], 
                one_time_keyboard=True, 
                resize_keyboard=True
            )
        
        await update.message.reply_text(question_data["text"], reply_markup=keyboard)
        return user_data['question_index']
    else:
        # Все вопросы отвечены
        await update.message.reply_text(
            "✅ **Анкета завершена!**\n\n"
            "Сейчас проанализирую ваши ответы и предложу 5 конкретных бизнес-идей...",
            reply_markup=ReplyKeyboardRemove()
        )
        return await generate_niches(update, context, user_id)

async def complete_quiz(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Завершает опрос и переходит к генерации идей."""
    user_data = user_data_store.get(user_id)
    if not user_data:
        return ConversationHandler.END
    
    chat_id = user_data['chat_id']
    
    await context.bot.send_message(
        chat_id=chat_id,
        text="✅ **Анкета завершена!**\n\n"
             "Сейчас проанализирую ваши ответы и предложу 5 конкретных бизнес-идей...",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Здесь будет логика генерации идей
    return GENERATE_NICHES

async def generate_niches(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Генерирует 5 ниш на основе ответов."""
    user_data = user_data_store.get(user_id)
    if not user_data:
        await update.message.reply_text("Ошибка: данные не найдены. Начните заново с /start")
        return ConversationHandler.END
    
    answers = user_data['answers']
    
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
        
        completion = await openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Ты - практикующий бизнес-консультант. Предлагаешь только реалистичные идеи."},
                {"role": "user", "content": prompt}
            ],
            timeout=30.0
        )
        
        bot_response = completion.choices[0].message.content
        
        # Сохраняем идеи для пользователя
        niches = []
        for line in bot_response.split('\n'):
            if line.strip() and line[0].isdigit():
                niches.append(line.strip())
        
        user_niches_store[user_id] = niches
        user_data['niches'] = niches
        
        # Создаем инлайн-клавиатуру
        keyboard = []
        for i, niche in enumerate(niches[:5], 1):
            button_text = niche[:30] + "..." if len(niche) > 30 else niche
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
        logger.error(f"Ошибка OpenAI API: {e}")
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
        
        if user_id in user_niches_store and niche_index < len(user_niches_store[user_id]):
            selected_niche = user_niches_store[user_id][niche_index]
            
            if user_id not in user_data_store:
                user_data_store[user_id] = {}
            user_data_store[user_id]['selected_niche'] = selected_niche
            
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
                completion = await openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "Ты - бизнес-аналитик. Даешь конкретные рекомендации."},
                        {"role": "user", "content": plan_prompt}
                    ],
                    timeout=30.0
                )
                
                business_plan = completion.choices[0].message.content
                user_data_store[user_id]['business_plan'] = business_plan
                
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
                logger.error(f"Ошибка генерации бизнес-плана: {e}")
                await query.edit_message_text(
                    "Ошибка при создании плана.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="back_to_niches")]])
                )
    
    elif query.data == "show_all":
        if user_id in user_niches_store:
            all_niches = "\n".join(user_niches_store[user_id])
            
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
        
        user_data = user_data_store.get(user_id)
        if user_data and 'answers' in user_data:
            new_prompt = f"""
            На основе этих же ответов предложи 5 ДРУГИХ бизнес-идей:
            {json.dumps(user_data['answers'], indent=2, ensure_ascii=False)}
            
            Идеи должны быть другими.
            Формат: "1. [Название] - [Описание]"
            """
            
            try:
                completion = await openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "Придумываешь неочевидные бизнес-идеи."},
                        {"role": "user", "content": new_prompt}
                    ],
                    timeout=30.0
                )
                
                new_niches = []
                for line in completion.choices[0].message.content.split('\n'):
                    if line.strip() and line[0].isdigit():
                        new_niches.append(line.strip())
                
                user_niches_store[user_id] = new_niches
                
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
                logger.error(f"Ошибка регенерации идей: {e}")
                await query.edit_message_text(
                    "Ошибка генерации.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("/start", callback_data="start")]])
                )
    
    elif query.data == "back_to_niches":
        if user_id in user_niches_store:
            keyboard = []
            for i, niche in enumerate(user_niches_store[user_id][:5], 1):
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
        await create_and_send_pdf(query, context, user_id)
    
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

async def create_and_send_pdf(query, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Создает PDF и отправляет через callback."""
    try:
        await query.answer("Создаю PDF...")
        
        user_data = user_data_store.get(user_id)
        if not user_data:
            await query.edit_message_text("Ошибка: данные не найдены")
            return
        
        selected_niche = user_data.get('selected_niche', 'Бизнес-план')
        business_plan = user_data.get('business_plan', '')
        
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        
        # Заголовок
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 800, "БИЗНЕС-ПЛАН")
        c.setFont("Helvetica", 14)
        c.drawString(50, 775, selected_niche[:80])
        
        c.line(50, 765, 550, 765)
        
        # Контент
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
        
        # Футер
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(50, 30, "Сгенерировано Business Idea Bot")
        c.drawString(50, 15, datetime.now().strftime("%d.%m.%Y"))
        
        c.save()
        buffer.seek(0)
        
        # Отправляем PDF
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=buffer,
            filename=f"business_plan_{user_id}.pdf",
            caption=f"📄 Ваш бизнес-план!\n\n{selected_niche[:50]}..."
        )
        
        buffer.close()
        
        # Обновляем сообщение
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
        logger.error(f"Ошибка создания PDF: {e}")
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
    user_id = update.effective_user.id
    
    # Очищаем данные пользователя
    if user_id in user_data_store:
        del user_data_store[user_id]
    if user_id in user_niches_store:
        del user_niches_store[user_id]
    
    await update.message.reply_text(
        "Диалог отменен. Используйте /start чтобы начать заново.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статус системы."""
    status_text = (
        "📊 **Статус системы:**\n\n"
        f"• Пользователей в памяти: {len(user_data_store)}\n"
        f"• Порт health check: {PORT}\n"
        f"• OpenAI модель: {OPENAI_MODEL}\n"
        f"• Внешний URL: {RENDER_EXTERNAL_URL or 'Не установлен'}\n"
        f"• Время сервера: {datetime.now().strftime('%H:%M:%S')}"
    )
    await update.message.reply_text(status_text, parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок."""
    logger.error(f'Ошибка: {context.error}', exc_info=context.error)
    
    if update and update.effective_user:
        await update.effective_user.send_message(
            "Произошла ошибка. Пожалуйста, попробуйте позже или используйте /start."
        )

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
async def main():
    """Основная функция запуска."""
    logger.info("🚀 Запуск бизнес-бота...")
    
    # 1. Запускаем HTTP сервер для health check
    http_runner = await start_http_server()
    
    # 2. Создаем приложение Telegram бота
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # 3. Настраиваем ConversationHandler
    quiz_states_dict = {
        i: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quiz_answer)]
        for i in range(NUM_QUESTIONS)
    }
    
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
            CommandHandler('start', start_command),
        ],
        per_user=True,
        per_chat=True
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('status', status_command))
    application.add_error_handler(error_handler)
    
    # 4. Запускаем self-ping в фоне
    if RENDER_EXTERNAL_URL:
        asyncio.create_task(start_self_ping())
    
    # 5. Запускаем бота с вебхуком
    webhook_url = f"https://gptpdf-github-vybor-nishy.onrender.com/{TELEGRAM_TOKEN}"
    await application.bot.set_webhook(webhook_url)
    
    logger.info(f"✅ Вебхук установлен: {webhook_url}")
    logger.info("✅ Бот готов к работе!")
    
    # 6. Запускаем приложение
    await application.initialize()
    await application.start()
    await application.updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=webhook_url,
        drop_pending_updates=True
    )
    
    # 7. Ждем завершения (никогда)
    try:
        await asyncio.Future()  # Бесконечное ожидание
    finally:
        # Очистка при завершении
        await application.stop()
        await http_runner.cleanup()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")
        raise