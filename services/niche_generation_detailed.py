from __future__ import annotations

import logging
from typing import List

from models.session import UserSession, NicheDetails, AnalysisResult

logger = logging.getLogger(__name__)


class NicheGenerationService:
    """
    Сервис генерации и ранжирования бизнес-ниш
    на основе психологического анализа пользователя.
    """

    def __init__(self, client, model: str = "gpt-4-turbo-preview", language: str = "ru"):
        self.client = client
        self.model = model
        self.language = language

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    async def generate_niches(
        self,
        session: UserSession,
        analysis: AnalysisResult,
        max_niches: int = 5,
    ) -> List[NicheDetails]:
        """
        Главный метод, вызываемый из questionnaire.py
        Возвращает список NicheDetails
        """
        logger.info("🏭 Генерация бизнес-ниш для user_id=%s", session.user_id)

        prompt = self._build_prompt(session, analysis, max_niches)

        response_text = await self._call_openai(prompt)

        niches = self._parse_response(response_text)

        logger.info("✅ Сгенерировано ниш: %s", len(niches))

        return niches

    # -------------------------------------------------
    # Prompt
    # -------------------------------------------------
    def _build_prompt(
        self,
        session: UserSession,
        analysis: AnalysisResult,
        max_niches: int,
    ) -> str:
        """
        Формирует промпт для генерации ниш
        """
        prompt = f"""
Ты — стратегический бизнес-аналитик и венчурный консультант.

На основе психологического профиля пользователя
предложи наиболее подходящие бизнес-ниши.

Язык ответа: {self.language}

Верни СТРОГО JSON без комментариев.

Ожидаемая структура:
{{
  "niches": [
    {{
      "niche_id": "string",
      "name": "string",
      "description": "string",
      "score": 0.0,
      "advantages": ["string"],
      "risks": ["string"],
      "recommendations": ["string"]
    }}
  ]
}}

Ограничения:
- максимум {max_niches} ниш
- score от 0 до 100

Психологический профиль пользователя:
{analysis.psychological_profile}

Сильные стороны:
{", ".join(analysis.strengths)}

Слабые стороны:
{", ".join(analysis.weaknesses)}

Мотивации:
{", ".join(analysis.motivations)}

Ограничения:
{", ".join(analysis.constraints)}
"""
        return prompt.strip()

    # -------------------------------------------------
    # OpenAI call
    # -------------------------------------------------
    async def _call_openai(self, prompt: str) -> str:
        """
        Обращение к OpenAI API
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты точный и прагматичный бизнес-аналитик.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.exception("❌ Ошибка генерации ниш")
            raise RuntimeError("Niche generation failed") from e

    # -------------------------------------------------
    # Parsing
    # -------------------------------------------------
    def _parse_response(self, text: str) -> List[NicheDetails]:
        """
        Парсит JSON и возвращает список NicheDetails
        """
        import json

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.error("❌ OpenAI вернул невалидный JSON при генерации ниш")
            raise ValueError("Invalid JSON from OpenAI (niches)")

        if "niches" not in data or not isinstance(data["niches"], list):
            raise ValueError("Invalid niches structure")

        niches: List[NicheDetails] = []

        for raw in data["niches"]:
            niche = NicheDetails(
                niche_id=str(raw.get("niche_id")),
                name=str(raw.get("name")),
                description=str(raw.get("description")),
                score=float(raw.get("score", 0)),
                advantages=list(raw.get("advantages", [])),
                risks=list(raw.get("risks", [])),
                recommendations=list(raw.get("recommendations", [])),
            )
            niches.append(niche)

        return niches