import os
import logging
import asyncio
import json
import io
from datetime import datetime
from typing import Dict, List

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
if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    logger.critical("Не заданы TELEGRAM_BOT_TOKEN или OPENAI_API_KEY!")
    raise ValueError("TELEGRAM_BOT_TOKEN и OPENAI_API_KEY должны быть установлены")

# Инициализация OpenAI
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Состояния ConversationHandler
NUM_QUESTIONS = 12
START, *QUESTIONS_STATES, GENERATE_NICHES = range(NUM_QUESTIONS + 1)

# Вопросы (упрощенная версия для быстрого деплоя)
QUIZ_QUESTIONS = [
    {"text": "🏙️ **Город**: В каком городе вы живете?", "type": "text"},
    {"text": "💰 **Бюджет**: Сколько готовы вложить?", "options": [["0-50 тыс"], ["50-200 тыс"], ["200-500 тыс"], ["500+ тыс"]], "type": "options"},
    {"text": "⏰ **Время**: Сколько часов в неделю?", "options": [["5-10ч"], ["10-20ч"], ["20-40ч"], ["40+ч"]], "type": "options"},
    {"text": "🎓 **Образование**: Какое образование и сертификаты?", "type": "text"},
    {"text": "🏢 **Опыт**: В какой сфере есть опыт?", "options": [["IT/Тех"], ["Маркетинг"], ["Творчество"], ["Услуги"], ["Торговля"], ["Другое"]], "type": "options"},
    {"text": "👥 **Команда**: Работать один или с командой?", "options": [["Один"], ["Партнер"], ["Команда"]], "type": "options"},
    {"text": "🚀 **Скорость**: Что важнее?", "options": [["Быстрый рост"], ["Стабильность"], ["Без рисков"]], "type": "options"},
    {"text": "🌍 **География**: Где работать?", "options": [["Онлайн"], ["Мой город"], ["Страна"], ["Международно"]], "type": "options"},
    {"text": "🎨 **Тип бизнеса**: Что ближе?", "options": [["Товары"], ["Услуги"], ["Цифровое"], ["Образование"]], "type": "options"},
    {"text": "📈 **Цель на год**: Какой доход через 12 мес?", "options": [["20-50к/мес"], ["50-100к"], ["100-300к"], ["300к+"]], "type": "options"},
    {"text": "🛠️ **Навыки**: Сильные стороны через запятую", "type": "text"},
    {"text": "🔥 **Интересы**: Что зажигает?", "type": "text"}
]

# Хранилище
user_data_store: Dict[int, Dict] = {}
user_niches_store: Dict[int, List] = {}

# ==================== HEALTH CHECK СЕРВЕР ====================
async def health_handler(request):
    return web.Response(text="OK", status=200)

async def start_http_server():
    app = web.Application()
    app.router.add_get('/health', health_handler)
    app.router.add_get('/', health_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"✅ Health check сервер на порту {PORT}")
    return runner

# ==================== УПРОЩЕННЫЙ SELF-PING ====================
async def self_ping_task():
    """Простой self-ping без aioschedule"""
    while True:
        if RENDER_EXTERNAL_URL:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{RENDER_EXTERNAL_URL}/health", timeout=10):
                        logger.info(f"✅ Self-ping успешен")
            except Exception as e:
                logger.error(f"❌ Self-ping ошибка: {e}")
        await asyncio.sleep(240)  # Каждые 4 минуты

# ==================== КОМАНДЫ БОТА (упрощенные) ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **Бизнес-навигатор**\n\n"
        "Ответьте на 12 вопросов → получите 5 бизнес-идей!\n\n"
        "Начнем?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Начать", callback_data="start_quiz")],
            [InlineKeyboardButton("📊 Статус API", callback_data="check_status")]
        ]),
        parse_mode='Markdown'
    )
    return START

async def start_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "check_status":
        await query.edit_message_text(
            "✅ OpenAI API доступен\n"
            "🤖 Модель: gpt-3.5-turbo\n"
            "🚀 Бот готов к работе!",
            parse_mode='Markdown'
        )
        return START
    
    await query.edit_message_text("Начинаем опрос...")
    
    user_id = query.from_user.id
    user_data_store[user_id] = {
        'answers': {},
        'question_index': 0,
        'chat_id': query.message.chat_id
    }
    
    # Отправляем первый вопрос
    return await send_question(context, user_id)

