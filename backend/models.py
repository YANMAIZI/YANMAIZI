"""
Модели данных для EKOSYSTEMA_FULL
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

# Статусы задач
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

class TaskType(str, Enum):
    TREND_MONITORING = "trend_monitoring"
    CONTENT_GENERATION = "content_generation"
    PUBLISHING = "publishing"
    ANALYTICS = "analytics"
    VIDEO_GENERATION = "video_generation"
    TTS_GENERATION = "tts_generation"

# Типы контента
class ContentType(str, Enum):
    VIDEO = "video"
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"

# Платформы публикации
class Platform(str, Enum):
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TELEGRAM = "telegram"

# Модель задачи
class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    
    # Параметры задачи
    parameters: Dict[str, Any] = {}
    
    # Результаты выполнения
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    # Логи выполнения
    logs: List[str] = []

class TaskCreate(BaseModel):
    type: TaskType
    parameters: Dict[str, Any] = {}

# Модель контента
class Content(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: ContentType
    title: str
    description: Optional[str] = None
    
    # Исходные данные
    topic: str
    keywords: List[str] = []
    
    # Генерированный контент
    script: Optional[str] = None  # Сценарий/текст
    audio_path: Optional[str] = None  # Путь к аудио файлу
    video_path: Optional[str] = None  # Путь к видео файлу
    image_path: Optional[str] = None  # Путь к изображению
    
    # Метаданные
    duration: Optional[int] = None  # Длительность в секундах
    size: Optional[int] = None  # Размер файла в байтах
    
    # Статус
    status: str = "draft"  # draft, ready, published
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Связанные задачи
    generation_task_id: Optional[str] = None
    
    # Настройки публикации
    target_platforms: List[Platform] = []
    
    # Партнерские ссылки
    affiliate_links: List[str] = []

class ContentCreate(BaseModel):
    type: ContentType
    title: str
    topic: str
    description: Optional[str] = None
    keywords: List[str] = []
    target_platforms: List[Platform] = []

# Модель публикации
class Publication(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content_id: str
    platform: Platform
    platform_post_id: Optional[str] = None  # ID поста на платформе
    
    status: str = "scheduled"  # scheduled, published, failed
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    
    # Настройки публикации для конкретной платформы
    platform_settings: Dict[str, Any] = {}
    
    # Статистика
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Модель тренда
class Trend(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    platform: Platform
    keyword: str
    description: str
    
    # Метрики популярности
    popularity_score: float = 0.0
    hashtags: List[str] = []
    
    # Временные данные
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    # Данные источника
    source_url: Optional[str] = None
    source_data: Dict[str, Any] = {}

# Модель аналитики
class Analytics(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content_id: Optional[str] = None
    platform: Platform
    
    # Метрики
    date: datetime = Field(default_factory=datetime.utcnow)
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    subscribers_gained: int = 0
    
    # Доходы
    revenue: float = 0.0
    clicks: int = 0
    conversions: int = 0

# Модель настроек системы
class SystemSettings(BaseModel):
    id: str = "system_settings"
    
    # API ключи
    api_keys: Dict[str, str] = {}
    
    # Настройки генерации контента
    content_generation: Dict[str, Any] = {
        "default_video_duration": 30,
        "default_voice": "female",
        "add_music": True,
        "add_affiliate_links": True
    }
    
    # Настройки публикации
    publishing: Dict[str, Any] = {
        "auto_publish": False,
        "publish_schedule": {},
        "platforms_enabled": []
    }
    
    # Настройки мониторинга трендов
    trend_monitoring: Dict[str, Any] = {
        "enabled": True,
        "check_interval": 3600,  # секунды
        "keywords": ["telegram", "подарки", "боты", "бесплатно"]
    }
    
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# Response модели
class TaskResponse(BaseModel):
    success: bool
    task_id: str
    message: str

class ContentResponse(BaseModel):
    success: bool
    content_id: str
    message: str
    content: Optional[Content] = None

class AnalyticsResponse(BaseModel):
    total_views: int
    total_likes: int
    total_subscribers: int
    total_revenue: float
    top_content: List[Dict[str, Any]]
    platform_stats: Dict[str, Dict[str, int]]