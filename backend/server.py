from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from typing import List
import uuid
from datetime import datetime

# Импорт моделей
from models import (
    Task, TaskCreate, TaskResponse, TaskStatus, TaskType,
    Content, ContentCreate, ContentResponse, ContentType,
    Publication, Platform, Trend, Analytics, AnalyticsResponse,
    SystemSettings
)

# Импорт системы мониторинга трендов
from trend_monitor import run_trend_monitoring, TrendData

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="EKOSYSTEMA_FULL API", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Коллекции MongoDB
tasks_collection = db.tasks
content_collection = db.content
publications_collection = db.publications
trends_collection = db.trends
analytics_collection = db.analytics
settings_collection = db.settings

# ================== TASKS ENDPOINTS ==================

@api_router.post("/tasks", response_model=TaskResponse)
async def create_task(task_data: TaskCreate):
    """Создание новой задачи"""
    try:
        task = Task(
            type=task_data.type,
            parameters=task_data.parameters
        )
        
        await tasks_collection.insert_one(task.dict())
        
        # Здесь будет запуск задачи через Celery
        
        return TaskResponse(
            success=True,
            task_id=task.id,
            message=f"Задача {task.type} создана успешно"
        )
    except Exception as e:
        logging.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при создании задачи")

@api_router.get("/tasks", response_model=List[Task])
async def get_tasks():
    """Получение списка всех задач"""
    try:
        tasks = await tasks_collection.find().to_list(100)
        return [Task(**task) for task in tasks]
    except Exception as e:
        logging.error(f"Error getting tasks: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении задач")

