#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер данных для управления сессиями пользователей
"""
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DataManager:
    """Менеджер для работы с пользовательскими сессиями"""

    def __init__(self):
        self.sessions: Dict[int, object] = {}
        logger.info("💾 DataManager инициализирован (in-memory storage)")

    async def get_session(self, user_id: int):
        """Получить сессию пользователя"""
        from models.session import UserSession
        session = self.sessions.get(user_id)
        if not session:
            session = UserSession(user_id=user_id)
            self.sessions[user_id] = session
        return session

    async def create_session(self, user_id: int):
        """Создать новую сессию"""
        from models.session import UserSession, SessionStatus
        session = UserSession(
            user_id=user_id,
            status=SessionStatus.STARTED,
            current_question=1,
        )
        self.sessions[user_id] = session
        logger.info(f"✅ Создана сессия для пользователя {user_id}")
        return session

    async def update_session(self, session) -> bool:
        """Обновить существующую сессию"""
        try:
            session.update_timestamp()
            self.sessions[session.user_id] = session
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления сессии: {e}")
            return False

    async def save_answer(self, user_id: int, question_id: str, answer: any) -> bool:
        """Сохранить ответ пользователя"""
        session = await self.get_session(user_id)
        if not session:
            return False
        try:
            session.add_answer(question_id, answer)
            await self.update_session(session)
            logger.info(f"✅ Ответ сохранен: user={user_id}, question={question_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения ответа: {e}")
            return False

    async def update_temp_data(self, user_id: int, key: str, value: any) -> bool:
        """Обновить временные данные сессии"""
        session = await self.get_session(user_id)
        if not session:
            return False
        try:
            session.temp_data[key] = value
            await self.update_session(session)
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления temp_data: {e}")
            return False

    async def update_status(self, user_id: int, status) -> bool:
        """Обновить статус сессии"""
        session = await self.get_session(user_id)
        if not session:
            return False
        try:
            session.status = status
            await self.update_session(session)
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления статуса: {e}")
            return False

    async def cleanup_old_sessions(self, days: int = 7) -> int:
        """Очистить старые сессии"""
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted = 0
        user_ids_to_delete = []
        for user_id, session in self.sessions.items():
            if session.updated_at < cutoff_date:
                user_ids_to_delete.append(user_id)
        for user_id in user_ids_to_delete:
            del self.sessions[user_id]
            deleted += 1
        if deleted > 0:
            logger.info(f"🧹 Очищено {deleted} старых сессий")
        return deleted


data_manager = DataManager()
