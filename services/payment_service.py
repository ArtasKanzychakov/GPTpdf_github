#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервис для работы с платежами и донатами
Готовая структура для интеграции с ЮКасса/Stripe/Telegram Stars
"""
import logging
import os
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class PaymentProvider(Enum):
    """Провайдеры платежей"""
    YOOKASSA = "yookassa"  # ЮКасса (Яндекс)
    STRIPE = "stripe"  # Stripe
    TELEGRAM_STARS = "telegram_stars"  # Telegram Stars (встроенные донаты)


class DonationTier(Enum):
    """Уровни донатов"""
    COFFEE = ("coffee", 100, "☕ Кофе автору", "Поддержите разработку!")
    LUNCH = ("lunch", 300, "🍕 Обед автору", "Спасибо за поддержку!")
    PREMIUM = ("premium", 500, "⭐ Премиум поддержка", "Вы - легенда!")
    CUSTOM = ("custom", 0, "💎 Своя сумма", "Укажите свою сумму")
    
    def __init__(self, tier_id: str, amount: int, title: str, description: str):
        self.tier_id = tier_id
        self.amount = amount
        self.title = title
        self.description = description


class PaymentService:
    """Сервис для работы с платежами"""
    
    def __init__(self):
        """
        Инициализация платежного сервиса
        
        Переменные окружения:
        - PAYMENT_ENABLED: True/False - включить платежи
        - PAYMENT_PROVIDER: yookassa/stripe/telegram_stars
        - YOOKASSA_SHOP_ID: ID магазина ЮКассы
        - YOOKASSA_SECRET_KEY: Секретный ключ ЮКассы
        - STRIPE_SECRET_KEY: Секретный ключ Stripe
        - STRIPE_WEBHOOK_SECRET: Секрет для webhook Stripe
        """
        self.is_available = os.getenv("PAYMENT_ENABLED", "false").lower() == "true"
        self.provider = self._get_provider()
        
        # Инициализация в зависимости от провайдера
        if self.is_available:
            self._initialize_provider()
        else:
            logger.info("💳 Платежный сервис в режиме заглушки")
    
    def _get_provider(self) -> Optional[PaymentProvider]:
        """Определить провайдера платежей"""
        provider_str = os.getenv("PAYMENT_PROVIDER", "").lower()
        
        provider_map = {
            "yookassa": PaymentProvider.YOOKASSA,
            "stripe": PaymentProvider.STRIPE,
            "telegram_stars": PaymentProvider.TELEGRAM_STARS
        }
        
        return provider_map.get(provider_str)
    
    def _initialize_provider(self):
        """Инициализация провайдера платежей"""
        if not self.provider:
            logger.warning("⚠️ Провайдер платежей не указан")
            self.is_available = False
            return
        
        try:
            if self.provider == PaymentProvider.YOOKASSA:
                self._init_yookassa()
            elif self.provider == PaymentProvider.STRIPE:
                self._init_stripe()
            elif self.provider == PaymentProvider.TELEGRAM_STARS:
                self._init_telegram_stars()
            
            logger.info(f"✅ Платежный провайдер {self.provider.value} инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации платежей: {e}")
            self.is_available = False
    
    def _init_yookassa(self):
        """Инициализация ЮКассы"""
        # TODO: Раскомментировать при подключении
        # from yookassa import Configuration, Payment
        # Configuration.account_id = os.getenv("YOOKASSA_SHOP_ID")
        # Configuration.secret_key = os.getenv("YOOKASSA_SECRET_KEY")
        pass
    
    def _init_stripe(self):
        """Инициализация Stripe"""
        # TODO: Раскомментировать при подключении
        # import stripe
        # stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        pass
    
    def _init_telegram_stars(self):
        """Инициализация Telegram Stars"""
        # Telegram Stars работают напрямую через Bot API
        # Дополнительной инициализации не требуется
        pass
    
    # ============================================
    # ПУБЛИЧНЫЕ МЕТОДЫ
    # ============================================
    
    async def create_donation_link(
        self, 
        user_id: int, 
        tier: DonationTier = DonationTier.COFFEE,
        custom_amount: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Создать ссылку для доната
        
        Args:
            user_id: ID пользователя Telegram
            tier: Уровень доната
            custom_amount: Своя сумма (для CUSTOM tier)
        
        Returns:
            Dict с данными платежа:
            {
                "payment_url": "https://...",
                "payment_id": "...",
                "amount": 100,
                "currency": "RUB"
            }
        """
        if not self.is_available:
            logger.info(f"Запрос доната (заглушка): user={user_id}, tier={tier.name}")
            return None
        
        amount = custom_amount if tier == DonationTier.CUSTOM else tier.amount
        
        try:
            if self.provider == PaymentProvider.YOOKASSA:
                return await self._create_yookassa_payment(user_id, amount, tier)
            elif self.provider == PaymentProvider.STRIPE:
                return await self._create_stripe_payment(user_id, amount, tier)
            elif self.provider == PaymentProvider.TELEGRAM_STARS:
                return await self._create_telegram_stars_payment(user_id, amount, tier)
        except Exception as e:
            logger.error(f"❌ Ошибка создания платежа: {e}")
            return None
    
    async def _create_yookassa_payment(
        self, 
        user_id: int, 
        amount: int, 
        tier: DonationTier
    ) -> Optional[Dict[str, Any]]:
        """Создать платеж через ЮКассу"""
        # TODO: Реализовать при подключении
        # from yookassa import Payment
        # 
        # payment = Payment.create({
        #     "amount": {
        #         "value": str(amount),
        #         "currency": "RUB"
        #     },
        #     "confirmation": {
        #         "type": "redirect",
        #         "return_url": "https://your-bot-url.com/payment-success"
        #     },
        #     "description": tier.title,
        #     "metadata": {
        #         "user_id": user_id,
        #         "tier": tier.tier_id
        #     }
        # })
        # 
        # return {
        #     "payment_url": payment.confirmation.confirmation_url,
        #     "payment_id": payment.id,
        #     "amount": amount,
        #     "currency": "RUB"
        # }
        
        logger.info(f"Создание платежа ЮКасса: user={user_id}, amount={amount}")
        return None
    
    async def _create_stripe_payment(
        self, 
        user_id: int, 
        amount: int, 
        tier: DonationTier
    ) -> Optional[Dict[str, Any]]:
        """Создать платеж через Stripe"""
        # TODO: Реализовать при подключении
        # import stripe
        # 
        # checkout_session = stripe.checkout.Session.create(
        #     payment_method_types=['card'],
        #     line_items=[{
        #         'price_data': {
        #             'currency': 'usd',
        #             'unit_amount': amount * 100,  # в центах
        #             'product_data': {
        #                 'name': tier.title,
        #                 'description': tier.description
        #             },
        #         },
        #         'quantity': 1,
        #     }],
        #     mode='payment',
        #     success_url='https://your-bot-url.com/success',
        #     cancel_url='https://your-bot-url.com/cancel',
        #     metadata={
        #         'user_id': user_id,
        #         'tier': tier.tier_id
        #     }
        # )
        # 
        # return {
        #     "payment_url": checkout_session.url,
        #     "payment_id": checkout_session.id,
        #     "amount": amount,
        #     "currency": "USD"
        # }
        
        logger.info(f"Создание платежа Stripe: user={user_id}, amount={amount}")
        return None
    
    async def _create_telegram_stars_payment(
        self, 
        user_id: int, 
        amount: int, 
        tier: DonationTier
    ) -> Optional[Dict[str, Any]]:
        """Создать платеж через Telegram Stars"""
        # TODO: Реализовать при подключении
        # Telegram Stars используют метод createInvoiceLink
        # https://core.telegram.org/bots/api#createinvoicelink
        
        logger.info(f"Создание платежа Telegram Stars: user={user_id}, amount={amount}")
        return None
    
    async def process_webhook(self, data: Dict[str, Any]) -> bool:
        """
        Обработать вебхук от платежной системы
        
        Args:
            data: Данные от платежной системы
        
        Returns:
            True если платеж успешно обработан
        """
        if not self.is_available:
            logger.info("Получен вебхук платежа (заглушка)")
            return False
        
        try:
            if self.provider == PaymentProvider.YOOKASSA:
                return await self._process_yookassa_webhook(data)
            elif self.provider == PaymentProvider.STRIPE:
                return await self._process_stripe_webhook(data)
            elif self.provider == PaymentProvider.TELEGRAM_STARS:
                return await self._process_telegram_webhook(data)
        except Exception as e:
            logger.error(f"❌ Ошибка обработки вебхука: {e}")
            return False
    
    async def _process_yookassa_webhook(self, data: Dict) -> bool:
        """Обработать вебхук ЮКассы"""
        # TODO: Реализовать
        # 1. Проверить подпись
        # 2. Извлечь payment_id
        # 3. Проверить статус платежа
        # 4. Обновить данные пользователя
        # 5. Отправить благодарность
        return False
    
    async def _process_stripe_webhook(self, data: Dict) -> bool:
        """Обработать вебхук Stripe"""
        # TODO: Реализовать
        return False
    
    async def _process_telegram_webhook(self, data: Dict) -> bool:
        """Обработать вебхук Telegram"""
        # TODO: Реализовать
        return False
    
    def get_donation_tiers(self) -> list[DonationTier]:
        """Получить доступные уровни донатов"""
        return list(DonationTier)
    
    def is_payment_enabled(self) -> bool:
        """Проверить, включены ли платежи"""
        return self.is_available
    
    def get_provider_name(self) -> str:
        """Получить название провайдера"""
        if self.provider:
            return self.provider.value
        return "не настроен"


