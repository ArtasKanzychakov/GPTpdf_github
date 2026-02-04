from __future__ import annotations

import logging
from typing import Any, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from models.session import (
    UserSession,
    SessionStatus,
)

# Conversation states
QUESTIONNAIRE = 1
ANALYSIS = 2
RESULT = 3

logger = logging.getLogger(__name__)


async def start_questionnaire(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Запуск анкеты (обработчик команды /questionnaire)
    """
    try:
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "Пользователь"

        logger.info(f"📝 Запуск анкеты: user_id={user_id}")

        # Получаем менеджер данных
        data_manager = context.bot_data.get('data_manager')
        if not data_manager:
            await update.message.reply_text("❌ Ошибка: менеджер данных не инициализирован")
            return ConversationHandler.END

        # Получаем или создаем сессию
        session = data_manager.get_session(user_id)
        if not session:
            session = UserSession(user_id=user_id)
            data_manager.save_session(session)
            logger.info(f"📝 Создана новая сессия для пользователя {user_id}")

        # Получаем движок вопросов
        question_engine = context.bot_data.get('question_engine')
        if not question_engine:
            await update.message.reply_text("❌ Ошибка: движок вопросов не инициализирован")
            return ConversationHandler.END

        # Начинаем анкету
        session.status = SessionStatus.IN_PROGRESS
        data_manager.save_session(session)

        # Получаем первый вопрос
        questions = context.bot_data.get('config', {}).get('questions', [])
        if not questions:
            await update.message.reply_text("❌ Ошибка: вопросы не загружены")
            return ConversationHandler.END

        # Находим первый вопрос (id=1)
        first_question = None
        for q in questions:
            if q.get('id') == 1:
                first_question = q
                break

        if not first_question:
            await update.message.reply_text("❌ Ошибка: первый вопрос не найден")
            return ConversationHandler.END

        # Форматируем вопрос
        from utils.formatters import format_question_text
        question_text = format_question_text(
            first_question.get('text', ''),
            user_name,
            1,
            len(questions)
        )

        # Создаем клавиатуру для вопроса
        keyboard = _create_keyboard_for_question(first_question)

        if keyboard:
            await update.message.reply_text(
                question_text,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
        else:
            await update.message.reply_text(
                question_text,
                parse_mode='Markdown'
            )

        # Сохраняем текущий вопрос в сессии
        session.current_question = 1
        data_manager.save_session(session)

        # Сохраняем session в context для следующего шага
        context.user_data['session'] = session
        context.user_data['question_id'] = 1

        return QUESTIONNAIRE

    except Exception as e:
        logger.error(f"❌ Ошибка при запуске анкеты: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при запуске анкеты. Попробуйте позже."
        )
        return ConversationHandler.END


async def handle_question_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Обработка ответа на вопрос
    """
    try:
        user_id = update.effective_user.id
        
        # Получаем данные из context
        data_manager = context.bot_data.get('data_manager')
        if not data_manager:
            await _send_error(update, "Менеджер данных не инициализирован")
            return ConversationHandler.END

        session = context.user_data.get('session')
        if not session:
            # Пытаемся восстановить сессию
            session = data_manager.get_session(user_id)
            if not session:
                await _send_error(update, "Сессия не найдена. Начните с /start")
                return ConversationHandler.END

        current_question_id = context.user_data.get('question_id', 1)
        
        # Извлекаем ответ
        if update.callback_query:
            answer = update.callback_query.data
            await update.callback_query.answer()
            message = update.callback_query.message
        else:
            answer = update.message.text
            message = update.message

        # Сохраняем ответ
        if session.answers is None:
            session.answers = {}
        session.answers[current_question_id] = answer
        data_manager.save_session(session)

        logger.info(f"📝 Ответ сохранен: user={user_id}, question={current_question_id}, answer={answer}")

        # Получаем следующий вопрос
        config = context.bot_data.get('config', {})
        questions = config.get('questions', [])
        
        next_question = _get_next_question(questions, current_question_id)
        
        if not next_question:
            # Анкета завершена
            logger.info(f"🎉 Анкета завершена: user_id={user_id}")
            session.status = SessionStatus.COMPLETED
            data_manager.save_session(session)
            
            await message.reply_text(
                "🎊 Поздравляем! Анкета заполнена!\n\n"
                "Сейчас я проанализирую ваши ответы и подготовлю персональные рекомендации.\n"
                "⏳ Это займет около 30-60 секунд..."
            )
            
            # Запускаем анализ если есть OpenAI
            openai_service = context.bot_data.get('openai_service')
            if openai_service:
                return await _start_analysis(update, context, session)
            else:
                await message.reply_text(
                    "🤖 OpenAI не настроен, поэтому анализ временно недоступен.\n"
                    "Используйте команду /status для просмотра ваших ответов."
                )
                return ConversationHandler.END
        
        # Показываем следующий вопрос
        next_id = next_question.get('id', current_question_id + 1)
        from utils.formatters import format_question_text
        question_text = format_question_text(
            next_question.get('text', ''),
            update.effective_user.first_name or "Пользователь",
            next_id,
            len(questions)
        )

        keyboard = _create_keyboard_for_question(next_question)

        if keyboard:
            await message.reply_text(
                question_text,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
        else:
            await message.reply_text(
                question_text,
                parse_mode='Markdown'
            )

        # Обновляем контекст
        context.user_data['session'] = session
        context.user_data['question_id'] = next_id
        session.current_question = next_id
        data_manager.save_session(session)

        return QUESTIONNAIRE

    except Exception as e:
        logger.error(f"❌ Ошибка обработки ответа: {e}", exc_info=True)
        await _send_error(update, "Ошибка обработки ответа")
        return ConversationHandler.END


async def handle_callback_query(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Обработка callback запросов (кнопок "Назад" и т.д.)
    """
    query = update.callback_query
    await query.answer()

    data = query.data
    
    if data == 'back':
        # Обработка кнопки "Назад"
        return await _handle_back_button(update, context)
    else:
        # Обработка обычного ответа на вопрос
        return await handle_question_answer(update, context)


async def _handle_back_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Обработка кнопки "Назад"
    """
    try:
        user_id = update.effective_user.id
        query = update.callback_query
        
        data_manager = context.bot_data.get('data_manager')
        if not data_manager:
            await query.edit_message_text("❌ Ошибка: менеджер данных не инициализирован")
            return QUESTIONNAIRE

        session = context.user_data.get('session')
        if not session:
            session = data_manager.get_session(user_id)
            if not session:
                await query.edit_message_text("❌ Сессия не найдена")
                return ConversationHandler.END

        current_question_id = context.user_data.get('question_id', 1)
        
        # Находим предыдущий вопрос
        config = context.bot_data.get('config', {})
        questions = config.get('questions', [])
        
        prev_question = None
        prev_id = None
        
        for i, q in enumerate(questions):
            if q.get('id') == current_question_id and i > 0:
                prev_question = questions[i-1]
                prev_id = prev_question.get('id')
                break
        
        if not prev_question:
            await query.edit_message_text("❌ Это первый вопрос")
            return QUESTIONNAIRE

        # Показываем предыдущий вопрос
        from utils.formatters import format_question_text
        question_text = format_question_text(
            prev_question.get('text', ''),
            update.effective_user.first_name or "Пользователь",
            prev_id,
            len(questions)
        )

        keyboard = _create_keyboard_for_question(prev_question)

        if keyboard:
            await query.edit_message_text(
                question_text,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
        else:
            await query.edit_message_text(
                question_text,
                parse_mode='Markdown'
            )

        # Обновляем контекст
        context.user_data['session'] = session
        context.user_data['question_id'] = prev_id
        session.current_question = prev_id
        data_manager.save_session(session)

        return QUESTIONNAIRE

    except Exception as e:
        logger.error(f"❌ Ошибка обработки кнопки 'Назад': {e}")
        await update.callback_query.answer("❌ Ошибка", show_alert=True)
        return QUESTIONNAIRE


async def _start_analysis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: UserSession,
):
    """
    Запуск анализа через OpenAI
    """
    try:
        openai_service = context.bot_data.get('openai_service')
        if not openai_service:
            await _send_error(update, "OpenAI сервис не инициализирован")
            return ConversationHandler.END

        logger.info(f"🧠 Запуск анализа для user_id={session.user_id}")

        # Отправляем сообщение о начале анализа
        await update.effective_message.reply_text(
            "🧠 Анализирую ваши ответы...\n"
            "Это займет около 30-60 секунд."
        )

        # Генерируем анализ
        analysis = await openai_service.generate_psychological_analysis(session)
        session.set_analysis(analysis)

        # Сохраняем сессию
        data_manager = context.bot_data.get('data_manager')
        data_manager.save_session(session)

        # Показываем результаты
        return await _show_analysis_results(update, context, session, analysis)

    except Exception as e:
        logger.error(f"❌ Ошибка анализа: {e}", exc_info=True)
        await _send_error(update, f"Ошибка анализа: {str(e)}")
        return ConversationHandler.END


async def _show_analysis_results(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: UserSession,
    analysis,
):
    """
    Показ результатов анализа
    """
    try:
        # Форматируем анализ
        from utils.formatters import format_analysis
        analysis_text = format_analysis(
            analysis.psychological_profile if hasattr(analysis, 'psychological_profile') else str(analysis),
            update.effective_user.first_name or "Пользователь"
        )

        await update.effective_message.reply_text(
            analysis_text,
            parse_mode='Markdown'
        )

        # Если есть сервис генерации ниш, показываем их
        niche_service = context.bot_data.get('niche_service')
        if niche_service:
            await update.effective_message.reply_text(
                "🏭 Генерирую подходящие бизнес-ниши..."
            )

            niches = await niche_service.generate_niches(
                session=session,
                analysis=analysis,
                max_niches=3
            )

            if niches:
                niches_text = "🎯 *Подходящие бизнес-ниши:*\n\n"
                for i, niche in enumerate(niches, 1):
                    niches_text += f"{i}. *{niche.name}*\n"
                    niches_text += f"   {niche.description}\n"
                    if hasattr(niche, 'score'):
                        niches_text += f"   📊 Совместимость: {niche.score:.0f}/100\n"
                    niches_text += "\n"

                await update.effective_message.reply_text(
                    niches_text,
                    parse_mode='Markdown'
                )

        # Завершаем диалог
        await update.effective_message.reply_text(
            "✅ Анализ завершен! Используйте команды:\n"
            "/status - просмотр вашего профиля\n"
            "/questionnaire - начать заново\n"
            "/help - помощь"
        )

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"❌ Ошибка показа результатов: {e}")
        await _send_error(update, "Ошибка показа результатов")
        return ConversationHandler.END


def _create_keyboard_for_question(question_data: dict) -> InlineKeyboardMarkup:
    """
    Создание клавиатуры для вопроса
    """
    question_type = question_data.get('type')
    
    if question_type == 'text':
        return None
    
    options = question_data.get('options', [])
    if not options:
        return None
    
    keyboard = []
    
    for option in options:
        label = option.get('label', option.get('text', 'Вариант'))
        value = option.get('value', label)
        
        # Для кнопок типа "quick_buttons" или "choice"
        keyboard.append([InlineKeyboardButton(label, callback_data=value)])
    
    # Добавляем кнопку "Назад" если это не первый вопрос
    if question_data.get('id', 0) > 1:
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])
    
    return InlineKeyboardMarkup(keyboard)


def _get_next_question(questions: list, current_id: int) -> dict:
    """
    Получение следующего вопроса
    """
    for i, q in enumerate(questions):
        if q.get('id') == current_id and i < len(questions) - 1:
            return questions[i + 1]
    return None


async def _send_error(update: Update, message: str):
    """Отправка сообщения об ошибке"""
    try:
        if update.callback_query:
            await update.callback_query.message.reply_text(f"❌ {message}")
        else:
            await update.message.reply_text(f"❌ {message}")
    except:
        pass


# ConversationHandler для анкеты
def build_questionnaire_conversation():
    """
    Создание ConversationHandler для анкеты
    """
    return ConversationHandler(
        entry_points=[
            CommandHandler("questionnaire", start_questionnaire),
            MessageHandler(filters.Regex(r'^📝 Начать анкету$'), start_questionnaire)
        ],
        states={
            QUESTIONNAIRE: [
                CallbackQueryHandler(handle_callback_query),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question_answer)
            ],
        },
        fallbacks=[
            CommandHandler("start", start_questionnaire),
            CommandHandler("help", lambda u, c: u.message.reply_text("Используйте /start для начала")),
            CommandHandler("cancel", lambda u, c: ConversationHandler.END)
        ],
        allow_reentry=True
    )