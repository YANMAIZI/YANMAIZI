"""
TTS (Text-to-Speech) модуль для EKOSYSTEMA_FULL
Поддерживает несколько TTS движков для генерации аудио контента
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import uuid
import tempfile

# TTS библиотеки
import pyttsx3
from gtts import gTTS
import threading
import queue

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TTSEngine(str, Enum):
    """Доступные TTS движки"""
    PYTTSX3 = "pyttsx3"  # Локальный TTS
    GTTS = "gtts"        # Google TTS (требует интернет)
    COQUI = "coqui"      # Coqui TTS (высокое качество)

class TTSVoice(str, Enum):
    """Типы голосов"""
    MALE = "male"
    FEMALE = "female"
    CHILD = "child"

@dataclass
class TTSRequest:
    """Структура запроса на TTS генерацию"""
    id: str
    text: str
    engine: TTSEngine
    voice: TTSVoice
    language: str = "ru"
    speed: float = 1.0
    output_path: Optional[str] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

@dataclass
class TTSResult:
    """Результат TTS генерации"""
    request_id: str
    success: bool
    audio_path: Optional[str] = None
    duration: Optional[float] = None
    file_size: Optional[int] = None
    error: Optional[str] = None
    engine_used: Optional[str] = None
    generation_time: Optional[float] = None

class TTSGenerator:
    """Основной класс для генерации TTS"""
    
    def __init__(self, default_engine: TTSEngine = TTSEngine.PYTTSX3):
        self.default_engine = default_engine
        self.audio_dir = Path(__file__).parent / "generated_audio"
        self.audio_dir.mkdir(exist_ok=True)
        
        # Настройки для разных движков
        self.engine_settings = {
            TTSEngine.PYTTSX3: {
                "rate": 150,  # Скорость речи
                "volume": 0.9  # Громкость
            },
            TTSEngine.GTTS: {
                "slow": False,
                "lang": "ru"
            },
            TTSEngine.COQUI: {
                "model_name": "tts_models/ru/fairseq/vits",  # Если доступно
                "gpu": False
            }
        }
        
        # Инициализация pyttsx3
        self._init_pyttsx3()
        
        # Проверка доступности Coqui TTS
        self.coqui_available = self._check_coqui_availability()
        
    def _init_pyttsx3(self):
        """Инициализация pyttsx3 движка"""
        try:
            # pyttsx3 работает только в основном потоке, поэтому используем очередь
            self.pyttsx3_available = True
        except Exception as e:
            logger.warning(f"pyttsx3 недоступен: {e}")
            self.pyttsx3_available = False
    
    def _check_coqui_availability(self) -> bool:
        """Проверка доступности Coqui TTS"""
        try:
            from TTS.api import TTS
            return True
        except ImportError:
            logger.warning("Coqui TTS не установлен")
            return False
        except Exception as e:
            logger.warning(f"Ошибка при проверке Coqui TTS: {e}")
            return False
    
    def get_available_engines(self) -> List[str]:
        """Получение списка доступных TTS движков"""
        engines = []
        
        if self.pyttsx3_available:
            engines.append(TTSEngine.PYTTSX3.value)
        
        # gTTS всегда доступен (при наличии интернета)
        engines.append(TTSEngine.GTTS.value)
        
        if self.coqui_available:
            engines.append(TTSEngine.COQUI.value)
            
        return engines
    
    def get_available_voices(self, engine: TTSEngine) -> List[Dict[str, str]]:
        """Получение доступных голосов для движка"""
        if engine == TTSEngine.PYTTSX3:
            return self._get_pyttsx3_voices()
        elif engine == TTSEngine.GTTS:
            return [
                {"id": "ru-female", "name": "Russian Female", "lang": "ru"},
                {"id": "en-female", "name": "English Female", "lang": "en"},
                {"id": "en-male", "name": "English Male", "lang": "en"}
            ]
        elif engine == TTSEngine.COQUI:
            return self._get_coqui_voices()
        return []
    
    def _get_pyttsx3_voices(self) -> List[Dict[str, str]]:
        """Получение голосов pyttsx3"""
        voices = []
        try:
            engine = pyttsx3.init()
            system_voices = engine.getProperty('voices')
            for voice in system_voices:
                voices.append({
                    "id": voice.id,
                    "name": voice.name,
                    "lang": getattr(voice, 'languages', ['ru'])[0] if hasattr(voice, 'languages') else 'ru'
                })
            engine.stop()
        except Exception as e:
            logger.error(f"Ошибка при получении голосов pyttsx3: {e}")
        return voices
    
    def _get_coqui_voices(self) -> List[Dict[str, str]]:
        """Получение голосов Coqui TTS"""
        voices = []
        if self.coqui_available:
            try:
                from TTS.api import TTS
                # Получаем список моделей
                voices.append({
                    "id": "coqui-ru-female",
                    "name": "Coqui Russian Female",
                    "lang": "ru"
                })
            except Exception as e:
                logger.error(f"Ошибка при получении голосов Coqui: {e}")
        return voices
    
    async def generate_audio(self, request: TTSRequest) -> TTSResult:
        """Основной метод генерации аудио"""
        start_time = datetime.utcnow()
        
        try:
            # Определяем путь к выходному файлу
            if not request.output_path:
                filename = f"tts_{request.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                output_path = self.audio_dir / filename
            else:
                output_path = Path(request.output_path)
            
            # Генерируем аудио в зависимости от движка
            if request.engine == TTSEngine.PYTTSX3:
                result = await self._generate_pyttsx3(request, output_path)
            elif request.engine == TTSEngine.GTTS:
                result = await self._generate_gtts(request, output_path)
            elif request.engine == TTSEngine.COQUI:
                result = await self._generate_coqui(request, output_path)
            else:
                return TTSResult(
                    request_id=request.id,
                    success=False,
                    error=f"Неподдерживаемый движок: {request.engine}"
                )
            
            # Вычисляем время генерации
            generation_time = (datetime.utcnow() - start_time).total_seconds()
            result.generation_time = generation_time
            result.engine_used = request.engine.value
            
            logger.info(f"TTS генерация завершена за {generation_time:.2f}с: {output_path}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при генерации TTS: {e}")
            return TTSResult(
                request_id=request.id,
                success=False,
                error=str(e)
            )
    
    async def _generate_pyttsx3(self, request: TTSRequest, output_path: Path) -> TTSResult:
        """Генерация через pyttsx3"""
        def _generate_in_thread():
            try:
                engine = pyttsx3.init()
                
                # Настройки голоса
                voices = engine.getProperty('voices')
                if voices:
                    # Выбираем голос (простая логика)
                    voice_index = 0 if request.voice == TTSVoice.MALE else 1
                    if voice_index < len(voices):
                        engine.setProperty('voice', voices[voice_index].id)
                
                # Настройки скорости и громкости
                settings = self.engine_settings[TTSEngine.PYTTSX3]
                engine.setProperty('rate', int(settings['rate'] * request.speed))
                engine.setProperty('volume', settings['volume'])
                
                # Сохраняем в файл
                engine.save_to_file(request.text, str(output_path))
                engine.runAndWait()
                engine.stop()
                
                return True, None
            except Exception as e:
                return False, str(e)
        
        # Запускаем в отдельном потоке (pyttsx3 требование)
        loop = asyncio.get_event_loop()
        success, error = await loop.run_in_executor(None, _generate_in_thread)
        
        if success and output_path.exists():
            file_size = output_path.stat().st_size
            return TTSResult(
                request_id=request.id,
                success=True,
                audio_path=str(output_path),
                file_size=file_size
            )
        else:
            return TTSResult(
                request_id=request.id,
                success=False,
                error=error or "Не удалось создать файл"
            )
    
    async def _generate_gtts(self, request: TTSRequest, output_path: Path) -> TTSResult:
        """Генерация через Google TTS"""
        def _generate():
            try:
                settings = self.engine_settings[TTSEngine.GTTS]
                tts = gTTS(
                    text=request.text,
                    lang=request.language,
                    slow=settings['slow']
                )
                
                # Создаем временный файл, так как gTTS сохраняет только в MP3
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                    temp_path = temp_file.name
                    tts.save(temp_path)
                
                # Конвертируем MP3 в WAV если необходимо
                if output_path.suffix.lower() == '.wav':
                    # Простое переименование для тестирования
                    final_path = output_path.with_suffix('.mp3')
                    # Используем shutil для корректного перемещения файла
                    import shutil
                    shutil.move(temp_path, str(final_path))
                else:
                    import shutil
                    shutil.move(temp_path, str(output_path))
                    final_path = output_path
                
                return True, str(final_path), None
            except Exception as e:
                return False, None, str(e)
        
        # Запускаем в executor
        loop = asyncio.get_event_loop()
        success, file_path, error = await loop.run_in_executor(None, _generate)
        
        if success and Path(file_path).exists():
            file_size = Path(file_path).stat().st_size
            return TTSResult(
                request_id=request.id,
                success=True,
                audio_path=file_path,
                file_size=file_size
            )
        else:
            return TTSResult(
                request_id=request.id,
                success=False,
                error=error
            )
    
    async def _generate_coqui(self, request: TTSRequest, output_path: Path) -> TTSResult:
        """Генерация через Coqui TTS"""
        if not self.coqui_available:
            return TTSResult(
                request_id=request.id,
                success=False,
                error="Coqui TTS не доступен"
            )
        
        def _generate():
            try:
                from TTS.api import TTS
                
                settings = self.engine_settings[TTSEngine.COQUI]
                
                # Инициализация модели
                tts = TTS(
                    model_name=settings['model_name'],
                    progress_bar=False,
                    gpu=settings['gpu']
                )
                
                # Генерация
                tts.tts_to_file(
                    text=request.text,
                    file_path=str(output_path)
                )
                
                return True, None
            except Exception as e:
                return False, str(e)
        
        # Запускаем в executor
        loop = asyncio.get_event_loop()
        success, error = await loop.run_in_executor(None, _generate)
        
        if success and output_path.exists():
            file_size = output_path.stat().st_size
            return TTSResult(
                request_id=request.id,
                success=True,
                audio_path=str(output_path),
                file_size=file_size
            )
        else:
            return TTSResult(
                request_id=request.id,
                success=False,
                error=error
            )

# Singleton instance
_tts_generator = None

def get_tts_generator() -> TTSGenerator:
    """Получение singleton instance TTS генератора"""
    global _tts_generator
    if _tts_generator is None:
        _tts_generator = TTSGenerator()
    return _tts_generator

# Функция-обёртка для использования в других модулях
async def generate_tts(text: str, engine: str = "pyttsx3", voice: str = "female", 
                      language: str = "ru", speed: float = 1.0, 
                      output_path: Optional[str] = None) -> TTSResult:
    """
    Упрощённая функция для генерации TTS
    
    Args:
        text: Текст для озвучки
        engine: TTS движок (pyttsx3, gtts, coqui)
        voice: Тип голоса (male, female)
        language: Язык (ru, en)
        speed: Скорость речи (0.5-2.0)
        output_path: Путь к выходному файлу (опционально)
    
    Returns:
        TTSResult с результатом генерации
    """
    request = TTSRequest(
        id=str(uuid.uuid4()),
        text=text,
        engine=TTSEngine(engine),
        voice=TTSVoice(voice),
        language=language,
        speed=speed,
        output_path=output_path
    )
    
    generator = get_tts_generator()
    return await generator.generate_audio(request)

# Функция для получения информации о TTS системе
async def get_tts_info() -> Dict[str, Any]:
    """Получение информации о доступных TTS возможностях"""
    generator = get_tts_generator()
    
    return {
        "available_engines": generator.get_available_engines(),
        "engine_voices": {
            engine: generator.get_available_voices(TTSEngine(engine))
            for engine in generator.get_available_engines()
        },
        "supported_languages": ["ru", "en"],
        "audio_formats": ["wav", "mp3"],
        "coqui_available": generator.coqui_available,
        "pyttsx3_available": generator.pyttsx3_available
    }

if __name__ == "__main__":
    # Тестирование TTS модуля
    async def test_tts():
        print("Тестирование TTS модуля...")
        
        # Получаем информацию о системе
        info = await get_tts_info()
        print("Доступные движки:", info['available_engines'])
        
        # Тестируем генерацию
        test_text = "Привет! Это тест системы синтеза речи для EKOSYSTEMA_FULL."
        
        for engine in info['available_engines']:
            print(f"\nТестируем движок {engine}...")
            result = await generate_tts(
                text=test_text,
                engine=engine,
                voice="female"
            )
            
            if result.success:
                print(f"✅ Успех! Файл: {result.audio_path}")
                print(f"   Размер: {result.file_size} байт")
                print(f"   Время: {result.generation_time:.2f}с")
            else:
                print(f"❌ Ошибка: {result.error}")
    
    # Запуск теста
    asyncio.run(test_tts())