@api_router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Получение статуса конкретной задачи"""
    try:
        task = await tasks_collection.find_one({"id": task_id})
        if not task:
            raise HTTPException(status_code=404, detail="Задача не найдена")
        
        return {
            "task_id": task["id"],
            "status": task["status"],
            "progress": task["progress"],
            "message": f"Задача {task['type']} - {task['status']}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении статуса задачи")

@api_router.post("/tasks/{task_id}/pause")
async def pause_task(task_id: str):
    """Приостановка задачи"""
    try:
        result = await tasks_collection.update_one(
            {"id": task_id},
            {"$set": {"status": TaskStatus.PAUSED, "updated_at": datetime.utcnow()}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Задача не найдена")
        
        return {"success": True, "message": "Задача приостановлена"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error pausing task: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при приостановке задачи")

@api_router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """Удаление задачи"""
    try:
        result = await tasks_collection.delete_one({"id": task_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Задача не найдена")
        
        return {"success": True, "message": "Задача удалена"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting task: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при удалении задачи")

# ================== CONTENT ENDPOINTS ==================

@api_router.post("/content", response_model=ContentResponse)
async def create_content(content_data: ContentCreate):
    """Создание нового контента"""
    try:
        content = Content(
            type=content_data.type,
            title=content_data.title,
            topic=content_data.topic,
            description=content_data.description,
            keywords=content_data.keywords,
            target_platforms=content_data.target_platforms
        )
        
        await content_collection.insert_one(content.dict())
        
        # Создаем задачу генерации контента
        generation_task = Task(
            type=TaskType.CONTENT_GENERATION,
            parameters={
                "content_id": content.id,
                "content_type": content_data.type,
                "topic": content_data.topic,
                "description": content_data.description
            }
        )
        
        await tasks_collection.insert_one(generation_task.dict())
        
        # Обновляем контент с ID задачи
        await content_collection.update_one(
            {"id": content.id},
            {"$set": {"generation_task_id": generation_task.id}}
        )
        
        return ContentResponse(
            success=True,
            content_id=content.id,
            message=f"Контент создан, запущена генерация (задача {generation_task.id})"
        )
    except Exception as e:
        logging.error(f"Error creating content: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при создании контента")

@api_router.get("/content", response_model=List[Content])
async def get_content():
    """Получение списка контента"""
    try:
        content_list = await content_collection.find().sort("created_at", -1).to_list(50)
        return [Content(**content) for content in content_list]
    except Exception as e:
        logging.error(f"Error getting content: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении контента")

@api_router.get("/content/{content_id}", response_model=Content)
async def get_content_by_id(content_id: str):
    """Получение контента по ID"""
    try:
        content = await content_collection.find_one({"id": content_id})
        if not content:
            raise HTTPException(status_code=404, detail="Контент не найден")
        
        return Content(**content)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting content by id: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении контента")

# ================== LEGACY ENDPOINTS (for compatibility) ==================

@api_router.get("/")
async def root():
    return {"message": "EKOSYSTEMA_FULL API v1.0.0"}

@api_router.post("/tasks/create", response_model=TaskResponse)
async def create_task_legacy(task_data: dict):
    """Legacy endpoint для создания задач (совместимость с dashboard)"""
    try:
        task_type = TaskType(task_data.get("type", "content_generation"))
        
        task_create = TaskCreate(
            type=task_type,
            parameters=task_data.get("parameters", {})
        )
        
        return await create_task(task_create)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Неверный тип задачи: {e}")
    except Exception as e:
        logging.error(f"Error in legacy create task: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при создании задачи")

@api_router.post("/content/generate", response_model=ContentResponse)
async def generate_content_legacy(content_data: dict):
    """Legacy endpoint для генерации контента (совместимость с dashboard)"""
    try:
        content_type = ContentType(content_data.get("type", "video"))
        platforms = [Platform(p) for p in content_data.get("platforms", ["telegram"])]
        
        content_create = ContentCreate(
            type=content_type,
            title=content_data.get("topic", "Без названия"),
            topic=content_data.get("topic", ""),
            description=content_data.get("description", ""),
            target_platforms=platforms
        )
        
        return await create_content(content_create)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Неверные параметры: {e}")
    except Exception as e:
        logging.error(f"Error in legacy generate content: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при генерации контента")

# ================== ANALYTICS ENDPOINTS ==================

@api_router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics():
    """Получение аналитики"""
    try:
        # Получаем базовую статистику
        total_content = await content_collection.count_documents({})
        total_publications = await publications_collection.count_documents({})
        
        # Mock данные для демонстрации
        return AnalyticsResponse(
            total_views=12543,
            total_likes=1205,
            total_subscribers=157,
            total_revenue=157.23,
            top_content=[
                {"title": "Лучшие Telegram боты для подарков", "views": 2341, "engagement": 8.5},
                {"title": "Как получить бесплатные подарки", "views": 1876, "engagement": 7.2}
            ],
            platform_stats={
                "tiktok": {"views": 5000, "likes": 400, "subscribers": 50},
                "youtube": {"views": 4000, "likes": 350, "subscribers": 60},
                "telegram": {"views": 3543, "likes": 455, "subscribers": 47}
            }
        )
    except Exception as e:
        logging.error(f"Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении аналитики")

# ================== SETTINGS ENDPOINTS ==================

@api_router.get("/settings", response_model=SystemSettings)
async def get_settings():
    """Получение настроек системы"""
    try:
        settings = await settings_collection.find_one({"id": "system_settings"})
        if not settings:
            # Создаем настройки по умолчанию
            default_settings = SystemSettings()
            await settings_collection.insert_one(default_settings.dict())
            return default_settings
        
        return SystemSettings(**settings)
    except Exception as e:
        logging.error(f"Error getting settings: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении настроек")

@api_router.post("/settings")
async def update_settings(settings: SystemSettings):
    """Обновление настроек системы"""
    try:
        settings.updated_at = datetime.utcnow()
        
        await settings_collection.update_one(
            {"id": "system_settings"},
            {"$set": settings.dict()},
            upsert=True
        )
        
        return {"success": True, "message": "Настройки обновлены"}
    except Exception as e:
        logging.error(f"Error updating settings: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при обновлении настроек")

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
