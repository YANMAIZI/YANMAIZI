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

# Импорт TTS модуля
from tts_module import get_tts_generator, TTSRequest, TTSEngine, TTSVoice, generate_tts, get_tts_info

# Импорт модуля генерации видео
from video_generator import generate_video, get_video_info, VideoType, VideoStyle

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

# ================== TRENDS ENDPOINTS ==================

@api_router.post("/trends/monitor")
async def start_trend_monitoring():
    """Запуск мониторинга трендов"""
    try:
        # Создаем задачу мониторинга трендов
        task = Task(
            type=TaskType.TREND_MONITORING,
            parameters={"sources": ["youtube", "google_trends", "rss_feeds"]}
        )
        
        await tasks_collection.insert_one(task.dict())
        
        # Запускаем мониторинг в фоне (в продакшене будет через Celery)
        import asyncio
        asyncio.create_task(monitor_trends_background(task.id))
        
        return {
            "success": True,
            "task_id": task.id,
            "message": "Мониторинг трендов запущен"
        }
    except Exception as e:
        logging.error(f"Error starting trend monitoring: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при запуске мониторинга трендов")

@api_router.get("/trends", response_model=List[Trend])
async def get_trends(limit: int = 20):
    """Получение списка найденных трендов"""
    try:
        trends = await trends_collection.find().sort("discovered_at", -1).limit(limit).to_list(limit)
        return [Trend(**trend) for trend in trends]
    except Exception as e:
        logging.error(f"Error getting trends: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении трендов")

@api_router.get("/trends/popular")
async def get_popular_trends(limit: int = 10):
    """Получение самых популярных трендов"""
    try:
        trends = await trends_collection.find().sort("popularity_score", -1).limit(limit).to_list(limit)
        return [Trend(**trend) for trend in trends]
    except Exception as e:
        logging.error(f"Error getting popular trends: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении популярных трендов")

