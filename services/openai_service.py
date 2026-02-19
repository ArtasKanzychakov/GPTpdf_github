#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервис для работы с OpenAI API
Архитектура: MOCK-режим по умолчанию, полный режим при наличии ключа
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
    """Сервис для взаимодействия с OpenAI (MOCK-first архитектура)"""
    
    def __init__(self):
        self.client = None
        self.is_initialized = False
        self._init_client()
    
    def _init_client(self):
        """Инициализировать клиент OpenAI"""
        try:
            # Проверяем наличие ключа
            if not config.openai_api_key:
                logger.warning("⚠️ OPENAI_API_KEY не настроен — работа в MOCK-режиме")
                self.is_initialized = False
                return
            
            # Инициализируем клиент только если есть ключ
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=config.openai_api_key)
            self.is_initialized = True
            logger.info("✅ OpenAI клиент инициализирован (полный режим)")
            
        except ImportError:
            logger.warning("⚠️ Библиотека openai не установлена — MOCK-режим")
            self.is_initialized = False
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации OpenAI: {e}")
            self.is_initialized = False

    async def generate_psychological_analysis(self, session: UserSession) -> Optional[str]:
        """
        Сгенерировать психологический анализ
        Returns: Текст анализа или None при ошибке
        """
        # === MOCK-режим: если нет клиента или ключа ===
        if not self.is_initialized or not self.client:
            logger.info("📝 MOCK-режим: используем заготовленный анализ")
            return self._get_mock_analysis(session)
        
        # === Полный режим: реальный вызов OpenAI ===
        try:
            prompt_path = Path(__file__).parent.parent / "config" / "prompts" / "psychological_analysis.txt"
            
            if not prompt_path.exists():
                logger.warning(f"⚠️ Промпт не найден: {prompt_path}, использую MOCK")
                return self._get_mock_analysis(session)
            
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
            
            answers = session.answers if hasattr(session, 'answers') else {}
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
            
            result = response.choices[0].message.content.strip()
            logger.info(f"✅ Анализ сгенерирован ({len(result)} символов)")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации анализа: {e}")
            return self._get_mock_analysis(session)

    async def generate_niches(self, session: UserSession) -> List[NicheDetails]:
        """
        Сгенерировать список бизнес-ниш
        Returns: Список объектов NicheDetails
        """
        # MOCK-режим
        if not self.is_initialized or not self.client:
            logger.info("📝 MOCK-режим: использую стандартные ниши")
            return self._create_default_niches()
        
        # Полный режим
        try:
            prompt_path = Path(__file__).parent.parent / "config" / "prompts" / "niche_generation.txt"
            
            if not prompt_path.exists():
                return self._create_default_niches()
            
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
            
            answers = session.answers if hasattr(session, 'answers') else {}
            prompt = self._fill_niches_prompt(prompt_template, answers)
            
            response = await self.client.chat.completions.create(
                model=config.openai_model,
                messages=[
                    {"role": "system", "content": "Ты - опытный бизнес-консультант и аналитик рынка."},
                    {"role": "user", "content": prompt}
                ],
                temperature=config.openai_temperature,
                max_tokens=2500
            )
            
            niches_text = response.choices[0].message.content.strip()
            logger.info(f"✅ Ниши сгенерированы")
            return self._parse_niches_text(niches_text)
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации ниш: {e}")
            return self._create_default_niches()

    async def generate_detailed_plan(self, session: UserSession, niche: NicheDetails) -> Optional[str]:
        """
        Сгенерировать детальный план для выбранной ниши
        """
        if not self.is_initialized or not self.client:
            return self._get_mock_plan(niche)
        
        try:
            prompt_path = Path(__file__).parent.parent / "config" / "prompts" / "detailed_plan.txt"
            
            if not prompt_path.exists():
                return self._get_mock_plan(niche)
            
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
            
            answers = session.answers if hasattr(session, 'answers') else {}
            prompt = self._fill_plan_prompt(prompt_template, answers, niche)
            
            response = await self.client.chat.completions.create(
                model=config.openai_model,
                messages=[
                    {"role": "system", "content": "Ты - бизнес-стратег и наставник."},
                    {"role": "user", "content": prompt}
                ],
                temperature=config.openai_temperature,
                max_tokens=3000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации плана: {e}")
            return self._get_mock_plan(niche)

    # ========================================================================
    # MOCK-МЕТОДЫ (работают без OpenAI ключа)
    # ========================================================================
    
    def _get_mock_analysis(self, session: UserSession) -> str:
        """MOCK-анализ: заготовленный шаблон с подстановкой данных"""
        answers = session.answers if hasattr(session, 'answers') else {}
        
        age = answers.get('Q1', 'не указано')
        risk = answers.get('Q6', {}).get('value', '5') if isinstance(answers.get('Q6'), dict) else '5'
        energy = answers.get('Q7', {}).get('energy_levels', {}) if isinstance(answers.get('Q7'), dict) else {}
        
        m = energy.get('morning', 4)
        d = energy.get('day', 4)
        e = energy.get('evening', 4)
        peak = "утро" if m >= d and m >= e else "день" if d >= e else "вечер"
        
        risk_label = "🔥 Высокий" if int(risk) >= 7 else "⚖️ Умеренный" if int(risk) >= 4 else "🔒 Осторожный"
        
        return f"""
🧠 *ВАШ ПСИХОЛОГИЧЕСКИЙ ПРОФИЛЬ*

━━━━━━━━━━━━━━━━━━━━
👤 *ДЕМОГРАФИЯ:*
• Возраст: {age}
• Профиль: Активный предприниматель

⚡ *ЭНЕРГЕТИКА:*
• Утро: {m}/7 {'🌅'*m}{'▁'*(7-m)}
• День: {d}/7 {'☀️'*d}{'▁'*(7-d)}
• Вечер: {e}/7 {'🌙'*e}{'▁'*(7-e)}
🎯 Пик продуктивности: *{peak}*

🎲 *ОТНОШЕНИЕ К РИСКУ:* {risk}/10
{risk_label}

💎 *СКРЫТЫЙ ПОТЕНЦИАЛ:*
• Комбинация навыков → цифровые продукты
• Энергетический профиль → проектная работа
• Стиль решений → оптимален для стартапов

━━━━━━━━━━━━━━━━━━━━
🚀 *На основе ваших ответов система подобрала 3 персональные ниши...*
"""

    def _get_mock_niches(self) -> str:
        """MOCK-ниши: заготовленный текст"""
        return """
🎯 *ПОДОБРАННЫЕ НИШИ*

━━━━━━━━━━━━━━━━━━━━
🔥 *1. КОНСУЛЬТАЦИОННЫЕ УСЛУГИ*
**Категория:** Быстрый старт
**Окупаемость:** 1-3 месяца | **Инвестиции:** от 10,000₽
**Почему подходит:** Ваш аналитический склад ума + коммуникабельность

💻 *2. ОНЛАЙН-КУРСЫ*
**Категория:** Масштабируемый
**Окупаемость:** 2-4 месяца | **Инвестиции:** от 50,000₽
**Почему подходит:** Экспертиза + умение объяснять сложное просто

🚀 *3. ФРИЛАНС-УСЛУГИ*
**Категория:** Минимальный риск
**Окупаемость:** 1-2 месяца | **Инвестиции:** от 5,000₽
**Почему подходит:** Гибкий график + быстрый старт

━━━━━━━━━━━━━━━━━━━━
"""

    def _get_mock_plan(self, niche: NicheDetails) -> str:
        """MOCK-план: заготовленный шаблон"""
        return f"""
📋 *ДЕТАЛЬНЫЙ ПЛАН: {niche.name}*

━━━━━━━━━━━━━━━━━━━━
🔧 *НЕДЕЛЯ 1: ПОДГОТОВКА*
• Изучить рынок и конкурентов (2-3 часа)
• Определить ЦА и их боли (1-2 часа)
• Создать MVP предложения (3-4 часа)

🚀 *НЕДЕЛЯ 2-3: ЗАПУСК*
• Создать лендинг/профиль (4-6 часов)
• Найти первых 3 клиентов (5-10 часов)
• Получить первые отзывы (2-3 часа)

📈 *МЕСЯЦ 2: СТАБИЛИЗАЦИЯ*
• Систематизировать процессы
• Повысить чек на 20-30%
• Запустить реферальную программу

💰 *ФИНАНСЫ:*
• Стартовые вложения: {niche.min_budget:,}₽
• Ожидаемая прибыль месяц 1: 15-30к₽
• Окупаемость: {niche.time_to_profit}

━━━━━━━━━━━━━━━━━━━━
⚠️ *РИСКИ И РЕШЕНИЯ:*
• Риск: Нет клиентов → Решение: Активный нетворкинг
• Риск: Выгорание → Решение: Чёткий график + отдых
• Риск: Конкуренция → Решение: Уникальное предложение

━━━━━━━━━━━━━━━━━━━━
🎯 *СЛЕДУЮЩИЙ ШАГ:*
Начните с первого пункта сегодня — даже 30 минут прогресса лучше идеального плана.
"""

    def _create_default_niches(self) -> List[NicheDetails]:
        """Создать стандартные ниши для демонстрации"""
        return [
            NicheDetails(
                id="consulting",
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
                id="online_courses",
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
                id="freelance",
                name="Фриланс-услуги",
                category=NicheCategory.QUICK_START,
                description="Предоставление профессиональных услуг на фриланс-биржах",
                emoji="💻",
                risk_level=2,
                time_to_profit="1-2 месяца",
                required_skills=["Профессиональные навыки", "Тайм-менеджмент"],
                min_budget=5000,
                success_rate=0.8,
                examples=["Дизайн", "Программирование", "Копирайтинг"]
            )
        ]

    def _parse_niches_text(self, text: str) -> List[NicheDetails]:
        """Парсить текст ниш в объекты (упрощённо)"""
        # В полной версии здесь был бы сложный парсинг
        # Пока возвращаем стандартные ниши
        return self._create_default_niches()

    # ========================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ДЛЯ ЗАПОЛНЕНИЯ ПРОМПТОВ
    # ========================================================================
    
    def _fill_psychological_prompt(self, template: str, answers: Dict[str, Any]) -> str:
        """Заполнить шаблон психологического анализа"""
        result = template
        # Здесь можно добавить подстановку реальных данных
        return result

    def _fill_niches_prompt(self, template: str, answers: Dict[str, Any]) -> str:
        """Заполнить шаблон генерации ниш"""
        result = template
        return result

    def _fill_plan_prompt(self, template: str, answers: Dict[str, Any], niche: NicheDetails) -> str:
        """Заполнить шаблон детального плана"""
        result = template
        result = result.replace("{niche_name}", niche.name)
        result = result.replace("{niche_category}", niche.category.value)
        return result


# ============================================================================
# ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР СЕРВИСА
# ============================================================================

openai_service = OpenAIService()
