FROM python:3.12-slim

# Робоча директорія
WORKDIR /app

# Встановлення залежностей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо весь проєкт
COPY . .

# Запуск бота
CMD ["python", "main.py"]