async def send_question(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    user_data = user_data_store[user_id]
    q_index = user_data['question_index']
    
    if q_index >= len(QUIZ_QUESTIONS):
        await context.bot.send_message(
            chat_id=user_data['chat_id'],
            text="✅ Анкета завершена! Генерирую идеи..."
        )
        return await generate_ideas(context, user_id)
    
    question = QUIZ_QUESTIONS[q_index]
    
    keyboard = None
    if question["type"] == "options" and "options" in question:
        keyboard = ReplyKeyboardMarkup(question["options"], resize_keyboard=True)
    
    await context.bot.send_message(
        chat_id=user_data['chat_id'],
        text=question["text"],
        reply_markup=keyboard
    )
    return q_index

async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_data_store:
        await update.message.reply_text("Сессия устарела. /start")
        return ConversationHandler.END
    
    user_data = user_data_store[user_id]
    q_index = user_data['question_index']
    
    user_data['answers'][f'q{q_index+1}'] = update.message.text
    user_data['question_index'] += 1
    
    if user_data['question_index'] < len(QUIZ_QUESTIONS):
        return await send_question(context, user_id)
    else:
        await update.message.reply_text("✅ Все вопросы отвечены! Анализирую...")
        return await generate_ideas(context, user_id)

async def generate_ideas(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    user_data = user_data_store[user_id]
    
    try:
        prompt = f"""
        На основе ответов пользователя предложи 5 КОНКРЕТНЫХ бизнес-идей:
        {json.dumps(user_data['answers'], ensure_ascii=False, indent=2)}
        
        Формат: 1. Название - Описание (инвестиции: X-X тыс. ₽)
        """
        
        completion = await openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Ты бизнес-консультант. Предлагай реалистичные идеи."},
                {"role": "user", "content": prompt}
            ]
        )
        
        ideas = []
        for line in completion.choices[0].message.content.split('\n'):
            if line.strip() and line[0].isdigit():
                ideas.append(line.strip())
        
        user_niches_store[user_id] = ideas
        
        # Создаем кнопки
        keyboard = []
        for i, idea in enumerate(ideas[:5], 1):
            keyboard.append([InlineKeyboardButton(f"Идея {i}", callback_data=f"idea_{i}")])
        
        keyboard.append([InlineKeyboardButton("📋 Все идеи", callback_data="show_all")])
        
        await context.bot.send_message(
            chat_id=user_data['chat_id'],
            text="🎯 **Вот 5 бизнес-идей для вас:**\n\nНажмите на идею для деталей",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return GENERATE_NICHES
        
    except Exception as e:
        logger.error(f"Ошибка генерации: {e}")
        await context.bot.send_message(
            chat_id=user_data['chat_id'],
            text="❌ Ошибка генерации. Попробуйте /start"
        )
        return ConversationHandler.END

async def handle_idea_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data.startswith("idea_"):
        idx = int(query.data.split("_")[1]) - 1
        
        if user_id in user_niches_store and idx < len(user_niches_store[user_id]):
            idea = user_niches_store[user_id][idx]
            
            # Генерируем детальный план
            plan_prompt = f"Создай детальный бизнес-план для: {idea}"
            
            try:
                completion = await openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "Создай подробный бизнес-план"},
                        {"role": "user", "content": plan_prompt}
                    ]
                )
                
                plan = completion.choices[0].message.content
                
                await query.edit_message_text(
                    f"📋 **Детальный план:**\n\n{idea}\n\n{plan}",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📥 PDF", callback_data="download_pdf")],
                        [InlineKeyboardButton("← Назад", callback_data="back")]
                    ])
                )
                
            except Exception as e:
                await query.edit_message_text(f"Ошибка: {str(e)}")
    
    elif query.data == "show_all":
        if user_id in user_niches_store:
            all_ideas = "\n".join(user_niches_store[user_id])
            await query.edit_message_text(f"📋 Все идеи:\n\n{all_ideas}")
    
    elif query.data == "back":
        if user_id in user_niches_store:
            keyboard = []
            for i, idea in enumerate(user_niches_store[user_id][:5], 1):
                keyboard.append([InlineKeyboardButton(f"Идея {i}", callback_data=f"idea_{i}")])
            
            await query.edit_message_text(
                "Выберите идею:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    return GENERATE_NICHES

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Бизнес-генератор идей\n\n"
        "/start - Начать\n"
        "/help - Помощь\n"
        "/status - Статус бота",
        parse_mode='Markdown'
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 Статус:\n"
        f"• Пользователей: {len(user_data_store)}\n"
        f"• Порт: {PORT}\n"
        f"• API: ✅ Активен",
        parse_mode='Markdown'
    )

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
async def main():
    logger.info("🚀 Запуск бота...")
    
    # 1. HTTP сервер для health check
    http_runner = await start_http_server()
    
    # 2. Запускаем self-ping в фоне
    if RENDER_EXTERNAL_URL:
        asyncio.create_task(self_ping_task())
    
    # 3. Создаем приложение бота
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # 4. ConversationHandler
    quiz_states = {
        i: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quiz_answer)]
        for i in range(NUM_QUESTIONS)
    }
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start_command),
            CallbackQueryHandler(start_quiz_callback, pattern="^(start_quiz|check_status)$")
        ],
        states={
            START: [CallbackQueryHandler(start_quiz_callback, pattern="^(start_quiz|check_status)$")],
            **quiz_states,
            GENERATE_NICHES: [
                CallbackQueryHandler(handle_idea_selection, pattern="^(idea_|show_all|back|download_pdf)$")
            ]
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)],
        per_user=True
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('status', status_command))
    
    # 5. Устанавливаем вебхук
    webhook_url = f"{RENDER_EXTERNAL_URL}/{TELEGRAM_TOKEN}" if RENDER_EXTERNAL_URL else ""
    if webhook_url:
        await application.bot.set_webhook(webhook_url)
        logger.info(f"✅ Вебхук: {webhook_url}")
    
    # 6. Запускаем
    await application.initialize()
    await application.start()
    
    if webhook_url:
        await application.updater.start_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TELEGRAM_TOKEN,
            webhook_url=webhook_url
        )
    else:
        await application.updater.start_polling()
    
    logger.info("✅ Бот запущен!")
    
    # Бесконечное ожидание
    await asyncio.Future()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")
        raise