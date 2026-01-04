import os
import logging
import asyncio
import json
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

# ВРЕМЕННО: Тестовые значения для проверки
if not TELEGRAM_TOKEN:
    logger.warning("⚠️ TELEGRAM_BOT_TOKEN не задан, используем тестовый токен")
    TELEGRAM_TOKEN = "test_telegram_token_placeholder"
    
if not OPENAI_API_KEY:
    logger.warning("⚠️ OPENAI_API_KEY не задан, используем тестовый ключ")
    OPENAI_API_KEY = "test_openai_key_placeholder"

logger.info(f"✅ PORT: {PORT}")
logger.info(f"✅ TELEGRAM_TOKEN задан: {'Да' if TELEGRAM_TOKEN and TELEGRAM_TOKEN != 'test_telegram_token_placeholder' else 'Нет (тестовый)'}")
logger.info(f"✅ OPENAI_API_KEY задан: {'Да' if OPENAI_API_KEY and OPENAI_API_KEY != 'test_openai_key_placeholder' else 'Нет (тестовый)'}")

# Инициализация OpenAI (даже с тестовым ключом)
try:
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    logger.info("✅ OpenAI клиент инициализирован")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации OpenAI: {e}")
    # Создаем заглушку для теста
    openai_client = None

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

# Хранилище данных в памяти
user_data_store: Dict[int, Dict] = {}
user_niches_store: Dict[int, List] = {}

# ==================== HEALTH CHECK СЕРВЕР ====================
async def health_handler(request):
    return web.Response(text="OK", status=200)

async def start_http_server():
    """Запуск сервера для health check"""
    app = web.Application()
    app.router.add_get('/health', health_handler)
    app.router.add_get('/', health_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"✅ Health check сервер запущен на порту {PORT}")
    return runner

# ==================== КОМАНДЫ БОТА ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    # Проверяем наличие ключей
    if TELEGRAM_TOKEN == "test_telegram_token_placeholder":
        await update.message.reply_text(
            "⚠️ *ВНИМАНИЕ: Бот в тестовом режиме*\n\n"
            "TELEGRAM_BOT_TOKEN не настроен. Бот работает в демо-режиме.",
            parse_mode='Markdown'
        )
    
    await update.message.reply_text(
        "🤖 **Бизнес-навигатор**\n\n"
        "✅ *Расширенная анкета из 16 вопросов*\n"
        "• Учет образования и сертификатов\n"
        "• Анализ навыков и личных качеств\n"
        "• Подбор реальных бизнесов вашего региона\n"
        "• Детальные бизнес-планы\n\n"
        "Начнем?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Начать анкету", callback_data="start_quiz")]
        ]),
        parse_mode='Markdown'
    )
    return START

