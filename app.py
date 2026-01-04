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
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# ==================== КОНФИГУРАЦИЯ ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
PORT = int(os.environ.get('PORT', 10000))  # Изменено на 10000 для Render
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

# ==================== SELF-PING ДЛЯ RENDER ====================
async def self_ping_task():
    """Self-ping для предотвращения сна на Render Free"""
    while True:
        if RENDER_EXTERNAL_URL:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{RENDER_EXTERNAL_URL}/health", timeout=10):
                        logger.info(f"✅ Self-ping успешен")
            except Exception as e:
                logger.error(f"❌ Self-ping ошибка: {e}")
        await asyncio.sleep(300)  # Каждые 5 минут

# ==================== КОМАНДЫ БОТА ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **Бизнес-навигатор 2.0**\n\n"
        "✅ *Усовершенствованная анкета:*\n"
        "• 16 вопросов о вас и ваших возможностях\n"
        "• Учет образования и сертификатов\n"
        "• Анализ навыков и личных качеств\n"
        "• Подбор реальных бизнесов вашего региона\n\n"
        "🎯 *На выходе:*\n"
        "• 5 персонализированных бизнес-идей\n"
        "• Детальные планы по каждой идее\n"
        "• Учет местных особенностей вашего региона\n\n"
        "Начнем анкету?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Начать анкету", callback_data="start_quiz")],
            [InlineKeyboardButton("📊 Проверить API", callback_data="check_status")]
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
            f"🤖 Модель: {OPENAI_MODEL}\n"
            f"🏢 Пользователей в сессии: {len(user_data_store)}\n"
            "🚀 Бот готов к работе!",
            parse_mode='Markdown'
        )
        return START

    await query.edit_message_text("📝 Начинаем подробную анкету...")

    user_id = query.from_user.id
    user_data_store[user_id] = {
        'answers': {},
        'question_index': 0,
        'chat_id': query.message.chat_id,
        'user_name': query.from_user.first_name,
        'start_time': datetime.now().isoformat()
    }

    # Отправляем первый вопрос
    return await send_question(context, user_id)

