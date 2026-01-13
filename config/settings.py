#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурационные настройки бота
"""

import os
import json  # ИЗМЕНЕНИЕ 1: Заменяем yaml на json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional

from models.enums import NicheCategory

@dataclass
class BotConfig:
    """Конфигурация бота"""
    
    # Токены и ключи
    telegram_token: str = field(default_factory=lambda: os.getenv('TELEGRAM_BOT_TOKEN', ''))
    openai_api_key: str = field(default_factory=lambda: os.getenv('OPENAI_API_KEY', ''))
    
    # Настройки сервера
    host: str = field(default_factory=lambda: os.getenv('HOST', '0.0.0.0'))
    port: int = field(default_factory=lambda: int(os.getenv('PORT', '10000')))
    
    # Настройки OpenAI
    openai_model: str = field(default_factory=lambda: os.getenv('OPENAI_MODEL', 'gpt-4-turbo-preview'))
    openai_temperature: float = field(default_factory=lambda: float(os.getenv('OPENAI_TEMPERATURE', '0.7')))
    openai_max_tokens: int = field(default_factory=lambda: int(os.getenv('OPENAI_MAX_TOKENS', '2000')))
    
    # Настройки бота
    bot_language: str = field(default_factory=lambda: os.getenv('BOT_LANGUAGE', 'ru'))
    cleanup_hours: int = field(default_factory=lambda: int(os.getenv('CLEANUP_HOURS', '24')))
    max_questions: int = field(default_factory=lambda: int(os.getenv('MAX_QUESTIONS', '18')))
    
    # Данные вопросов
    questions: List[Dict[str, Any]] = field(default_factory=list)
    question_categories: Dict[str, str] = field(default_factory=dict)
    niche_categories: List[NicheCategory] = field(default_factory=list)
    
    def __post_init__(self):
        """Загрузка вопросов после инициализации"""
        # Определяем путь к файлу с вопросами
        # ИЗМЕНЕНИЕ 2: Пытаемся найти JSON, если нет - YAML
        config_dir = Path(__file__).parent
        
        # Сначала ищем questions.json
        json_path = config_dir / 'questions.json'
        yaml_path = config_dir / 'questions.yaml'
        
        questions_path = None
        if json_path.exists():
            questions_path = json_path
            logger_method = "JSON"
        elif yaml_path.exists():
            questions_path = yaml_path
            logger_method = "YAML"
            # Если используем YAML, нужно импортировать библиотеку
            try:
                import yaml
            except ImportError:
                raise ImportError("Для работы с YAML файлами требуется библиотека PyYAML. "
                                "Установите её: pip install pyyaml")
        else:
            raise FileNotFoundError(
                f"Не найден файл с вопросами. Ожидался один из: "
                f"questions.json или questions.yaml в папке {config_dir}"
            )
        
        # Загружаем вопросы
        with open(questions_path, 'r', encoding='utf-8') as f:
            # ИЗМЕНЕНИЕ 3: Загружаем в зависимости от формата
            if questions_path.suffix == '.json':
                data = json.load(f)
            else:
                data = yaml.safe_load(f)
        
        # Извлекаем данные
        self.questions = data.get('questions', [])
        self.question_categories = data.get('categories', {})
        
        # Преобразуем категории ниш в enum
        niche_categories_data = data.get('niche_categories', [])
        self.niche_categories = []
        
        for category_data in niche_categories_data:
            try:
                category = NicheCategory(
                    id=category_data['id'],
                    name=category_data['name'],
                    description=category_data.get('description', ''),
                    emoji=category_data.get('emoji', '📊')
                )
                self.niche_categories.append(category)
            except (KeyError, ValueError) as e:
                print(f"⚠️ Ошибка загрузки категории: {e}")
        
        print(f"✅ Конфигурация загружена из {logger_method} файла")
        print(f"   📋 Вопросов: {len(self.questions)}")
        print(f"   📊 Категорий ниш: {len(self.niche_categories)}")
    
    def validate(self) -> bool:
        """Проверка корректности конфигурации"""
        if not self.telegram_token:
            print("❌ Ошибка: TELEGRAM_BOT_TOKEN не установлен")
            return False
        
        if len(self.questions) == 0:
            print("❌ Ошибка: Не загружены вопросы анкеты")
            return False
        
        return True
    
    def get_question_by_id(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Получить вопрос по ID"""
        for question in self.questions:
            if question.get('id') == question_id:
                return question
        return None
    
    def get_category_name(self, category_id: str) -> str:
        """Получить название категории по ID"""
        return self.question_categories.get(category_id, f"Категория {category_id}")
    
    def get_niche_category_by_id(self, category_id: str) -> Optional[NicheCategory]:
        """Получить категорию ниши по ID"""
        for category in self.niche_categories:
            if category.id == category_id:
                return category
        return None

# Создаем глобальный экземпляр конфигурации
config = BotConfig()