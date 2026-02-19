#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервис для работы с OpenAI API (MOCK-режим для демо)
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes
from config.settings import config
from models.session import UserSession, NicheDetails, AnalysisResult
from models.enums import NicheCategory

logger = logging.getLogger(__name__)

class OpenAIService:
    """Сервис для взаимодействия с OpenAI (MOCK-режим)"""
    
    def __init__(self):
        self.client = None
        self.is_initialized = False
        self._init_client()
    
    def _init_client(self):
        """Инициализировать клиент OpenAI"""
        try:
            if not config.openai_api_key:
                logger.warning("⚠️ OPENAI_API_KEY не настроен - работа в MOCK-режиме")
                self.is_initialized = False
                return
            
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=config.openai_api_key)
            self.is_initialized = True
            logger.info("✅ OpenAI клиент инициализирован")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации OpenAI: {e}")
            self.is_initialized = False

    async def generate_psychological_analysis(self, session: UserSession) -> Optional[str]:
        """Сгенерировать психологический анализ (MOCK)"""
        if not self.is_initialized:
            logger.info("📝 Используем MOCK-анализ вместо OpenAI")
            return self._get_mock_analysis(session)
        
        try:
            # Реальный вызов OpenAI если ключ есть
            prompt_path = Path(__file__).parent.parent / "config" / "prompts" / "psychological_analysis.txt"
            if not prompt_path.exists():
                return self._get_mock_analysis(session)
            
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
            
            answers = session.get_all_answers() if hasattr(session, 'get_all_answers') else session.answers
            prompt = self._fill_psychological_prompt(prompt_template, answers)
            
            response = await self.client.chat.completions.create(
                model=config.openai_model,
                messages=[
                    {"role": "system", "content": "Ты - нейропсихолог и бизнес-стратег с 20-летним опытом."},
                    {"role": "user", "content": prompt}
                ],
                temperature=config.openai_temperature,
                max_tokens=config.openai_max_tokens
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Ошибка генерации анализа: {e}")
            return self._get_mock_analysis(session)

    async def generate_niches(self, session: UserSession) -> List[NicheDetails]:
        """Сгенерировать ниши (MOCK)"""
        return self._create_default_niches()

    def _get_mock_analysis(self, session: UserSession) -> str:
        """MOCK-анализ"""
        answers = session.answers if hasattr(session, 'answers') else {}
        
        age = answers.get('Q1', 'не указано')
        risk = answers.get('Q6', {}).get('value', '5') if isinstance(answers.get('Q6'), dict) else '5'
        
        return f"""
🧠 *ВАШ ПСИХОЛОГИЧЕСКИЙ ПРОФИЛЬ*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 *ДЕМОГРАФИЯ:*
• Возраст: {age}
• Профиль: Активный предприниматель

🎲 *ОТНОШЕНИЕ К РИСКУ:* {risk}/10

💎 *СКРЫТЫЕ ВОЗМОЖНОСТИ:*
• Комбинация навыков указывает на потенциал в цифровых продуктах
• Энергетический профиль подходит для проектной работы

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 *На основе ваших ответов система подобрала 3 персональные ниши...*
"""

    def _fill_psychological_prompt(self, template: str, answers: Dict[str, Any]) -> str:
        """Заполнить шаблон психологического анализа"""
        return template

    def _fill_niches_prompt(self, template: str, answers: Dict[str, Any]) -> str:
        """Заполнить шаблон генерации ниш"""
        return template

    def _fill_plan_prompt(self, template: str, answers: Dict[str, Any], niche: NicheDetails) -> str:
        """Заполнить шаблон детального плана"""
        return template

    def _create_default_niches(self) -> List[NicheDetails]:
        """Создать стандартные ниши для демонстрации"""
        default_niches = [
            NicheDetails(
                id="niche_1",
                name="Консультационные услуги",
                category=NicheCategory.BALANCED,
                description="Оказание консультационных услуг в вашей области экспертизы",
                emoji="💼",
                risk_level=2,
                time_to_profit="1-3 месяца",
                required_skills=["Коммуникация", "Экспертиза", "Аналитика"],
                min_budget=10000,
                success_rate=0.7,
                examples=["Бизнес-консультации", "Коучинг", "Менторство"]
            ),
            NicheDetails(
                id="niche_2",
                name="Онлайн-курсы",
                category=NicheCategory.QUICK_START,
                description="Создание и продажа онлайн-курсов по вашей специальности",
                emoji="🎓",
                risk_level=3,
                time_to_profit="2-4 месяца",
                required_skills=["Экспертиза", "Презентация", "Маркетинг"],
                min_budget=50000,
                success_rate=0.6,
                examples=["Видеокурсы", "Вебинары", "Тренинги"]
            ),
            NicheDetails(
                id="niche_3",
                name="Фриланс-услуги",
                category=NicheCategory.QUICK_START,
                description="Предоставление профессиональных услуг на фриланс-биржах",
                emoji="💻",
                risk_level=2,
                time_to_profit="1-2 месяца",
                required_skills=["Профессиональные навыки", "Тайм-менеджмент", "Коммуникация"],
                min_budget=5000,
                success_rate=0.8,
                examples=["Дизайн", "Программирование", "Копирайтинг"]
            )
        ]
        return default_niches

    def _update_openai_stats(self, requests: int, tokens: int):
        """Обновить статистику использования OpenAI"""
        pass

# Глобальный экземпляр сервиса
openai_service = OpenAIService()
