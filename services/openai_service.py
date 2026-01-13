"""
Сервис для работы с OpenAI
Версия для openai==0.28.1 и Python 3.9.16
"""
import logging
import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

import openai
from openai.error import (
    OpenAIError, AuthenticationError, RateLimitError, 
    APIError, ServiceUnavailableError, InvalidRequestError
)
import requests

from config.settings import BotConfig
from models.session import OpenAIUsage

logger = logging.getLogger(__name__)

class OpenAIService:
    """Сервис для работы с OpenAI (версия 0.28.1)"""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.is_available = bool(config.openai_api_key)
        self.last_check = None
        self.balance_cache = None
        self.balance_cache_time = None
        
        if self.is_available:
            openai.api_key = config.openai_api_key
            logger.info("✅ OpenAI клиент инициализирован (v0.28.1)")
        else:
            logger.warning("⚠️ OpenAI API ключ не установлен, AI функции отключены")
    
    async def check_availability(self) -> Tuple[bool, Optional[str]]:
        """Проверить доступность OpenAI и баланс"""
        if not self.is_available:
            return False, "OpenAI API ключ не установлен"
        
        try:
            # Проверяем баланс и доступность
            balance_info = await self._check_balance_with_timeout()
            
            if balance_info["available"]:
                self.last_check = datetime.now()
                balance_text = balance_info["message"]
                
                logger.info(f"✅ OpenAI доступен. {balance_text}")
                return True, balance_text
            else:
                logger.warning(f"⚠️ OpenAI проблемы: {balance_info['message']}")
                return False, balance_info["message"]
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки OpenAI: {e}")
            return False, f"Ошибка подключения: {str(e)}"
    
    async def _check_balance_with_timeout(self, timeout: int = 10) -> Dict[str, Any]:
        """Проверить баланс с таймаутом"""
        try:
            return await asyncio.wait_for(
                self._check_balance(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return {
                "available": False,
                "message": "Таймаут при проверке баланса",
                "balance": None
            }
    
    async def _check_balance(self) -> Dict[str, Any]:
        """Проверить баланс OpenAI"""
        if not self.is_available:
            return {
                "available": False,
                "message": "API ключ не установлен",
                "balance": None
            }
        
        # Проверяем кэш (кешируем на 5 минут)
        if (self.balance_cache_time and 
            (datetime.now() - self.balance_cache_time) < timedelta(minutes=5)):
            return self.balance_cache
        
        try:
            # Метод 1: Проверка через billing API (для новых аккаунтов)
            headers = {
                "Authorization": f"Bearer {openai.api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                "https://api.openai.com/dashboard/billing/credit_grants",
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'total_granted' in data and 'total_used' in data:
                    total = data['total_granted']
                    used = data['total_used']
                    balance = total - used
                    
                    result = {
                        "available": True,
                        "message": f"Баланс: ${balance:.2f} (из ${total:.2f})",
                        "balance": balance,
                        "total": total,
                        "used": used
                    }
                    
                    # Кэшируем результат
                    self.balance_cache = result
                    self.balance_cache_time = datetime.now()
                    
                    return result
            
            # Метод 2: Проверка через usage API
            try:
                # Получаем использование за текущий месяц
                today = datetime.now()
                start_date = today.replace(day=1).strftime("%Y-%m-%d")
                end_date = today.strftime("%Y-%m-%d")
                
                usage_url = f"https://api.openai.com/dashboard/billing/usage"
                usage_params = {
                    "start_date": start_date,
                    "end_date": end_date
                }
                
                usage_response = requests.get(
                    usage_url,
                    headers=headers,
                    params=usage_params,
                    timeout=15
                )
                
                if usage_response.status_code == 200:
                    usage_data = usage_response.json()
                    total_usage = usage_data.get("total_usage", 0) / 100  # Центы в доллары
                    
                    # Для pay-as-you-go аккаунтов
                    result = {
                        "available": True,
                        "message": f"Pay-as-you-go. Использовано: ${total_usage:.2f} в этом месяце",
                        "balance": None,
                        "total_usage": total_usage
                    }
                    
                    self.balance_cache = result
                    self.balance_cache_time = datetime.now()
                    
                    return result
            
            except Exception as e:
                logger.debug(f"Usage API недоступен: {e}")
            
            # Метод 3: Простая проверка доступности API
            try:
                # Делаем тестовый запрос к models endpoint
                models_response = requests.get(
                    "https://api.openai.com/v1/models",
                    headers=headers,
                    timeout=10
                )
                
                if models_response.status_code == 200:
                    result = {
                        "available": True,
                        "message": "API доступен (баланс не проверен)",
                        "balance": None
                    }
                    
                    self.balance_cache = result
                    self.balance_cache_time = datetime.now()
                    
                    return result
            
            except Exception as e:
                logger.debug(f"Models API недоступен: {e}")
            
            # Если ничего не сработало
            return {
                "available": False,
                "message": "Не удалось проверить баланс",
                "balance": None
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Ошибка сети при проверке баланса: {e}")
            return {
                "available": False,
                "message": f"Ошибка сети: {str(e)}",
                "balance": None
            }
        except Exception as e:
            logger.error(f"❌ Неизвестная ошибка при проверке баланса: {e}")
            return {
                "available": False,
                "message": f"Ошибка: {str(e)}",
                "balance": None
            }
    
    async def _call_openai(
        self, 
        prompt: str, 
        max_tokens: int = None, 
        temperature: float = None,
        usage_tracker: OpenAIUsage = None
    ) -> Optional[str]:
        """Вызов OpenAI API для версии 0.28.1"""
        if not self.is_available:
            logger.warning("OpenAI недоступен")
            return None
        
        try:
            response = openai.ChatCompletion.create(
                model=self.config.openai_model,
                messages=[
                    {"role": "system", "content": "Ты - опытный бизнес-консультант и психолог."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens or self.config.openai_max_tokens,
                temperature=temperature or self.config.openai_temperature,
                timeout=60
            )
            
            content = response.choices[0].message.content
            
            # Логируем использование токенов
            if usage_tracker:
                usage = response.usage.to_dict()
                usage_tracker.add_usage(usage)
                logger.info(f"✅ OpenAI: использовано {usage.get('total_tokens', 0)} токенов")
            
            return content
            
        except AuthenticationError:
            logger.error("❌ Ошибка аутентификации OpenAI. Проверьте API ключ.")
            if usage_tracker:
                usage_tracker.add_failure()
            self.is_available = False
            return None
        except RateLimitError as e:
            logger.error(f"❌ Превышен лимит запросов к OpenAI: {e}")
            if usage_tracker:
                usage_tracker.add_failure()
            return None
        except InvalidRequestError as e:
            logger.error(f"❌ Неверный запрос к OpenAI: {e}")
            if usage_tracker:
                usage_tracker.add_failure()
            return None
        except APIError as e:
            logger.error(f"❌ Ошибка API OpenAI: {e}")
            if usage_tracker:
                usage_tracker.add_failure()
            return None
        except ServiceUnavailableError:
            logger.error("❌ Сервис OpenAI временно недоступен")
            if usage_tracker:
                usage_tracker.add_failure()
            return None
        except Exception as e:
            logger.error(f"❌ Неизвестная ошибка вызова OpenAI: {e}")
            if usage_tracker:
                usage_tracker.add_failure()
            return None
    
    async def generate_psychological_analysis(
        self, 
        session_data: Dict, 
        usage_tracker: OpenAIUsage
    ) -> Optional[str]:
        """Генерация психологического анализа"""
        logger.info(f"🧠 Генерация психологического анализа")
        
        # Загружаем промт из файла
        prompt = await self._load_prompt("psychological_analysis")
        if not prompt:
            logger.error("❌ Не удалось загрузить промт для анализа")
            return None
        
        # Заполняем промт данными
        filled_prompt = self._fill_template(prompt, session_data)
        
        analysis = await self._call_openai(
            filled_prompt, 
            max_tokens=3000, 
            temperature=0.5,
            usage_tracker=usage_tracker
        )
        
        if analysis:
            logger.info(f"✅ Психологический анализ сгенерирован ({len(analysis)} символов)")
        else:
            logger.warning("❌ Не удалось сгенерировать анализ")
            analysis = self._create_fallback_analysis(session_data)
        
        return analysis
    
    async def generate_business_niches(
        self, 
        session_data: Dict, 
        analysis: str,
        usage_tracker: OpenAIUsage
    ) -> List[Dict]:
        """Генерация бизнес-ниш"""
        logger.info("🎯 Генерация бизнес-ниш")
        
        prompt = await self._load_prompt("generate_niches")
        if not prompt:
            logger.error("❌ Не удалось загрузить промт для ниш")
            return self._create_fallback_niches(session_data)
        
        # Подготавливаем данные для промта
        template_data = {
            "analysis": analysis[:2000],
            **session_data
        }
        
        filled_prompt = self._fill_template(prompt, template_data)
        
        niches_text = await self._call_openai(
            filled_prompt, 
            max_tokens=4000, 
            temperature=0.8,
            usage_tracker=usage_tracker
        )
        
        if not niches_text:
            logger.warning("❌ Не удалось сгенерировать ниши")
            return self._create_fallback_niches(session_data)
        
        # Парсинг сгенерированных ниш
        niches = self._parse_niches_from_text(niches_text)
        
        if niches:
            logger.info(f"✅ Сгенерировано {len(niches)} ниш")
        else:
            logger.warning("❌ Не удалось распарсить ниши")
            niches = self._create_fallback_niches(session_data)
        
        return niches
    
    async def generate_detailed_plan(
        self, 
        session_data: Dict, 
        niche: Dict,
        usage_tracker: OpenAIUsage
    ) -> Optional[str]:
        """Генерация детального плана"""
        logger.info(f"📋 Генерация плана для ниши: {niche.get('name', '')}")
        
        prompt = await self._load_prompt("detailed_plan")
        if not prompt:
            logger.error("❌ Не удалось загрузить промт для плана")
            return self._create_fallback_plan(session_data, niche)
        
        # Подготавливаем данные
        template_data = {
            "niche": niche,
            **session_data
        }
        
        filled_prompt = self._fill_template(prompt, template_data)
        
        plan = await self._call_openai(
            filled_prompt, 
            max_tokens=4000, 
            temperature=0.6,
            usage_tracker=usage_tracker
        )
        
        if not plan:
            logger.warning("❌ Не удалось сгенерировать план")
            plan = self._create_fallback_plan(session_data, niche)
        
        return plan
    
    async def _load_prompt(self, prompt_name: str) -> Optional[str]:
        """Загрузить промт из файла"""
        try:
            prompts_dir = self.config.get_prompts_dir()
            prompt_path = prompts_dir / f"{prompt_name}.txt"
            
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                logger.warning(f"⚠️ Файл промта не найден: {prompt_path}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки промта {prompt_name}: {e}")
            return None
    
    def _fill_template(self, template: str, data: Dict) -> str:
        """Заполнить шаблон данными"""
        try:
            # Простая замена переменных в формате {var_name}
            for key, value in data.items():
                if isinstance(value, (str, int, float)):
                    placeholder = f"{{{key}}}"
                    template = template.replace(placeholder, str(value))
                elif isinstance(value, dict):
                    # Рекурсивно обрабатываем вложенные словари
                    for sub_key, sub_value in value.items():
                        placeholder = f"{{{key}.{sub_key}}}"
                        if isinstance(sub_value, (str, int, float)):
                            template = template.replace(placeholder, str(sub_value))
            
            return template
        except Exception as e:
            logger.error(f"❌ Ошибка заполнения шаблона: {e}")
            return template
    
    def _parse_niches_from_text(self, text: str) -> List[Dict]:
        """Парсинг ниш из текста OpenAI"""
        niches = []
        current_niche = {}
        
        lines = text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('НИША'):
                if current_niche:
                    niches.append(current_niche.copy())
                current_niche = {'id': len(niches) + 1}
                match = re.search(r'НИША\s+\d+:\s*(.+?)$', line)
                if match:
                    current_niche['type'] = match.group(1).strip()
            
            elif line.startswith('НАЗВАНИЕ:'):
                current_niche['name'] = line.replace('НАЗВАНИЕ:', '').strip()
            
            elif line.startswith('СУТЬ:'):
                current_niche['description'] = line.replace('СУТЬ:', '').strip()
            
            elif line.startswith('ПОЧЕМУ ПОДХОДИТ:'):
                current_niche['why'] = line.replace('ПОЧЕМУ ПОДХОДИТ:', '').strip()
            
            elif line.startswith('ФОРМАТ:'):
                current_niche['format'] = line.replace('ФОРМАТ:', '').strip()
            
            elif line.startswith('ИНВЕСТИЦИИ:'):
                current_niche['investment'] = line.replace('ИНВЕСТИЦИИ:', '').strip()
            
            elif line.startswith('СРОК ОКУПАЕМОСТИ:'):
                current_niche['roi'] = line.replace('СРОК ОКУПАЕМОСТИ:', '').strip()
            
            elif line.startswith('ПЕРВЫЕ 3 ШАГА:'):
                current_niche['steps'] = []
            elif line.startswith('1.') and 'steps' in current_niche:
                current_niche['steps'].append(line[2:].strip())
            elif line.startswith('2.') and 'steps' in current_niche:
                current_niche['steps'].append(line[2:].strip())
            elif line.startswith('3.') and 'steps' in current_niche:
                current_niche['steps'].append(line[2:].strip())
        
        if current_niche:
            niches.append(current_niche)
        
        # Добавляем дефолтные шаги если их нет
        for niche in niches:
            if 'steps' not in niche or len(niche['steps']) < 3:
                niche['steps'] = [
                    'Провести анализ рынка и конкурентов',
                    'Создать MVP продукта или услуги',
                    'Найти первых 3 клиентов для тестирования'
                ]
        
        return niches
    
    def _create_fallback_analysis(self, session_data: Dict) -> str:
        """Запасной психологический анализ"""
        return f"""# ПСИХОЛОГИЧЕСКИЙ АНАЛИЗ (базовый режим)

## 1. КЛЮЧЕВЫЕ ХАРАКТЕРИСТИКИ:
- **Возрастная группа:** {session_data.get('demographics', {}).get('age_group', 'Не указано')}
- **Образование:** {session_data.get('demographics', {}).get('education', 'Не указано')}
- **Локация:** {session_data.get('demographics', {}).get('location', 'Не указано')}

## 2. СКРЫТЫЙ ПОТЕНЦИАЛ:
- Возможность монетизации образования и опыта
- Географические преимущества вашего региона
- Сочетание практических навыков и личных интересов

## 3. РЕКОМЕНДАЦИИ:
1. Начинать с небольших проектов для быстрого получения результата
2. Использовать сильные стороны для создания конкурентного преимущества
3. Постепенно расширять масштаб по мере роста уверенности"""

    def _create_fallback_niches(self, session_data: Dict) -> List[Dict]:
        """Запасные бизнес-ниши"""
        location = session_data.get('demographics', {}).get('location', 'вашем городе')
        
        return [
            {
                'id': 1,
                'type': '🔥 Быстрый старт',
                'name': 'Консультационные услуги',
                'description': f'Предоставление профессиональных консультаций в вашей сфере знаний бизнесам в {location}',
                'why': 'Использует ваши профессиональные навыки и образование',
                'format': 'Гибрид',
                'investment': '10,000-50,000₽',
                'roi': '1-2 месяца',
                'steps': [
                    'Определить 3 ключевые темы для консультаций',
                    'Создать профессиональное портфолио',
                    'Найти первых клиентов через LinkedIn'
                ]
            },
            {
                'id': 2,
                'type': '🚀 Сбалансированный',
                'name': 'Онлайн-обучение',
                'description': 'Создание и продажа онлайн-курсов по вашей экспертизе',
                'why': 'Сочетает образование и желание делиться знаниями',
                'format': 'Онлайн',
                'investment': '50,000-100,000₽',
                'roi': '3-4 месяца',
                'steps': [
                    'Разработать программу мини-курса',
                    'Создать пробные уроки',
                    'Запустить предзаказ через соцсети'
                ]
            }
        ]
    
    def _create_fallback_plan(self, session_data: Dict, niche: Dict) -> str:
        """Запасной детальный план"""
        return f"""# 📋 ДЕТАЛЬНЫЙ БИЗНЕС-ПЛАН (базовый режим)

## 🎯 НИША: {niche.get('name', 'Бизнес-услуги')}

### 1. ПЕРВЫЕ ШАГИ (неделя 1):
- Изучить конкурентов в вашей нише
- Определить уникальное предложение
- Создать базовые материалы для продвижения

### 2. ЗАПУСК (месяц 1-3):
- Найти первых 3-5 клиентов
- Протестировать предложение
- Собрать обратную связь и улучшить

### 3. МАСШТАБИРОВАНИЕ (месяц 4-6):
- Оптимизировать процессы
- Расширить предложение
- Увеличить клиентскую базу

💡 **Совет:** Начинайте с малого, быстро тестируйте гипотезы, собирайте обратную связь."""