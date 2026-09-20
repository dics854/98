# Используем официальный образ Python
FROM python:3.12-slim

WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код приложения
COPY . .

# Устанавливаем PYTHONPATH чтобы Python мог найти модули в /app
ENV PYTHONPATH=/app

# Запускаем бот
CMD ["python", "main.py"]
