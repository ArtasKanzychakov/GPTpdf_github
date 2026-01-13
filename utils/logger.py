"""
Настройка логирования
"""
import logging
import sys
from pathlib import Path
from datetime import datetime

def setup_logging():
    """Настройка логирования"""
    # Создаем директорию для логов
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Файловый обработчик
    file_handler = logging.FileHandler(
        log_dir / f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Удаляем существующие обработчики
    root_logger.handlers.clear()
    
    # Добавляем новые обработчики
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Логгер для telegram
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    
    logging.info("✅ Логирование настроено")