# ============================================
# УТИЛИТЫ ДЛЯ ФОРМАТИРОВАНИЯ ДОНАТОВ
# ============================================

def format_donation_message(tier: DonationTier, custom_amount: Optional[int] = None) -> str:
    """
    Форматировать сообщение с информацией о донате
    
    Args:
        tier: Уровень доната
        custom_amount: Своя сумма (для CUSTOM)
    
    Returns:
        Отформатированное сообщение
    """
    amount = custom_amount if tier == DonationTier.CUSTOM else tier.amount
    
    return f"""
{tier.title}

💰 Сумма: {amount} ₽
📝 {tier.description}

Нажмите на кнопку ниже, чтобы поддержать проект!
"""


def format_thank_you_message(tier: DonationTier, amount: int) -> str:
    """
    Форматировать сообщение благодарности
    
    Args:
        tier: Уровень доната
        amount: Сумма
    
    Returns:
        Сообщение благодарности
    """
    messages = {
        DonationTier.COFFEE: "☕ Спасибо за кофе! Это очень мотивирует продолжать развивать бота!",
        DonationTier.LUNCH: "🍕 Огромное спасибо! Ваша поддержка помогает делать бота лучше!",
        DonationTier.PREMIUM: "⭐ ВАУ! Вы невероятны! Благодаря таким людям как вы проект живет!",
        DonationTier.CUSTOM: f"💎 Спасибо за щедрую поддержку в размере {amount} ₽! Вы - лучшие!"
    }
    
    base_message = messages.get(tier, "❤️ Спасибо за поддержку!")
    
    return f"""
🎉 ПЛАТЕЖ УСПЕШНО ОБРАБОТАН!

{base_message}

Ваш вклад помогает:
• Развивать и улучшать функциональность бота
• Добавлять новые возможности
• Поддерживать стабильную работу сервиса

С благодарностью,
Команда Бизнес-Навигатор ❤️
"""