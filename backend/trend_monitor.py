"""
Система мониторинга трендов для EKOSYSTEMA_FULL
Автоматический поиск популярных тем для генерации контента
"""

import asyncio
import aiohttp
import feedparser
import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import quote_plus
import logging
from bs4 import BeautifulSoup
import random

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TrendData:
    """Структура данных тренда"""
    keyword: str
    title: str
    description: str
    source: str
    url: str
    popularity_score: float
    hashtags: List[str]
    discovered_at: datetime
    metadata: Dict

class TrendMonitor:
    """Основной класс для мониторинга трендов"""
    
    def __init__(self):
        self.target_keywords = [
            "telegram", "телеграм", "подарки", "боты", "bot", 
            "бесплатно", "криптовалюта", "заработок", "деньги",
            "giveaway", "gift", "crypto", "bitcoin", "free"
        ]
        
        self.trend_sources = {
            'youtube': True,
            'google_trends': True,
            'rss_feeds': True,
            'social_media': False  # Пока отключено
        }
        
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def monitor_all_sources(self) -> List[TrendData]:
        """Мониторинг всех источников трендов"""
        all_trends = []
        
        try:
            if self.trend_sources['youtube']:
                youtube_trends = await self.monitor_youtube_trends()
                all_trends.extend(youtube_trends)
                logger.info(f"Найдено {len(youtube_trends)} трендов с YouTube")
            
            if self.trend_sources['google_trends']:
                google_trends = await self.monitor_google_trends()
                all_trends.extend(google_trends)
                logger.info(f"Найдено {len(google_trends)} трендов с Google")
            
            if self.trend_sources['rss_feeds']:
                rss_trends = await self.monitor_rss_feeds()
                all_trends.extend(rss_trends)
                logger.info(f"Найдено {len(rss_trends)} трендов из RSS")
                
            # Фильтруем и ранжируем тренды
            filtered_trends = self.filter_and_rank_trends(all_trends)
            
            logger.info(f"Итого найдено {len(filtered_trends)} релевантных трендов")
            return filtered_trends
            
        except Exception as e:
            logger.error(f"Ошибка при мониторинге трендов: {e}")
            return []
    
    async def monitor_youtube_trends(self) -> List[TrendData]:
        """Мониторинг трендов YouTube через парсинг"""
        trends = []
        
        try:
            # Парсим YouTube trending через RSS (не требует API ключ)
            rss_url = "https://www.youtube.com/feeds/trending.xml"
            
            async with self.session.get(rss_url) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    
                    for entry in feed.entries[:20]:  # Берем топ-20
                        title = entry.title
                        description = getattr(entry, 'summary', '')
                        url = entry.link
                        
                        # Проверяем релевантность по ключевым словам
                        relevance_score = self.calculate_relevance_score(title + " " + description)
                        
                        if relevance_score > 0.3:  # Пороговое значение релевантности
                            hashtags = self.extract_hashtags(title + " " + description)
                            
                            trend = TrendData(
                                keyword=self.extract_main_keyword(title),
                                title=title,
                                description=description[:500],
                                source="youtube",
                                url=url,
                                popularity_score=relevance_score * random.uniform(0.7, 1.0),
                                hashtags=hashtags,
                                discovered_at=datetime.utcnow(),
                                metadata={
                                    'published': getattr(entry, 'published', ''),
                                    'author': getattr(entry, 'author', '')
                                }
                            )
                            trends.append(trend)
                            
        except Exception as e:
            logger.error(f"Ошибка при парсинге YouTube трендов: {e}")
        
        return trends
    
    async def monitor_google_trends(self) -> List[TrendData]:
        """Мониторинг Google Trends через RSS"""
        trends = []
        
        try:
            # Google Trends RSS для популярных поисковых запросов
            for keyword in self.target_keywords[:5]:  # Ограничиваем количество запросов
                encoded_keyword = quote_plus(keyword)
                rss_url = f"https://trends.google.com/trends/trendingsearches/daily/rss?geo=RU&hl=ru"
                
                try:
                    async with self.session.get(rss_url) as response:
                        if response.status == 200:
                            content = await response.text()
                            feed = feedparser.parse(content)
                            
                            for entry in feed.entries[:10]:
                                title = entry.title
                                description = getattr(entry, 'summary', '')
                                
                                # Проверяем релевантность
                                relevance_score = self.calculate_relevance_score(title + " " + description)
                                
                                if relevance_score > 0.2:
                                    hashtags = self.extract_hashtags(title + " " + description)
                                    
                                    trend = TrendData(
                                        keyword=self.extract_main_keyword(title),
                                        title=title,
                                        description=description[:500],
                                        source="google_trends",
                                        url=getattr(entry, 'link', ''),
                                        popularity_score=relevance_score * random.uniform(0.8, 1.0),
                                        hashtags=hashtags,
                                        discovered_at=datetime.utcnow(),
                                        metadata={
                                            'published': getattr(entry, 'published', ''),
                                            'search_volume': 'high'
                                        }
                                    )
                                    trends.append(trend)
                    
                    # Задержка между запросами
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.warning(f"Ошибка при получении трендов для '{keyword}': {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Ошибка при мониторинге Google Trends: {e}")
        
        return trends
    
    async def monitor_rss_feeds(self) -> List[TrendData]:
        """Мониторинг RSS лент технологических и криптовалютных сайтов"""
        trends = []
        
        # RSS ленты релевантных источников
        rss_sources = [
            "https://vc.ru/rss",
            "https://habr.com/ru/rss/hub/cryptocurrency/",
            "https://coindesk.com/arc/outboundfeeds/rss/",
            "https://cointelegraph.com/rss",
            "https://feeds.feedburner.com/techcrunch/startups",
        ]
        
        for rss_url in rss_sources:
            try:
                async with self.session.get(rss_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        feed = feedparser.parse(content)
                        
                        for entry in feed.entries[:15]:
                            title = entry.title
                            description = getattr(entry, 'summary', '')
                            
                            # Проверяем релевантность
                            relevance_score = self.calculate_relevance_score(title + " " + description)
                            
                            if relevance_score > 0.25:
                                hashtags = self.extract_hashtags(title + " " + description)
                                
                                trend = TrendData(
                                    keyword=self.extract_main_keyword(title),
                                    title=title,
                                    description=description[:500],
                                    source=f"rss_{rss_url.split('//')[1].split('/')[0]}",
                                    url=getattr(entry, 'link', ''),
                                    popularity_score=relevance_score * random.uniform(0.6, 0.9),
                                    hashtags=hashtags,
                                    discovered_at=datetime.utcnow(),
                                    metadata={
                                        'published': getattr(entry, 'published', ''),
                                        'source_domain': rss_url.split('//')[1].split('/')[0]
                                    }
                                )
                                trends.append(trend)
                
                # Задержка между источниками
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.warning(f"Ошибка при парсинге RSS {rss_url}: {e}")
                continue
        
        return trends
    
    def calculate_relevance_score(self, text: str) -> float:
        """Расчет релевантности текста по ключевым словам"""
        text_lower = text.lower()
        score = 0.0
        
        # Проверяем наличие целевых ключевых слов
        for keyword in self.target_keywords:
            if keyword.lower() in text_lower:
                # Бонус за точное совпадение
                if keyword.lower() == text_lower.strip():
                    score += 1.0
                # Бонус за наличие в заголовке
                elif keyword.lower() in text_lower[:100]:
                    score += 0.5
                else:
                    score += 0.3
        
        # Бонус за популярные финансовые/технологические термины
        bonus_terms = ['crypto', 'bitcoin', 'ethereum', 'nft', 'blockchain', 'ai', 'startup', 'tech']
        for term in bonus_terms:
            if term in text_lower:
                score += 0.2
        
        return min(score, 1.0)  # Ограничиваем максимальный скор
    
    def extract_hashtags(self, text: str) -> List[str]:
        """Извлечение хештегов из текста"""
        hashtags = re.findall(r'#\w+', text, re.UNICODE)
        
        # Если хештегов нет, создаем на основе ключевых слов
        if not hashtags:
            words = re.findall(r'\b[а-яёa-z]+\b', text.lower(), re.UNICODE)
            relevant_words = [word for word in words if word in self.target_keywords]
            hashtags = [f"#{word}" for word in relevant_words[:3]]
        
        return hashtags[:5]  # Максимум 5 хештегов
    
    def extract_main_keyword(self, title: str) -> str:
        """Извлечение основного ключевого слова из заголовка"""
        title_lower = title.lower()
        
        # Ищем первое совпадение с целевыми ключевыми словами
        for keyword in self.target_keywords:
            if keyword.lower() in title_lower:
                return keyword
        
        # Если не найдено, берем первое значимое слово
        words = re.findall(r'\b[а-яёa-z]{3,}\b', title_lower, re.UNICODE)
        return words[0] if words else "trending"
    
    def filter_and_rank_trends(self, trends: List[TrendData]) -> List[TrendData]:
        """Фильтрация и ранжирование трендов"""
        # Удаляем дубликаты по заголовку
        unique_trends = {}
        for trend in trends:
            key = trend.title.lower()[:50]  # Первые 50 символов как ключ
            if key not in unique_trends or trend.popularity_score > unique_trends[key].popularity_score:
                unique_trends[key] = trend
        
        # Сортируем по популярности
        sorted_trends = sorted(unique_trends.values(), key=lambda x: x.popularity_score, reverse=True)
        
        # Возвращаем топ-30 трендов
        return sorted_trends[:30]

class TrendAnalyzer:
    """Анализатор трендов для выделения идей контента"""
    
    @staticmethod
    def analyze_trends_for_content(trends: List[TrendData]) -> List[Dict]:
        """Анализ трендов для создания идей контента"""
        content_ideas = []
        
        for trend in trends:
            # Генерируем идеи контента на основе тренда
            ideas = TrendAnalyzer.generate_content_ideas(trend)
            content_ideas.extend(ideas)
        
        return content_ideas[:20]  # Топ-20 идей
    
    @staticmethod
    def generate_content_ideas(trend: TrendData) -> List[Dict]:
        """Генерация идей контента на основе тренда"""
        ideas = []
        
        # Шаблоны для разных типов контента
        video_templates = [
            f"Как использовать {trend.keyword} для получения подарков в Telegram",
            f"Топ-5 {trend.keyword} ботов для бесплатных подарков",
            f"Секреты заработка с {trend.keyword} в 2025 году",
            f"{trend.keyword}: Новые возможности для пользователей Telegram"
        ]
        
        text_templates = [
            f"Подробный гид по {trend.keyword} в Telegram",
            f"Как {trend.keyword} изменит мир подарков в мессенджерах",
            f"Личный опыт: Мой успех с {trend.keyword}"
        ]
        
        # Создаем идеи видео
        for template in video_templates[:2]:
            ideas.append({
                'type': 'video',
                'title': template,
                'description': f"Видео на основе тренда: {trend.title}",
                'keywords': [trend.keyword] + trend.hashtags,
                'source_trend': trend.title,
                'estimated_popularity': trend.popularity_score * 0.8,
                'platforms': ['tiktok', 'youtube', 'telegram']
            })
        
        # Создаем идеи текстовых постов
        for template in text_templates[:1]:
            ideas.append({
                'type': 'text',
                'title': template,
                'description': f"Пост на основе тренда: {trend.title}",
                'keywords': [trend.keyword] + trend.hashtags,
                'source_trend': trend.title,
                'estimated_popularity': trend.popularity_score * 0.6,
                'platforms': ['telegram']
            })
        
        return ideas

# Функция для запуска мониторинга (будет использоваться в Celery задачах)
async def run_trend_monitoring() -> Dict:
    """Запуск мониторинга трендов"""
    try:
        async with TrendMonitor() as monitor:
            trends = await monitor.monitor_all_sources()
            
            # Анализируем тренды для создания контента
            content_ideas = TrendAnalyzer.analyze_trends_for_content(trends)
            
            return {
                'success': True,
                'trends_found': len(trends),
                'content_ideas': len(content_ideas),
                'trends': [
                    {
                        'keyword': trend.keyword,
                        'title': trend.title,
                        'source': trend.source,
                        'score': trend.popularity_score,
                        'hashtags': trend.hashtags,
                        'discovered_at': trend.discovered_at.isoformat()
                    }
                    for trend in trends
                ],
                'content_ideas': content_ideas
            }
    except Exception as e:
        logger.error(f"Ошибка при мониторинге трендов: {e}")
        return {
            'success': False,
            'error': str(e),
            'trends_found': 0,
            'content_ideas': 0
        }

# Тестовая функция
if __name__ == "__main__":
    async def test_trends():
        result = await run_trend_monitoring()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    asyncio.run(test_trends())