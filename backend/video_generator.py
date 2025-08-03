"""
Модуль генерации видео для EKOSYSTEMA_FULL
Создание видео контента из текста, изображений и аудио
"""

import os
import asyncio
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import uuid
import json

# Библиотеки для работы с изображениями и видео
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import cv2
import numpy as np
from moviepy import (
    VideoFileClip, ImageSequenceClip, CompositeVideoClip, 
    concatenate_videoclips, AudioFileClip, TextClip, ColorClip,
    ImageClip, concatenate_audioclips
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoType(str, Enum):
    """Типы генерируемого видео"""
    TEXT_TO_VIDEO = "text_to_video"
    IMAGE_SLIDESHOW = "image_slideshow" 
    ANIMATED_TEXT = "animated_text"
    TEMPLATE_BASED = "template_based"

class VideoStyle(str, Enum):
    """Стили видео"""
    MODERN = "modern"
    CLASSIC = "classic"
    MINIMAL = "minimal"
    COLORFUL = "colorful"
    DARK = "dark"

@dataclass
class VideoRequest:
    """Запрос на генерацию видео"""
    id: str
    type: VideoType
    text: str
    style: VideoStyle = VideoStyle.MODERN
    duration: int = 30  # секунды
    resolution: tuple = (1080, 1920)  # (width, height) для вертикального видео
    fps: int = 30
    audio_path: Optional[str] = None
    background_color: str = "#1a1a2e"
    text_color: str = "#ffffff"
    accent_color: str = "#ff6b35"
    font_size: int = 48
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

@dataclass 
class VideoResult:
    """Результат генерации видео"""
    request_id: str
    success: bool
    video_path: Optional[str] = None
    duration: Optional[float] = None
    file_size: Optional[int] = None
    resolution: Optional[tuple] = None
    error: Optional[str] = None
    generation_time: Optional[float] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class VideoGenerator:
    """Основной класс для генерации видео"""
    
    def __init__(self):
        self.video_dir = Path(__file__).parent / "generated_videos"
        self.templates_dir = Path(__file__).parent / "video_templates"
        self.assets_dir = Path(__file__).parent / "video_assets"
        
        # Создаём необходимые директории
        self.video_dir.mkdir(exist_ok=True)
        self.templates_dir.mkdir(exist_ok=True)
        self.assets_dir.mkdir(exist_ok=True)
        
        # Настройки для разных стилей
        self.style_configs = {
            VideoStyle.MODERN: {
                "background_gradient": ["#667eea", "#764ba2"],
                "text_color": "#ffffff",
                "accent_color": "#ff6b35",
                "font_family": "Arial Bold"
            },
            VideoStyle.CLASSIC: {
                "background_gradient": ["#2c3e50", "#3498db"],
                "text_color": "#ecf0f1",
                "accent_color": "#e74c3c",
                "font_family": "Times New Roman"
            },
            VideoStyle.MINIMAL: {
                "background_gradient": ["#f8f9fa", "#e9ecef"],
                "text_color": "#212529",
                "accent_color": "#007bff",
                "font_family": "Arial"
            },
            VideoStyle.COLORFUL: {
                "background_gradient": ["#ff9a9e", "#fecfef", "#fecfef"],
                "text_color": "#ffffff",
                "accent_color": "#ff6b9d",
                "font_family": "Arial Bold"
            },
            VideoStyle.DARK: {
                "background_gradient": ["#0f0f23", "#1a1a2e"],
                "text_color": "#eee",
                "accent_color": "#00d2ff",
                "font_family": "Arial"
            }
        }
        
        # Инициализация системы шрифтов
        self._init_fonts()
    
    def _init_fonts(self):
        """Инициализация шрифтов"""
        self.available_fonts = {}
        
        # Пытаемся найти системные шрифты
        font_paths = [
            "/usr/share/fonts/truetype/liberation/",
            "/usr/share/fonts/truetype/dejavu/",
            "/System/Library/Fonts/",
            "/Windows/Fonts/"
        ]
        
        self.default_font = None
        
        for font_path in font_paths:
            if Path(font_path).exists():
                for font_file in Path(font_path).glob("*.ttf"):
                    try:
                        font_name = font_file.stem
                        self.available_fonts[font_name] = str(font_file)
                        if self.default_font is None:
                            self.default_font = str(font_file)
                    except:
                        continue
                break
        
        if not self.default_font:
            logger.warning("Не найдены системные шрифты, будет использован шрифт по умолчанию")
    
    async def generate_video(self, request: VideoRequest) -> VideoResult:
        """Основной метод генерации видео"""
        start_time = datetime.utcnow()
        
        try:
            # Определяем путь к выходному файлу
            filename = f"video_{request.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            output_path = self.video_dir / filename
            
            # Генерируем видео в зависимости от типа
            if request.type == VideoType.ANIMATED_TEXT:
                result = await self._generate_animated_text_video(request, output_path)
            elif request.type == VideoType.IMAGE_SLIDESHOW:
                result = await self._generate_slideshow_video(request, output_path)
            elif request.type == VideoType.TEMPLATE_BASED:
                result = await self._generate_template_video(request, output_path)
            else:
                # По умолчанию - анимированный текст
                result = await self._generate_animated_text_video(request, output_path)
            
            # Добавляем аудио если есть
            if result.success and request.audio_path and Path(request.audio_path).exists():
                audio_result = await self._add_audio_to_video(result.video_path, request.audio_path)
                if audio_result.success:
                    result.video_path = audio_result.video_path
                    result.duration = audio_result.duration
            
            # Вычисляем время генерации
            generation_time = (datetime.utcnow() - start_time).total_seconds()
            result.generation_time = generation_time
            
            if result.success:
                # Получаем метаданные файла
                video_path = Path(result.video_path)
                result.file_size = video_path.stat().st_size
                
                logger.info(f"Видео сгенерировано за {generation_time:.2f}с: {output_path}")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при генерации видео: {e}")
            return VideoResult(
                request_id=request.id,
                success=False,
                error=str(e)
            )
    
    async def _generate_animated_text_video(self, request: VideoRequest, output_path: Path) -> VideoResult:
        """Генерация анимированного текстового видео"""
        def _generate():
            try:
                # Разбиваем текст на предложения
                sentences = [s.strip() for s in request.text.split('.') if s.strip()]
                if not sentences:
                    sentences = [request.text]
                
                # Создаём клипы для каждого предложения
                clips = []
                sentence_duration = request.duration / len(sentences)
                
                for i, sentence in enumerate(sentences):
                    # Создаем фоновый клип с градиентом
                    background = self._create_gradient_background(
                        request.resolution, 
                        request.style,
                        sentence_duration
                    )
                    
                    # Создаем текстовый клип
                    text_clip = TextClip(
                        sentence,
                        fontsize=request.font_size,
                        color=request.text_color,
                        font=self.default_font,
                        size=request.resolution,
                        method='caption'
                    ).set_duration(sentence_duration)
                    
                    # Добавляем анимацию появления
                    text_clip = text_clip.fadein(0.5).fadeout(0.5)
                    
                    # Композиция
                    sentence_clip = CompositeVideoClip([background, text_clip])
                    clips.append(sentence_clip)
                
                # Соединяем все клипы
                final_video = concatenate_videoclips(clips)
                
                # Сохраняем видео
                final_video.write_videofile(
                    str(output_path),
                    fps=request.fps,
                    codec='libx264',
                    audio_codec='aac',
                    verbose=False,
                    logger=None
                )
                
                return True, str(output_path), final_video.duration, None
                
            except Exception as e:
                return False, None, None, str(e)
        
        # Запускаем в executor
        loop = asyncio.get_event_loop()
        success, video_path, duration, error = await loop.run_in_executor(None, _generate)
        
        return VideoResult(
            request_id=request.id,
            success=success,
            video_path=video_path,
            duration=duration,
            error=error,
            resolution=request.resolution
        )
    
    async def _generate_slideshow_video(self, request: VideoRequest, output_path: Path) -> VideoResult:
        """Генерация видео-слайдшоу из изображений и текста"""
        def _generate():
            try:
                # Создаём изображения для каждой части текста
                sentences = [s.strip() for s in request.text.split('.') if s.strip()]
                if not sentences:
                    sentences = [request.text]
                
                image_paths = []
                for i, sentence in enumerate(sentences):
                    img_path = output_path.parent / f"slide_{request.id}_{i}.png"
                    self._create_text_image(
                        sentence, 
                        img_path,
                        request.resolution,
                        request.style
                    )
                    image_paths.append(str(img_path))
                
                # Создаём видео из изображений
                fps = max(1, request.fps // 10)  # Медленнее для слайдшоу
                duration_per_image = request.duration / len(image_paths)
                
                # Создаём клипы с переходами
                clips_with_transitions = []
                for i, img_path in enumerate(image_paths):
                    img_clip = ImageClip(img_path, duration=duration_per_image)
                    if i > 0:
                        img_clip = img_clip.fadein(0.5)
                    if i < len(image_paths) - 1:
                        img_clip = img_clip.fadeout(0.5)
                    clips_with_transitions.append(img_clip)
                
                final_video = concatenate_videoclips(clips_with_transitions)
                
                # Сохраняем
                final_video.write_videofile(
                    str(output_path),
                    fps=fps,
                    codec='libx264',
                    verbose=False,
                    logger=None
                )
                
                # Удаляем временные изображения
                for img_path in image_paths:
                    try:
                        Path(img_path).unlink()
                    except:
                        pass
                
                return True, str(output_path), final_video.duration, None
                
            except Exception as e:
                return False, None, None, str(e)
        
        loop = asyncio.get_event_loop()
        success, video_path, duration, error = await loop.run_in_executor(None, _generate)
        
        return VideoResult(
            request_id=request.id,
            success=success,
            video_path=video_path,
            duration=duration,
            error=error,
            resolution=request.resolution
        )
    
    async def _generate_template_video(self, request: VideoRequest, output_path: Path) -> VideoResult:
        """Генерация видео на основе шаблона"""
        # Пока заглушка - используем анимированный текст
        return await self._generate_animated_text_video(request, output_path)
    
    def _create_gradient_background(self, resolution: tuple, style: VideoStyle, duration: float) -> ColorClip:
        """Создание градиентного фона"""
        style_config = self.style_configs.get(style, self.style_configs[VideoStyle.MODERN])
        
        # Пока используем простой цветной фон (градиент сложнее реализовать в MoviePy)
        gradient_start = style_config["background_gradient"][0]
        
        return ColorClip(
            size=resolution,
            color=self._hex_to_rgb(gradient_start),
            duration=duration
        )
    
    def _create_text_image(self, text: str, output_path: Path, resolution: tuple, style: VideoStyle):
        """Создание изображения с текстом"""
        style_config = self.style_configs.get(style, self.style_configs[VideoStyle.MODERN])
        
        # Создаём изображение
        image = Image.new('RGB', resolution, color=self._hex_to_rgb(style_config["background_gradient"][0]))
        draw = ImageDraw.Draw(image)
        
        # Загружаем шрифт
        try:
            font = ImageFont.truetype(self.default_font, 60) if self.default_font else ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        # Вычисляем размер текста и позицию
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Перенос текста если слишком широкий
        if text_width > resolution[0] - 100:
            words = text.split()
            lines = []
            current_line = []
            
            for word in words:
                test_line = ' '.join(current_line + [word])
                test_bbox = draw.textbbox((0, 0), test_line, font=font)
                test_width = test_bbox[2] - test_bbox[0]
                
                if test_width <= resolution[0] - 100:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        lines.append(word)
            
            if current_line:
                lines.append(' '.join(current_line))
            
            # Рисуем многострочный текст
            total_text_height = len(lines) * text_height
            start_y = (resolution[1] - total_text_height) // 2
            
            for i, line in enumerate(lines):
                line_bbox = draw.textbbox((0, 0), line, font=font)
                line_width = line_bbox[2] - line_bbox[0]
                x = (resolution[0] - line_width) // 2
                y = start_y + i * text_height
                
                draw.text((x, y), line, fill=self._hex_to_rgb(style_config["text_color"]), font=font)
        else:
            # Рисуем одну строку по центру
            x = (resolution[0] - text_width) // 2
            y = (resolution[1] - text_height) // 2
            draw.text((x, y), text, fill=self._hex_to_rgb(style_config["text_color"]), font=font)
        
        # Сохраняем изображение
        image.save(output_path)
    
    async def _add_audio_to_video(self, video_path: str, audio_path: str) -> VideoResult:
        """Добавление аудиодорожки к видео"""
        def _add_audio():
            try:
                video_clip = VideoFileClip(video_path)
                audio_clip = AudioFileClip(audio_path)
                
                # Подгоняем аудио под длину видео
                if audio_clip.duration > video_clip.duration:
                    audio_clip = audio_clip.subclip(0, video_clip.duration)
                elif audio_clip.duration < video_clip.duration:
                    # Повторяем аудио если нужно
                    repeats = int(video_clip.duration / audio_clip.duration) + 1
                    audio_clips = [audio_clip] * repeats
                    audio_clip = concatenate_audioclips(audio_clips).subclip(0, video_clip.duration)
                
                # Комбинируем видео и аудио
                final_clip = video_clip.set_audio(audio_clip)
                
                # Создаём новый файл
                output_path = Path(video_path).with_stem(Path(video_path).stem + "_with_audio")
                final_clip.write_videofile(
                    str(output_path),
                    codec='libx264',
                    audio_codec='aac',
                    verbose=False,
                    logger=None
                )
                
                # Удаляем старый файл
                Path(video_path).unlink()
                
                return True, str(output_path), final_clip.duration, None
                
            except Exception as e:
                return False, video_path, None, str(e)
        
        loop = asyncio.get_event_loop()
        success, new_video_path, duration, error = await loop.run_in_executor(None, _add_audio)
        
        return VideoResult(
            request_id="audio_add",
            success=success,
            video_path=new_video_path,
            duration=duration,
            error=error
        )
    
    def _hex_to_rgb(self, hex_color: str) -> tuple:
        """Конвертация HEX в RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def get_available_styles(self) -> List[str]:
        """Получение доступных стилей"""
        return [style.value for style in VideoStyle]
    
    def get_supported_resolutions(self) -> List[tuple]:
        """Получение поддерживаемых разрешений"""
        return [
            (1080, 1920),  # Вертикальное для TikTok/Instagram
            (1920, 1080),  # Горизонтальное для YouTube
            (1080, 1080),  # Квадратное для Instagram
            (720, 1280),   # Вертикальное HD
            (1280, 720)    # Горизонтальное HD
        ]

# Singleton instance
_video_generator = None

def get_video_generator() -> VideoGenerator:
    """Получение singleton instance генератора видео"""
    global _video_generator
    if _video_generator is None:
        _video_generator = VideoGenerator()
    return _video_generator

# Упрощённая функция для генерации
async def generate_video(text: str, video_type: str = "animated_text", style: str = "modern",
                        duration: int = 30, resolution: tuple = (1080, 1920),
                        audio_path: Optional[str] = None) -> VideoResult:
    """
    Упрощённая функция для генерации видео
    
    Args:
        text: Текст для видео
        video_type: Тип видео (animated_text, image_slideshow, template_based)
        style: Стиль (modern, classic, minimal, colorful, dark)
        duration: Длительность в секундах
        resolution: Разрешение (width, height)
        audio_path: Путь к аудиофайлу
    
    Returns:
        VideoResult с результатом генерации
    """
    request = VideoRequest(
        id=str(uuid.uuid4()),
        type=VideoType(video_type),
        text=text,
        style=VideoStyle(style),
        duration=duration,
        resolution=resolution,
        audio_path=audio_path
    )
    
    generator = get_video_generator()
    return await generator.generate_video(request)

# Функция для получения информации о видео системе
async def get_video_info() -> Dict[str, Any]:
    """Получение информации о возможностях видео генерации"""
    generator = get_video_generator()
    
    return {
        "available_types": [vtype.value for vtype in VideoType],
        "available_styles": generator.get_available_styles(),
        "supported_resolutions": generator.get_supported_resolutions(),
        "default_duration": 30,
        "max_duration": 120,
        "supported_formats": ["mp4"],
        "fonts_available": len(generator.available_fonts) > 0
    }

if __name__ == "__main__":
    # Тестирование видео генератора
    async def test_video_generator():
        print("Тестирование генератора видео...")
        
        # Получаем информацию о системе
        info = await get_video_info()
        print("Доступные типы видео:", info['available_types'])
        print("Доступные стили:", info['available_styles'])
        print("Поддерживаемые разрешения:", info['supported_resolutions'])
        
        # Тестируем генерацию
        test_text = "Привет! Это демо видео системы EKOSYSTEMA_FULL. Мы создаём автоматический контент для социальных сетей."
        
        print(f"\nГенерируем тестовое видео...")
        result = await generate_video(
            text=test_text,
            video_type="animated_text",
            style="modern",
            duration=10
        )
        
        if result.success:
            print(f"✅ Видео создано успешно!")
            print(f"   Файл: {result.video_path}")
            print(f"   Размер: {result.file_size} байт")
            print(f"   Длительность: {result.duration:.2f}с")
            print(f"   Время генерации: {result.generation_time:.2f}с")
        else:
            print(f"❌ Ошибка: {result.error}")
    
    # Запуск теста
    asyncio.run(test_video_generator())