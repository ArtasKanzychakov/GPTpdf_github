"""
Сервис для работы с платежами (ЮКасса)
Заглушка для будущей интеграции
"""
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class PaymentService:
    """Сервис для работы с платежами"""
    
    def __init__(self):
        self.is_available = False
        logger.info("💳 Платежный сервис инициализирован (режим заглушки)")
    
    async def create_donation_link(self, user_id: int, amount: float) -> Optional[str]:
        """Создать ссылку для доната"""
        logger.info(f"Запрос доната: user_id={user_id}, amount={amount}")
        
        # В будущем здесь будет интеграция с ЮКассой
        # Пока возвращаем заглушку
        return None
    
    async def process_webhook(self, data: Dict) -> bool:
        """Обработать вебхук от платежной системы"""
        logger.info("Получен вебхук платежа (заглушка)")
        
        # В будущем здесь будет обработка платежей
        return False
    
    def is_payment_enabled(self) -> bool:
        """Проверить, включены ли платежи"""
        return self.is_available