@api_router.post("/trends/{trend_id}/create_content")
async def create_content_from_trend(trend_id: str):
    """Создание контента на основе тренда"""
    try:
        # Получаем тренд
        trend = await trends_collection.find_one({"id": trend_id})
        if not trend:
            raise HTTPException(status_code=404, detail="Тренд не найден")
        
        # Создаем контент на основе тренда
        content_title = f"Топ-5 способов использовать {trend['keyword']} для получения подарков"
        
        content = Content(
            type=ContentType.VIDEO,
            title=content_title,
            topic=trend['keyword'],
            description=f"Контент создан на основе тренда: {trend['title']}",
            keywords=[trend['keyword']] + trend.get('hashtags', []),
            target_platforms=[Platform.TIKTOK, Platform.YOUTUBE, Platform.TELEGRAM]
        )
        
        await content_collection.insert_one(content.dict())
        
        # Создаем задачу генерации
        generation_task = Task(
            type=TaskType.CONTENT_GENERATION,
            parameters={
                "content_id": content.id,
                "source_trend_id": trend_id,
                "trend_data": trend
            }
        )
        
        await tasks_collection.insert_one(generation_task.dict())
        
        return {
            "success": True,
            "content_id": content.id,
            "task_id": generation_task.id,
            "message": f"Контент на основе тренда '{trend['keyword']}' создан"
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error creating content from trend: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при создании контента из тренда")

async def monitor_trends_background(task_id: str):
    """Фоновая задача мониторинга трендов"""
    try:
        # Обновляем статус задачи
        await tasks_collection.update_one(
            {"id": task_id},
            {"$set": {"status": TaskStatus.RUNNING, "progress": 10, "updated_at": datetime.utcnow()}}
        )
        
        # Запускаем мониторинг
        result = await run_trend_monitoring()
        
        if result['success']:
            # Сохраняем найденные тренды в базу
            trends_to_save = []
            for trend_data in result['trends']:
                trend = Trend(
                    platform=Platform.TIKTOK,  # Основная платформа для трендов
                    keyword=trend_data['keyword'],
                    description=trend_data['title'],
                    popularity_score=trend_data['score'],
                    hashtags=trend_data['hashtags'],
                    source_url="",  # Если есть URL
                    source_data=trend_data,
                    discovered_at=datetime.fromisoformat(trend_data['discovered_at'].replace('Z', '+00:00')) if 'T' in trend_data['discovered_at'] else datetime.utcnow()
                )
                trends_to_save.append(trend.dict())
            
            if trends_to_save:
                await trends_collection.insert_many(trends_to_save)
            
            # Создаем задачи для популярных трендов
            popular_trends = sorted(result['trends'], key=lambda x: x['score'], reverse=True)[:5]
            content_tasks_created = 0
            
            for trend_data in popular_trends:
                if trend_data['score'] > 0.6:  # Только высокорейтинговые тренды
                    # Создаем контент на основе тренда
                    content_title = f"Как использовать {trend_data['keyword']} для получения подарков в Telegram"
                    
                    content = Content(
                        type=ContentType.VIDEO,
                        title=content_title,
                        topic=trend_data['keyword'],
                        description=f"Автоматически создано на основе тренда: {trend_data['title']}",
                        keywords=[trend_data['keyword']] + trend_data['hashtags'],
                        target_platforms=[Platform.TIKTOK, Platform.YOUTUBE, Platform.TELEGRAM]
                    )
                    
                    await content_collection.insert_one(content.dict())
                    
                    # Создаем задачу генерации
                    generation_task = Task(
                        type=TaskType.CONTENT_GENERATION,
                        parameters={
                            "content_id": content.id,
                            "auto_generated": True,
                            "source_trend": trend_data
                        }
                    )
                    
                    await tasks_collection.insert_one(generation_task.dict())
                    content_tasks_created += 1
            
            # Обновляем статус задачи - завершена
            await tasks_collection.update_one(
                {"id": task_id},
                {"$set": {
                    "status": TaskStatus.COMPLETED,
                    "progress": 100,
                    "completed_at": datetime.utcnow(),
                    "result": {
                        "trends_found": result['trends_found'],
                        "content_tasks_created": content_tasks_created,
                        "content_ideas": result['content_ideas']
                    }
                }}
            )
            
            logger.info(f"Мониторинг трендов завершен: найдено {result['trends_found']} трендов, создано {content_tasks_created} задач контента")
            
        else:
            # Ошибка при мониторинге
            await tasks_collection.update_one(
                {"id": task_id},
                {"$set": {
                    "status": TaskStatus.FAILED,
                    "error_message": result.get('error', 'Неизвестная ошибка'),
                    "updated_at": datetime.utcnow()
                }}
            )
            
    except Exception as e:
        logger.error(f"Ошибка в фоновой задаче мониторинга трендов: {e}")
        
        # Обновляем статус задачи - ошибка
        await tasks_collection.update_one(
            {"id": task_id},
            {"$set": {
                "status": TaskStatus.FAILED,
                "error_message": str(e),
                "updated_at": datetime.utcnow()
            }}
        )

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

# ================== TTS ENDPOINTS ==================

@api_router.get("/tts/info")
async def get_tts_system_info():
    """Получение информации о TTS системе"""
    try:
        info = await get_tts_info()
        return {
            "success": True,
            "data": info
        }
    except Exception as e:
        logging.error(f"Error getting TTS info: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении информации о TTS")

@api_router.post("/tts/generate")
async def generate_tts_audio(request_data: dict):
    """Генерация TTS аудио"""
    try:
        text = request_data.get("text", "")
        engine = request_data.get("engine", "gtts")
        voice = request_data.get("voice", "female")
        language = request_data.get("language", "ru")
        speed = request_data.get("speed", 1.0)
        
        if not text.strip():
            raise HTTPException(status_code=400, detail="Текст не может быть пустым")
        
        # Создаём задачу TTS генерации
        task = Task(
            type=TaskType.TTS_GENERATION,
            parameters={
                "text": text,
                "engine": engine,
                "voice": voice,
                "language": language,
                "speed": speed
            }
        )
        
        await tasks_collection.insert_one(task.dict())
        
        # Запускаем TTS генерацию в фоне
        import asyncio
        asyncio.create_task(process_tts_generation(task.id, request_data))
        
        return {
            "success": True,
            "task_id": task.id,
            "message": "TTS генерация запущена"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error starting TTS generation: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при запуске TTS генерации")

async def process_tts_generation(task_id: str, request_data: dict):
    """Фоновая обработка TTS генерации"""
    try:
        # Обновляем статус задачи
        await tasks_collection.update_one(
            {"id": task_id},
            {"$set": {"status": TaskStatus.RUNNING, "progress": 10, "updated_at": datetime.utcnow()}}
        )
        
        # Генерируем TTS
        result = await generate_tts(
            text=request_data.get("text", ""),
            engine=request_data.get("engine", "gtts"),
            voice=request_data.get("voice", "female"),
            language=request_data.get("language", "ru"),
            speed=request_data.get("speed", 1.0)
        )
        
        if result.success:
            # Обновляем задачу - успешно завершена
            await tasks_collection.update_one(
                {"id": task_id},
                {"$set": {
                    "status": TaskStatus.COMPLETED,
                    "progress": 100,
                    "completed_at": datetime.utcnow(),
                    "result": {
                        "audio_path": result.audio_path,
                        "file_size": result.file_size,
                        "duration": result.duration,
                        "generation_time": result.generation_time,
                        "engine_used": result.engine_used
                    }
                }}
            )
            
            logger.info(f"TTS генерация успешно завершена: {result.audio_path}")
        else:
            # Обновляем задачу - ошибка
            await tasks_collection.update_one(
                {"id": task_id},
                {"$set": {
                    "status": TaskStatus.FAILED,
                    "error_message": result.error,
                    "updated_at": datetime.utcnow()
                }}
            )
            
            logger.error(f"Ошибка TTS генерации: {result.error}")
            
    except Exception as e:
        logger.error(f"Ошибка в фоновой задаче TTS генерации: {e}")
        
        # Обновляем статус задачи - ошибка
        await tasks_collection.update_one(
            {"id": task_id},
            {"$set": {
                "status": TaskStatus.FAILED,
                "error_message": str(e),
                "updated_at": datetime.utcnow()
            }}
        )

@api_router.post("/content/{content_id}/generate_tts")
async def generate_content_tts(content_id: str, tts_params: dict = None):
    """Генерация TTS для существующего контента"""
    try:
        # Получаем контент
        content = await content_collection.find_one({"id": content_id})
        if not content:
            raise HTTPException(status_code=404, detail="Контент не найден")
        
        # Проверяем наличие скрипта/текста
        text_to_speech = content.get("script") or content.get("description") or content.get("title", "")
        
        if not text_to_speech.strip():
            raise HTTPException(status_code=400, detail="У контента нет текста для озвучки")
        
        # Параметры TTS
        if not tts_params:
            tts_params = {}
        
        tts_data = {
            "text": text_to_speech,
            "engine": tts_params.get("engine", "gtts"),
            "voice": tts_params.get("voice", "female"),
            "language": tts_params.get("language", "ru"),
            "speed": tts_params.get("speed", 1.0)
        }
        
        # Создаём задачу TTS
        task = Task(
            type=TaskType.TTS_GENERATION,
            parameters=dict(tts_data, content_id=content_id)
        )
        
        await tasks_collection.insert_one(task.dict())
        
        # Запускаем TTS генерацию в фоне
        import asyncio
        asyncio.create_task(process_content_tts_generation(task.id, content_id, tts_data))
        
        return {
            "success": True,
            "task_id": task.id,
            "content_id": content_id,
            "message": "TTS генерация для контента запущена"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error generating TTS for content: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при генерации TTS для контента")

async def process_content_tts_generation(task_id: str, content_id: str, tts_data: dict):
    """Фоновая обработка TTS генерации для контента"""
    try:
        # Обновляем статус задачи
        await tasks_collection.update_one(
            {"id": task_id},
            {"$set": {"status": TaskStatus.RUNNING, "progress": 20, "updated_at": datetime.utcnow()}}
        )
        
        # Генерируем TTS
        result = await generate_tts(**tts_data)
        
        if result.success:
            # Обновляем контент с путем к аудиофайлу
            await content_collection.update_one(
                {"id": content_id},
                {"$set": {
                    "audio_path": result.audio_path,
                    "updated_at": datetime.utcnow()
                }}
            )
            
            # Обновляем задачу - успешно завершена
            await tasks_collection.update_one(
                {"id": task_id},
                {"$set": {
                    "status": TaskStatus.COMPLETED,
                    "progress": 100,
                    "completed_at": datetime.utcnow(),
                    "result": {
                        "content_id": content_id,
                        "audio_path": result.audio_path,
                        "file_size": result.file_size,
                        "duration": result.duration,
                        "generation_time": result.generation_time,
                        "engine_used": result.engine_used
                    }
                }}
            )
            
            logger.info(f"TTS для контента {content_id} успешно создан: {result.audio_path}")
        else:
            # Обновляем задачу - ошибка
            await tasks_collection.update_one(
                {"id": task_id},
                {"$set": {
                    "status": TaskStatus.FAILED,
                    "error_message": result.error,
                    "updated_at": datetime.utcnow()
                }}
            )
            
            logger.error(f"Ошибка TTS генерации для контента {content_id}: {result.error}")
            
    except Exception as e:
        logger.error(f"Ошибка в фоновой задаче TTS генерации для контента: {e}")
        
        # Обновляем статус задачи - ошибка
        await tasks_collection.update_one(
            {"id": task_id},
            {"$set": {
                "status": TaskStatus.FAILED,
                "error_message": str(e),
                "updated_at": datetime.utcnow()
            }}
        )

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
