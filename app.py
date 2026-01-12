#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Бизнес-навигатор: Telegram бот для подбора бизнес-идей
Версия с расширенной отладкой
"""

import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass, field

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

from openai import OpenAI
import aiohttp
from aiohttp import web

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Добавляем более детальное логирование для отладки
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

# ==================== КОНСТАНТЫ ====================
QUESTIONNAIRE_STATE = 1
BUSINESS_IDEAS_STATE = 2
BUSINESS_PLAN_STATE = 3

QUESTIONS = [
    "1. В каком городе/регионе вы проживаете?",
    "2. Какое у вас образование и сертификаты?",
    "3. Какие технические навыки у вас есть?",
    "4. Какие профессиональные навыки?",
    "5. Какие у вас личные качества?",
    "6. Какие сферы вам интересны?",
    "7. Какой у вас опыт работы?",
    "8. Какой стартовый бюджет?",
    "9. Сколько времени готовы уделять?",
    "10. Есть ли команда или партнеры?",
    "11. Каков ваш риск-профиль?",
    "12. Какой тип бизнеса предпочитаете?",
    "13. Есть ли доступ к специальным ресурсам?",
    "14. На какой срок планируете бизнес?",
    "15. Какие цели кроме прибыли?",
    "16. Есть ли у вас хобби для монетизации?"
]

# ==================== МОДЕЛИ ====================
@dataclass
class UserProfile:
    user_id: int
    timestamp: datetime = field(default_factory=datetime.now)
    answers: Dict[int, str] = field(default_factory=dict)
    current_question: int = 0
    business_ideas: List[str] = field(default_factory=list)
    selected_business_idea: str = ""
    business_plan: str = ""

user_sessions: Dict[int, UserProfile] = {}

# ==================== OPENAI ====================
def init_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "test-key-123":
        logger.warning("⚠️ OPENAI_API_KEY не задан, используем тестовый режим")
        return None
    logger.info("✅ OPENAI_API_KEY задан")
    return OpenAI(api_key=api_key)

openai_client = init_openai_client()

# ==================== ОТЛАДОЧНЫЕ ФУНКЦИИ ====================
async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для отладки"""
    user = update.effective_user
    user_id = user.id
    
    debug_info = f"""
🔍 *ОТЛАДОЧНАЯ ИНФОРМАЦИЯ:*

👤 *Пользователь:*
ID: {user_id}
Имя: {user.first_name or ''} {user.last_name or ''}
Username: @{user.username or 'нет'}

🛠 *Система:*
Python: {os.sys.version}
Рабочая директория: {os.getcwd()}
Файлы: {', '.join([f for f in os.listdir('.') if f.endswith('.py')])}

⚙️ *Переменные окружения:*
TELEGRAM_BOT_TOKEN: {'ЕСТЬ' if os.getenv('TELEGRAM_BOT_TOKEN') else 'НЕТ'}
TELEGRAM_TOKEN: {'ЕСТЬ' if os.getenv('TELEGRAM_TOKEN') else 'НЕТ'}
OPENAI_API_KEY: {'ЕСТЬ (реальный)' if os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_API_KEY') != 'test-key-123' else 'НЕТ (тестовый)'}
PORT: {os.getenv('PORT', '10000')}

📊 *Сессии:*
Активных сессий: {len(user_sessions)}
Ваша сессия: {'ЕСТЬ' if user_id in user_sessions else 'НЕТ'}

🔄 *Состояние бота:* АКТИВЕН
🕒 *Время:* {datetime.now()}
"""
    
    await update.message.reply_text(debug_info, parse_mode='Markdown')

async def echo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Эхо-команда для проверки связи"""
    text = update.message.text
    user = update.effective_user
    
    echo_text = f"""
📨 *Эхо-ответ:*

Ваше сообщение: "{text}"
Длина: {len(text)} символов

👤 От: {user.first_name} (ID: {user.id})
🕒 Время: {datetime.now()}
🔗 Chat ID: {update.effective_chat.id}

