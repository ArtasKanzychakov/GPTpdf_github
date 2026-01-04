import os
import logging
import asyncio
import json
import io
from datetime import datetime
from typing import Dict, List, Optional

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

# ==================== КОНФИГУРАЦИЯ ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
PORT = int(os.environ.get('PORT', 10000))
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_MODEL = "gpt-3.5-turbo"

# Проверка конфигурации
if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    logger.critical("Не заданы TELEGRAM_BOT_TOKEN или OPENAI_API_KEY!")
    raise ValueError("TELEGRAM_BOT_TOKEN и OPENAI_API_KEY должны быть установлены")

# Инициализация OpenAI
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Состояния ConversationHandler
START, Q1, Q2, Q3, Q4, Q5, Q6, Q7, Q8, Q9, Q10, Q11, Q12, Q13, Q14, Q15, Q16, GENERATE_NICHES = range(18)

# Расширенные вопросы анкеты
QUIZ_QUESTIONS = [
    {"text": "🏙️ **Город**: В каком городе и регионе вы живете?\n\n_Пример: Москва, Центральный регион или Краснодар, Южный регион_", "type": "text"},
    {"text": "🎓 **Образование**: Какое у вас образование?\n\n_Укажите: 1) Основное образование 2) Дополнительные курсы/сертификаты 3) Самообразование_", "type": "text"},
    {"text": "📜 **Сертификаты и корочки**: Какие официальные документы/сертификаты у вас есть?\n\n_Перечислите через запятую или напишите 'нет'_", "type": "text"},
    {"text": "🛠️ **Технические навыки**: Какие технические навыки у вас есть?\n\n_Примеры: программирование (Python/JS), дизайн (Figma/Photoshop), анализ данных, работа с оборудованием_", "type": "text"},
    {"text": "💼 **Профессиональные навыки**: Какие профессиональные/управленческие навыки?\n\n_Примеры: управление проектами, продажи, маркетинг, финансы, переговоры_", "type": "text"},
    {"text": "🌟 **Личные качества**: Какие ваши сильные личные качества?\n\n_Примеры: коммуникабельность, лидерство, креативность, стрессоустойчивость, внимательность_", "type": "text"},
    {"text": "🔥 **Сфера интересов**: В каких сферах вам интересно работать?\n\n_Примеры: технологии, образование, здоровье, творчество, спорт, экология_", "type": "text"},
    {"text": "💰 **Стартовый бюджет**: Сколько готовы вложить на старте?", 
     "options": [["0-50 тыс ₽"], ["50-200 тыс ₽"], ["200-500 тыс ₽"], ["500 тыс - 1 млн ₽"], ["1 млн + ₽"]], 
     "type": "options"},
    {"text": "⏰ **Время в неделю**: Сколько часов в неделю готовы уделять?", 
     "options": [["5-10 часов"], ["10-20 часов"], ["20-30 часов"], ["30-40 часов"], ["40+ часов"]], 
     "type": "options"},
    {"text": "🏢 **Опыт работы**: В какой сфере есть опыт?", 
     "options": [["IT/Технологии"], ["Маркетинг/Продажи"], ["Творчество/Дизайн"], ["Услуги/Сервис"], ["Торговля/Розница"], ["Образование/Консалтинг"], ["Производство"], ["Другое"]], 
     "type": "options"},
    {"text": "👥 **Команда**: Предпочитаете работать?", 
     "options": [["В одиночку"], ["С партнером"], ["В команде"], ["Найм сотрудников"]], 
     "type": "options"},
    {"text": "🚀 **Темп роста**: Что для вас важнее?", 
     "options": [["Быстрый рост и масштабирование"], ["Стабильный умеренный рост"], ["Минимальные риски, постепенное развитие"]], 
     "type": "options"},
    {"text": "🌍 **География работы**: Где планируете работать?", 
     "options": [["Только онлайн"], ["В своем городе"], ["По региону"], ["По всей стране"], ["Международно"]], 
     "type": "options"},
    {"text": "🎨 **Формат бизнеса**: Что ближе?", 
     "options": [["Физические товары"], ["Услуги"], ["Цифровые продукты"], ["Образование/Коучинг"], ["Франшиза"], ["Смешанный формат"]], 
     "type": "options"},
    {"text": "📈 **Цель на год**: Какой ежемесячный доход через 12 месяцев?", 
     "options": [["20-50 тыс ₽"], ["50-100 тыс ₽"], ["100-200 тыс ₽"], ["200-500 тыс ₽"], ["500 тыс + ₽"]], 
     "type": "options"},
    {"text": "🎯 **Предпочтения по бизнесу**: Что важно в бизнесе?\n\n_Можно выбрать несколько через запятую: работа с людьми, творчество, стабильность, гибкий график, высокая маржинальность, социальная польза_", 
     "type": "text"},
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

# ==================== КОМАНДЫ БОТА ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **Бизнес-навигатор**\n\n"
        "✅ *Расширенная анкета (16 вопросов):*\n"
        "• Образование и сертификаты\n"
        "• Навыки и личные качества\n"
        "• Бюджет и цели\n"
        "• Учет вашего региона\n\n"
        "Начнем?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Начать анкету", callback_data="start_quiz")]
        ]),
        parse_mode='Markdown'
    )
    return START

