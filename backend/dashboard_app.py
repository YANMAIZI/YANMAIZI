"""
Flask Dashboard для EKOSYSTEMA_FULL
Панель управления локальной системой автоматического создания контента
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_cors import CORS
import os
import requests
from datetime import datetime, timedelta
import logging
from pathlib import Path
import asyncio
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'ekosystema_secret_key_change_in_production'
CORS(app)

# Конфигурация
ROOT_DIR = Path(__file__).parent
BACKEND_API_URL = os.environ.get('BACKEND_API_URL', 'http://localhost:8001/api')

class DashboardAPI:
    """Класс для взаимодействия с основным FastAPI backend"""
    
    @staticmethod
    def get(endpoint):
        try:
            response = requests.get(f"{BACKEND_API_URL}{endpoint}")
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"API GET error: {e}")
            return None
    
    @staticmethod
    def post(endpoint, data):
        try:
            response = requests.post(f"{BACKEND_API_URL}{endpoint}", json=data)
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"API POST error: {e}")
            return None

# Главная страница Dashboard
@app.route('/')
def dashboard():
    """Главная страница с обзором системы"""
    
    # Получаем статистику системы
    stats = {
        'total_content': 0,
        'pending_tasks': 0,
        'published_today': 0,
        'system_status': 'active'
    }
    
    # Последние задачи (пока mock данные)
    recent_tasks = [
        {
            'id': '1',
            'type': 'content_generation',
            'status': 'completed',
            'created_at': datetime.now() - timedelta(hours=2),
            'title': 'Сгенерировать видео о Telegram-подарках'
        },
        {
            'id': '2', 
            'type': 'publishing',
            'status': 'pending',
            'created_at': datetime.now() - timedelta(minutes=30),
            'title': 'Опубликовать в TikTok'
        }
    ]
    
    return render_template('dashboard.html', stats=stats, recent_tasks=recent_tasks)

# Генерация контента
@app.route('/content')
def content_management():
    """Управление генерацией контента"""
    return render_template('content.html')

# Публикация
@app.route('/publishing')  
def publishing_management():
    """Управление публикацией контента"""
    platforms = [
        {'name': 'TikTok', 'status': 'disconnected', 'last_post': None},
        {'name': 'YouTube', 'status': 'disconnected', 'last_post': None},
        {'name': 'Instagram', 'status': 'disconnected', 'last_post': None},
        {'name': 'Telegram', 'status': 'disconnected', 'last_post': None},
    ]
    return render_template('publishing.html', platforms=platforms)

# Задачи и очереди
@app.route('/tasks')
def tasks_management():
    """Управление задачами и очередями"""
    tasks = [
        {
            'id': '1',
            'type': 'trend_monitoring',
            'status': 'running',
            'progress': 65,
            'created_at': datetime.now() - timedelta(hours=1),
            'estimated_completion': datetime.now() + timedelta(minutes=15)
        },
        {
            'id': '2',
            'type': 'video_generation', 
            'status': 'pending',
            'progress': 0,
            'created_at': datetime.now() - timedelta(minutes=5),
            'estimated_completion': None
        }
    ]
    return render_template('tasks.html', tasks=tasks)

# Аналитика
@app.route('/analytics')
def analytics():
    """Аналитика и статистика"""
    analytics_data = {
        'views_total': 12543,
        'subscribers_total': 1205,
        'revenue_total': 157.23,
        'top_content': [
            {'title': 'Лучшие Telegram боты для подарков', 'views': 2341, 'engagement': 8.5},
            {'title': 'Как получить бесплатные подарки', 'views': 1876, 'engagement': 7.2}
        ]
    }
    return render_template('analytics.html', data=analytics_data)

# Настройки
@app.route('/settings')
def settings():
    """Настройки системы"""
    return render_template('settings.html')

# Мониторинг трендов
@app.route('/trends')
def trends_monitoring():
    """Мониторинг трендов"""
    return render_template('trends.html')

# API endpoints для AJAX запросов
@app.route('/api/tasks/create', methods=['POST'])
def create_task():
    """Создание новой задачи"""
    data = request.json
    task_type = data.get('type')
    
    # Здесь будет логика создания задачи через Celery
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': f'Задача {task_type} создана успешно'
    })

@app.route('/api/tasks/<task_id>/status')
def get_task_status(task_id):
    """Получение статуса задачи"""
    # Mock данные - позже будет реальная проверка через Celery
    return jsonify({
        'task_id': task_id,
        'status': 'running',
        'progress': 45,
        'message': 'Обработка в процессе...'
    })

@app.route('/api/content/generate', methods=['POST'])
def generate_content():
    """Запуск генерации контента"""
    data = request.json
    content_type = data.get('type', 'video')
    topic = data.get('topic', 'Telegram подарки')
    
    # Здесь будет запуск задачи генерации через Celery
    return jsonify({
        'success': True,
        'message': f'Запущена генерация {content_type} на тему: {topic}'
    })

if __name__ == '__main__':
    # Создаем папку для templates если не существует
    templates_dir = ROOT_DIR / 'templates'
    templates_dir.mkdir(exist_ok=True)
    
    app.run(host='0.0.0.0', port=5000, debug=True)