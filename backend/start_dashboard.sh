#!/bin/bash

# Скрипт для запуска Flask Dashboard
cd /app/backend

# Устанавливаем переменные окружения
export FLASK_APP=dashboard_app.py
export FLASK_ENV=development
export BACKEND_API_URL=http://localhost:8001/api

# Запускаем Flask приложение
python dashboard_app.py