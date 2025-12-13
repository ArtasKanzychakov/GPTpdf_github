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
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация (оставляем всё как было)
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = "gpt-3.5-turbo"

# Проверка переменных окружения
if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    logger.critical("Не заданы TELEGRAM_BOT_TOKEN или OPENAI_API_KEY!")
    raise ValueError("TELEGRAM_BOT_TOKEN и OPENAI_API_KEY должны быть установлены")

# Инициализация OpenAI клиента
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Определяем состояния для ConversationHandler (теперь 10 вопросов)
NUM_QUESTIONS = 10
START, *QUESTIONS_STATES, GENERATE_NICHES = range(NUM_QUESTIONS + 1)

# Обновленные вопросы - конкретнее и практичнее
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
        "options": None  # Открытый вопрос
    },
    {
        "text": "🔥 **Страсть**: О чём вы можете говорить часами? Что вас зажигает?",
        "options": None  # Открытый вопрос
    }
]

# Глобальное хранилище для идей пользователя
user_niches = {}

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
    
    # Запускаем первый вопрос
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
    2. Каждая идея должна быть ОЧЕНЬ конкретной (не "онлайн-бизнес", а "онлайн-школа по обучению Photoshop для дизайнеров-фрилансеров")
    3. Учитывай бюджет, время и опыт из ответов
    4. Формат: "1. [Название идеи] - [Краткое описание 10-15 слов]"
    5. Без лишнего текста, только список
    """
    
    try:
        await update.message.reply_chat_action("typing")
        
        completion = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Ты - практикующий бизнес-консультант с 10-летним опытом. Предлагаешь только реалистичные и выполнимые бизнес-идеи."},
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
        
        # Создаем инлайн-клавиатуру с 5 идеями
        keyboard = []
        for i, niche in enumerate(niches[:5], 1):
            # Обрезаем длинное название для кнопки
            button_text = niche[:3] + "..." if len(niche) > 30 else niche
            keyboard.append([InlineKeyboardButton(f"{i}. {button_text}", callback_data=f"niche_{i}")])
        
        # Добавляем кнопки управления
        keyboard.append([
            InlineKeyboardButton("🔄 Новые идеи", callback_data="regenerate"),
            InlineKeyboardButton("📋 Все идеи", callback_data="show_all")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🎯 **Вот 5 бизнес-идей специально для вас:**\n\n"
            "Нажмите на любую идею, чтобы получить подробный план.\n"
            "Вы можете вернуться и посмотреть другие идеи в любой момент!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return GENERATE_NICHES

    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        await update.message.reply_text(
            "Произошла ошибка при генерации идей. Пожалуйста, попробуйте позже.",
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
                f"⏳ **Готовлю подробный план для:**\n\n"
                f"**{selected_niche}**\n\n"
                f"Это займет 20-30 секунд...",
                parse_mode='Markdown'
            )
            
            # Генерируем бизнес-план
            plan_prompt = f"""
            Создай ПОДРОБНЫЙ бизнес-план для идеи: "{selected_niche}"
            
            Структура плана:
            1. **🎯 Суть проекта** (1-2 предложения)
            2. **💰 Стартовые инвестиции** (разбивка по статьям)
            3. **📅 План запуска на 30 дней** (конкретные шаги по дням)
            4. **🎯 Целевая аудитория** (где искать клиентов)
            5. **📈 Монетизация** (ценовая политика, каналы продаж)
            6. **⚠️ Риски и решения** (что может пойти не так и как избежать)
            7. **🚀 Первые 3 шага** (что сделать прямо сейчас)
            
            Будь максимально конкретным и практичным!
            """
            
            try:
                completion = openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "Ты - практикующий бизнес-аналитик. Даешь конкретные, выполнимые рекомендации с цифрами и сроками."},
                        {"role": "user", "content": plan_prompt}
                    ]
                )
                business_plan = completion.choices[0].message.content
                context.user_data['business_plan'] = business_plan
                
                # Создаем клавиатуру с кнопкой PDF и возвратом к идеям
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
                    "Ошибка при создании плана. Попробуйте выбрать другую идею.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="back_to_niches")]])
                )
    
    elif query.data == "show_all":
        # Показываем все идеи списком
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
        # Генерируем новые идеи
        await query.edit_message_text("🔄 Генерирую новые идеи...")
        
        # Используем сохраненные ответы для генерации новых идей
        if 'answers' in context.user_data:
            # Немного изменяем промпт для разнообразия
            new_prompt = f"""
            На основе этих же ответов предложи 5 ДРУГИХ, новых бизнес-идей:
            {json.dumps(context.user_data['answers'], indent=2, ensure_ascii=False)}
            
            Идеи должны быть СОВЕРШЕННО другими, не похожими на предыдущие.
            Формат: "1. [Название] - [Описание]"
            """
            
            try:
                completion = openai_client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "Ты креативный бизнес-консультант. Придумываешь неочевидные, но реалистичные бизнес-идеи."},
                        {"role": "user", "content": new_prompt}
                    ]
                )
                new_niches = []
                for line in completion.choices[0].message.content.split('\n'):
                    if line.strip() and line[0].isdigit():
                        new_niches.append(line.strip())
                
                user_niches[user_id] = new_niches
                
                # Показываем новые идеи
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
                    "Ошибка генерации. Попробуйте начать заново /start",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("/start", callback_data="start")]])
                )
    
    elif query.data == "back_to_niches":
        # Возвращаемся к списку идей
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
        # Создаем и отправляем PDF
        await create_and_send_pdf_callback(query, context)
    
    elif query.data == "back_main":
        # Возврат к главному меню
        await query.edit_message_text(
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Мои идеи", callback_data="back_to_niches")],
                [InlineKeyboardButton("🔄 Новые идеи", callback_data="regenerate")],
                [InlineKeyboardButton("/start", callback_data="start")]
            ])
        )
    
    elif query.data == "start":
        # Перезапуск
        await query.edit_message_text(
            "Используйте команду /start чтобы начать новую анкету.",
            reply_markup=None
        )
    
    return GENERATE_NICHES

async def create_and_send_pdf_callback(query, context: ContextTypes.DEFAULT_TYPE):
    """Создает PDF и отправляет через callback."""
    try:
        await query.answer("Создаю PDF...")
        
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        
        # Используем стандартные шрифты
        c.setFont("Helvetica", 12)
        
        # Заголовок
        title = context.user_data.get('selected_niche', 'Бизнес-план')
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 800, "БИЗНЕС-ПЛАН")
        c.setFont("Helvetica", 14)
        c.drawString(50, 775, title[:80])  # Обрезаем слишком длинный заголовок
        
        # Линия-разделитель
        c.line(50, 765, 550, 765)
        
        # Контент
        business_plan = context.user_data.get('business_plan', 'Бизнес-план не сгенерирован')
        c.setFont("Helvetica", 12)
        
        # Упрощаем форматирование
        lines = []
        for line in business_plan.split('\n'):
            clean_line = line.replace('**', '').replace('__', '').replace('###', '').strip()
            if clean_line:
                lines.append(clean_line)
        
        y_position = 740
        line_height = 14
        
        for line in lines:
            if y_position < 50:
                c.showPage()
                c.setFont("Helvetica", 12)
                y_position = 800
            
            # Разбиваем длинные строки
            if len(line) > 80:
                words = line.split(' ')
                current_line = ""
                for word in words:
                    if len(current_line + word) < 80:
                        current_line += word + " "
                    else:
                        c.drawString(50, y_position, current_line)
                        y_position -= line_height
                        current_line = word + " "
                        if y_position < 50:
                            c.showPage()
                            c.setFont("Helvetica", 12)
                            y_position = 800
                if current_line:
                    c.drawString(50, y_position, current_line)
                    y_position -= line_height
            else:
                c.drawString(50, y_position, line)
                y_position -= line_height
            
            y_position -= 2
        
        # Футер
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(50, 30, "Сгенерировано Business Idea Bot")
        c.drawString(50, 15, datetime.now().strftime("%d.%m.%Y %H:%M"))
        
        c.save()
        buffer.seek(0)
        
        # Отправляем PDF
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=buffer,
            filename=f"business_plan_{query.from_user.id}.pdf",
            caption=f"📄 Ваш бизнес-план готов!\n\n{title[:50]}..."
        )
        
        buffer.close()
        
        # Оставляем сообщение с планом и кнопками
        keyboard = [
            [InlineKeyboardButton("← К идеям", callback_data="back_to_niches")],
            [InlineKeyboardButton("🔄 Новые идеи", callback_data="regenerate")]
        ]
        
        await query.edit_message_text(
            f"✅ **PDF отправлен!**\n\n"
            f"**{title}**\n\n"
            f"Проверьте документы в чате ↑\n\n"
            f"Что дальше?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error creating/sending PDF: {e}")
        # Отправляем как текстовый файл
        try:
            business_plan = context.user_data.get('business_plan', '')
            text_buffer = io.BytesIO(business_plan.encode('utf-8'))
            text_buffer.seek(0)
            
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=text_buffer,
                filename=f"business_plan_{query.from_user.id}.txt",
                caption=f"📄 Ваш бизнес-план в TXT формате\n\n{title[:50]}..."
            )
            text_buffer.close()
            
            await query.edit_message_text(
                f"✅ **Файл отправлен в формате TXT!**\n\n"
                f"Проверьте документы в чате ↑",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="back_to_niches")]])
            )
        except:
            await query.edit_message_text(
                "Ошибка при создании файла. Но вы можете скопировать текст плана выше.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="niche_1")]])
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
        "🔄 **Вы можете:**\n"
        "• Просматривать все идеи в любое время\n"
        "• Генерировать новые идеи\n"
        "• Скачивать PDF для любой идеи\n\n"
        "📝 **Команды:**\n"
        "/start - Начать анкету\n"
        "/help - Эта справка\n"
        "/cancel - Отменить текущий диалог"
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
        '✅ Данные сброшены. Используйте /start чтобы начать новую анкету.',
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Логирует ошибки."""
    logger.error(f'Update {update} caused error {context.error}')

async def keep_alive():
    """Фоновая задача чтобы бот не засыпал."""
    while True:
        try:
            # Просто логируем что бот жив
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"🤖 Бот активен - {current_time}")
            await asyncio.sleep(300)  # Каждые 5 минут
        except Exception as e:
            logger.error(f"Keep alive error: {e}")
            await asyncio.sleep(60)

def main() -> None:
    """Запускает бота с вебхуком для Production."""
    PORT = int(os.environ.get('PORT', 8443))
    
    # Создаем Application с job_queue
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Запускаем фоновую задачу для поддержания активности
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(keep_alive())
    
    # Определяем состояния для каждого вопроса (теперь 10)
    quiz_states_dict = {i: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quiz_answer)] for i in range(NUM_QUESTIONS)}
    
    # ConversationHandler для анкеты с per_message=True
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
            CallbackQueryHandler(cancel_command, pattern="^cancel$")
        ],
        per_message=True  # Это исправляет предупреждение
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('reset', reset_command))
    app.add_error_handler(error)
    
    # ВЕБХУКИ - оставляем как было
    logger.info("Starting bot with webhook...")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"https://gptpdf-github-vybor-nishy.onrender.com/{TELEGRAM_TOKEN}"
    )

if __name__ == '__main__':
    main()
