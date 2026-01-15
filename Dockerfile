FROM python:3.9-slim

WORKDIR /app

# Обновляем pip до последней версии перед установкой зависимостей
RUN pip install --upgrade pip

COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]