✅ Бот работает и получает сообщения!
"""
    
    await update.message.reply_text(echo_text, parse_mode='Markdown')
    logger.info(f"ECHO: Пользователь {user.id} отправил: {text[:50]}...")

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    logger.info(f"START вызван пользователем {update.effective_user.id}")
    
    user = update.effective_user
    user_id = user.id
    
    # Логируем детали
    logger.info(f"Детали запроса: message_id={update.message.message_id}, chat_id={update.effective_chat.id}")
    
    # Создаем сессию
    user_sessions[user_id] = UserProfile(user_id=user_id)
    logger.info(f"Создана сессия для пользователя {user_id}")
    
    welcome_text = """
👋 *Добро пожаловать в Бизнес-Навигатор!*

Я помогу вам найти подходящую бизнес-идею на основе ваших навыков и интересов.

🎯 *Что я могу:*
1. Провести анкету из 16 вопросов
2. Проанализировать ваш профиль
3. Предложить 5 персонализированных бизнес-идей
4. Подробно расписать план для выбранной идеи

🚀 *Давайте начнем!*
"""
    
    keyboard = [
        [InlineKeyboardButton("📋 Начать анкету", callback_data='start_questionnaire')],
        [InlineKeyboardButton("🛠 Отладка", callback_data='debug_info')],
        [InlineKeyboardButton("❓ Помощь", callback_data='help_info')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        logger.info(f"START: Приветственное сообщение отправлено пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при отправке сообщения. Попробуйте еще раз.",
            parse_mode='Markdown'
        )

async def debug_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать отладочную информацию через кнопку"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = user.id
    
    debug_text = f"""
🛠 *Отладочная информация:*

✅ Кнопки работают!
👤 Ваш ID: {user_id}
📱 Chat ID: {query.message.chat_id}
🕒 Время: {datetime.now()}

📊 *Статус сессии:* {'Активна' if user_id in user_sessions else 'Не активна'}
🎯 *Текущий вопрос:* {user_sessions[user_id].current_question if user_id in user_sessions else 'Н/Д'}

