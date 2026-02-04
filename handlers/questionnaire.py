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

from services.data_manager import DataManager
from services.openai_service import OpenAIService
from services.niche_generation_detailed import NicheGenerationService

# ✅ ПРАВИЛЬНЫЙ ИМПОРТ
from core.question_engine_v2 import QuestionEngineV2

logger = logging.getLogger(__name__)

# Conversation states
QUESTIONNAIRE = 1
ANALYSIS = 2
RESULT = 3


class QuestionnaireHandler:
    """
    Основной обработчик анкеты.
    Архитектура сохранена полностью.
    """

    def __init__(
        self,
        data_manager: DataManager,
        openai_service: OpenAIService,
        niche_service: NicheGenerationService,
        question_engine: QuestionEngineV2,
    ):
        self.data_manager = data_manager
        self.openai_service = openai_service
        self.niche_service = niche_service
        self.question_engine = question_engine

    # -------------------------------------------------
    # Entry point
    # -------------------------------------------------
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        session = self.data_manager.get_or_create_session(user_id)
        session.start()

        logger.info("▶️ Старт анкеты user_id=%s", user_id)

        first_question = self.question_engine.get_first_question()
        session.current_question = first_question.id
        session.current_category = first_question.category

        self.data_manager.save_session(session)

        await update.message.reply_text(
            first_question.text,
            reply_markup=self._build_keyboard(first_question),
        )

        return QUESTIONNAIRE

    # -------------------------------------------------
    # Questionnaire step
    # -------------------------------------------------
    async def handle_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        session: UserSession = self.data_manager.get_session(user_id)

        if not session or session.status != SessionStatus.IN_PROGRESS:
            return ConversationHandler.END

        answer = self._extract_answer(update)
        question_id = session.current_question

        session.save_answer(question_id, answer)
        session.add_to_navigation(question_id, session.current_category)

        next_question = self.question_engine.get_next_question(session)

        if not next_question:
            logger.info("📊 Анкета завершена user_id=%s", user_id)
            session.complete_questionnaire()
            self.data_manager.save_session(session)
            return await self._start_analysis(update, context, session)

        session.current_question = next_question.id
        session.current_category = next_question.category
        self.data_manager.save_session(session)

        await self._send_question(update, next_question)

        return QUESTIONNAIRE

    # -------------------------------------------------
    # Back navigation
    # -------------------------------------------------
    async def go_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        session: UserSession = self.data_manager.get_session(user_id)

        step = session.go_back()
        if not step:
            return QUESTIONNAIRE

        question = self.question_engine.get_question_by_id(step.question_id)
        self.data_manager.save_session(session)

        await query.edit_message_text(
            question.text,
            reply_markup=self._build_keyboard(question),
        )

        return QUESTIONNAIRE

    # -------------------------------------------------
    # Analysis
    # -------------------------------------------------
    async def _start_analysis(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: UserSession,
    ):
        logger.info("🧠 Запуск анализа user_id=%s", session.user_id)

        await update.effective_message.reply_text(
            "Спасибо! Анализирую ответы и подбираю бизнес-направления…"
        )

        analysis = await self.openai_service.generate_psychological_analysis(session)
        session.set_analysis(analysis)

        niches = await self.niche_service.generate_niches(
            session=session,
            analysis=analysis,
        )

        session.clear_niches()
        for niche in niches:
            session.add_niche(niche)

        self.data_manager.save_session(session)

        return await self._show_result(update, session)

    # -------------------------------------------------
    # Result
    # -------------------------------------------------
    async def _show_result(self, update: Update, session: UserSession):
        text_lines: List[str] = []

        text_lines.append("🧠 Психологический профиль:")
        text_lines.append(session.psychological_analysis.psychological_profile)
        text_lines.append("\n🏭 Рекомендованные бизнес-ниши:")

        for idx, niche in enumerate(session.niches, start=1):
            text_lines.append(
                f"\n{idx}. {niche.name} (оценка {niche.score:.0f}/100)\n"
                f"{niche.description}"
            )

        await update.effective_message.reply_text("\n".join(text_lines))

        session.finish()
        self.data_manager.save_session(session)

        return ConversationHandler.END

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def _extract_answer(self, update: Update) -> Any:
        if update.callback_query:
            return update.callback_query.data
        return update.message.text

    def _send_question(self, update: Update, question):
        return update.effective_message.reply_text(
            question.text,
            reply_markup=self._build_keyboard(question),
        )

    def _build_keyboard(self, question):
        if question.type != "buttons":
            return None

        keyboard = [
            [InlineKeyboardButton(opt["text"], callback_data=opt["value"])]
            for opt in question.options
        ]

        keyboard.append(
            [InlineKeyboardButton("⬅️ Назад", callback_data="__back__")]
        )

        return InlineKeyboardMarkup(keyboard)


# -------------------------------------------------
# ConversationHandler factory
# -------------------------------------------------
def build_questionnaire_conversation(handler: QuestionnaireHandler):
    return ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.COMMAND & filters.Regex("^/start$"),
                handler.start,
            )
        ],
        states={
            QUESTIONNAIRE: [
                CallbackQueryHandler(handler.go_back, pattern="^__back__$"),
                CallbackQueryHandler(handler.handle_answer),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handler.handle_answer,
                ),
            ],
        },
        fallbacks=[],
        allow_reentry=False,
    )


# =====================================================================
# 🔌 ADAPTER ДЛЯ core.bot (КРИТИЧЕСКИ ВАЖНО)
# =====================================================================

_questionnaire_handler: QuestionnaireHandler | None = None


def _get_handler(context: ContextTypes.DEFAULT_TYPE) -> QuestionnaireHandler:
    global _questionnaire_handler
    if _questionnaire_handler is None:
        _questionnaire_handler = QuestionnaireHandler(
            data_manager=context.bot_data["data_manager"],
            openai_service=context.bot_data["openai_service"],
            niche_service=context.bot_data["niche_service"],
            question_engine=context.bot_data["question_engine"],
        )
    return _questionnaire_handler


async def start_questionnaire(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    handler = _get_handler(context)
    return await handler.start(update, context)


async def handle_question_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    handler = _get_handler(context)
    return await handler.handle_answer(update, context)


async def handle_callback_query(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    handler = _get_handler(context)
    return await handler.go_back(update, context)