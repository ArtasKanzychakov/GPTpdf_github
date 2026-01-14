#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Настройка логирования
"""

import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

class BotLogger:
    """Класс для настройки логирования бота"""
    
    def __init__(self, log_dir: str = "logs", log_level: int = logging.INFO):
        self.log_dir = Path(log_dir)
        self.log_level = log_level
        self._setup_done = False
    
    def setup(self, bot_name: str = "business_bot"):
        """Настройка логирования"""
        if self._setup_done:
            return
        
        # Создаем директорию для логов
        self.log_dir.mkdir(exist_ok=True)
        
        # Создаем имя файла лога
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = self.log_dir / f"{bot_name}_{timestamp}.log"
        
        # Форматтер
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Файловый обработчик
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(self.log_level)
        
        # Консольный обработчик
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(self.log_level)
        
        # Настраиваем корневой логгер
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # Очищаем существующие обработчики
        root_logger.handlers.clear()
        
        # Добавляем новые обработчики
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # Устанавливаем уровень логирования для сторонних библиотек
        logging.getLogger('telegram').setLevel(logging.WARNING)
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('openai').setLevel(logging.WARNING)
        logging.getLogger('asyncio').setLevel(logging.WARNING)
        
        self._setup_done = True
        
        # Записываем информацию о запуске
        logging.info("=" * 60)
        logging.info(f"🚀 Бот запущен: {bot_name}")
        logging.info(f"📁 Логи сохраняются в: {log_file}")
        logging.info(f"📊 Уровень логирования: {logging.getLevelName(self.log_level)}")
        logging.info("=" * 60)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Получить логгер с указанным именем"""
        return logging.getLogger(name)
    
    def log_startup_info(self, config_info: dict):
        """Записать информацию о конфигурации при запуске"""
        logger = self.get_logger(__name__)
        logger.info("📋 КОНФИГУРАЦИЯ БОТА:")
        for key, value in config_info.items():
            if key.lower().endswith('key') or key.lower().endswith('token'):
                logger.info(f"  {key}: {'***' + str(value)[-4:] if value else 'НЕ УСТАНОВЛЕН'}")
            else:
                logger.info(f"  {key}: {value}")
        logger.info("=" * 60)
    
    def log_session_event(self, user_id: int, event: str, details: str = ""):
        """Записать событие сессии"""
        logger = self.get_logger("session")
        message = f"👤 User {user_id}: {event}"
        if details:
            message += f" - {details}"
        logger.info(message)
    
    def log_question_event(self, user_id: int, question_id: str, answer: str = ""):
        """Записать событие вопроса"""
        logger = self.get_logger("questionnaire")
        # Маскируем длинные ответы
        if answer and len(answer) > 100:
            answer = answer[:100] + "..."
        logger.info(f"❓ User {user_id}: Q{question_id} - A: {answer}")
    
    def log_openai_event(self, model: str, tokens: int, duration: float):
        """Записать событие OpenAI"""
        logger = self.get_logger("openai")
        logger.info(f"🤖 OpenAI: {model} - {tokens} токенов за {duration:.2f}с")
    
    def log_error(self, error_type: str, error_message: str, user_id: Optional[int] = None):
        """Записать ошибку"""
        logger = self.get_logger("error")
        if user_id:
            logger.error(f"💥 User {user_id}: {error_type} - {error_message}")
        else:
            logger.error(f"💥 {error_type} - {error_message}")

# Глобальный экземпляр логгера
bot_logger = BotLogger()

def setup_logging(log_level: int = logging.INFO, bot_name: str = "business_navigator"):
    """Функция для быстрой настройки логирования"""
    bot_logger.log_level = log_level
    bot_logger.setup(bot_name)
    return bot_logger

def get_logger(name: str) -> logging.Logger:
    """Быстрое получение логгера"""
    return bot_logger.get_logger(name)

# Быстрые функции для общего использования
def log_info(message: str, logger_name: str = "main"):
    """Записать информационное сообщение"""
    get_logger(logger_name).info(message)

def log_warning(message: str, logger_name: str = "main"):
    """Записать предупреждение"""
    get_logger(logger_name).warning(message)

def log_error(message: str, logger_name: str = "main"):
    """Записать ошибку"""
    get_logger(logger_name).error(message)

def log_debug(message: str, logger_name: str = "main"):
    """Записать отладочное сообщение"""
    get_logger(logger_name).debug(message)