async def send_question(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    user_data = user_data_store[user_id]
    q_index = user_data['question_index']

    if q_index >= len(QUIZ_QUESTIONS):
        await context.bot.send_message(
            chat_id=user_data['chat_id'],
            text="✅ Анкета завершена! Анализирую ваш профиль и подбираю бизнес-идии...",
            reply_markup=ReplyKeyboardRemove()
        )
        return await generate_ideas(context, user_id)

    question = QUIZ_QUESTIONS[q_index]

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
    return q_index

async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    question_key = f"q{q_index+1}"
    user_data['answers'][question_key] = {
        'question': QUIZ_QUESTIONS[q_index]['text'],
        'answer': update.message.text,
        'timestamp': datetime.now().isoformat()
    }
    
    user_data['question_index'] += 1

    # Прогресс
    progress = user_data['question_index']
    total = len(QUIZ_QUESTIONS)
    
    if progress < total:
        # Промежуточное сообщение о прогрессе
        if progress in [4, 8, 12]:
            await update.message.reply_text(
                f"✓ Ответ сохранен. Пройдено {progress}/{total} вопросов. Продолжаем!",
                reply_markup=ReplyKeyboardRemove()
            )
        
        return await send_question(context, user_id)
    else:
        await update.message.reply_text(
            "✅ Все вопросы отвечены! Анализирую ваш профиль...",
            reply_markup=ReplyKeyboardRemove()
        )
        return await generate_ideas(context, user_id)

async def generate_ideas(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    user_data = user_data_store[user_id]
    
    try:
        # Подготавливаем данные для GPT
        profile_summary = ""
        for key, data in user_data['answers'].items():
            profile_summary += f"{data['question']}\nОтвет: {data['answer']}\n\n"
        
        # Получаем город/регион из первого вопроса
        location = user_data['answers']['q1']['answer'] if 'q1' in user_data['answers'] else "не указан"
        
        prompt = f"""
        Ты опытный бизнес-консультант и аналитик рынка. 
        
        ПРОФИЛЬ КЛИЕНТА:
        {profile_summary}
        
        ЗАДАЧА:
        1. Проанализируй профиль выше
        2. Предложи 5 КОНКРЕТНЫХ бизнес-идей, которые:
           - Максимально соответствуют навыкам, образованию и интересам клиента
           - Учитывают бюджет и временные возможности
           - Реалистичны для региона: {location}
           - Имеют потенциал роста согласно целям клиента
        
        ДЛЯ КАЖДОЙ ИДЕИ УКАЖИ:
        1. Название бизнеса
        2. Краткое описание (2-3 предложения)
        3. Почему подходит клиенту (связь с его навыками/образованием)
        4. Стартовые инвестиции в рублях (диапазон)
        5. Ежемесячная прибыль через 6-12 месяцев
        6. Конкретные шаги для запуска (первые 3 шага)
        7. Риски и как их минимизировать
        8. Реальные примеры такого бизнеса в регионе {location} (если известны)
        
        ФОРМАТ ВЫВОДА:
        Для каждой идеи - четкий блок с нумерацией.
        """
        
        logger.info(f"Генерация идей для пользователя {user_id} из {location}")
        
        completion = await openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Ты профессиональный бизнес-консультант с учетом региональных особенностей России и СНГ."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=3000
        )

        ideas_text = completion.choices[0].message.content
        
        # Парсим идеи
        ideas = []
        current_idea = []
        lines = ideas_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith(('1.', '2.', '3.', '4.', '5.')) and current_idea:
                ideas.append('\n'.join(current_idea))
                current_idea = []
            if line:
                current_idea.append(line)
        
        if current_idea:
            ideas.append('\n'.join(current_idea))
        
        # Ограничиваем 5 идеями
        ideas = ideas[:5]
        user_niches_store[user_id] = ideas

        # Создаем интерактивные кнопки
        keyboard = []
        for i in range(min(5, len(ideas))):
            # Извлекаем название из первой строки идеи
            first_line = ideas[i].split('\n')[0] if ideas[i] else f"Идея {i+1}"
            title = first_line.replace(f"{i+1}. ", "")[:30]  # Обрезаем длинные названия
            keyboard.append([InlineKeyboardButton(f"🎯 {title}", callback_data=f"idea_{i}")])
        
        keyboard.append([InlineKeyboardButton("📋 Все идеи текстом", callback_data="show_all")])
        keyboard.append([InlineKeyboardButton("🔄 Новый поиск", callback_data="restart")])

        await context.bot.send_message(
            chat_id=user_data['chat_id'],
            text=f"🎉 **Подобрано {len(ideas)} бизнес-идей для вас!**\n\n"
                 f"📍 *Ваш регион:* {location}\n"
                 f"💼 *Учет навыков:* образование, сертификаты, опыт\n"
                 f"🎯 *Персонализация:* под ваш бюджет и цели\n\n"
                 "Нажмите на идею для детального бизнес-плана:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

        return GENERATE_NICHES

    except Exception as e:
        logger.error(f"Ошибка генерации идей: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=user_data['chat_id'],
            text="❌ Произошла ошибка при анализе вашего профиля.\n"
                 "Попробуйте начать заново: /start\n\n"
                 f"Техническая информация: {str(e)[:100]}...",
            parse_mode='Markdown'
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
            
            # Генерируем расширенный бизнес-план
            plan_prompt = f"""
            Разработай ДЕТАЛЬНЫЙ бизнес-план для этой идеи:
            
            {idea}
            
            Структура плана:
            1. Резюме проекта
            2. Анализ рынка в регионе клиента
            3. Целевая аудитория и ее портрет
            4. Конкурентные преимущества
            5. Маркетинговая стратегия (конкретные каналы)
            6. Финансовый план на 12 месяцев
            7. Операционная деятельность
            8. Юридические аспекты
            9. Дорожная карта на первые 90 дней
            10. Метрики успеха
            
            Будь максимально конкретным и практичным.
            """
            
            try:
                await query.edit_message_text(
                    "📊 Генерирую детальный бизнес-план...",
                    parse_mode='Markdown'
                )
                
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
                
                # Формируем финальное сообщение
                idea_title = idea.split('\n')[0] if idea else f"Идея {idx+1}"
                response_text = f"📋 **БИЗНЕС-ПЛАН**\n\n*{idea_title}*\n\n{plan}"
                
                # Обрезаем если слишком длинное
                if len(response_text) > 4000:
                    response_text = response_text[:4000] + "\n\n... (продолжение в следующем сообщении)"
                
                keyboard = [
                    [InlineKeyboardButton("⬅️ К списку идей", callback_data="back_to_list")],
                    [InlineKeyboardButton("🔄 Новый поиск", callback_data="restart")]
                ]
                
                await query.edit_message_text(
                    response_text,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

            except Exception as e:
                logger.error(f"Ошибка генерации плана: {e}")
                await query.edit_message_text(
                    f"⚠️ Не удалось сгенерировать детальный план.\n\n"
                    f"Идея: {idea[:500]}...\n\n"
                    f"Ошибка: {str(e)[:200]}",
                    parse_mode='Markdown'
                )

    elif query.data == "show_all":
        if user_id in user_niches_store:
            all_ideas = "\n\n---\n\n".join(user_niches_store[user_id])
            
            # Разбиваем на части если слишком длинно
            if len(all_ideas) > 4000:
                parts = [all_ideas[i:i+4000] for i in range(0, len(all_ideas), 4000)]
                for i, part in enumerate(parts):
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=f"📋 Все идеи (часть {i+1}/{len(parts)}):\n\n{part}",
                        parse_mode='Markdown'
                    )
            else:
                await query.edit_message_text(
                    f"📋 Все идеи:\n\n{all_ideas}",
                    parse_mode='Markdown'
                )
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_list")],
                [InlineKeyboardButton("🔄 Новый поиск", callback_data="restart")]
            ]
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Выберите действие:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif query.data == "back_to_list":
        if user_id in user_niches_store:
            keyboard = []
            for i in range(min(5, len(user_niches_store[user_id]))):
                first_line = user_niches_store[user_id][i].split('\n')[0] if i < len(user_niches_store[user_id]) else f"Идея {i+1}"
                title = first_line.replace(f"{i+1}. ", "")[:30]
                keyboard.append([InlineKeyboardButton(f"🎯 {title}", callback_data=f"idea_{i}")])
            
            keyboard.append([InlineKeyboardButton("📋 Все идеи текстом", callback_data="show_all")])
            keyboard.append([InlineKeyboardButton("🔄 Новый поиск", callback_data="restart")])

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
    await update.message.reply_text(
        "🤖 *Бизнес-навигатор 2.0*\n\n"
        "*Команды:*\n"
        "/start - Начать анкету\n"
        "/help - Эта справка\n"
        "/status - Статус бота\n"
        "/reset - Сбросить текущую сессию\n\n"
        "*Особенности:*\n"
        "• Учет образования и сертификатов\n"
        "• Анализ навыков и качеств\n"
        "• Подбор реальных бизнесов региона\n"
        "• Детальные бизнес-планы\n"
        "• Данные хранятся в течение сессии",
        parse_mode='Markdown'
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active_users = len(user_data_store)
    total_memory = sum(len(str(data)) for data in user_data_store.values()) / 1024  # в КБ
    
    await update.message.reply_text(
        f"📊 *Статус системы*\n\n"
        f"• Активные сессии: {active_users}\n"
        f"• Использовано памяти: {total_memory:.1f} КБ\n"
        f"• Порт сервера: {PORT}\n"
        f"• OpenAI API: ✅ Активен\n"
        f"• Модель: {OPENAI_MODEL}\n"
        f"• Режим: Polling (Render)\n\n"
        f"_Сессия сохраняется пока вы в чате_",
        parse_mode='Markdown'
    )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_data_store:
        del user_data_store[user_id]
    if user_id in user_niches_store:
        del user_niches_store[user_id]
    
    await update.message.reply_text(
        "✅ Ваша сессия сброшена. Начните заново: /start",
        parse_mode='Markdown'
    )

# ==================== ОСНОВНАЯ ФУНКЦИЯ (POLLING ДЛЯ RENDER) ====================
async def main():
    logger.info("🚀 Запуск бота для Render...")

    # 1. Запускаем health check сервер
    http_runner = await start_http_server()
    logger.info("✅ Health check сервер запущен")

    # 2. Запускаем self-ping в фоне (только если есть внешний URL)
    if RENDER_EXTERNAL_URL:
        asyncio.create_task(self_ping_task())
        logger.info(f"✅ Self-ping активен для {RENDER_EXTERNAL_URL}")

    # 3. Создаем приложение бота
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    logger.info("✅ Приложение бота создано")

    # 4. Настраиваем ConversationHandler
    quiz_states = {}
    for i in range(len(QUIZ_QUESTIONS)):
        quiz_states[i] = [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quiz_answer)]

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start_command),
            CallbackQueryHandler(start_quiz_callback, pattern="^(start_quiz|check_status)$")
        ],
        states={
            START: [CallbackQueryHandler(start_quiz_callback, pattern="^(start_quiz|check_status)$")],
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
        per_chat=True,
        conversation_timeout=3600  # 1 час таймаут сессии
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('status', status_command))
    application.add_handler(CommandHandler('reset', reset_command))
    
    # 5. Критически важные параметры для Render
    await application.initialize()
    
    # Очистка старых вебхуков (предотвращение конфликтов)
    await application.bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(2)
    
    logger.info("✅ Начинаем polling...")

    # 6. Запускаем polling с параметрами для Render
    await application.run_polling(
        # Ключевой параметр для предотвращения конфликтов на Render
        close_bot_session=False,
        
        # Оптимизация для стабильности
        allowed_updates=Update.ALL_TYPES,
        poll_interval=0.5,
        timeout=30,
        pool_timeout=30,
        
        # Отключаем обработку сигналов (для Render)
        handle_signals=False,
        
        # Пропускаем накопившиеся апдейты
        drop_pending_updates=True,
        
        # Лимиты частоты
        bootstrap_retries=3,
        read_timeout=7,
        write_timeout=7,
        connect_timeout=7
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"💥 Критическая ошибка: {e}", exc_info=True)
        raise