#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурационные настройки бота
"""

import os
import json
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
        config_dir = Path(__file__).parent
        
        # Сначала ищем questions.json
        json_path = config_dir / 'questions.json'
        yaml_path = config_dir / 'questions.yaml'
        
        questions_path = None
        file_format = ""
        
        if json_path.exists():
            questions_path = json_path
            file_format = "JSON"
        elif yaml_path.exists():
            questions_path = yaml_path
            file_format = "YAML"
            # Если используем YAML, нужно импортировать библиотеку
            try:
                import yaml
            except ImportError:
                print("❌ Для работы с YAML файлами требуется библиотека PyYAML.")
                print("   Установите её: pip install pyyaml")
                print("   Или создайте файл questions.json")
                raise ImportError("PyYAML не установлен. Нужен либо pyyaml, либо questions.json файл.")
        else:
            error_msg = (
                f"❌ Не найден файл с вопросами.\n"
                f"   Ожидался один из:\n"
                f"   - {json_path}\n"
                f"   - {yaml_path}\n"
                f"   Убедитесь, что файл существует в папке {config_dir}"
            )
            print(error_msg)
            raise FileNotFoundError(f"Файл с вопросами не найден в {config_dir}")
        
        # Загружаем вопросы
        try:
            with open(questions_path, 'r', encoding='utf-8') as f:
                if file_format == "JSON":
                    data = json.load(f)
                else:  # YAML
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
                    print(f"   Данные категории: {category_data}")
            
            print(f"✅ Конфигурация загружена из {file_format} файла")
            print(f"   📋 Вопросов: {len(self.questions)}")
            print(f"   📊 Категорий ниш: {len(self.niche_categories)}")
            
            # ДЕБАГ: выводим информацию о вопросах
            if len(self.questions) > 0:
                print(f"\n📝 Первые {min(3, len(self.questions))} вопроса:")
                for i, question in enumerate(self.questions[:3]):
                    q_id = question.get('id', 'нет id')
                    q_text = question.get('text', 'нет текста')[:50]
                    q_type = question.get('type', 'неизвестно')
                    print(f"   {i+1}. [{q_id}] {q_text}... (тип: {q_type})")
            else:
                print("⚠️ Вопросы не загружены или список пуст!")
                
            # ДЕБАГ: выводим информацию о категориях ниш
            if len(self.niche_categories) > 0:
                print(f"\n🏢 Категории ниш ({len(self.niche_categories)}):")
                for i, category in enumerate(self.niche_categories[:5]):
                    print(f"   {i+1}. {category.emoji} {category.name} ({category.id})")
                if len(self.niche_categories) > 5:
                    print(f"   ... и ещё {len(self.niche_categories) - 5}")
            else:
                print("⚠️ Категории ниш не загружены!")
                
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            print(f"   Проверьте синтаксис файла {questions_path}")
            self.questions = []
            self.niche_categories = []
        except yaml.YAMLError as e:
            print(f"❌ Ошибка парсинга YAML: {e}")
            print(f"   Проверьте синтаксис файла {questions_path}")
            self.questions = []
            self.niche_categories = []
        except Exception as e:
            print(f"❌ Неожиданная ошибка при загрузке конфигурации: {e}")
            import traceback
            traceback.print_exc()
            self.questions = []
            self.niche_categories = []
    
    def validate(self) -> bool:
        """Проверка корректности конфигурации"""
        errors = []
        
        if not self.telegram_token:
            errors.append("TELEGRAM_BOT_TOKEN не установлен")
        
        if len(self.questions) == 0:
            errors.append("Не загружены вопросы анкеты")
        elif len(self.questions) < self.max_questions:
            errors.append(f"Загружено только {len(self.questions)} вопросов из {self.max_questions}")
        
        if errors:
            print("❌ Ошибки конфигурации:")
            for error in errors:
                print(f"   - {error}")
            return False
        
        print("✅ Конфигурация прошла проверку")
        return True
    
    def get_question_by_id(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Получить вопрос по ID"""
        for question in self.questions:
            if question.get('id') == question_id:
                return question
        print(f"⚠️ Вопрос с ID '{question_id}' не найден")
        return None
    
    def get_category_name(self, category_id: str) -> str:
        """Получить название категории по ID"""
        return self.question_categories.get(category_id, f"Категория {category_id}")
    
    def get_niche_category_by_id(self, category_id: str) -> Optional[NicheCategory]:
        """Получить категорию ниши по ID"""
        for category in self.niche_categories:
            if category.id == category_id:
                return category
        print(f"⚠️ Категория ниши с ID '{category_id}' не найдена")
        return None
    
    def get_question_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """Получить вопрос по индексу"""
        if 0 <= index < len(self.questions):
            return self.questions[index]
        return None
    
    def get_total_questions(self) -> int:
        """Получить общее количество вопросов"""
        return len(self.questions)

# Создаем глобальный экземпляр конфигурации
# Этот импорт должен быть в конце, чтобы избежать циклических зависимостей
# Если нужно использовать config в других модулях, импортируйте его так:
# from config.settings import config
print("🔄 Инициализация конфигурации бота...")
config = BotConfig()