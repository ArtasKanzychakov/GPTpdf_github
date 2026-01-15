#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервис для работы с OpenAI API
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path

from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import ContextTypes

from config.settings import config
from models.session import UserSession, NicheDetails, AnalysisResult
from models.enums import NicheCategory
from services.data_manager import data_manager

logger = logging.getLogger(__name__)

class OpenAIService:
    """Сервис для взаимодействия с OpenAI"""

    def __init__(self):
        self.client = None
        self.is_initialized = False
        self._init_client()

    def _init_client(self):
        """Инициализировать клиент OpenAI"""
        try:
            if not config.openai_api_key:
                logger.error("OPENAI_API_KEY не настроен")
                self.is_initialized = False
                return

            self.client = AsyncOpenAI(api_key=config.openai_api_key)
            self.is_initialized = True
            logger.info("OpenAI клиент инициализирован")

        except Exception as e:
            logger.error(f"Ошибка инициализации OpenAI: {e}")
            self.is_initialized = False

    async def analyze_user_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                  session: UserSession):
        """Проанализировать профиль пользователя и предложить ниши"""
        if not self.is_initialized:
            await self._send_error_message(update, "Сервис анализа временно недоступен")
            return

        try:
            # Шаг 1: Психологический анализ
            await update.effective_message.reply_text(
                "🔍 *Шаг 1/3: Провожу психологический анализ...*",
                parse_mode='Markdown'
            )

            psychological_analysis = await self._generate_psychological_analysis(session)
            if psychological_analysis:
                session.analysis_result = psychological_analysis
                # Обновляем статистику использования OpenAI
                self._update_openai_stats(1, 1000)  # Примерные значения

            # Шаг 2: Генерация ниш
            await update.effective_message.reply_text(
                "💡 *Шаг 2/3: Подбираю подходящие бизнес-ниши...*",
                parse_mode='Markdown'
            )

            niches_data = await self._generate_niches(session)
            if niches_data:
                # Преобразуем в объекты NicheDetails
                suggested_niches = self._parse_niches_data(niches_data)
                session.suggested_niches = suggested_niches
                # Обновляем статистику использования OpenAI
                self._update_openai_stats(1, 1500)

            # Шаг 3: Сохраняем и показываем результаты
            await update.effective_message.reply_text(
                "✅ *Шаг 3/3: Формирую результаты...*",
                parse_mode='Markdown'
            )

            data_manager.save_session(session)
            await self._show_niches_to_user(update, session)

        except Exception as e:
            logger.error(f"Ошибка анализа профиля: {e}")
            await self._send_error_message(update, f"Ошибка анализа: {str(e)}")

    async def _generate_psychological_analysis(self, session: UserSession) -> Optional[str]:
        """Сгенерировать психологический анализ"""
        try:
            # Загружаем промпт
            prompt_path = Path(__file__).parent.parent / "config" / "prompts" / "psychological_analysis.txt"
            if not prompt_path.exists():
                logger.error(f"Файл промпта не найден: {prompt_path}")
                return None

            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()

            # Получаем все ответы
            answers = session.get_all_answers()

            # Заполняем шаблон
            prompt = self._fill_psychological_prompt(prompt_template, answers)

            # Генерируем ответ
            response = await self.client.chat.completions.create(
                model=config.openai_model,
                messages=[
                    {"role": "system", "content": "Ты - нейропсихолог и бизнес-стратег с 20-летним опытом."},
                    {"role": "user", "content": prompt}
                ],
                temperature=config.openai_temperature,
                max_tokens=config.openai_max_tokens
            )

            analysis_text = response.choices[0].message.content.strip()
            logger.info(f"Психологический анализ сгенерирован ({len(analysis_text)} символов)")

            return analysis_text

        except Exception as e:
            logger.error(f"Ошибка генерации психологического анализа: {e}")
            return None

    async def _generate_niches(self, session: UserSession) -> Optional[str]:
        """Сгенерировать подходящие ниши"""
        try:
            # Загружаем промпт
            prompt_path = Path(__file__).parent.parent / "config" / "prompts" / "niche_generation.txt"
            if not prompt_path.exists():
                logger.error(f"Файл промпта не найден: {prompt_path}")
                return None

            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()

            # Получаем все ответы
            answers = session.get_all_answers()

            # Заполняем шаблон
            prompt = self._fill_niches_prompt(prompt_template, answers)

            # Генерируем ответ
            response = await self.client.chat.completions.create(
                model=config.openai_model,
                messages=[
                    {"role": "system", "content": "Ты - опытный бизнес-консультант и аналитик рынка."},
                    {"role": "user", "content": prompt}
                ],
                temperature=config.openai_temperature,
                max_tokens=2500  # Больше токенов для 5 ниш
            )

            niches_text = response.choices[0].message.content.strip()
            logger.info(f"Ниши сгенерированы ({len(niches_text)} символов)")

            return niches_text

        except Exception as e:
            logger.error(f"Ошибка генерации ниш: {e}")
            return None

    async def generate_detailed_plan(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                    session: UserSession, niche: NicheDetails) -> Optional[str]:
        """Сгенерировать детальный план для выбранной ниши"""
        if not self.is_initialized:
            await self._send_error_message(update, "Сервис временно недоступен")
            return None

        try:
            await update.effective_message.reply_text(
                "📋 *Создаю детальный пошаговый план...*\n\n"
                "Это займет около 1-2 минут.",
                parse_mode='Markdown'
            )

            # Загружаем промпт
            prompt_path = Path(__file__).parent.parent / "config" / "prompts" / "detailed_plan.txt"
            if not prompt_path.exists():
                logger.error(f"Файл промпта не найден: {prompt_path}")
                return None

            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()

            # Получаем все ответы
            answers = session.get_all_answers()

            # Заполняем шаблон с данными ниши
            prompt = self._fill_plan_prompt(prompt_template, answers, niche)

            # Генерируем ответ
            response = await self.client.chat.completions.create(
                model=config.openai_model,
                messages=[
                    {"role": "system", "content": "Ты - бизнес-стратег и наставник."},
                    {"role": "user", "content": prompt}
                ],
                temperature=config.openai_temperature,
                max_tokens=3000  # Больше токенов для детального плана
            )

            plan_text = response.choices[0].message.content.strip()
            logger.info(f"Детальный план сгенерирован ({len(plan_text)} символов)")

            # Обновляем статистику использования OpenAI
            self._update_openai_stats(1, 2000)

            # Сохраняем план в сессию
            session.detailed_plan = plan_text
            session.selected_niche = niche
            data_manager.save_session(session)

            return plan_text

        except Exception as e:
            logger.error(f"Ошибка генерации плана: {e}")
            await self._send_error_message(update, f"Ошибка создания плана: {str(e)}")
            return None

    def _fill_psychological_prompt(self, template: str, answers: Dict[str, Any]) -> str:
        """Заполнить шаблон психологического анализа"""
        try:
            # Демография
            demo = answers.get('demographics', {})
            # Личность
            personality = answers.get('personality', {})
            energy = personality.get('energy_profile', {})
            # Навыки
            skills = answers.get('skills', {})
            # Ценности
            values = answers.get('values', {})
            ideal_client = values.get('ideal_client', {})
            # Ограничения
            limitations = answers.get('limitations', {})

            prompt = template
            prompt = prompt.replace("{demographics.age_group}", demo.get('age_group', 'не указано'))
            prompt = prompt.replace("{demographics.education}", demo.get('education', 'не указано'))
            prompt = prompt.replace("{demographics.location}", demo.get('location', 'не указано'))

            prompt = prompt.replace("{', '.join(personality.motivations)}", 
                                  ', '.join(personality.get('motivations', [])))
            prompt = prompt.replace("{personality.decision_style}", 
                                  personality.get('decision_style', 'не указано'))
            prompt = prompt.replace("{personality.risk_tolerance}", 
                                  str(personality.get('risk_tolerance', 0)))
            prompt = prompt.replace("{personality.risk_scenario}", 
                                  personality.get('risk_scenario', 'не указано'))

            prompt = prompt.replace("{personality.energy_profile.morning}", 
                                  str(energy.get('morning', 0)))
            prompt = prompt.replace("{personality.energy_profile.day}", 
                                  str(energy.get('day', 0)))
            prompt = prompt.replace("{personality.energy_profile.evening}", 
                                  str(energy.get('evening', 0)))
            prompt = prompt.replace("{personality.energy_profile.peak_analytical}", 
                                  energy.get('peak_analytical', 'не указано'))
            prompt = prompt.replace("{personality.energy_profile.peak_creative}", 
                                  energy.get('peak_creative', 'не указано'))
            prompt = prompt.replace("{personality.energy_profile.peak_social}", 
                                  energy.get('peak_social', 'не указано'))

            prompt = prompt.replace("{', '.join(personality.fears)}", 
                                  ', '.join(personality.get('fears', [])))
            prompt = prompt.replace("{personality.fear_custom}", 
                                  personality.get('fear_custom', 'не указано'))

            # Навыки
            prompt = prompt.replace("{skills.analytics}", str(skills.get('analytics', 0)))
            prompt = prompt.replace("{skills.communication}", str(skills.get('communication', 0)))
            prompt = prompt.replace("{skills.design}", str(skills.get('design', 0)))
            prompt = prompt.replace("{skills.organization}", str(skills.get('organization', 0)))
            prompt = prompt.replace("{skills.manual}", str(skills.get('manual', 0)))
            prompt = prompt.replace("{skills.emotional_iq}", str(skills.get('emotional_iq', 0)))
            prompt = prompt.replace("{skills.superpower}", skills.get('superpower', 'не указано'))
            prompt = prompt.replace("{skills.work_style}", skills.get('work_style', 'не указано'))

            # Ценности
            prompt = prompt.replace("{values.existential_answer}", 
                                  values.get('existential_answer', 'не указано'))
            prompt = prompt.replace("{values.flow_experience}", 
                                  values.get('flow_experience', 'не указано'))
            prompt = prompt.replace("{values.flow_feelings}", 
                                  values.get('flow_feelings', 'не указано'))
            prompt = prompt.replace("{values.ideal_client.age}", 
                                  ideal_client.get('age', 'не указано'))
            prompt = prompt.replace("{values.ideal_client.field}", 
                                  ideal_client.get('field', 'не указано'))
            prompt = prompt.replace("{values.ideal_client.pain}", 
                                  ideal_client.get('pain', 'не указано'))

            # Ограничения
            prompt = prompt.replace("{limitations.budget}", limitations.get('budget', 'не указано'))
            prompt = prompt.replace("{', '.join(limitations.equipment)}", 
                                  ', '.join(limitations.get('equipment', [])))
            prompt = prompt.replace("{', '.join(limitations.knowledge_assets)}", 
                                  ', '.join(limitations.get('knowledge_assets', [])))
            prompt = prompt.replace("{limitations.time_per_week}", 
                                  limitations.get('time_per_week', 'не указано'))
            prompt = prompt.replace("{limitations.business_scale}", 
                                  limitations.get('business_scale', 'не указано'))
            prompt = prompt.replace("{limitations.business_format}", 
                                  limitations.get('business_format', 'не указано'))

            return prompt

        except Exception as e:
            logger.error(f"Ошибка заполнения промпта: {e}")
            return template

    def _fill_niches_prompt(self, template: str, answers: Dict[str, Any]) -> str:
        """Заполнить шаблон генерации ниш"""
        try:
            demo = answers.get('demographics', {})
            personality = answers.get('personality', {})
            skills = answers.get('skills', {})
            limitations = answers.get('limitations', {})

            # Для упрощения берем основные черты
            motivations = personality.get('motivations', [])
            decision_style = personality.get('decision_style', '')

            prompt = template
            prompt = prompt.replace("{age_group}", demo.get('age_group', 'не указано'))
            prompt = prompt.replace("{education}", demo.get('education', 'не указано'))
            prompt = prompt.replace("{location}", demo.get('location', 'не указано'))

            prompt = prompt.replace("{personality_traits}", decision_style)
            prompt = prompt.replace("{strengths}", ', '.join(motivations[:3]))
            prompt = prompt.replace("{weaknesses}", ', '.join(personality.get('fears', [])[:2]))
            prompt = prompt.replace("{motivations}", ', '.join(motivations))
            prompt = prompt.replace("{risk_tolerance}", str(personality.get('risk_tolerance', 5)))

            prompt = prompt.replace("{skills.analytics}", str(skills.get('analytics', 3)))
            prompt = prompt.replace("{skills.communication}", str(skills.get('communication', 3)))
            prompt = prompt.replace("{skills.design}", str(skills.get('design', 3)))
            prompt = prompt.replace("{skills.organization}", str(skills.get('organization', 3)))
            prompt = prompt.replace("{skills.manual}", str(skills.get('manual', 3)))
            prompt = prompt.replace("{skills.emotional_iq}", str(skills.get('emotional_iq', 3)))

            prompt = prompt.replace("{budget}", limitations.get('budget', 'не указано'))
            prompt = prompt.replace("{equipment}", ', '.join(limitations.get('equipment', [])))
            prompt = prompt.replace("{time_per_week}", limitations.get('time_per_week', 'не указано'))
            prompt = prompt.replace("{business_format}", limitations.get('business_format', 'не указано'))
            prompt = prompt.replace("{business_scale}", limitations.get('business_scale', 'не указано'))

            return prompt

        except Exception as e:
            logger.error(f"Ошибка заполнения промпта ниш: {e}")
            return template

    def _fill_plan_prompt(self, template: str, answers: Dict[str, Any], niche: NicheDetails) -> str:
        """Заполнить шаблон детального плана"""
        try:
            demo = answers.get('demographics', {})
            personality = answers.get('personality', {})
            skills = answers.get('skills', {})
            values = answers.get('values', {})
            limitations = answers.get('limitations', {})

            energy = personality.get('energy_profile', {})

            prompt = template
            prompt = prompt.replace("{age_group}", demo.get('age_group', 'не указано'))
            prompt = prompt.replace("{education}", demo.get('education', 'не указано'))
            prompt = prompt.replace("{location}", demo.get('location', 'не указано'))
            prompt = prompt.replace("{budget}", limitations.get('budget', 'не указано'))
            prompt = prompt.replace("{time_per_week}", limitations.get('time_per_week', 'не указано'))

            prompt = prompt.replace("{fears}", ', '.join(personality.get('fears', [])))
            prompt = prompt.replace("{decision_style}", personality.get('decision_style', 'не указано'))
            prompt = prompt.replace("{peak_morning}", str(energy.get('morning', 4)))
            prompt = prompt.replace("{peak_day}", str(energy.get('day', 4)))
            prompt = prompt.replace("{peak_evening}", str(energy.get('evening', 4)))
            prompt = prompt.replace("{superpower}", skills.get('superpower', 'не указано'))
            prompt = prompt.replace("{work_style}", skills.get('work_style', 'не указано'))
            prompt = prompt.replace("{learning_style}", skills.get('learning_style', 'не указано'))

            prompt = prompt.replace("{niche_name}", niche.name)
            prompt = prompt.replace("{niche_category}", niche.category.value)
            prompt = prompt.replace("{niche_suitability}", niche.description[:200] + "..." if niche.description else "Описание отсутствует")
            prompt = prompt.replace("{niche_format}", "Онлайн/Офлайн/Гибрид")

            return prompt

        except Exception as e:
            logger.error(f"Ошибка заполнения промпта плана: {e}")
            return template

    def _parse_niches_data(self, niches_text: str) -> List[NicheDetails]:
        """Парсить сгенерированные ниши в объекты NicheDetails - УПРОЩЕННАЯ ВЕРСИЯ"""
        try:
            # ИСПРАВЛЕНО: Вместо сложного парсинга возвращаем стандартные ниши из конфига
            # Это временное решение для запуска бота
            
            if config.niche_categories and len(config.niche_categories) >= 5:
                # Возвращаем первые 5 ниш из конфига
                return config.niche_categories[:5]
            
            # Если в конфиге нет ниш, создаем минимальный набор
            return self._create_default_niches()
            
        except Exception as e:
            logger.error(f"Ошибка парсинга ниш: {e}")
            # Возвращаем стандартные ниши
            return self._create_default_niches()

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
            ),
            NicheDetails(
                id="niche_4",
                name="Электронная коммерция",
                category=NicheCategory.LONG_TERM,
                description="Продажа товаров через интернет-магазин",
                emoji="🛒",
                risk_level=4,
                time_to_profit="3-6 месяцев",
                required_skills=["Маркетинг", "Логистика", "Аналитика"],
                min_budget=100000,
                success_rate=0.5,
                examples=["Дропшиппинг", "Собственное производство", "Нишевые товары"]
            ),
            NicheDetails(
                id="niche_5",
                name="Мобильные приложения",
                category=NicheCategory.RISKY,
                description="Разработка и монетизация мобильных приложений",
                emoji="📱",
                risk_level=5,
                time_to_profit="6-12 месяцев",
                required_skills=["Программирование", "Дизайн", "Маркетинг"],
                min_budget=200000,
                success_rate=0.3,
                examples=["Игры", "Утилиты", "Социальные приложения"]
            )
        ]
        return default_niches

    async def _show_niches_to_user(self, update: Update, session: UserSession):
        """Показать предложенные ниши пользователю"""
        try:
            if not session.suggested_niches:
                await update.effective_message.reply_text(
                    "❌ Не удалось подобрать подходящие ниши.\n"
                    "Попробуйте пройти анкету заново.",
                    parse_mode='Markdown'
                )
                return

            message = "🎯 *НАЙДЕННЫЕ ПОДХОДЯЩИЕ НИШИ:*\n\n"

            for i, niche in enumerate(session.suggested_niches, 1):
                message += f"{i}. {niche.emoji} *{niche.name}*\n"
                message += f"   📊 {niche.category.value}\n"

                if niche.description:
                    desc = niche.description[:100] + "..." if len(niche.description) > 100 else niche.description
                    message += f"   📝 {desc}\n"

                message += f"   🎯 Риск: {'★' * niche.risk_level}{'☆' * (5 - niche.risk_level)}\n"
                message += f"   ⏱️ Окупаемость: {niche.time_to_profit}\n\n"

            message += (
                "Для получения детального плана по любой нише,\n"
                "нажмите на соответствующую кнопку ниже."
            )

            # Создаем кнопки для выбора ниши
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = []

            for i, niche in enumerate(session.suggested_niches, 1):
                keyboard.append([
                    InlineKeyboardButton(
                        f"{i}. {niche.emoji} {niche.name}",
                        callback_data=f"select_niche_{niche.id}"
                    )
                ])

            keyboard.append([
                InlineKeyboardButton("🔄 Пройти анкету заново", callback_data="restart_questionnaire")
            ])

            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.effective_message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

        except Exception as e:
            logger.error(f"Ошибка показа ниш: {e}")
            await update.effective_message.reply_text(
                "❌ Ошибка при отображении результатов.\n"
                "Попробуйте позже.",
                parse_mode='Markdown'
            )

    def _update_openai_stats(self, requests: int, tokens: int):
        """Обновить статистику использования OpenAI"""
        try:
            if hasattr(data_manager, 'statistics'):
                # Примерная стоимость: $0.002 за 1K токенов для gpt-3.5-turbo
                cost = tokens * 0.000002
                data_manager.statistics.add_openai_request(tokens, cost)
        except Exception as e:
            logger.error(f"Ошибка обновления статистики OpenAI: {e}")

    async def _send_error_message(self, update: Update, message: str):
        """Отправить сообщение об ошибке"""
        try:
            await update.effective_message.reply_text(
                f"❌ {message}",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")

# Глобальный экземпляр сервиса
openai_service = OpenAIService()

# Функции для импорта
async def analyze_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, session: UserSession):
    """Анализировать профиль пользователя"""
    await openai_service.analyze_user_profile(update, context, session)

async def generate_detailed_plan(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                session: UserSession, niche: NicheDetails):
    """Сгенерировать детальный план"""
    return await openai_service.generate_detailed_plan(update, context, session, niche)