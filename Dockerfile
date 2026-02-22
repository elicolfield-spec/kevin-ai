# Используем легковесный образ Python
FROM python:3.10-slim

# Устанавливаем рабочую папку внутри контейнера
WORKDIR /app

# Копируем список зависимостей
COPY requirements.txt .

# Устанавливаем библиотеки без лишнего мусора
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код бота в контейнер
COPY . .

# Открываем порт (Render будет использовать 8080)
EXPOSE 8080

# Команда для запуска бота
CMD ["python", "main.py"]