async def start_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📝 Начинаем анкету...")

    user_id = query.from_user.id
    user_data_store[user_id] = {
        'answers': {},
        'question_index': 0,
        'chat_id': query.message.chat_id,
        'user_name': query.from_user.first_name
    }

    return await send_question(context, user_id)

async def send_question(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    user_data = user_data_store[user_id]
    q_index = user_data['question_index']

    if q_index >= len(QUIZ_QUESTIONS):
        await context.bot.send_message(
            chat_id=user_data['chat_id'],
            text="✅ Анкета завершена! Анализирую данные...",
            reply_markup=ReplyKeyboardRemove()
        )
        return await generate_ideas(context, user_id)

    question = QUIZ_QUESTIONS[q_index]

    keyboard = None
    if question["type"] == "options" and "options" in question:
        keyboard = ReplyKeyboardMarkup(
            [[opt] for opt in question["options"]], 
            resize_keyboard=True
        )

    await context.bot.send_message(
        chat_id=user_data['chat_id'],
        text=f"*Вопрос {q_index+1}/{len(QUIZ_QUESTIONS)}*\n\n{question['text']}",
        reply_markup=keyboard,
        parse_mode='Markdown'
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
        await update.message.reply_text("✅ Все вопросы отвечены! Генерирую идеи...")
        return await generate_ideas(context, user_id)

async def generate_ideas(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    user_data = user_data_store[user_id]
    
    try:
        profile_summary = ""
        for key, answer in user_data['answers'].items():
            profile_summary += f"{key}: {answer}\n"
        
        # Получаем город из первого ответа
        location = user_data['answers'].get('q1', 'не указан')
        
        prompt = f"""
        На основе профиля клиента предложи 5 КОНКРЕТНЫХ бизнес-идей:
        
        ПРОФИЛЬ:
        {profile_summary}
        
        РЕГИОН: {location}
        
        ТРЕБОВАНИЯ:
        1. Учитывай образование, сертификаты и навыки клиента
        2. Предлагай реальные бизнесы, которые есть в регионе {location}
        3. Учитывай бюджет и временные возможности
        4. Каждая идея должна иметь потенциал роста
        
        ФОРМАТ:
        Для каждой идеи (1-5):
        1. [Название] - [Краткое описание]
        2. Почему подходит: [связь с навыками клиента]
        3. Инвестиции: [сумма в рублях]
        4. Реализация в {location}: [как работает в этом регионе]
        5. Первые шаги: [3 конкретных действия]
        """
        
        completion = await openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Ты бизнес-консультант, специализирующийся на региональном бизнесе в России и СНГ."},
                {"role": "user", "content": prompt}
            ]
        )

        ideas_text = completion.choices[0].message.content
        
        # Парсим идеи
        ideas = []
        lines = ideas_text.split('\n')
        current_idea = []
        
        for line in lines:
            if line.strip().startswith(('1.', '2.', '3.', '4.', '5.')) and current_idea:
                ideas.append('\n'.join(current_idea))
                current_idea = []
            if line.strip():
                current_idea.append(line.strip())
        
        if current_idea:
            ideas.append('\n'.join(current_idea))
        
        ideas = ideas[:5]
        user_niches_store[user_id] = ideas

        # Создаем кнопки
        keyboard = []
        for i in range(min(5, len(ideas))):
            # Берем первую строку как название
            first_line = ideas[i].split('\n')[0] if ideas[i] else f"Идея {i+1}"
            title = first_line[:30]
            keyboard.append([InlineKeyboardButton(f"🎯 {title}", callback_data=f"idea_{i}")])
        
        keyboard.append([InlineKeyboardButton("📋 Все идеи", callback_data="show_all")])

        await context.bot.send_message(
            chat_id=user_data['chat_id'],
            text=f"🎉 **Готово! {len(ideas)} бизнес-идей для вас**\n\n📍 *Регион:* {location}\n💼 *Учет навыков и образования*\n🎯 *Персонализированный подбор*\n\nВыберите идею:",
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
        idx = int(query.data.split("_")[1])

        if user_id in user_niches_store and idx < len(user_niches_store[user_id]):
            idea = user_niches_store[user_id][idx]
            
            # Генерируем детальный план
            plan_prompt = f"Создай детальный бизнес-план для: {idea}"
            
            try:
                completion = await openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "Создай подробный бизнес-план с шагами реализации."},
                        {"role": "user", "content": plan_prompt}
                    ]
                )

                plan = completion.choices[0].message.content
                
                await query.edit_message_text(
                    f"📋 **Детальный бизнес-план:**\n\n{idea}\n\n{plan}",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Назад к идеям", callback_data="back")]
                    ])
                )

            except Exception as e:
                await query.edit_message_text(f"Ошибка: {str(e)}")

    elif query.data == "show_all":
        if user_id in user_niches_store:
            all_ideas = "\n\n---\n\n".join(user_niches_store[user_id])
            await query.edit_message_text(f"📋 Все идеи:\n\n{all_ideas}")

    elif query.data == "back":
        if user_id in user_niches_store:
            keyboard = []
            for i in range(min(5, len(user_niches_store[user_id]))):
                first_line = user_niches_store[user_id][i].split('\n')[0] if i < len(user_niches_store[user_id]) else f"Идея {i+1}"
                title = first_line[:30]
                keyboard.append([InlineKeyboardButton(f"🎯 {title}", callback_data=f"idea_{i}")])
            
            await query.edit_message_text(
                "Выберите идею:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    return GENERATE_NICHES

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Бизнес-навигатор*\n\n"
        "/start - Начать анкету\n"
        "/help - Помощь\n"
        "/status - Статус бота\n"
        "/reset - Сбросить сессию",
        parse_mode='Markdown'
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 *Статус:*\n"
        f"• Активные сессии: {len(user_data_store)}\n"
        f"• Порт: {PORT}\n"
        f"• API: ✅ Активен\n"
        f"• Python: 3.9.16",
        parse_mode='Markdown'
    )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_data_store:
        del user_data_store[user_id]
    if user_id in user_niches_store:
        del user_niches_store[user_id]
    
    await update.message.reply_text("✅ Сессия сброшена. /start")

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
async def main():
    logger.info("🚀 Запуск бота на Render (Python 3.9.16)...")

    # 1. Запускаем health check сервер
    http_runner = await start_http_server()

    # 2. Создаем приложение бота
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # 3. ConversationHandler
    quiz_states = {}
    for i in range(len(QUIZ_QUESTIONS)):
        quiz_states[i] = [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quiz_answer)]

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start_command),
            CallbackQueryHandler(start_quiz_callback, pattern="^start_quiz$")
        ],
        states={
            START: [CallbackQueryHandler(start_quiz_callback, pattern="^start_quiz$")],
            **quiz_states,
            GENERATE_NICHES: [
                CallbackQueryHandler(handle_idea_selection, pattern="^(idea_|show_all|back)$")
            ]
        },
        fallbacks=[
            CommandHandler('help', help_command),
            CommandHandler('reset', reset_command),
            CommandHandler('status', status_command)
        ],
        per_user=True
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('status', status_command))
    application.add_handler(CommandHandler('reset', reset_command))

    # 4. Критически важные настройки для Render
    await application.initialize()
    await application.bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(2)

    logger.info("✅ Начинаем polling...")

    # 5. Запускаем polling (главное для Render)
    await application.run_polling(
        close_bot_session=False,  # ПРЕДОТВРАЩАЕТ КОНФЛИКТЫ
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
        poll_interval=1.0,
        timeout=30,
        handle_signals=False
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен")
    except Exception as e:
        logger.critical(f"💥 Ошибка: {e}")
        raise