async def start_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало анкеты"""
    query = update.callback_query
    await query.answer()
    
    # Проверяем OpenAI ключ
    if not openai_client or OPENAI_API_KEY == "test_openai_key_placeholder":
        await query.edit_message_text(
            "❌ *OpenAI API ключ не настроен*\n\n"
            "Для работы бота требуется настроить OPENAI_API_KEY в настройках Render.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    user_id = query.from_user.id
    user_data_store[user_id] = {
        'answers': {},
        'question_index': 0,
        'chat_id': query.message.chat_id,
        'user_name': query.from_user.first_name,
        'start_time': datetime.now().isoformat()
    }
    
    await query.edit_message_text("📝 Начинаем анкету...")
    return await send_question(context, user_id)

async def send_question(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Отправка следующего вопроса"""
    user_data = user_data_store[user_id]
    q_index = user_data['question_index']
    
    if q_index >= len(QUIZ_QUESTIONS):
        await context.bot.send_message(
            chat_id=user_data['chat_id'],
            text="✅ Анкета завершена! Анализирую ваш профиль...",
            reply_markup=ReplyKeyboardRemove()
        )
        return await generate_ideas(context, user_id)
    
    question = QUIZ_QUESTIONS[q_index]
    
    # Создаем клавиатуру для вопросов с вариантами
    keyboard = None
    if question["type"] == "options" and "options" in question:
        keyboard = ReplyKeyboardMarkup(
            [[opt] for opt in question["options"]],
            resize_keyboard=True,
            one_time_keyboard=False
        )
    
    await context.bot.send_message(
        chat_id=user_data['chat_id'],
        text=f"*Вопрос {q_index+1}/{len(QUIZ_QUESTIONS)}*\n\n{question['text']}",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    return q_index  # Возвращаем номер состояния

async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа на вопрос"""
    user_id = update.effective_user.id
    
    if user_id not in user_data_store:
        await update.message.reply_text(
            "Сессия устарела. Начните заново: /start",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    user_data = user_data_store[user_id]
    q_index = user_data['question_index']
    
    # Сохраняем ответ
    user_data['answers'][f'q{q_index+1}'] = update.message.text
    user_data['question_index'] += 1
    
    # Проверяем, закончились ли вопросы
    if user_data['question_index'] < len(QUIZ_QUESTIONS):
        return await send_question(context, user_id)
    else:
        await update.message.reply_text(
            "✅ Все вопросы отвечены! Формирую персонализированные бизнес-идеи...",
            reply_markup=ReplyKeyboardRemove()
        )
        return await generate_ideas(context, user_id)

async def generate_ideas(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Генерация бизнес-идей на основе анкеты"""
    user_data = user_data_store[user_id]
    
    # Проверка OpenAI клиента
    if not openai_client:
        await context.bot.send_message(
            chat_id=user_data['chat_id'],
            text="❌ OpenAI API не настроен. Проверьте OPENAI_API_KEY в настройках Render.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    try:
        # Формируем промпт для GPT
        profile_summary = "\n".join([f"{key}: {value}" for key, value in user_data['answers'].items()])
        
        # Получаем город из первого ответа
        location = user_data['answers'].get('q1', 'регион не указан')
        
        prompt = f"""
        Ты бизнес-консультант с экспертизой в российских регионах.
        
        ПРОФИЛЬ КЛИЕНТА:
        {profile_summary}
        
        РЕГИОН: {location}
        
        ЗАДАЧА: Предложи 5 конкретных бизнес-идей, которые:
        1. Максимально соответствуют образованию, навыкам и интересам клиента
        2. Реалистичны для региона {location} (учитывай местный рынок)
        3. Учитывают бюджет и временные возможности
        4. Имеют потенциал роста
        5. Основаны на реальных примерах из региона
        
        ДЛЯ КАЖДОЙ ИДЕИ:
        1. [Название] - [Краткое описание, 1-2 предложения]
        2. Почему подходит: [связь с профилем клиента]
        3. Инвестиции: [диапазон в рублях]
        4. Особенности в {location}: [как адаптировать под регион]
        5. Первые шаги: [3 конкретных действия]
        
        Формат: каждая идея с новой строки, с четкой нумерацией 1-5.
        """
        
        logger.info(f"Генерация идей для пользователя {user_id}, регион: {location}")
        
        # Отправляем запрос к OpenAI
        completion = await openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Ты профессиональный бизнес-консультант, который дает практические рекомендации для российских регионов."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        ideas_text = completion.choices[0].message.content
        
        # Разбиваем на отдельные идеи
        ideas = []
        current_idea = []
        
        for line in ideas_text.split('\n'):
            line = line.strip()
            if line and line[0].isdigit() and '.' in line and current_idea:
                ideas.append('\n'.join(current_idea))
                current_idea = [line]
            elif line:
                current_idea.append(line)
        
        if current_idea:
            ideas.append('\n'.join(current_idea))
        
        # Ограничиваем 5 идеями
        ideas = ideas[:5]
        user_niches_store[user_id] = ideas
        
        # Создаем интерактивные кнопки
        keyboard = []
        for i, idea in enumerate(ideas[:5], 1):
            # Извлекаем название из первой строки
            first_line = idea.split('\n')[0] if idea else f"Идея {i}"
            title = first_line[:35] + "..." if len(first_line) > 35 else first_line
            keyboard.append([InlineKeyboardButton(f"{i}. {title}", callback_data=f"idea_{i-1}")])
        
        keyboard.append([InlineKeyboardButton("📋 Показать все идеи", callback_data="show_all")])
        
        await context.bot.send_message(
            chat_id=user_data['chat_id'],
            text=f"🎉 **Подобрано {len(ideas)} бизнес-идей для вас!**\n\n"
                 f"📍 *Ваш регион:* {location}\n"
                 f"💼 *Учтено:* образование, навыки, опыт\n"
                 f"🎯 *Персонализированный подбор*\n\n"
                 "Нажмите на идею для детального бизнес-плана:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return GENERATE_NICHES
        
    except Exception as e:
        logger.error(f"Ошибка генерации идей: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=user_data['chat_id'],
            text="❌ Произошла ошибка при генерации идей. Попробуйте начать заново: /start",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

async def handle_idea_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора идеи"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data.startswith("idea_"):
        idx = int(query.data.split("_")[1])
        
        if user_id in user_niches_store and idx < len(user_niches_store[user_id]):
            idea = user_niches_store[user_id][idx]
            
            # Проверка OpenAI клиента
            if not openai_client:
                await query.edit_message_text(
                    "❌ OpenAI API не настроен. Невозможно сгенерировать бизнес-план.",
                    parse_mode='Markdown'
                )
                return GENERATE_NICHES
            
            # Генерируем детальный план
            plan_prompt = f"""
            Разработай детальный бизнес-план для этой идеи:
            
            {idea}
            
            Включи:
            1. Анализ рынка и конкурентов
            2. Целевая аудитория
            3. Маркетинговая стратегия
            4. Финансовый план на 12 месяцев
            5. Операционные процессы
            6. Риски и их минимизация
            7. План действий на первые 90 дней
            
            Будь конкретным и практичным.
            """
            
            try:
                await query.edit_message_text("📊 Составляю детальный бизнес-план...")
                
                completion = await openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "Ты бизнес-аналитик, создающий практические бизнес-планы."},
                        {"role": "user", "content": plan_prompt}
                    ],
                    temperature=0.5,
                    max_tokens=2500
                )
                
                plan = completion.choices[0].message.content
                
                # Формируем ответ (обрезаем если слишком длинный)
                response = f"📋 **ДЕТАЛЬНЫЙ БИЗНЕС-ПЛАН**\n\n{idea}\n\n{plan}"
                if len(response) > 4000:
                    response = response[:4000] + "\n\n... (план продолжается, сохраните его)"
                
                await query.edit_message_text(
                    response,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Назад к списку идей", callback_data="back_to_list")],
                        [InlineKeyboardButton("🔄 Новый поиск", callback_data="restart")]
                    ])
                )
                
            except Exception as e:
                logger.error(f"Ошибка генерации плана: {e}")
                await query.edit_message_text(
                    f"⚠️ Не удалось сгенерировать детальный план.\n\n"
                    f"Идея: {idea[:300]}...",
                    parse_mode='Markdown'
                )
    
    elif query.data == "show_all":
        if user_id in user_niches_store:
            all_ideas = "\n\n" + "="*50 + "\n\n".join(user_niches_store[user_id])
            await query.edit_message_text(
                f"📋 **Все идеи:**{all_ideas}",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_list")],
                    [InlineKeyboardButton("🔄 Новый поиск", callback_data="restart")]
                ])
            )
    
    elif query.data == "back_to_list":
        if user_id in user_niches_store:
            keyboard = []
            for i, idea in enumerate(user_niches_store[user_id][:5], 1):
                first_line = idea.split('\n')[0] if idea else f"Идея {i}"
                title = first_line[:35] + "..." if len(first_line) > 35 else first_line
                keyboard.append([InlineKeyboardButton(f"{i}. {title}", callback_data=f"idea_{i-1}")])
            
            keyboard.append([InlineKeyboardButton("📋 Показать все идеи", callback_data="show_all")])
            
            await query.edit_message_text(
                "Выберите идею для детального бизнес-плана:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    elif query.data == "restart":
        # Очищаем данные пользователя
        if user_id in user_data_store:
            del user_data_store[user_id]
        if user_id in user_niches_store:
            del user_niches_store[user_id]
        
        await query.edit_message_text(
            "🔄 Начинаем новую анкету...",
            parse_mode='Markdown'
        )
        # Запускаем новый диалог
        user_data_store[user_id] = {
            'answers': {},
            'question_index': 0,
            'chat_id': query.message.chat_id,
            'user_name': query.from_user.first_name,
            'start_time': datetime.now().isoformat()
        }
        return await send_question(context, user_id)
    
    return GENERATE_NICHES

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    # Информация о настройках
    config_status = "✅" if TELEGRAM_TOKEN != "test_telegram_token_placeholder" else "⚠️"
    openai_status = "✅" if OPENAI_API_KEY != "test_openai_key_placeholder" else "❌"
    
    await update.message.reply_text(
        f"🤖 *Бизнес-навигатор*\n\n"
        f"📋 *Статус настроек:*\n"
        f"• Telegram бот: {config_status}\n"
        f"• OpenAI API: {openai_status}\n\n"
        f"📋 *Команды:*\n"
        f"/start - Начать анкету\n"
        f"/help - Эта справка\n"
        f"/status - Статус бота\n"
        f"/reset - Сбросить текущую сессию\n\n"
        f"💡 *Как работает:*\n"
        f"1. Ответьте на 16 вопросов о себе\n"
        f"2. Получите 5 персонализированных бизнес-идей\n"
        f"3. Выберите идею для детального плана\n"
        f"4. Данные сохраняются пока вы в чате",
        parse_mode='Markdown'
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /status"""
    config_status = "✅ НАСТРОЕН" if TELEGRAM_TOKEN != "test_telegram_token_placeholder" else "⚠️ ТЕСТОВЫЙ"
    openai_status = "✅ НАСТРОЕН" if OPENAI_API_KEY != "test_openai_key_placeholder" else "❌ НЕ НАСТРОЕН"
    
    await update.message.reply_text(
        f"📊 *Статус системы*\n\n"
        f"• Активные сессии: {len(user_data_store)}\n"
        f"• Telegram бот: {config_status}\n"
        f"• OpenAI API: {openai_status}\n"
        f"• Порт сервера: {PORT}\n"
        f"• Python версия: 3.9.16\n"
        f"• Режим: Polling (Render)\n\n"
        f"🌐 *Health check:* https://ваш-сервис.onrender.com/health",
        parse_mode='Markdown'
    )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /reset"""
    user_id = update.effective_user.id
    if user_id in user_data_store:
        del user_data_store[user_id]
    if user_id in user_niches_store:
        del user_niches_store[user_id]
    
    await update.message.reply_text(
        "✅ Ваша сессия сброшена. Начните заново: /start",
        parse_mode='Markdown'
    )

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
async def main():
    """Главная функция запуска бота"""
    logger.info("=" * 50)
    logger.info("🚀 Запуск бизнес-бота на Render...")
    logger.info(f"Порт: {PORT}")
    logger.info(f"Telegram токен: {'Настроен' if TELEGRAM_TOKEN != 'test_telegram_token_placeholder' else 'Тестовый'}")
    logger.info(f"OpenAI ключ: {'Настроен' if OPENAI_API_KEY != 'test_openai_key_placeholder' else 'Тестовый'}")
    logger.info("=" * 50)
    
    # 1. Запускаем health check сервер
    try:
        http_runner = await start_http_server()
        logger.info("✅ Health check сервер запущен")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска health check сервера: {e}")
        return
    
    # 2. Создаем приложение бота
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        logger.info("✅ Приложение Telegram бота создано")
    except Exception as e:
        logger.error(f"❌ Ошибка создания приложения бота: {e}")
        return
    
    # 3. Настраиваем ConversationHandler
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
                CallbackQueryHandler(handle_idea_selection, pattern="^(idea_|show_all|back_to_list|restart)$")
            ]
        },
        fallbacks=[
            CommandHandler('help', help_command),
            CommandHandler('reset', reset_command),
            CommandHandler('status', status_command),
            CommandHandler('cancel', lambda u, c: ConversationHandler.END)
        ],
        per_user=True,
        per_chat=True
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('status', status_command))
    application.add_handler(CommandHandler('reset', reset_command))
    
    # 4. Настройки для Render
    await application.initialize()
    
    # Очищаем старые вебхуки (важно для предотвращения конфликтов)
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        await asyncio.sleep(2)
        logger.info("✅ Вебхуки очищены")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка очистки вебхуков: {e}")
    
    logger.info("✅ Бот запускается в режиме polling...")
    
    # 5. Запускаем polling с параметрами для Render
    try:
        await application.run_polling(
            # Ключевой параметр для предотвращения конфликтов на Render
            close_bot_session=False,
            
            # Оптимизация для стабильности
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            poll_interval=1.0,
            timeout=30,
            
            # Отключаем обработку сигналов (для Render)
            handle_signals=False
        )
    except Exception as e:
        logger.critical(f"❌ Ошибка при запуске polling: {e}")
        raise
    finally:
        # Останавливаем health check сервер
        try:
            await http_runner.cleanup()
            logger.info("✅ Health check сервер остановлен")
        except:
            pass
        logger.info("⏹️ Бот остановлен")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"💥 Критическая ошибка: {e}", exc_info=True)
        raise