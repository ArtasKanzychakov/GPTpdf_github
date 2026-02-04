"""
Менеджер данных для управления сессиями пользователей
"""
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

from models.session import UserSession, SessionStatus

logger = logging.getLogger(__name__)


class DataManager:
    """Менеджер для работы с пользовательскими сессиями"""
    
    def __init__(self):
        """Инициализация менеджера данных"""
        # Временное хранилище в памяти (до интеграции PostgreSQL)
        self.sessions: Dict[int, UserSession] = {}
        self._initialized = False
        logger.info("DataManager создан")
    
    def initialize(self):
        """Инициализация менеджера (вызывается при старте)"""
        if not self._initialized:
            self._initialized = True
            logger.info("✅ DataManager инициализирован (in-memory storage)")
    
    def get_session(self, user_id: int) -> Optional[UserSession]:
        """
        Получить сессию пользователя (синхронный метод)
        
        Args:
            user_id: ID пользователя в Telegram
        
        Returns:
            UserSession или None
        """
        session = self.sessions.get(user_id)
        
        if session:
            logger.debug(f"Сессия найдена для пользователя {user_id}")
        else:
            logger.debug(f"Сессия не найдена для пользователя {user_id}")
        
        return session
    
    def create_session(self, user_id: int, **kwargs) -> UserSession:
        """
        Создать новую сессию (синхронный метод)
        
        Args:
            user_id: ID пользователя в Telegram
            **kwargs: Дополнительные параметры
        
        Returns:
            Новая UserSession
        """
        session = UserSession(user_id=user_id)
        
        self.sessions[user_id] = session
        logger.info(f"Создана новая сессия для пользователя {user_id}")
        
        return session
    
    def save_session(self, session: UserSession) -> bool:
        """
        Сохранить сессию (синхронный метод)
        
        Args:
            session: Объект сессии
        
        Returns:
            True если успешно
        """
        try:
            session.touch()
            self.sessions[session.user_id] = session
            logger.debug(f"Сессия сохранена для пользователя {session.user_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения сессии: {e}")
            return False
    
    def update_session(self, session: UserSession) -> bool:
        """
        Обновить существующую сессию (синхронный метод)
        Алиас для save_session для совместимости
        """
        return self.save_session(session)
    
    def delete_session(self, user_id: int) -> bool:
        """
        Удалить сессию (синхронный метод)
        
        Args:
            user_id: ID пользователя
        
        Returns:
            True если успешно
        """
        try:
            if user_id in self.sessions:
                del self.sessions[user_id]
                logger.info(f"Сессия удалена для пользователя {user_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка удаления сессии: {e}")
            return False
    
    def save_answer(
        self, 
        user_id: int, 
        question_id: str, 
        answer: any
    ) -> bool:
        """
        Сохранить ответ пользователя
        
        Args:
            user_id: ID пользователя
            question_id: ID вопроса
            answer: Ответ
        
        Returns:
            True если успешно
        """
        session = self.get_session(user_id)
        
        if not session:
            logger.warning(f"Попытка сохранить ответ для несуществующей сессии: {user_id}")
            return False
        
        try:
            session.save_answer(question_id, answer)
            self.save_session(session)
            logger.info(f"Ответ сохранен: user={user_id}, question={question_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения ответа: {e}")
            return False
    
    def update_temp_data(
        self, 
        user_id: int, 
        key: str, 
        value: any
    ) -> bool:
        """
        Обновить временные данные сессии
        
        Args:
            user_id: ID пользователя
            key: Ключ
            value: Значение
        
        Returns:
            True если успешно
        """
        session = self.get_session(user_id)
        
        if not session:
            return False
        
        try:
            session.temp_data[key] = value
            self.save_session(session)
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления temp_data: {e}")
            return False
    
    def clear_temp_data(self, user_id: int) -> bool:
        """
        Очистить временные данные
        
        Args:
            user_id: ID пользователя
        
        Returns:
            True если успешно
        """
        session = self.get_session(user_id)
        
        if not session:
            return False
        
        try:
            session.temp_data = {}
            self.save_session(session)
            return True
        except Exception as e:
            logger.error(f"Ошибка очистки temp_data: {e}")
            return False
    
    def update_status(
        self, 
        user_id: int, 
        status: SessionStatus
    ) -> bool:
        """
        Обновить статус сессии
        
        Args:
            user_id: ID пользователя
            status: Новый статус
        
        Returns:
            True если успешно
        """
        session = self.get_session(user_id)
        
        if not session:
            return False
        
        try:
            session.status = status
            self.save_session(session)
            logger.info(f"Статус обновлен: user={user_id}, status={status.value}")
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления статуса: {e}")
            return False
    
    def get_all_sessions(self) -> Dict[int, UserSession]:
        """
        Получить все сессии (для админа)
        
        Returns:
            Словарь всех сессий
        """
        return self.sessions.copy()
    
    def cleanup_old_sessions(self, days: int = 7) -> int:
        """
        Очистить старые неактивные сессии
        
        Args:
            days: Количество дней неактивности
        
        Returns:
            Количество удаленных сессий
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted = 0
        
        user_ids_to_delete = []
        
        for user_id, session in self.sessions.items():
            if session.updated_at < cutoff_date and session.status != SessionStatus.COMPLETED:
                user_ids_to_delete.append(user_id)
        
        for user_id in user_ids_to_delete:
            self.delete_session(user_id)
            deleted += 1
        
        if deleted > 0:
            logger.info(f"Очищено {deleted} старых сессий")
        
        return deleted
    
    def get_session_statistics(self) -> Dict[str, any]:
        """
        Получить статистику по сессиям
        
        Returns:
            Словарь со статистикой
        """
        total = len(self.sessions)
        
        statuses = {}
        for session in self.sessions.values():
            status = session.status.value
            statuses[status] = statuses.get(status, 0) + 1
        
        completed = statuses.get(SessionStatus.COMPLETED.value, 0)
        in_progress = statuses.get(SessionStatus.IN_PROGRESS.value, 0)
        
        avg_completion = 0
        if self.sessions:
            # Считаем среднее количество ответов
            total_answers = sum(len(s.answers) for s in self.sessions.values())
            avg_completion = (total_answers / len(self.sessions)) if len(self.sessions) > 0 else 0
        
        return {
            'total_sessions': total,
            'completed': completed,
            'in_progress': in_progress,
            'statuses': statuses,
            'average_completion': round(avg_completion, 2)
        }
    
    def __len__(self) -> int:
        """Количество активных сессий"""
        return len(self.sessions)
    
    def __contains__(self, user_id: int) -> bool:
        """Проверка наличия сессии"""
        return user_id in self.sessions


# Глобальный экземпляр (создается но НЕ инициализируется)
data_manager = DataManager()