🔍 *Тест кнопок пройден успешно!*
"""
    
    keyboard = [
        [InlineKeyboardButton("📋 Начать анкету", callback_data='start_questionnaire')],
        [InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        debug_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    logger.info(f"DEBUG_INFO: Отладочная информация показана пользователю {user_id}")

async def help_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать справку"""
    query = update.callback_query
    await query.answer()
    
    help_text = """
❓ *Помощь и поддержка:*

📋 *Основные команды:*
• /start - Начать работу с ботом
• /debug - Отладочная информация
• /echo [текст] - Проверка связи
• /test - Проверка работоспособности
• /cancel - Отмена текущего действия

🎯 *Как пользоваться:*
1. Нажмите "Начать анкету"
2. Отвечайте на вопросы по порядку
3. Получите персонализированные бизнес-идеи
4. Выберите идею для детального плана

⚠️ *Если что-то не работает:*
• Проверьте подключение к интернету
• Попробуйте команду /start заново
• Используйте /debug для диагностики
• Обратитесь к разработчику

👨‍💻 *Разработчик:* @ArtasKanzychakov
"""
    
    keyboard = [
        [InlineKeyboardButton("📋 Начать анкету", callback_data='start_questionnaire')],
        [InlineKeyboardButton("🛠 Отладка", callback_data='debug_info')],
        [InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в начало"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    logger.info(f"BACK_TO_START: Пользователь {user_id} вернулся в начало")
    
    # Сбрасываем сессию
    user_sessions[user_id] = UserProfile(user_id=user_id)
    
    welcome_text = """
👋 *Снова здравствуйте!*

Вы вернулись в главное меню.

🎯 *Что дальше?*
• Начать новую анкету
• Проверить работу бота
• Посмотреть справку

🚀 *Выберите действие:*
"""
    
    keyboard = [
        [InlineKeyboardButton("📋 Начать анкету", callback_data='start_questionnaire')],
        [InlineKeyboardButton("🛠 Отладка", callback_data='debug_info')],
        [InlineKeyboardButton("❓ Помощь", callback_data='help_info')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def start_questionnaire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать анкету - обработчик кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    logger.info(f"START_QUESTIONNAIRE: Начало анкеты для пользователя {user_id}")
    
    # Создаем/сбрасываем профиль
    user_sessions[user_id] = UserProfile(user_id=user_id)
    profile = user_sessions[user_id]
    profile.current_question = 0
    
    await query.edit_message_text(
        f"📝 *Анкета началась!*\n\n"
        f"*Вопрос 1 из {len(QUESTIONS)}:*\n"
        f"{QUESTIONS[0]}\n\n"
        f"✏️ *Пожалуйста, ответьте текстом:*",
        parse_mode='Markdown'
    )
    
    return QUESTIONNAIRE_STATE

async def handle_questionnaire_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответов на вопросы"""
    user_id = update.effective_user.id
    text = update.message.text
    
    logger.info(f"QUESTIONNAIRE_ANSWER: Пользователь {user_id}, ответ: {text[:50]}...")
    
    if user_id not in user_sessions:
        logger.warning(f"Сессия не найдена для пользователя {user_id}")
        await update.message.reply_text("❌ Сессия устарела. Начните заново с /start")
        return ConversationHandler.END
    
    profile = user_sessions[user_id]
    profile.answers[profile.current_question] = text
    
    profile.current_question += 1
    
    if profile.current_question >= len(QUESTIONS):
        logger.info(f"Анкета завершена для пользователя {user_id}")
        await update.message.reply_text(
            "✅ *Анкета завершена!*\n\n"
            "Сейчас проанализирую ваши ответы и подготовлю бизнес-идеи...",
            parse_mode='Markdown'
        )
        return await generate_business_ideas(update, context)
    else:
        await update.message.reply_text(
            f"✅ *Ответ принят!*\n\n"
            f"*Вопрос {profile.current_question + 1} из {len(QUESTIONS)}:*\n"
            f"{QUESTIONS[profile.current_question]}\n\n"
            f"✏️ *Пожалуйста, ответьте текстом:*",
            parse_mode='Markdown'
        )
        return QUESTIONNAIRE_STATE

async def generate_business_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация бизнес-идей"""
    user_id = update.effective_user.id
    logger.info(f"GENERATE_IDEAS: Начало генерации для пользователя {user_id}")
    
    profile = user_sessions[user_id]
    
    # Тестовые идеи (для отладки без OpenAI)
    test_ideas = [
        "1. Онлайн-консультации по вашей экспертизе - Помощь начинающим специалистам через Zoom/Skype",
        "2. Местный сервис доставки - Организация доставки товаров в вашем городе",
        "3. Образовательный канал на YouTube - Создание контента по вашей специализации",
        "4. Ремонтная мастерская - Услуги по ремонту техники или оборудования",
        "5. Организация мероприятий - Проведение локальных событий и встреч"
    ]
    
    profile.business_ideas = test_ideas
    
    keyboard = [
        [InlineKeyboardButton("🎯 Идея 1", callback_data='select_idea_0')],
        [InlineKeyboardButton("🎯 Идея 2", callback_data='select_idea_1')],
        [InlineKeyboardButton("🎯 Идея 3", callback_data='select_idea_2')],
        [InlineKeyboardButton("🎯 Идея 4", callback_data='select_idea_3')],
        [InlineKeyboardButton("🎯 Идея 5", callback_data='select_idea_4')],
        [InlineKeyboardButton("🔄 Сгенерировать заново", callback_data='regenerate_ideas')],
        [InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    ideas_text = "\n\n".join(test_ideas)
    
    await update.message.reply_text(
        f"🎉 *Вот 5 бизнес-идей специально для вас:*\n\n{ideas_text}\n\n"
        f"*Выберите идею для детального плана:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return BUSINESS_IDEAS_STATE

async def select_business_idea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор бизнес-идеи"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    logger.info(f"SELECT_IDEA: Пользователь {user_id} выбрал {data}")
    
    if data.startswith('select_idea_'):
        idea_index = int(data.split('_')[-1])
        profile = user_sessions[user_id]
        
        if 0 <= idea_index < len(profile.business_ideas):
            profile.selected_business_idea = profile.business_ideas[idea_index]
            
            # Тестовый бизнес-план
            business_plan = f"""
📈 **БИЗНЕС-ПЛАН: Идея {idea_index + 1}**

🎯 *Выбранная идея:*
{profile.business_ideas[idea_index]}

📋 *Краткое описание:*
Это реалистичная бизнес-идея, основанная на ваших ответах в анкете.

💰 *Финансовый план:*
• Стартовые инвестиции: 50,000 - 150,000 руб
• Ежемесячные расходы: 20,000 - 40,000 руб
• Окупаемость: 4-8 месяцев
• Потенциальная прибыль: от 30,000 руб/мес

🚀 *Этапы запуска:*
1. Подготовка (1-2 недели)
2. Тестирование (2-4 недели)
3. Запуск (1 неделя)
4. Масштабирование (3-6 месяцев)

📊 *Маркетинг:*
• Социальные сети
• Локальная реклама
• Партнерские программы
• Сарафанное радио

⚠️ *Риски:*
• Конкуренция
• Сезонность
• Изменения на рынке

💡 *Рекомендации:*
Начните с малого, тестируйте спрос, собирайте обратную связь.
"""
            
            profile.business_plan = business_plan
            
            keyboard = [
                [InlineKeyboardButton("💾 Сохранить план", callback_data='save_plan')],
                [InlineKeyboardButton("🔄 Другие идеи", callback_data='back_to_ideas')],
                [InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                business_plan,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            return BUSINESS_PLAN_STATE
    
    return BUSINESS_IDEAS_STATE

async def save_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение плана"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    logger.info(f"SAVE_PLAN: Пользователь {user_id} сохранил план")
    
    await query.edit_message_text(
        "✅ *Бизнес-план сохранен!*\n\n"
        "💡 *Дальнейшие шаги:*\n"
        "1. Детально проработайте план\n"
        "2. Начните с минимального продукта\n"
        "3. Собирайте обратную связь\n"
        "4. Корректируйте стратегию\n\n"
        "🚀 *Удачи в реализации!*\n\n"
        "Для нового поиска нажмите /start",
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

async def back_to_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться к идеям"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    logger.info(f"BACK_TO_IDEAS: Пользователь {user_id} вернулся к идеям")
    
    profile = user_sessions.get(user_id)
    if not profile:
        await query.edit_message_text("❌ Данные не найдены. Начните заново с /start")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("🎯 Идея 1", callback_data='select_idea_0')],
        [InlineKeyboardButton("🎯 Идея 2", callback_data='select_idea_1')],
        [InlineKeyboardButton("🎯 Идея 3", callback_data='select_idea_2')],
        [InlineKeyboardButton("🎯 Идея 4", callback_data='select_idea_3')],
        [InlineKeyboardButton("🎯 Идея 5", callback_data='select_idea_4')],
        [InlineKeyboardButton("🔄 Сгенерировать заново", callback_data='regenerate_ideas')],
        [InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    ideas_text = "\n\n".join(profile.business_ideas[:5])
    
    await query.edit_message_text(
        f"🔄 *Выберите бизнес-идею:*\n\n{ideas_text}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return BUSINESS_IDEAS_STATE

async def regenerate_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Регенерация идей"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    logger.info(f"REGENERATE_IDEAS: Пользователь {user_id} запросил новые идеи")
    
    # Просто возвращаем тот же список (для отладки)
    profile = user_sessions[user_id]
    
    keyboard = [
        [InlineKeyboardButton("🎯 Идея 1", callback_data='select_idea_0')],
        [InlineKeyboardButton("🎯 Идея 2", callback_data='select_idea_1')],
        [InlineKeyboardButton("🎯 Идея 3", callback_data='select_idea_2')],
        [InlineKeyboardButton("🎯 Идея 4", callback_data='select_idea_3')],
        [InlineKeyboardButton("🎯 Идея 5", callback_data='select_idea_4')],
        [InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🔄 *Новые идеи сгенерированы!*\n\n"
        "В тестовом режиме идеи остаются теми же.\n"
        "В рабочем режиме будут генерироваться новые.\n\n"
        "*Выберите идею:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return BUSINESS_IDEAS_STATE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена"""
    user_id = update.effective_user.id
    logger.info(f"CANCEL: Пользователь {user_id} отменил диалог")
    
    if user_id in user_sessions:
        del user_sessions[user_id]
    
    if update.message:
        await update.message.reply_text("❌ Диалог отменен. Начните заново с /start")
    elif update.callback_query:
        await update.callback_query.message.reply_text("❌ Диалог отменен. Начните заново с /start")
    
    return ConversationHandler.END

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовая команда"""
    logger.info(f"TEST вызван пользователем {update.effective_user.id}")
    
    status = f"""
✅ *ТЕСТ ПРОЙДЕН УСПЕШНО!*

📊 *Статус системы:*
• Бот активен: ДА
• Команды работают: ДА
• Кнопки работают: ПРОВЕРЬТЕ
• OpenAI: {'ДОСТУПЕН' if openai_client else 'ТЕСТОВЫЙ РЕЖИМ'}
• Сессии: {len(user_sessions)} активных

🛠 *Тестовые действия:*
1. Нажмите /debug для диагностики
2. Напишите /echo привет для проверки связи
3. Нажмите /start для начала работы

🔧 *Версия бота:* 2.0 (с отладкой)
🕒 *Время сервера:* {datetime.now()}
"""
    
    await update.message.reply_text(status, parse_mode='Markdown')

# ==================== HEALTH CHECK ====================
async def health_check(request):
    return web.Response(text="OK - Business Bot is running\nDebug mode active")

async def run_health_server():
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", "10000"))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"✅ Health check сервер запущен на порту {port}")
    return runner

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
async def main():
    """Основная функция с расширенной отладкой"""
    
    # Проверяем переменные окружения
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    
    if not token:
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: TELEGRAM_TOKEN не найден!")
        logger.error("Проверьте настройки Render:")
        logger.error("1. TELEGRAM_BOT_TOKEN или TELEGRAM_TOKEN должен быть установлен")
        logger.error("2. Ключ должен быть действительным")
        return
    
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК БОТА С ОТЛАДКОЙ")
    logger.info(f"✅ Токен найден: {'ДА' if token else 'НЕТ'}")
    logger.info(f"✅ Длина токена: {len(token) if token else 0}")
    logger.info(f"✅ PORT: {os.getenv('PORT', '10000')}")
    logger.info("=" * 50)
    
    # Создаем приложение
    try:
        application = Application.builder().token(token).build()
        logger.info("✅ Приложение создано успешно")
    except Exception as e:
        logger.error(f"❌ Ошибка создания приложения: {e}")
        return
    
    # Регистрируем команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("debug", debug_command))
    application.add_handler(CommandHandler("echo", echo_command))
    application.add_handler(CommandHandler("test", test_command))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # Создаем ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_questionnaire, pattern='^start_questionnaire$')
        ],
        states={
            QUESTIONNAIRE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_questionnaire_answer)
            ],
            BUSINESS_IDEAS_STATE: [
                CallbackQueryHandler(select_business_idea, pattern='^select_idea_'),
                CallbackQueryHandler(regenerate_ideas, pattern='^regenerate_ideas$'),
                CallbackQueryHandler(back_to_start, pattern='^back_to_start$')
            ],
            BUSINESS_PLAN_STATE: [
                CallbackQueryHandler(save_plan, pattern='^save_plan$'),
                CallbackQueryHandler(back_to_ideas, pattern='^back_to_ideas$'),
                CallbackQueryHandler(back_to_start, pattern='^back_to_start$')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(back_to_start, pattern='^back_to_start$')
        ],
        per_message=False
    )
    
    application.add_handler(conv_handler)
    
    # Другие callback-обработчики
    application.add_handler(CallbackQueryHandler(debug_info, pattern='^debug_info$'))
    application.add_handler(CallbackQueryHandler(help_info, pattern='^help_info$'))
    application.add_handler(CallbackQueryHandler(back_to_start, pattern='^back_to_start$'))
    
    # Запускаем health сервер
    health_server = await run_health_server()
    
    # Запускаем бота
    try:
        await application.initialize()
        await application.start()
        
        # Проверяем токен
        bot_info = await application.bot.get_me()
        logger.info(f"✅ Бот запущен: @{bot_info.username} ({bot_info.first_name})")
        
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            timeout=30,
            pool_timeout=30
        )
        
        logger.info("✅ Бот успешно запущен и слушает команды!")
        logger.info("✅ Отправьте /start в Telegram для проверки")
        
        # Бесконечный цикл
        while True:
            await asyncio.sleep(3600)
            
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА при запуске бота: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # Очистка
        try:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
            await health_server.cleanup()
        except:
            pass

if __name__ == '__main__':
    # Добавляем максимальную отладку
    logger.info("=" * 50)
    logger.info("НАЧАЛО ЗАПУСКА БОТА")
    logger.info("=" * 50)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ ФАТАЛЬНАЯ ОШИБКА: {e}")
        import traceback
        logger.error(traceback.format_exc())