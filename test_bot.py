#!/usr/bin/env python3
# test_bot.py - скрипт для проверки бота

import os
import sys

print("🔍 ПРОВЕРКА КОНФИГУРАЦИИ БОТА")
print("=" * 50)

# Проверяем файлы
files = ['app.py', 'requirements.txt', 'runtime.txt', 'render.yaml']
for file in files:
    exists = os.path.exists(file)
    print(f"{'✅' if exists else '❌'} {file}: {'ЕСТЬ' if exists else 'НЕТ'}")

print("\n📦 ПРОВЕРКА ЗАВИСИМОСТЕЙ:")
try:
    import telegram
    print(f"✅ python-telegram-bot: {telegram.__version__}")
except ImportError:
    print("❌ python-telegram-bot: НЕ УСТАНОВЛЕН")

try:
    import openai
    print(f"✅ openai: {openai.__version__}")
except ImportError:
    print("❌ openai: НЕ УСТАНОВЛЕН")

print("\n🔑 ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ:")
token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
print(f"TELEGRAM_TOKEN: {'ЕСТЬ' if token else '❌ НЕТ'}")
if token:
    print(f"  Длина: {len(token)} символов")
    print(f"  Начинается с: {token[:10]}...")

print(f"\nOPENAI_API_KEY: {'ЕСТЬ' if os.getenv('OPENAI_API_KEY') else 'НЕТ (будет тестовый режим)'}")
print(f"PORT: {os.getenv('PORT', '10000')}")

print("\n🚀 РЕКОМЕНДАЦИИ:")
if not token:
    print("1. Установите TELEGRAM_BOT_TOKEN в настройках Render")
    print("2. Получите токен у @BotFather в Telegram")
else:
    print("1. Запустите бота: python app.py")
    print("2. Отправьте /start в Telegram")
    print("3. Проверьте логи на Render")