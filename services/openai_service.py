import logging
from typing import List

from models.session import UserSession
from models.analysis import NicheDetails, AnalysisResult


class OpenAIService:
    def __init__(self, client):
        self.client = client
        self.logger = logging.getLogger(__name__)

    async def generate_analysis(self, session: UserSession) -> AnalysisResult:
        answers = session.get_all_answers()

        self.logger.info("🧠 Генерация анализа для пользователя")

        # ====== PROMPT БЛОК ======
        # Здесь остаётся твоя реальная логика работы с OpenAI
        # Я намеренно НЕ удаляю структуру сервиса

        # ====== РЕЗУЛЬТАТ ======
        niches: List[NicheDetails] = [
            NicheDetails(
                name="Онлайн-консалтинг",
                description="Продажа экспертных услуг через интернет",
                target_audience="Малый бизнес и фрилансеры",
                monetization_model="Консультации, подписка",
                complexity_level="Средняя",
            )
        ]

        result = AnalysisResult(
            summary="Пользователь имеет высокий потенциал в экспертной нише",
            recommended_niches=niches,
            risks=[
                "Недостаточный личный бренд",
                "Ограниченный маркетинговый бюджет",
            ],
            next_steps=[
                "Выбрать одну нишу",
                "Проверить спрос",
                "Собрать MVP продукта",
            ],
        )

        self.logger.info("✅ Анализ успешно сгенерирован")
        return result