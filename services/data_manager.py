#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер данных с автоматической очисткой старых сессий
"""
import json
import logging
import asyncio
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
import threading
import weakref

from models.session import UserSession, OpenAIUsage, BotStatistics

logger = logging.getLogger(__name__)

class DataManager:
    """Менеджер данных с автоматической очисткой"""

    def __init__(self, session_timeout_hours: int = 24):
        self.session_timeout_hours = session_timeout_hours
        self.user_sessions: Dict[int, UserSession] = {}
        self.openai_usage = OpenAIUsage()
        self.stats = BotStatistics()

        # Используем weakref для избежания memory leak
        self._session_refs = weakref.WeakValueDictionary()

        # Пути для хранения данных
        self.data_dir = Path("./data")
        self.data_dir.mkdir(exist_ok=True)

        # Семафор для thread-safe операций
        self._lock = threading.Lock()

        # Загружаем сохраненные сессии
        self._load_sessions()

        # ИСПРАВЛЕНИЕ: Не запускаем cleanup сразу, будет запущен позже
        # self._start_cleanup_task()  # ЗАКОММЕНТИРОВАНО!

        self._cleanup_task = None  # Будет хранить задачу очистки
        
        logger.info("✅ DataManager инициализирован (cleanup отложен)")

    def _load_sessions(self):
        """Загрузить сохраненные сессии"""
        try:
            session_files = list(self.data_dir.glob("session_*.json"))
            logger.info(f"Найдено {len(session_files)} файлов сессий")

            loaded_count = 0
            for file_path in session_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Проверяем время последней активности
                    last_activity_str = data.get('last_activity')
                    if last_activity_str:
                        last_activity = datetime.fromisoformat(last_activity_str)
                        age_hours = (datetime.now() - last_activity).total_seconds() / 3600

                        # Удаляем сессии старше timeout
                        if age_hours > self.session_timeout_hours:
                            logger.debug(f"Удаляем старую сессию: {file_path.name}")
                            file_path.unlink()
                            continue

                    # Конвертируем строковые значения обратно в Enum
                    self._convert_session_data(data)

                    # Создаем сессию
                    session = UserSession(**data)
                    self.user_sessions[session.user_id] = session
                    self._session_refs[session.user_id] = session
                    loaded_count += 1

                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка JSON в файле {file_path}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Ошибка загрузки сессии из {file_path}: {e}")
                    continue

            self.stats.active_sessions = loaded_count
            logger.info(f"✅ Загружено {loaded_count} активных сессий")

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки сессий: {e}")

    def _convert_session_data(self, data: Dict):
        """Конвертировать данные сессии"""
        # Конвертируем строки в Enum
        from models.enums import BotState

        if 'current_state' in data and data['current_state']:
            try:
                data['current_state'] = BotState[data['current_state']]
            except:
                data['current_state'] = BotState.START

        # Конвертируем даты
        date_fields = ['start_time', 'last_activity']
        for field in date_fields:
            if field in data and data[field]:
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except:
                    data[field] = datetime.now()

    # ИСПРАВЛЕНИЕ: Изменённый метод _start_cleanup_task
    def _start_cleanup_task(self):
        """Запустить задачу периодической очистки (ОСТАВЛЯЕМ для совместимости)"""
        # Этот метод теперь ничего не делает при инициализации
        # Реальная задача будет запущена через async_start_cleanup
        logger.debug("_start_cleanup_task вызван (ничего не делаем)")
        pass

    # ИСПРАВЛЕНИЕ: Новый метод для запуска очистки когда event loop уже работает
    async def async_start_cleanup(self):
        """Запустить очистку асинхронно (вызывается когда event loop уже работает)"""
        logger.info("🔄 Запуск асинхронной задачи очистки сессий...")
        
        async def cleanup_loop():
            """Фоновая задача очистки"""
            logger.info("✅ Фоновая задача очистки сессий запущена")
            while True:
                try:
                    await self.cleanup_old_sessions()
                    # Очищаем каждые 30 минут
                    await asyncio.sleep(1800)
                except asyncio.CancelledError:
                    logger.info("❌ Задача очистки сессий остановлена")
                    break
                except Exception as e:
                    logger.error(f"❌ Ошибка в cleanup_loop: {e}")
                    await asyncio.sleep(300)  # Ждем 5 минут при ошибке
        
        # Создаем и сохраняем задачу
        self._cleanup_task = asyncio.create_task(cleanup_loop())
        return self._cleanup_task

    async def stop_cleanup(self):
        """Остановить задачу очистки"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("✅ Задача очистки сессий остановлена")

    async def cleanup_old_sessions(self):
        """Очистить старые сессии"""
        with self._lock:
            now = datetime.now()
            expired_users = []

            for user_id, session in list(self.user_sessions.items()):
                age_hours = (now - session.last_activity).total_seconds() / 3600

                if age_hours > self.session_timeout_hours:
                    # Сохраняем перед удалением
                    self._save_session_to_file(session)
                    expired_users.append(user_id)

            # Удаляем истекшие сессии
            for user_id in expired_users:
                if user_id in self.user_sessions:
                    del self.user_sessions[user_id]
                    if user_id in self._session_refs:
                        del self._session_refs[user_id]
                    self.stats.active_sessions -= 1

            if expired_users:
                logger.info(f"🗑️ Очищено {len(expired_users)} неактивных сессий")
            else:
                logger.debug("✅ Нет старых сессий для очистки")

    def get_or_create_session(
        self, 
        user_id: int, 
        chat_id: int, 
        **kwargs
    ) -> UserSession:
        """Получить или создать сессию"""
        with self._lock:
            if user_id in self.user_sessions:
                session = self.user_sessions[user_id]
                session.update_activity()
                return session
            else:
                session = UserSession(
                    user_id=user_id,
                    chat_id=chat_id,
                    username=kwargs.get('username'),
                    first_name=kwargs.get('first_name'),
                    last_name=kwargs.get('last_name')
                )
                self.user_sessions[user_id] = session
                self._session_refs[user_id] = session
                self.stats.total_users += 1
                self.stats.active_sessions += 1
                return session

    def save_session(self, session: UserSession):
        """Сохранить сессию"""
        with self._lock:
            try:
                session.update_activity()
                self._save_session_to_file(session)
            except Exception as e:
                logger.error(f"Ошибка сохранения сессии {session.user_id}: {e}")

    def _save_session_to_file(self, session: UserSession):
        """Сохранить сессию в файл"""
        try:
            # Подготавливаем данные для JSON
            session_dict = {}
            for key, value in session.__dict__.items():
                if isinstance(value, datetime):
                    session_dict[key] = value.isoformat()
                elif hasattr(value, 'name'):  # Enum
                    session_dict[key] = value.name
                else:
                    session_dict[key] = value

            file_path = self.data_dir / f"session_{session.user_id}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(session_dict, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Ошибка записи сессии в файл: {e}")

    def delete_session(self, user_id: int):
        """Удалить сессию"""
        with self._lock:
            if user_id in self.user_sessions:
                # Удаляем файл
                file_path = self.data_dir / f"session_{user_id}.json"
                if file_path.exists():
                    file_path.unlink()

                # Удаляем из памяти
                del self.user_sessions[user_id]
                if user_id in self._session_refs:
                    del self._session_refs[user_id]
                self.stats.active_sessions -= 1

    def mark_profile_completed(self, user_id: int):
        """Пометить профиль как завершенный"""
        with self._lock:
            if user_id in self.user_sessions:
                self.stats.completed_profiles += 1
                self.save_session(self.user_sessions[user_id])

    def add_generated_niches(self, niches_count: int):
        """Добавить сгенерированные ниши"""
        with self._lock:
            self.stats.generated_niches += niches_count

    def add_generated_plan(self):
        """Добавить сгенерированный план"""
        with self._lock:
            self.stats.generated_plans += 1

    def increment_messages(self):
        """Увеличить счетчик сообщений"""
        with self._lock:
            self.stats.total_messages += 1

    def get_session(self, user_id: int) -> Optional[UserSession]:
        """Получить сессию по ID пользователя"""
        with self._lock:
            return self.user_sessions.get(user_id)

    def get_all_sessions(self) -> List[UserSession]:
        """Получить все активные сессии"""
        with self._lock:
            return list(self.user_sessions.values())

    def get_session_count(self) -> int:
        """Получить количество активных сессий"""
        with self._lock:
            return len(self.user_sessions)

    def get_active_sessions_count(self) -> int:
        """Получить количество активных сессий (alias для совместимости)"""
        return self.get_session_count()

    def get_statistics(self) -> BotStatistics:
        """Получить статистику"""
        with self._lock:
            return self.stats

# ИСПРАВЛЕНИЕ: Убрали создание глобального экземпляра здесь
# data_manager = DataManager()  # УДАЛИТЬ эту строку, если она есть!