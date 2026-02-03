from __future__ import annotations

import json
import logging
from typing import List

from models.session import UserSession, AnalysisResult

logger = logging.getLogger(__name__)


class OpenAIService:
    """
    Сервис генерации психологического анализа пользователя
    на основе его ответов в анкете.
    Архитектурно рассчитан на расширение (ниши, стратегии, отчёты).
    """

    def __init__(self, client, model: str = "gpt-4-turbo-preview", language: str = "ru"):
        self.client = client
        self.model = model
        self.language = language

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    async def generate_psychological_analysis(self, session: UserSession) -> AnalysisResult:
        """
        Главный метод, который используется в questionnaire.py
        Возвращает строго AnalysisResult
        """
        logger.info("🧠 Генерация психологического анализа для user_id=%s", session.user_id)

        prompt = self._build_prompt(session)

        response_text = await self._call_openai(prompt)

        analysis = self._parse_response(response_text)

        logger.info("✅ Психологический анализ успешно создан")

        return analysis

    # -------------------------------------------------
    # Prompt
    # -------------------------------------------------
    def _build_prompt(self, session: UserSession) -> str:
        """
        Формирует полный промпт для OpenAI
        """
        answers_block = self._format_answers(session)

        prompt = f"""
Ты — профессиональный бизнес-психолог и аналитик.

Твоя задача:
на основе ответов пользователя провести глубокий психологический анализ
и выдать структурированный результат.

Язык ответа: {self.language}

Ответ верни СТРОГО в JSON без комментариев и пояснений.

Ожидаемая структура JSON:
{{
  "psychological_profile": "текст",
  "strengths": ["строка", "строка"],
  "weaknesses": ["строка", "строка"],
  "motivations": ["строка", "строка"],
  "constraints": ["строка", "строка"]
}}

Ответы пользователя:
{answers_block}
"""
        return prompt.strip()

    def _format_answers(self, session: UserSession) -> str:
        """
        Приводит ответы пользователя к читаемому виду для LLM
        """
        lines: List[str] = []

        for question_id, answer in session.answers.items():
            lines.append(f"Вопрос {question_id}: {answer}")

        return "\n".join(lines)

    # -------------------------------------------------
    # OpenAI call
    # -------------------------------------------------
    async def _call_openai(self, prompt: str) -> str:
        """
        Единственная точка общения с OpenAI API
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты полезный и точный аналитик."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.6,
            )

            content = response.choices[0].message.content
            return content

        except Exception as e:
            logger.exception("❌ Ошибка при обращении к OpenAI")
            raise RuntimeError("OpenAI generation failed") from e

    # -------------------------------------------------
    # Parsing
    # -------------------------------------------------
    def _parse_response(self, text: str) -> AnalysisResult:
        """
        Парсит JSON ответ от модели и возвращает AnalysisResult
        """
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.error("❌ OpenAI вернул невалидный JSON")
            raise ValueError("Invalid JSON from OpenAI")

        required_fields = [
            "psychological_profile",
            "strengths",
            "weaknesses",
            "motivations",
            "constraints",
        ]

        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing field in analysis result: {field}")

        return AnalysisResult(
            psychological_profile=data["psychological_profile"],
            strengths=list(data["strengths"]),
            weaknesses=list(data["weaknesses"]),
            motivations=list(data["motivations"]),
            constraints=list(data["constraints"]),
            raw_response=text,
        )