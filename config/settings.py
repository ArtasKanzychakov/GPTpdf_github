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

# Импортируем из enums
from models.enums import NicheCategory, NicheDetails

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
    max_questions: int = field(default_factory=lambda: int(os.getenv('MAX_QUESTIONS', '35')))  # Увеличиваем для YAML

    # Данные вопросов
    questions: List[Dict[str, Any]] = field(default_factory=list)
    question_categories: Dict[str, str] = field(default_factory=dict)
    niche_categories: List[NicheDetails] = field(default_factory=list)

    def __post_init__(self):
        """Загрузка вопросов после инициализации"""
        config_dir = Path(__file__).parent

        print("🔄 Загрузка конфигурации бота...")
        
        # Определяем пути к файлам
        json_path = config_dir / 'questions.json'
        yaml_path = config_dir / 'questions.yaml'
        
        # Проверяем существование файлов
        json_exists = json_path.exists()
        yaml_exists = yaml_path.exists()
        
        print(f"📄 questions.json существует: {json_exists}")
        print(f"📄 questions.yaml существует: {yaml_exists}")

        # Сначала пробуем YAML (приоритет)
        if yaml_exists:
            try:
                # Пробуем импортировать yaml
                yaml_available = self._try_import_yaml()
                
                if yaml_available:
                    with open(yaml_path, 'r', encoding='utf-8') as f:
                        import yaml
                        data = yaml.safe_load(f)
                    
                    self.questions = data.get('questions', [])
                    print(f"✅ Загружено {len(self.questions)} вопросов из YAML")
                    
                    # Для YAML создаем стандартные ниши (в YAML их нет в вашем файле)
                    self._create_default_niches()
                    
                    # Проверяем структуру вопросов
                    self._validate_questions_structure()
                    
                    return  # Успешно загрузили YAML
                else:
                    print("⚠️ PyYAML не установлен, переключаюсь на JSON...")
                    
            except Exception as e:
                print(f"❌ Ошибка загрузки YAML: {e}")
                print("⚠️ Переключаюсь на JSON...")

        # Пробуем JSON (резервный вариант)
        if json_exists:
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.questions = data.get('questions', [])
                self.question_categories = data.get('categories', {})
                
                # Загружаем ниши из JSON
                niche_categories_data = data.get('niche_categories', [])
                self._load_niche_categories(niche_categories_data)
                
                print(f"✅ Загружено {len(self.questions)} вопросов из JSON")
                print(f"✅ Загружено {len(self.niche_categories)} категорий ниш")
                
                # Проверяем структуру
                self._validate_questions_structure()
                
            except json.JSONDecodeError as e:
                print(f"❌ Ошибка парсинга JSON: {e}")
                print("⚠️ Создаю минимальный набор вопросов...")
                self._create_minimal_questions()
                self._create_default_niches()
            except Exception as e:
                print(f"❌ Неожиданная ошибка при загрузке JSON: {e}")
                print("⚠️ Создаю минимальный набор вопросов...")
                self._create_minimal_questions()
                self._create_default_niches()
        else:
            # Если нет ни одного файла
            print("⚠️ Нет файлов с вопросами, создаю минимальный набор...")
            self._create_minimal_questions()
            self._create_default_niches()
    
    def _try_import_yaml(self) -> bool:
        """Попробовать импортировать yaml"""
        try:
            import yaml
            return True
        except ImportError:
            return False
    
    def _create_minimal_questions(self):
        """Создать минимальный набор вопросов для теста"""
        print("📝 Создаю минимальный набор вопросов...")
        self.questions = [
            {
                "id": "test_1",
                "text": "👋 Привет! Как тебя зовут?",
                "type": "text",
                "category": "start"
            },
            {
                "id": "test_2",
                "text": "📊 Сколько тебе лет?",
                "type": "text", 
                "category": "demography"
            },
            {
                "id": "test_3",
                "text": "🎯 Что тебя мотивирует?",
                "type": "text",
                "category": "personality"
            }
        ]
        self.question_categories = {
            "start": "Старт",
            "demography": "Демография",
            "personality": "Личность"
        }
    
    def _create_default_niches(self):
        """Создать стандартные категории ниш"""
        print("🏢 Создаю стандартные категории ниш...")
        
        category_map = {
            "QUICK_START": NicheCategory.QUICK_START,
            "BALANCED": NicheCategory.BALANCED,
            "LONG_TERM": NicheCategory.LONG_TERM,
            "RISKY": NicheCategory.RISKY,
            "HIDDEN": NicheCategory.HIDDEN
        }
        
        default_niches = [
            {
                "id": "QUICK_START",
                "name": "Быстрый старт",
                "category": "QUICK_START",
                "description": "Проекты с быстрой окупаемостью",
                "emoji": "🔥",
                "risk_level": 4,
                "time_to_profit": "1-3 месяца",
                "required_skills": ["Маркетинг", "Коммуникация"],
                "min_budget": 50000,
                "success_rate": 0.6,
                "examples": ["Дропшиппинг", "Консультации"]
            },
            {
                "id": "BALANCED",
                "name": "Сбалансированный",
                "category": "BALANCED",
                "description": "Оптимальное соотношение риска и доходности",
                "emoji": "🚀",
                "risk_level": 3,
                "time_to_profit": "3-6 месяцев",
                "required_skills": ["Планирование", "Управление"],
                "min_budget": 150000,
                "success_rate": 0.7,
                "examples": ["Интернет-магазин", "SMM-агентство"]
            }
        ]
        
        self.niche_categories = []
        for niche_data in default_niches:
            try:
                niche_enum = category_map.get(niche_data['category'])
                if not niche_enum:
                    continue
                    
                niche = NicheDetails(
                    id=niche_data['id'],
                    name=niche_data['name'],
                    category=niche_enum,
                    description=niche_data['description'],
                    emoji=niche_data['emoji'],
                    risk_level=niche_data['risk_level'],
                    time_to_profit=niche_data['time_to_profit'],
                    required_skills=niche_data['required_skills'],
                    min_budget=niche_data['min_budget'],
                    success_rate=niche_data['success_rate'],
                    examples=niche_data['examples']
                )
                self.niche_categories.append(niche)
                
            except Exception as e:
                print(f"⚠️ Ошибка создания ниши {niche_data.get('id')}: {e}")
        
        print(f"✅ Создано {len(self.niche_categories)} стандартных ниш")
    
    def _load_niche_categories(self, niche_categories_data):
        """Загрузить категории ниш из данных"""
        self.niche_categories = []
        
        if not niche_categories_data:
            self._create_default_niches()
            return
        
        for category_data in niche_categories_data:
            try:
                category_id = category_data.get('category', '')
                if not category_id:
                    continue
                
                # Ищем соответствующий Enum
                niche_enum = None
                for enum_item in NicheCategory:
                    if enum_item.name == category_id:
                        niche_enum = enum_item
                        break
                
                if not niche_enum:
                    print(f"⚠️ Категория '{category_id}' не найдена в NicheCategory Enum")
                    continue

                # Создаем объект NicheDetails
                niche = NicheDetails(
                    id=category_data.get('id', category_id),
                    name=category_data.get('name', category_id),
                    category=niche_enum,
                    description=category_data.get('description', ''),
                    emoji=category_data.get('emoji', '📊'),
                    risk_level=category_data.get('risk_level', 3),
                    time_to_profit=category_data.get('time_to_profit', ''),
                    required_skills=category_data.get('required_skills', []),
                    min_budget=category_data.get('min_budget', 0),
                    success_rate=category_data.get('success_rate', 0.5),
                    examples=category_data.get('examples', [])
                )

                self.niche_categories.append(niche)

            except Exception as e:
                print(f"⚠️ Ошибка загрузки категории: {e}")
    
    def _validate_questions_structure(self):
        """Проверить структуру вопросов"""
        if not self.questions:
            print("⚠️ Список вопросов пуст!")
            return
        
        print(f"📊 Проверяю структуру {len(self.questions)} вопросов...")
        
        # Проверяем первые 3 вопроса
        for i, question in enumerate(self.questions[:3]):
            q_id = question.get('id', 'нет id')
            q_type = question.get('type', 'неизвестно')
            has_text = 'text' in question
            
            status = "✅" if has_text and q_id else "⚠️"
            print(f"   {status} Вопрос {i+1}: ID={q_id}, Тип={q_type}, Текст={'есть' if has_text else 'нет'}")
        
        # Считаем типы вопросов
        type_counts = {}
        for q in self.questions:
            q_type = q.get('type', 'unknown')
            type_counts[q_type] = type_counts.get(q_type, 0) + 1
        
        if type_counts:
            print("📈 Распределение типов вопросов:")
            for q_type, count in type_counts.items():
                print(f"   • {q_type}: {count}")
    
    def validate(self) -> bool:
        """Проверка корректности конфигурации"""
        errors = []

        if not self.telegram_token:
            errors.append("❌ TELEGRAM_BOT_TOKEN не установен")
            print("⚠️ ВНИМАНИЕ: Бот не сможет работать без TELEGRAM_BOT_TOKEN!")

        if len(self.questions) == 0:
            errors.append("❌ Не загружены вопросы анкеты")
        elif len(self.questions) < 3:
            errors.append(f"❌ Слишком мало вопросов: {len(self.questions)}")
        elif len(self.questions) < self.max_questions:
            print(f"⚠️ Загружено {len(self.questions)} вопросов из {self.max_questions}")

        if errors:
            print("❌ Ошибки конфигурации:")
            for error in errors:
                print(f"   {error}")
            
            # Не блокируем запуск, но предупреждаем
            print("⚠️ Бот запустится, но некоторые функции могут не работать")
            return False

        print("✅ Конфигурация прошла проверку")
        print(f"   📝 Вопросов: {len(self.questions)}")
        print(f"   🏢 Ниш: {len(self.niche_categories)}")
        print(f"   🤖 OpenAI модель: {self.openai_model}")
        print(f"   🌐 Язык: {self.bot_language}")
        
        return True

    def get_question_by_id(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Получить вопрос по ID"""
        for question in self.questions:
            if str(question.get('id')) == str(question_id):
                return question
        return None

    def get_category_name(self, category_id: str) -> str:
        """Получить название категории по ID"""
        return self.question_categories.get(category_id, f"Категория {category_id}")

    def get_niche_by_id(self, niche_id: str) -> Optional[NicheDetails]:
        """Получить детали ниши по ID"""
        for niche in self.niche_categories:
            if niche.id == niche_id:
                return niche
        return None

    def get_niche_by_enum(self, niche_enum: NicheCategory) -> Optional[NicheDetails]:
        """Получить детали ниши по Enum значению"""
        for niche in self.niche_categories:
            if niche.category == niche_enum:
                return niche
        return None

    def get_question_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """Получить вопрос по индексу"""
        if 0 <= index < len(self.questions):
            return self.questions[index]
        return None

    def get_total_questions(self) -> int:
        """Получить общее количество вопросов"""
        return len(self.questions)

    def get_niche_categories_for_user(self, user_skills: List[str], user_risk_tolerance: int) -> List[NicheDetails]:
        """Получить подходящие ниши для пользователя"""
        suitable_niches = []

        for niche in self.niche_categories:
            # Фильтрация по риску
            if abs(niche.risk_level - user_risk_tolerance) <= 2:
                suitable_niches.append(niche)

        # Сортировка по соответствию навыкам
        if suitable_niches:
            suitable_niches.sort(
                key=lambda n: len(set(n.required_skills) & set(user_skills)),
                reverse=True
            )

        return suitable_niches

# Создаем глобальный экземпляр конфигурации
print("🚀 Инициализация конфигурации бота...")
try:
    config = BotConfig()
    if config.validate():
        print("✨ Конфигурация готова к работе!")
    else:
        print("⚠️ Конфигурация имеет ошибки, но бот попытается запуститься")
except Exception as e:
    print(f"💥 Критическая ошибка при инициализации конфигурации: {e}")
    import traceback
    traceback.print_exc()
    # Создаем минимальную конфигурацию для возможности запуска
    config = BotConfig()
    config.questions = []
    config.niche_categories = []
    print("⚠️ Создана минимальная конфигурация для запуска")