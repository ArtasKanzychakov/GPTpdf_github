#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Бизнес-навигатор: Telegram бот для подбора бизнес-идей
Разработан на базе GPTpdf_github, адаптирован под бизнес-задачу
"""

import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
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

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы состояний
QUESTIONNAIRE_STATE = 1
BUSINESS_IDEAS_STATE = 2
BUSINESS_PLAN_STATE = 3

# ==================== МОДЕЛИ ДАННЫХ ====================

@dataclass
class UserProfile:
    """Профиль пользователя с ответами на вопросы анкеты"""
    user_id: int
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Основная информация
    city: str = ""
    education: List[str] = field(default_factory=list)
    certificates: List[str] = field(default_factory=list)
    
    # Навыки
    tech_skills: List[str] = field(default_factory=list)
    professional_skills: List[str] = field(default_factory=list)
    personal_qualities: List[str] = field(default_factory=list)
    
    # Интересы и предпочтения
    interests: List[str] = field(default_factory=list)
    work_preference: str = ""
    stress_tolerance: str = ""
    
    # Ресурсы
    budget: str = ""
    time_availability: str = ""
    has_team: bool = False
    
    # Бизнес предпочтения
    business_scale: str = ""
    innovation_level: str = ""
    
    # Ответы на вопросы
    answers: Dict[int, str] = field(default_factory=dict)
    current_question: int = 0
    business_ideas: List[str] = field(default_factory=list)
    selected_business_idea: str = ""
    business_plan: str = ""

# Временное хранилище данных
user_sessions: Dict[int, UserProfile] = {}

# ==================== ВОПРОСЫ АНКЕТЫ ====================

QUESTIONS = [
    "1. В каком городе/регионе вы проживаете? (Это поможет учесть местный рынок)",
    "2. Какое у вас образование и профессиональные сертификаты? (Перечислите через запятую)",
    "3. Какие технические навыки у вас есть? (Программирование, дизайн, работа с оборудованием и т.д.)",
    "4. Какие профессиональные навыки? (Менеджмент, маркетинг, продажи, финансы и т.д.)",
    "5. Какие у вас личные качества? (Коммуникабельность, ответственность, креативность и т.д.)",
    "6. Какие сферы вам интересны? (Технологии, спорт, здоровье, образование, развлечения и т.д.)",
    "7. Какой у вас опыт работы? (Опишите кратко)",
    "8. Какой стартовый бюджет? (до 100к руб, 100-500к, 500к-1 млн, 1 млн+)",
    "9. Сколько времени готовы уделять? (частичная занятость, полная, только выходные)",
    "10. Есть ли команда или партнеры? (Да/Нет, если да - опишите)",
    "11. Каков ваш риск-профиль? (Консервативный, умеренный, агрессивный)",
    "12. Какой тип бизнеса предпочитаете? (Онлайн, офлайн, смешанный)",
    "13. Есть ли у вас доступ к специальным ресурсам? (Помещение, оборудование, связи)",
    "14. На какой срок планируете бизнес? (Краткосрочный, долгосрочный, проект)",
    "15. Какие цели кроме прибыли? (Социальное влияние, самореализация, наследие)",
    "16. Есть ли у вас хобби, которые можно монетизировать?"
]

# ==================== OPENAI КЛИЕНТ ====================

def init_openai_client():
    """Инициализация OpenAI клиента"""
    api_key = os.getenv("OPENAI_API_KEY", "test-key-123")
    
    if not api_key or api_key == "test-key-123":
        logger.warning("⚠️ OPENAI_API_KEY не задан, используем тестовый ключ")
        return OpenAI(api_key="test-key-123")
    
    logger.info("✅ OPENAI_API_KEY задан")
    return OpenAI(api_key=api_key)

openai_client = init_openai_client()

# ==================== ТЕЛЕГРАМ ОБРАБОТЧИКИ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    
    # Создаем или сбрасываем профиль
    user_sessions[user_id] = UserProfile(user_id=user_id)
    
    welcome_text = (
        "👋 Привет! Я *Бизнес-Навигатор* — бот для подбора персонализированных бизнес-идей.\n\n"
        "🎯 *Как это работает:*\n"
        "1. Вы заполняете анкету из 16 вопросов\n"
        "2. Я анализирую ваши навыки, интересы и возможности\n"
        "3. Генерирую 5 уникальных бизнес-идей специально для вас\n"
        "4. Подробно расписываю план для выбранной идеи\n\n"
        "📋 *Что учитывается:*\n"
        "• Ваше образование и сертификаты\n"
        "• Технические и профессиональные навыки\n"
        "• Личные качества и интересы\n"
        "• Бюджет и временные возможности\n"
        "• Региональные особенности вашего города\n\n"
        "🚀 *Начнем?*"
    )
    
    keyboard = [
        [InlineKeyboardButton("📋 Начать анкету", callback_data='start_questionnaire')],
        [InlineKeyboardButton("❓ О проекте", callback_data='about')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о проекте"""
    query = update.callback_query
    await query.answer()
    
    about_text = (
        "🤖 *Бизнес-Навигатор*\n\n"
        "Проект для предпринимателей, которые ищут свою нишу.\n\n"
        "📊 *Возможности:*\n"
        "• Анализ вашего профиля\n"
        "• Подбор бизнеса по региону\n"
        "• Учет бюджета и навыков\n"
        "• Детальные бизнес-планы\n\n"
        "🛠 *Технологии:*\n"
        "• Python 3.9\n"
        "• OpenAI GPT-3.5\n"
        "• Telegram Bot API\n"
        "• Render.com для хостинга\n\n"
        "👨‍💻 *Разработчик:* Artas Kanzychakov\n"
        "🔗 *GitHub:* https://github.com/ArtasKanzychakov"
    )
    
    keyboard = [[InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        about_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в начало"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # Сбрасываем сессию
    user_sessions[user_id] = UserProfile(user_id=user_id)
    
    welcome_text = (
        "👋 Снова привет! Я *Бизнес-Навигатор* — бот для подбора персонализированных бизнес-идей.\n\n"
        "🎯 *Как это работает:*\n"
        "1. Вы заполняете анкету из 16 вопросов\n"
        "2. Я анализирую ваши навыки, интересы и возможности\n"
        "3. Генерирую 5 уникальных бизнес-идей специально для вас\n"
        "4. Подробно расписываю план для выбранной идеи\n\n"
        "📋 *Что учитывается:*\n"
        "• Ваше образование и сертификаты\n"
        "• Технические и профессиональные навыки\n"
        "• Личные качества и интересы\n"
        "• Бюджет и временные возможности\n"
        "• Региональные особенности вашего города\n\n"
        "🚀 *Начнем?*"
    )
    
    keyboard = [
        [InlineKeyboardButton("📋 Начать анкету", callback_data='start_questionnaire')],
        [InlineKeyboardButton("❓ О проекте", callback_data='about')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def start_questionnaire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать анкету"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Создаем профиль если его нет
    if user_id not in user_sessions:
        user_sessions[user_id] = UserProfile(user_id=user_id)
    
    profile = user_sessions[user_id]
    profile.current_question = 0
    
    # Отправляем первый вопрос
    await query.edit_message_text(
        f"📝 *Вопрос 1 из {len(QUESTIONS)}*\n\n{QUESTIONS[0]}\n\n"
        f"✏️ *Введите ваш ответ текстом:*",
        parse_mode='Markdown'
    )
    
    return QUESTIONNAIRE_STATE

async def handle_questionnaire_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых ответов в анкете"""
    user_id = update.effective_user.id
    
    if user_id not in user_sessions:
        await update.message.reply_text("❌ Сессия истекла. Начните заново с /start")
        return ConversationHandler.END
    
    profile = user_sessions[user_id]
    answer = update.message.text
    
    # Сохраняем ответ
    profile.answers[profile.current_question] = answer
    
    # Переходим к следующему вопросу
    profile.current_question += 1
    
    # Проверяем, закончилась ли анкета
    if profile.current_question >= len(QUESTIONS):
        # Все вопросы отвечены, генерируем бизнес-идеи
        await update.message.reply_text("✅ *Анкета завершена!*\n\nАнализирую ваши ответы...", parse_mode='Markdown')
        return await generate_business_ideas(update, context)
    else:
        # Показываем следующий вопрос
        question_num = profile.current_question + 1
        await update.message.reply_text(
            f"✅ Ответ сохранен!\n\n"
            f"📝 *Вопрос {question_num} из {len(QUESTIONS)}*\n\n"
            f"{QUESTIONS[profile.current_question]}\n\n"
            f"✏️ *Введите ваш ответ текстом:*",
            parse_mode='Markdown'
        )
        return QUESTIONNAIRE_STATE

async def generate_business_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация бизнес-идей на основе анкеты"""
    user_id = update.effective_user.id
    profile = user_sessions[user_id]
    
    # Формируем промпт для GPT
    answers_text = "\n".join([f"{i+1}. {QUESTIONS[i]}\n   Ответ: {profile.answers.get(i, 'Нет ответа')}" 
                              for i in range(len(QUESTIONS))])
    
    prompt = f"""
    Задание: Сгенерируй 5 персонализированных бизнес-идей для пользователя на основе его анкеты.
    
    Контекст анкеты:
    {answers_text}
    
    Требования к бизнес-идеям:
    1. Учитывать город/регион проживания
    2. Учитывать образование и навыки
    3. Учитывать бюджетные возможности
    4. Быть реалистичными для реализации
    5. Иметь потенциал для роста
    
    Формат вывода:
    1. [Название идеи] - Краткое описание (1-2 предложения)
    2. ...
    3. ...
    4. ...
    5. ...
    
    Каждая идея должна быть пронумерована и содержать четкое название.
    """
    
    loading_message = await update.message.reply_text(
        "🤔 *Анализирую ваши ответы...*\n"
        "Генерирую персонализированные бизнес-идеи...",
        parse_mode='Markdown'
    )
    
    try:
        api_key = os.getenv("OPENAI_API_KEY", "test-key-123")
        
        if not api_key or api_key == "test-key-123":
            # Тестовый режим
            await asyncio.sleep(2)
            test_ideas = [
                "1. Онлайн-школа по вашей специализации - Обучение через платформу с видеоуроками и вебинарами для специалистов вашего региона",
                "2. Консалтинг для местного бизнеса - Помощь малым предприятиям в digital-трансформации и автоматизации процессов",
                "3. Эко-продукты с доставкой - Продажа экологичных товаров для дома и здоровья с доставкой по вашему городу",
                "4. Ремонт и настройка гаджетов - Сервисный центр с выездом к клиенту для ремонта техники",
                "5. Организация локальных событий - Проведение корпоративов, частных праздников и тематических мероприятий"
            ]
            ideas_text = "\n\n".join(test_ideas)
            profile.business_ideas = test_ideas
        else:
            # Реальный вызов OpenAI
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты бизнес-консультант с опытом запуска стартапов. Генерируй реалистичные бизнес-идеи."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )
            
            ideas_text = response.choices[0].message.content
            profile.business_ideas = [idea.strip() for idea in ideas_text.split("\n") if idea.strip()]
        
        # Создаем клавиатуру для выбора идеи
        keyboard = []
        for i in range(min(5, len(profile.business_ideas))):
            keyboard.append([InlineKeyboardButton(
                f"🎯 Идея {i+1}", 
                callback_data=f'select_idea_{i}'
            )])
        
        keyboard.append([InlineKeyboardButton("🔄 Сгенерировать заново", callback_data='regenerate_ideas')])
        keyboard.append([InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await loading_message.edit_text(
            f"🎉 *Вот 5 бизнес-идей специально для вас:*\n\n"
            f"{ideas_text}\n\n"
            f"*Выберите идею для детального разбора:*",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        return BUSINESS_IDEAS_STATE
        
    except Exception as e:
        logger.error(f"Ошибка генерации идей: {e}")
        await loading_message.edit_text(
            f"❌ *Произошла ошибка при генерации идей*\n\n"
            f"Попробуйте снова позже или начните заново с /start",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

async def regenerate_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Регенерация бизнес-идей"""
    query = update.callback_query
    await query.answer()
    
    # Просто вызываем генерацию заново
    await query.edit_message_text(
        "🔄 *Генерирую новые идеи...*",
        parse_mode='Markdown'
    )
    
    # Создаем фейковое обновление для передачи в generate_business_ideas
    fake_update = Update(
        update_id=update.update_id,
        message=update.effective_message,
        callback_query=None
    )
    
    return await generate_business_ideas(fake_update, context)

async def select_business_idea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора бизнес-идеи"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    profile = user_sessions.get(user_id)
    
    if not profile or not profile.business_ideas:
        await query.edit_message_text("❌ Данные не найдены. Начните заново с /start")
        return ConversationHandler.END
    
    # Извлекаем номер идеи
    data = query.data
    if data.startswith('select_idea_'):
        idea_index = int(data.split('_')[-1])
        
        if 0 <= idea_index < len(profile.business_ideas):
            profile.selected_business_idea = profile.business_ideas[idea_index]
            
            # Генерируем бизнес-план
            await generate_business_plan(query, idea_index)
            return BUSINESS_PLAN_STATE
    
    return BUSINESS_IDEAS_STATE

async def generate_business_plan(query, idea_index: int):
    """Генерация детального бизнес-плана"""
    user_id = query.from_user.id
    profile = user_sessions[user_id]
    
    selected_idea = profile.business_ideas[idea_index]
    
    prompt = f"""
    Задание: Создай детальный бизнес-план для следующей идеи:
    
    Идея: {selected_idea}
    
    Контекст пользователя из анкеты:
    Город: {profile.answers.get(0, 'Не указан')}
    Бюджет: {profile.answers.get(7, 'Не указан')}
    Навыки: {profile.answers.get(2, 'Не указаны')} {profile.answers.get(3, '')}
    Время: {profile.answers.get(8, 'Не указано')}
    
    Структура бизнес-плана:
    1. Краткое резюме идеи
    2. Анализ рынка и конкурентов
    3. Целевая аудитория
    4. Монетизация и финансовый план
    5. Этапы запуска (пошагово на 3-6 месяцев)
    6. Маркетинговая стратегия
    7. Риски и их минимизация
    8. Дальнейшее развитие
    
    Будь конкретным, предлагай цифры и сроки. Форматируй ответ с использованием Markdown.
    """
    
    await query.edit_message_text(
        "📊 *Разрабатываю детальный бизнес-план...*\nЭто займет около 30 секунд.",
        parse_mode='Markdown'
    )
    
    try:
        api_key = os.getenv("OPENAI_API_KEY", "test-key-123")
        
        if not api_key or api_key == "test-key-123":
            # Тестовый режим
            await asyncio.sleep(3)
            business_plan = """📈 **БИЗНЕС-ПЛАН: Онлайн-школа по вашей специализации**

1. **Краткое резюме:**
   - Онлайн-платформа с курсами по вашей экспертизе
   - Старт с 3 базовых курсов
   - Планируемая аудитория: 100+ студентов в первый год

2. **Анализ рынка:**
   - Рынок онлайн-образования растет на 15% ежегодно
   - В вашем регионе мало нишевых предложений
   - Ценовой сегмент: 5,000-25,000 руб за курс

3. **Целевая аудитория:**
   - Специалисты, желающие повысить квалификацию
   - Студенты последних курсов
   - Предприниматели смежных областей

4. **Монетизация:**
   - Продажа курсов: 3 курса × 10,000 руб = 30,000 руб/мес
   - Индивидуальные консультации: 5,000 руб/час
   - Корпоративное обучение: от 50,000 руб/мес

5. **Этапы запуска (3 месяца):**
   - Месяц 1: Разработка программы и материалов
   - Месяц 2: Создание платформы (можно на Tilda/GetCourse)
   - Месяц 3: Привлечение первых 20 студентов

6. **Маркетинг:**
   - Контент-маркетинг в Telegram и YouTube
   - Партнерства с локальными бизнес-сообществами
   - Бесплатные вебинары для привлечения аудитории

7. **Риски:**
   - Конкуренция: дифференцироваться через персонализацию
   - Нехватка студентов: начинать с небольшой ниши
   - Технические проблемы: использовать проверенные платформы

8. **Развитие:**
   - Расширение тематик курсов
   - Добавление менторской программы
   - Выход на смежные рынки через 1-2 года

**Стартовые инвестиции:** ~150,000 руб  
**Окупаемость:** 6-8 месяцев  
**Планируемая прибыль:** от 50,000 руб/мес на второй год"""
        else:
            # Реальный вызов OpenAI
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты опытный бизнес-консультант, составляющий подробные планы. Форматируй ответ с заголовками и списками."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            
            business_plan = response.choices[0].message.content
        
        profile.business_plan = business_plan
        
        keyboard = [
            [InlineKeyboardButton("📥 Сохранить результаты", callback_data='save_results')],
            [InlineKeyboardButton("🔄 Другие идеи", callback_data='back_to_ideas')],
            [InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🎯 *Ваш бизнес-план*\n\n"
            f"*Выбранная идея:* {selected_idea}\n\n"
            f"{business_plan}\n\n"
            f"---\n"
            f"💡 *Что дальше?*\n"
            f"1. Сохраните этот план\n"
            f"2. Проработайте детали с экспертами\n"
            f"3. Начните с минимального рабочего продукта",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Ошибка генерации плана: {e}")
        await query.edit_message_text(
            f"❌ *Ошибка при генерации бизнес-плана*\n\nПопробуйте выбрать другую идею.",
            parse_mode='Markdown'
        )

async def save_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение результатов"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    profile = user_sessions.get(user_id)
    
    if profile and profile.business_plan:
        await query.edit_message_text(
            "✅ *Результаты сохранены!*\n\n"
            "💡 *Рекомендации на старте:*\n"
            "1. Начните с прототипа или MVP\n"
            "2. Соберите обратную связь от первых клиентов\n"
            "3. Адаптируйте план по результатам\n"
            "4. Не бойтесь корректировать стратегию\n\n"
            "🚀 *Удачи в реализации вашей бизнес-идеи!*\n\n"
            "Чтобы начать заново, нажмите /start",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text(
            "❌ Не удалось сохранить результаты. Начните заново с /start",
            parse_mode='Markdown'
        )
    
    return ConversationHandler.END

async def back_to_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться к списку идей"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    profile = user_sessions.get(user_id)
    
    if not profile or not profile.business_ideas:
        await query.edit_message_text("❌ Данные не найдены. Начните заново с /start")
        return ConversationHandler.END
    
    # Создаем клавиатуру для выбора идеи
    keyboard = []
    for i in range(min(5, len(profile.business_ideas))):
        keyboard.append([InlineKeyboardButton(
            f"🎯 Идея {i+1}", 
            callback_data=f'select_idea_{i}'
        )])
    
    keyboard.append([InlineKeyboardButton("🔄 Сгенерировать заново", callback_data='regenerate_ideas')])
    keyboard.append([InlineKeyboardButton("🏠 В начало", callback_data='back_to_start')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    ideas_text = "\n\n".join(profile.business_ideas[:5])
    
    await query.edit_message_text(
        f"🔄 *Список ваших бизнес-идей:*\n\n{ideas_text}\n\n*Выберите идею для детального плана:*",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    return BUSINESS_IDEAS_STATE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена диалога"""
    user_id = update.effective_user.id
    
    # Удаляем сессию пользователя
    if user_id in user_sessions:
        del user_sessions[user_id]
    
    if update.message:
        await update.message.reply_text(
            "❌ Диалог отменен. Начните заново с /start",
            parse_mode='Markdown'
        )
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            "❌ Диалог отменен. Начните заново с /start",
            parse_mode='Markdown'
        )
    
    return ConversationHandler.END

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовая команда для проверки работы бота"""
    await update.message.reply_text(
        "✅ *Бот работает!*\n\n"
        f"📊 Активных сессий: {len(user_sessions)}\n"
        f"🤖 Режим OpenAI: {'Тестовый' if not os.getenv('OPENAI_API_KEY') or os.getenv('OPENAI_API_KEY') == 'test-key-123' else 'Реальный'}\n"
        f"🕒 Время сервера: {datetime.now()}\n"
        f"🔗 Health check: https://gptpdf-github2.onrender.com/health",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда помощи"""
    help_text = (
        "🆘 *Помощь по командам:*\n\n"
        "• /start - Начать работу с ботом\n"
        "• /test - Проверить работоспособность бота\n"
        "• /cancel - Отменить текущий диалог\n"
        "• /help - Показать это сообщение\n\n"
        "📞 *Поддержка:*\n"
        "По вопросам работы бота обращайтесь к разработчику."
    )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ==================== HEALTH CHECK SERVER ====================

async def health_check(request):
    """Эндпоинт для health check"""
    return web.Response(text="OK - Business Navigator Bot is running")

async def run_health_server():
    """Запуск сервера для health check"""
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
    """Основная асинхронная функция запуска бота"""
    
    # Получаем токен из переменных окружения
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        token = os.getenv("TELEGRAM_TOKEN")  # Пробуем альтернативное имя
    
    if not token:
        logger.error("❌ TELEGRAM_TOKEN не задан в переменных окружения")
        logger.error("Добавьте TELEGRAM_BOT_TOKEN или TELEGRAM_TOKEN в настройки Render")
        return
    
    logger.info(f"✅ PORT: {os.getenv('PORT', '10000')}")
    logger.info(f"✅ TELEGRAM_TOKEN задан: {'Да' if token else 'Нет'}")
    logger.info(f"✅ OPENAI_API_KEY задан: {'Нет (тестовый)' if not os.getenv('OPENAI_API_KEY') or os.getenv('OPENAI_API_KEY') == 'test-key-123' else 'Да'}")
    logger.info("✅ OpenAI клиент инициализирован")
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("test", test))
    application.add_handler(CommandHandler("help", help_command))
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
                CallbackQueryHandler(save_results, pattern='^save_results$'),
                CallbackQueryHandler(back_to_ideas, pattern='^back_to_ideas$'),
                CallbackQueryHandler(back_to_start, pattern='^back_to_start$')
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(back_to_start, pattern='^back_to_start$')
        ],
        per_message=False  # Важно: False для работы с MessageHandler
    )
    
    # Добавляем ConversationHandler
    application.add_handler(conv_handler)
    
    # Обработчики callback'ов вне ConversationHandler
    application.add_handler(CallbackQueryHandler(about, pattern='^about$'))
    application.add_handler(CallbackQueryHandler(back_to_start, pattern='^back_to_start$'))
    
    # Запускаем health check сервер в фоне
    health_server = await run_health_server()
    
    logger.info("🚀 Запуск бизнес-бота на Render...")
    logger.info("✅ Бот запускается...")
    
    # Запускаем polling
    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )
    
    logger.info("✅ Бот успешно запущен и слушает команды!")
    
    # Бесконечный цикл
    try:
        while True:
            await asyncio.sleep(3600)  # Спим по часу
    except asyncio.CancelledError:
        pass
    finally:
        # Очистка при завершении
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        await health_server.cleanup()

if __name__ == '__main__':
    # Запускаем основную функцию
    asyncio.run(main())