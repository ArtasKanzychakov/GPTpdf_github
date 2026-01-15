#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер данных для хранения сессий пользователей
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio

from models.session import UserSession, BotStatistics

logger = logging.getLogger(__name__)

class DataManager:
    """Менеджер для работы с данными пользователей"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.sessions: Dict[int, UserSession] = {}
        self.statistics = BotStatistics()
        self._lock = asyncio.Lock()
        
        # Создаем директорию для данных
        self.data_dir.mkdir(exist_ok=True)
    
    def initialize(self):
        """Инициализация менеджера данных"""
        logger.info("📂 Инициализация менеджера данных...")
        
        # Загружаем сохраненные сессии
        self._load_sessions()
        
        logger.info(f"✅ Загружено {len(self.sessions)} сессий")
        logger.info(f"📊 Статистика: {self.statistics}")
    
    def _load_sessions(self):
        """Загрузить сессии из файла"""
        sessions_file = self.data_dir / "sessions.json"
        
        if not sessions_file.exists():
            logger.info("📭 Файл сессий не найден, начинаю с пустого списка")
            return
        
        try:
            with open(sessions_file, 'r', encoding='utf-8') as f:
                sessions_data = json.load(f)
            
            loaded_count = 0
            for session_data in sessions_data:
                try:
                    # Создаем сессию из данных
                    session = self._create_session_from_dict(session_data)
                    if session:
                        self.sessions[session.user_id] = session
                        loaded_count += 1
                        
                        # Обновляем статистику
                        if session.is_completed:
                            self.statistics.complete_session()
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка загрузки сессии: {e}")
            
            logger.info(f"📥 Загружено {loaded_count} сессий из файла")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки файла сессий: {e}")
    
    def _create_session_from_dict(self, session_dict: Dict[str, Any]) -> Optional[UserSession]:
        """Создать сессию из словаря"""
        try:
            # Базовые поля
            user_id = session_dict.get('user_id')
            if not user_id:
                return None
            
            # Создаем новую сессию
            session = UserSession(
                user_id=user_id,
                username=session_dict.get('username', ''),
                full_name=session_dict.get('full_name', '')
            )
            
            # Восстанавливаем состояние
            current_state = session_dict.get('current_state')
            if current_state:
                from models.enums import BotState
                try:
                    session.current_state = BotState[current_state]
                except:
                    pass
            
            session.current_question_index = session_dict.get('current_question_index', 0)
            session.is_completed = session_dict.get('is_completed', False)
            
            # Восстанавливаем ответы
            answers = session_dict.get('answers', {})
            if answers:
                self._restore_answers(session, answers)
            
            # Восстанавливаем временные метки
            created_at = session_dict.get('created_at')
            if created_at:
                try:
                    session.created_at = datetime.fromisoformat(created_at)
                except:
                    pass
            
            updated_at = session_dict.get('updated_at')
            if updated_at:
                try:
                    session.updated_at = datetime.fromisoformat(updated_at)
                except:
                    pass
            
            return session
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания сессии из словаря: {e}")
            return None
    
    def _restore_answers(self, session: UserSession, answers: Dict[str, Any]):
        """Восстановить ответы в сессию"""
        try:
            # Демография
            demo = answers.get('demographics', {})
            session.age_group = demo.get('age_group', '')
            session.education = demo.get('education', '')
            session.location_type = demo.get('location_type', '')
            session.location_custom = demo.get('location_custom', '')
            
            # Личность
            personality = answers.get('personality', {})
            session.motivations = personality.get('motivations', [])
            session.decision_style = personality.get('decision_style', '')
            session.risk_scenario = personality.get('risk_scenario', '')
            session.risk_tolerance = personality.get('risk_tolerance', 0)
            
            # Энергетический профиль
            energy = personality.get('energy_profile', {})
            morning = energy.get('morning', 0)
            day = energy.get('day', 0)
            evening = energy.get('evening', 0)
            session.energy_profile = f"{morning} {day} {evening}"
            
            session.peak_analytical = energy.get('peak_analytical', '')
            session.peak_creative = energy.get('peak_creative', '')
            session.peak_social = energy.get('peak_social', '')
            
            session.fears_selected = personality.get('fears', [])
            session.fear_custom = personality.get('fear_custom', '')
            
            # Навыки
            skills = answers.get('skills', {})
            session.analytical_skills = skills.get('analytics', 0)
            session.communication_skills = skills.get('communication', 0)
            session.design_skills = skills.get('design', 0)
            session.organizational_skills = skills.get('organization', 0)
            session.manual_skills = skills.get('manual', 0)
            session.emotional_iq = skills.get('emotional_iq', 0)
            session.superpower = skills.get('superpower', '')
            session.work_style = skills.get('work_style', '')
            session.learning_style = skills.get('learning_style', '')
            
            # Ценности
            values = answers.get('values', {})
            session.existential_answer = values.get('existential_answer', '')
            session.flow_experience = values.get('flow_experience', '')
            session.flow_feelings = values.get('flow_feelings', '')
            
            ideal_client = values.get('ideal_client', {})
            session.ideal_client_age = ideal_client.get('age', '')
            session.ideal_client_field = ideal_client.get('field', '')
            session.ideal_client_pain = ideal_client.get('pain', '')
            session.ideal_client_details = ideal_client.get('details', '')
            
            # Ограничения
            limitations = answers.get('limitations', {})
            session.budget = limitations.get('budget', '')
            session.equipment = limitations.get('equipment', [])
            session.knowledge_assets = limitations.get('knowledge_assets', [])
            session.time_per_week = limitations.get('time_per_week', '')
            session.business_scale = limitations.get('business_scale', '')
            session.business_format = limitations.get('business_format', '')
            
        except Exception as e:
            logger.error(f"❌ Ошибка восстановления ответов: {e}")
    
    def get_session(self, user_id: int) -> Optional[UserSession]:
        """Получить сессию пользователя"""
        if user_id in self.sessions:
            return self.sessions[user_id]
        return None
    
    def create_session(self, user_id: int, username: str = "", full_name: str = "") -> UserSession:
        """Создать новую сессию"""
        session = UserSession(
            user_id=user_id,
            username=username,
            full_name=full_name
        )
        
        self.sessions[user_id] = session
        self.statistics.add_session()
        self.statistics.add_user()
        
        logger.info(f"📝 Создана новая сессия для пользователя {user_id}")
        self._save_sessions_async()
        
        return session
    
    def save_session(self, session: UserSession):
        """Сохранить сессию"""
        self.sessions[session.user_id] = session
        
        # Обновляем статистику
        if session.is_completed:
            self.statistics.complete_session()
        
        # Асинхронное сохранение
        self._save_sessions_async()
    
    async def save_session_async(self, session: UserSession):
        """Сохранить сессию асинхронно"""
        async with self._lock:
            self.save_session(session)
    
    def _save_sessions_async(self):
        """Асинхронно сохранить сессии в файл"""
        try:
            # Создаем список данных для сохранения
            sessions_data = []
            for session in self.sessions.values():
                try:
                    session_dict = session.to_dict()
                    session_dict['answers'] = session.get_all_answers()
                    session_dict['created_at'] = session.created_at.isoformat()
                    session_dict['updated_at'] = session.updated_at.isoformat()
                    sessions_data.append(session_dict)
                except Exception as e:
                    logger.error(f"❌ Ошибка сериализации сессии {session.user_id}: {e}")
            
            # Сохраняем в файл
            sessions_file = self.data_dir / "sessions.json"
            with open(sessions_file, 'w', encoding='utf-8') as f:
                json.dump(sessions_data, f, ensure_ascii=False, indent=2, default=str)
            
            logger.debug(f"💾 Сохранено {len(sessions_data)} сессий")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения сессий: {e}")
    
    def cleanup_old_sessions(self, days: int = 7):
        """Очистить старые сессии"""
        cutoff_date = datetime.now() - timedelta(days=days)
        removed_count = 0
        
        user_ids_to_remove = []
        
        for user_id, session in self.sessions.items():
            if session.updated_at < cutoff_date:
                user_ids_to_remove.append(user_id)
        
        for user_id in user_ids_to_remove:
            del self.sessions[user_id]
            removed_count += 1
        
        if removed_count > 0:
            logger.info(f"🗑️ Удалено {removed_count} старых сессий")
            self._save_sessions_async()
        
        return removed_count
    
    def get_statistics(self) -> BotStatistics:
        """Получить статистику"""
        # Обновляем количество активных сессий
        active_count = sum(1 for s in self.sessions.values() 
                          if not s.is_completed and 
                          (datetime.now() - s.last_interaction).days < 1)
        self.statistics.update_active_sessions(active_count)
        
        return self.statistics
    
    def get_active_sessions_count(self) -> int:
        """Получить количество активных сессий"""
        active_count = sum(1 for s in self.sessions.values() 
                          if not s.is_completed and 
                          (datetime.now() - s.last_interaction).days < 1)
        return active_count

# Создаем глобальный экземпляр менеджера данных
data_manager = DataManager()

# Функция для быстрого доступа
def get_data_manager() -> DataManager:
    """Получить менеджер данных"""
    return data_manager