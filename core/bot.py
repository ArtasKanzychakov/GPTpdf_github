#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Основной модуль бота Бизнес-Навигатор v7.0
Production Version — Webhook mode для Render.com
Автоматическая установка вебхука при запуске
"""
import asyncio
import logging
import os
from typing import Optional, Dict, Any
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

logger = logging.getLogger(__name__)


class BotStatus:
    """Статус работы бота"""
    
    def __init__(self):
        self.is_running: bool = False
        self.started_at: Optional[float] = None
        self.total_users: int = 0
        self.active_sessions: int = 0


class BusinessNavigatorBot:
    """
    Основной класс бота Бизнес-Навигатор
    
    Работает в webhook mode для деплоя на Render.com
    Обработка обновлений происходит через FastAPI endpoint /webhook
    """
    
    def __init__(self, config: Any):
        """
        Инициализация бота
        
        Args:
            config: Объект конфигурации BotConfig
        """
        self.config = config
        self.application: Optional[Application] = None
        self._status = BotStatus()
        self._webhook_url: Optional[str] = None
        
        self._initialize_application()
    
    def _initialize_application(self) -> None:
        """
        Инициализация Telegram Application
        
        Создает экземпляр Application с правильными настройками
        для webhook mode и регистрирует обработчики
        """
        try:
            logger.info("🤖 Инициализация Telegram Application...")
            
            self.application = (
                ApplicationBuilder()
                .token(self.config.telegram_token)
                .post_init(self._post_init)
                .post_shutdown(self._post_shutdown)
                .build()
            )
            
            self._setup_handlers()
            logger.info("✅ Telegram Application инициализирован")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Application: {e}", exc_info=True)
            raise
    
    def _setup_handlers(self) -> None:
        """
        Настройка всех обработчиков команд и сообщений
        
        Регистрирует:
        - Команды: /start, /help, /restart, /status, /questionnaire
        - Callback query handler для кнопок
        - Text message handler для текстовых ответов
        - Error handler для обработки исключений
        """
        if not self.application:
            logger.error("❌ Application не инициализирован")
            return
        
        logger.info("⚙️ Настройка обработчиков...")
        
        # Импорт обработчиков команд
        from handlers.commands import (
            start_command,
            help_command,
            restart_command,
            status_command,
            questionnaire_command,
        )
        
        # Регистрация команд
        self.application.add_handler(CommandHandler("start", start_command))
        self.application.add_handler(CommandHandler("help", help_command))
        self.application.add_handler(CommandHandler("restart", restart_command))
        self.application.add_handler(CommandHandler("status", status_command))
        self.application.add_handler(CommandHandler("questionnaire", questionnaire_command))
        
        # Импорт и регистрация обработчика анкеты
        from handlers.questionnaire import questionnaire_handler
        
        self.application.add_handler(
            CallbackQueryHandler(questionnaire_handler.handle_callback)
        )
        
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                questionnaire_handler.handle_text_input
            )
        )
        
        # Регистрация обработчика ошибок
        self.application.add_error_handler(self._error_handler)
        
        logger.info("✅ Обработчики настроены")
    
    async def _post_init(self, application: Application) -> None:
        """
        Post-init hook — вызывается после инициализации Application
        
        Автоматически устанавливает вебхук для Render.com
        Выполняется ВСЕГДА, включая DEMO режим
        """
        logger.info("🔄 Post-init выполнен")
        self._status.started_at = asyncio.get_event_loop().time()
        
        # Устанавливаем вебхук (основная логика)
        await self._setup_webhook()
    
    async def _setup_webhook(self) -> None:
        """
        Автоматическая настройка вебхука для Render.com
        
        Получает публичный URL из переменной окружения RENDER_EXTERNAL_URL
        и регистрирует его в Telegram Bot API.
        
        Особенности:
        - Retry logic при подтверждении установки
        - Корректное формирование URL без дублирующих слэшей
        - Логирование всех этапов для отладки
        """
        try:
            # Получаем базовый URL из переменной окружения Render
            webhook_base = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
            
            if not webhook_base:
                logger.warning("⚠️ RENDER_EXTERNAL_URL не задан — вебхук не установлен")
                logger.warning("💡 Добавьте переменную в Render Dashboard:")
                logger.warning("   RENDER_EXTERNAL_URL = https://ваш-сервис.onrender.com")
                return
            
            # Формируем полный URL вебхука
            self._webhook_url = f"{webhook_base}/webhook"
            logger.info(f"🔗 Webhook URL: {self._webhook_url}")
            
            # Удаляем старый вебхук (на всякий случай)
            try:
                await self.application.bot.delete_webhook(drop_pending_updates=True)
                await asyncio.sleep(0.3)  # Пауза для применения
                logger.info("✅ Старый вебхук удалён")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось удалить старый webhook: {e}")
            
            # Устанавливаем новый вебхук с явным списком обновлений
            allowed_updates = [
                "message",
                "edited_message",
                "callback_query",
                "channel_post",
                "edited_channel_post",
            ]
            
            await self.application.bot.set_webhook(
                url=self._webhook_url,
                allowed_updates=allowed_updates,
                drop_pending_updates=True,
            )
            
            logger.info(f"✅ set_webhook вызван: {self._webhook_url}")
            
            # Проверяем установку с retry logic
            for attempt in range(3):
                try:
                    info = await self.application.bot.get_webhook_info()
                    
                    if info.url == self._webhook_url:
                        logger.info("✅ Webhook подтверждён Telegram API")
                        logger.info(f"📬 Pending updates: {info.pending_update_count}")
                        
                        if info.last_error_message:
                            logger.warning(f"⚠️ Telegram сообщает: {info.last_error_message}")
                        
                        return
                    
                    logger.warning(
                        f"⚠️ Попытка {attempt + 1}/3: URL не совпадает. "
                        f"Ожидался: {self._webhook_url}, получен: {info.url}"
                    )
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Попытка {attempt + 1}/3 проверки failed: {e}")
                    await asyncio.sleep(1)
            
            # Если не удалось подтвердить после 3 попыток
            logger.error(f"❌ Webhook НЕ подтверждён после 3 попыток")
            logger.error(f"   Ожидался: {self._webhook_url}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка установки вебхука: {e}", exc_info=True)
            # Не выбрасываем исключение — бот может работать и без вебхука для отладки
    
    async def _post_shutdown(self, application: Application) -> None:
        """
        Post-shutdown hook — вызывается при остановке приложения
        
        Важно: НЕ удаляем вебхук при shutdown, так как Render может
        перезапустить сервис (hot-restart), и вебхук должен сохраниться.
        """
        logger.info("🔄 Post-shutdown выполнен")
        self._status.is_running = False
        
        # Не удаляем webhook — сохраняем для следующего запуска на Render
        logger.info("ℹ️ Webhook сохранён для следующего запуска (Render hot-restart)")
    
    async def _error_handler(self, update: object, context: Any) -> None:
        """
        Обработчик ошибок Telegram Bot API
        
        Логирует ошибку и отправляет пользователю понятное сообщение
        
        Args:
            update: Объект обновления (может быть None)
            context: Контекст обработки с информацией об ошибке
        """
        logger.error(f"❌ Ошибка при обработке обновления: {context.error}", exc_info=True)
        
        try:
            # Пытаемся отправить сообщение пользователю
            if update and hasattr(update, "effective_chat"):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⚠️ Произошла техническая ошибка. Пожалуйста, попробуйте позже или используйте команду /start",
                )
        except Exception as e:
            logger.error(f"❌ Не удалось отправить сообщение об ошибке: {e}")
    
    async def start(self) -> None:
        """
        Запуск бота в webhook mode
        
        Инициализирует Application и подготавливает его к обработке
        обновлений через webhook endpoint. НЕ запускает polling.
        
        Обработка входящих обновлений происходит через:
        POST /webhook в FastAPI → bot.process_update()
        """
        if self._status.is_running:
            logger.warning("⚠️ Бот уже запущен")
            return
        
        try:
            logger.info("▶️ Запуск бота (webhook mode)...")
            
            if not self.application:
                logger.error("❌ Application не инициализирован")
                return
            
            # Инициализируем приложение (подключение к Telegram API)
            await self.application.initialize()
            
            # Запускаем приложение (готовность к обработке обновлений)
            # В webhook mode polling не запускается — обновления приходят через /webhook
            await self.application.start()
            
            self._status.is_running = True
            
            logger.info("✅ Бот запущен (webhook mode)")
            logger.info(f"📡 Ожидает обновления на: {self._webhook_url or 'не установлен'}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при запуске: {e}", exc_info=True)
            self._status.is_running = False
            raise
    
    async def stop(self) -> None:
        """
        Остановка бота
        
        Корректно завершает работу Application и освобождает ресурсы.
        Вызывается при graceful shutdown (SIGTERM/SIGINT).
        """
        if not self._status.is_running:
            logger.warning("⚠️ Бот уже остановлен")
            return
        
        try:
            logger.info("⏹️ Остановка бота...")
            self._status.is_running = False
            
            if self.application:
                # Останавливаем приложение
                await self.application.stop()
                # Завершаем сессию и освобождаем ресурсы
                await self.application.shutdown()
            
            logger.info("✅ Бот остановлен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке: {e}", exc_info=True)
            raise
    
    async def process_update(self, update_dict: Dict[str, Any]) -> bool:
        """
        Обработка входящего обновления от вебхука
        
        Вызывается из FastAPI endpoint POST /webhook при получении
        обновления от Telegram Bot API.
        
        Args:
            update_dict: Словарь с JSON-данными обновления от Telegram
            
        Returns:
            True если обновление обработано успешно, False иначе
        """
        if not self.application or not self._status.is_running:
            logger.warning("⚠️ process_update: бот не готов к обработке")
            return False
        
        try:
            from telegram import Update
            
            # Десериализуем обновление из JSON в объект Update
            update = Update.de_json(update_dict, self.application.bot)
            
            if not update:
                logger.warning("⚠️ Не удалось десериализовать обновление")
                return False
            
            # Передаём обновление в Application для обработки
            # Application сам определит тип и вызовет нужный обработчик
            await self.application.process_update(update)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки обновления: {e}", exc_info=True)
            return False
    
    @property
    def is_running(self) -> bool:
        """
        Статус работы бота (только для чтения)
        
        Returns:
            True если бот запущен и готов обрабатывать обновления
        """
        return self._status.is_running
    
    @property
    def webhook_url(self) -> Optional[str]:
        """
        URL установленного вебхука (только для чтения)
        
        Returns:
            URL вебхука или None если не установлен
        """
        return self._webhook_url
    
    def get_status(self) -> Dict[str, Any]:
        """
        Получить подробный статус бота
        
        Returns:
            Словарь с информацией о состоянии бота
        """
        return {
            "is_running": self._status.is_running,
            "started_at": self._status.started_at,
            "webhook_url": self._webhook_url,
            "config": {
                "bot_language": getattr(self.config, "bot_language", "ru"),
                "demo_mode": getattr(self.config, "demo_mode", True),
                "questions_count": len(getattr(self.config, "questions", [])),
            }
        }
