#!/usr/bin/env python3
"""
Backend Test Suite for EKOSYSTEMA_FULL Video Generation System
Tests Video API endpoints, functionality, and integration with task system
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

import requests
from dotenv import load_dotenv

# Add backend to path for imports
sys.path.append('/app/backend')

# Load environment variables
load_dotenv('/app/frontend/.env')
BACKEND_URL = os.getenv('REACT_APP_BACKEND_URL', 'http://localhost:8001')
API_BASE = f"{BACKEND_URL}/api"

class VideoTestSuite:
    """Test suite for Video Generation module functionality"""
    
    def __init__(self):
        self.api_base = API_BASE
        self.test_results = []
        self.created_content_ids = []
        self.created_task_ids = []
        
    def log_result(self, test_name: str, success: bool, message: str, details: Dict = None):
        """Log test result"""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "details": details or {}
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        if details:
            print(f"    Details: {details}")
    
    def test_api_connectivity(self) -> bool:
        """Test basic API connectivity"""
        try:
            response = requests.get(f"{self.api_base}/", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log_result("API Connectivity", True, f"API accessible: {data.get('message', 'OK')}")
                return True
            else:
                self.log_result("API Connectivity", False, f"API returned status {response.status_code}")
                return False
        except Exception as e:
            self.log_result("API Connectivity", False, f"Failed to connect to API: {str(e)}")
            return False
    
    def test_video_info_endpoint(self) -> bool:
        """Test GET /api/video/info endpoint"""
        try:
            response = requests.get(f"{self.api_base}/video/info", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check response structure
                if data.get('success') and 'data' in data:
                    video_info = data['data']
                    required_fields = ['available_types', 'available_styles', 'supported_resolutions']
                    
                    missing_fields = [field for field in required_fields if field not in video_info]
                    if missing_fields:
                        self.log_result("Video Info Endpoint", False, f"Missing fields: {missing_fields}")
                        return False
                    
                    # Check if video types are available
                    types = video_info.get('available_types', [])
                    if not types:
                        self.log_result("Video Info Endpoint", False, "No video types available")
                        return False
                    
                    self.log_result("Video Info Endpoint", True, f"Video info retrieved successfully", {
                        "types": types,
                        "styles": video_info.get('available_styles', []),
                        "resolutions": video_info.get('supported_resolutions', []),
                        "fonts_available": video_info.get('fonts_available', False)
                    })
                    return True
                else:
                    self.log_result("Video Info Endpoint", False, "Invalid response structure")
                    return False
            else:
                self.log_result("Video Info Endpoint", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("Video Info Endpoint", False, f"Request failed: {str(e)}")
            return False
    
    def test_video_generate_endpoint(self, text: str, video_type: str = "animated_text", 
                                   style: str = "modern", resolution: str = "1080x1920") -> Dict[str, Any]:
        """Test POST /api/video/generate endpoint"""
        try:
            payload = {
                "text": text,
                "video_type": video_type,
                "style": style,
                "duration": 15,  # Shorter for testing
                "resolution": resolution
            }
            
            start_time = time.time()
            response = requests.post(f"{self.api_base}/video/generate", json=payload, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success') and 'task_id' in data:
                    task_id = data['task_id']
                    self.created_task_ids.append(task_id)
                    
                    # Wait for task completion and check status
                    task_result = self.wait_for_task_completion(task_id, timeout=90)
                    
                    generation_time = time.time() - start_time
                    
                    if task_result and task_result.get('success'):
                        self.log_result(f"Video Generate ({video_type}, {style})", True, 
                                      f"Video generated successfully in {generation_time:.2f}s", {
                                          "task_id": task_id,
                                          "video_path": task_result.get('video_path'),
                                          "file_size": task_result.get('file_size'),
                                          "duration": task_result.get('duration'),
                                          "resolution": task_result.get('resolution')
                                      })
                        return {"success": True, "task_id": task_id, "result": task_result}
                    else:
                        error_msg = task_result.get('error', 'Task failed') if task_result else 'Task timeout'
                        self.log_result(f"Video Generate ({video_type}, {style})", False, error_msg)
                        return {"success": False, "error": error_msg}
                else:
                    self.log_result(f"Video Generate ({video_type}, {style})", False, "Invalid response structure")
                    return {"success": False, "error": "Invalid response"}
            else:
                self.log_result(f"Video Generate ({video_type}, {style})", False, 
                              f"HTTP {response.status_code}: {response.text}")
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            self.log_result(f"Video Generate ({video_type}, {style})", False, f"Request failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def wait_for_task_completion(self, task_id: str, timeout: int = 90) -> Dict[str, Any]:
        """Wait for task completion and return result"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self.api_base}/tasks/{task_id}", timeout=10)
                
                if response.status_code == 200:
                    task_data = response.json()
                    status = task_data.get('status', 'unknown')
                    
                    if status == 'completed':
                        # Get full task details
                        tasks_response = requests.get(f"{self.api_base}/tasks", timeout=10)
                        if tasks_response.status_code == 200:
                            tasks = tasks_response.json()
                            for task in tasks:
                                if task.get('id') == task_id:
                                    result = task.get('result', {})
                                    return {"success": True, **result}
                        return {"success": True}
                    elif status == 'failed':
                        return {"success": False, "error": task_data.get('message', 'Task failed')}
                    elif status in ['pending', 'running']:
                        time.sleep(2)  # Longer wait for video generation
                        continue
                    else:
                        return {"success": False, "error": f"Unknown status: {status}"}
                else:
                    return {"success": False, "error": f"Failed to get task status: {response.status_code}"}
                    
            except Exception as e:
                return {"success": False, "error": f"Error checking task status: {str(e)}"}
        
        return {"success": False, "error": "Task timeout"}
    
    def test_content_creation_and_video(self) -> bool:
        """Test content creation and video generation for content"""
        try:
            # Create test content
            content_payload = {
                "type": "video",
                "title": "Тест видео генерации для контента",
                "topic": "telegram боты подарки",
                "description": "Telegram боты для получения подарков - это современный способ монетизации контента. Пользователи могут получать различные призы и бонусы.",
                "keywords": ["telegram", "боты", "подарки"],
                "target_platforms": ["telegram", "tiktok"]
            }
            
            response = requests.post(f"{self.api_base}/content", json=content_payload, timeout=15)
            
            if response.status_code != 200:
                self.log_result("Content Creation for Video", False, f"Failed to create content: {response.status_code}")
                return False
            
            content_data = response.json()
            if not content_data.get('success'):
                self.log_result("Content Creation for Video", False, "Content creation failed")
                return False
            
            content_id = content_data['content_id']
            self.created_content_ids.append(content_id)
            
            # Generate video for the content
            video_params = {
                "video_type": "animated_text",
                "style": "modern",
                "duration": 15,
                "resolution": "1080x1920"
            }
            
            start_time = time.time()
            video_response = requests.post(f"{self.api_base}/content/{content_id}/generate_video", 
                                         json=video_params, timeout=60)
            
            if video_response.status_code == 200:
                video_data = video_response.json()
                
                if video_data.get('success') and 'task_id' in video_data:
                    task_id = video_data['task_id']
                    self.created_task_ids.append(task_id)
                    
                    # Wait for video completion
                    task_result = self.wait_for_task_completion(task_id, timeout=90)
                    generation_time = time.time() - start_time
                    
                    if task_result and task_result.get('success'):
                        # Verify content was updated with video_path
                        content_response = requests.get(f"{self.api_base}/content/{content_id}", timeout=10)
                        if content_response.status_code == 200:
                            updated_content = content_response.json()
                            video_path = updated_content.get('video_path')
                            
                            if video_path:
                                self.log_result("Content Video Generation", True, 
                                              f"Video generated and linked to content in {generation_time:.2f}s", {
                                                  "content_id": content_id,
                                                  "task_id": task_id,
                                                  "video_path": video_path,
                                                  "file_size": task_result.get('file_size')
                                              })
                                return True
                            else:
                                self.log_result("Content Video Generation", False, 
                                              "Video generated but content not updated with video_path")
                                return False
                        else:
                            self.log_result("Content Video Generation", False, 
                                          "Failed to verify content update")
                            return False
                    else:
                        error_msg = task_result.get('error', 'Task failed') if task_result else 'Task timeout'
                        self.log_result("Content Video Generation", False, error_msg)
                        return False
                else:
                    self.log_result("Content Video Generation", False, "Invalid video response structure")
                    return False
            else:
                self.log_result("Content Video Generation", False, 
                              f"Video request failed: {video_response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Content Video Generation", False, f"Test failed: {str(e)}")
            return False
    
    def test_video_different_styles_and_types(self) -> bool:
        """Test video generation with different styles and types"""
        test_cases = [
            {
                "text": "Привет! Это тест видео системы EKOSYSTEMA_FULL с современным стилем.",
                "video_type": "animated_text",
                "style": "modern",
                "resolution": "1080x1920"
            },
            {
                "text": "Классический стиль видео для YouTube контента.",
                "video_type": "animated_text", 
                "style": "classic",
                "resolution": "1920x1080"
            },
            {
                "text": "Минималистичное видео для Instagram.",
                "video_type": "image_slideshow",
                "style": "minimal",
                "resolution": "1080x1080"
            }
        ]
        
        all_passed = True
        
        for i, test_case in enumerate(test_cases):
            result = self.test_video_generate_endpoint(
                text=test_case["text"],
                video_type=test_case["video_type"],
                style=test_case["style"],
                resolution=test_case["resolution"]
            )
            
            if not result.get("success"):
                all_passed = False
        
        return all_passed
    
    def test_video_with_russian_text(self) -> bool:
        """Test video generation with Russian text"""
        russian_texts = [
            "Привет! Добро пожаловать в мир Telegram ботов для получения подарков!",
            "Как получить бесплатные подарки через Telegram боты? Очень просто!",
            "Топ-5 лучших Telegram ботов для получения подарков в 2024 году."
        ]
        
        all_passed = True
        
        for i, text in enumerate(russian_texts):
            result = self.test_video_generate_endpoint(
                text=text,
                video_type="animated_text",
                style="colorful",
                resolution="1080x1920"
            )
            
            if not result.get("success"):
                all_passed = False
        
        return all_passed
    
    def test_video_file_creation(self) -> bool:
        """Test that video files are actually created in the correct directory"""
        try:
            video_dir = Path("/app/backend/generated_videos")
            
            # Check if directory exists
            if not video_dir.exists():
                self.log_result("Video Directory Check", False, "Generated videos directory does not exist")
                return False
            
            # Count existing files before test
            existing_files = list(video_dir.glob("*.mp4"))
            initial_count = len(existing_files)
            
            # Generate a test video
            result = self.test_video_generate_endpoint(
                "Тест создания видеофайла", 
                "animated_text", 
                "modern",
                "1080x1920"
            )
            
            if result.get("success"):
                # Check if new files were created
                new_files = list(video_dir.glob("*.mp4"))
                new_count = len(new_files)
                
                if new_count > initial_count:
                    # Find the newest file
                    newest_file = max(new_files, key=lambda f: f.stat().st_mtime)
                    file_size = newest_file.stat().st_size
                    
                    self.log_result("Video File Creation", True, 
                                  f"Video file created successfully", {
                                      "file_path": str(newest_file),
                                      "file_size": file_size,
                                      "files_before": initial_count,
                                      "files_after": new_count
                                  })
                    return True
                else:
                    self.log_result("Video File Creation", False, 
                                  "Video generation succeeded but no new video file found")
                    return False
            else:
                self.log_result("Video File Creation", False, 
                              "Video generation failed, cannot test file creation")
                return False
                
        except Exception as e:
            self.log_result("Video File Creation", False, f"Test failed: {str(e)}")
            return False
    
    def test_video_task_system_integration(self) -> bool:
        """Test integration with task system"""
        try:
            # Get initial task count
            response = requests.get(f"{self.api_base}/tasks", timeout=10)
            if response.status_code != 200:
                self.log_result("Video Task System Integration", False, "Failed to get initial task list")
                return False
            
            initial_tasks = response.json()
            initial_count = len(initial_tasks)
            
            # Create a video task
            result = self.test_video_generate_endpoint(
                "Тест интеграции с системой задач", 
                "animated_text", 
                "dark",
                "1080x1920"
            )
            
            if result.get("success"):
                task_id = result["task_id"]
                
                # Verify task appears in task list
                response = requests.get(f"{self.api_base}/tasks", timeout=10)
                if response.status_code == 200:
                    current_tasks = response.json()
                    
                    # Find our task
                    our_task = None
                    for task in current_tasks:
                        if task.get('id') == task_id:
                            our_task = task
                            break
                    
                    if our_task:
                        # Check task properties
                        if (our_task.get('type') == 'video_generation' and 
                            our_task.get('status') == 'completed'):
                            
                            self.log_result("Video Task System Integration", True, 
                                          "Video task properly integrated with task system", {
                                              "task_id": task_id,
                                              "task_type": our_task.get('type'),
                                              "task_status": our_task.get('status'),
                                              "has_result": bool(our_task.get('result'))
                                          })
                            return True
                        else:
                            self.log_result("Video Task System Integration", False, 
                                          f"Task found but incorrect properties: type={our_task.get('type')}, status={our_task.get('status')}")
                            return False
                    else:
                        self.log_result("Video Task System Integration", False, 
                                      "Video task not found in task list")
                        return False
                else:
                    self.log_result("Video Task System Integration", False, 
                                  "Failed to get updated task list")
                    return False
            else:
                self.log_result("Video Task System Integration", False, 
                              "Video generation failed, cannot test task integration")
                return False
                
        except Exception as e:
            self.log_result("Video Task System Integration", False, f"Test failed: {str(e)}")
            return False
    
    def test_video_with_tts_integration(self) -> bool:
        """Test video generation with TTS audio integration"""
        try:
            # First create TTS audio
            tts_payload = {
                "text": "Это тест интеграции TTS с видео генерацией",
                "engine": "gtts",
                "voice": "female",
                "language": "ru",
                "speed": 1.0
            }
            
            tts_response = requests.post(f"{self.api_base}/tts/generate", json=tts_payload, timeout=30)
            
            if tts_response.status_code == 200:
                tts_data = tts_response.json()
                
                if tts_data.get('success') and 'task_id' in tts_data:
                    tts_task_id = tts_data['task_id']
                    self.created_task_ids.append(tts_task_id)
                    
                    # Wait for TTS completion
                    tts_result = self.wait_for_task_completion(tts_task_id, timeout=30)
                    
                    if tts_result and tts_result.get('success'):
                        audio_path = tts_result.get('audio_path')
                        
                        if audio_path:
                            # Now generate video with this audio
                            video_payload = {
                                "text": "Это тест интеграции TTS с видео генерацией",
                                "video_type": "animated_text",
                                "style": "modern",
                                "duration": 15,
                                "resolution": "1080x1920",
                                "audio_path": audio_path
                            }
                            
                            video_response = requests.post(f"{self.api_base}/video/generate", 
                                                         json=video_payload, timeout=60)
                            
                            if video_response.status_code == 200:
                                video_data = video_response.json()
                                
                                if video_data.get('success') and 'task_id' in video_data:
                                    video_task_id = video_data['task_id']
                                    self.created_task_ids.append(video_task_id)
                                    
                                    # Wait for video completion
                                    video_result = self.wait_for_task_completion(video_task_id, timeout=90)
                                    
                                    if video_result and video_result.get('success'):
                                        self.log_result("Video with TTS Integration", True, 
                                                      "Video with TTS audio generated successfully", {
                                                          "tts_task_id": tts_task_id,
                                                          "video_task_id": video_task_id,
                                                          "audio_path": audio_path,
                                                          "video_path": video_result.get('video_path')
                                                      })
                                        return True
                                    else:
                                        self.log_result("Video with TTS Integration", False, 
                                                      "Video generation with TTS failed")
                                        return False
                                else:
                                    self.log_result("Video with TTS Integration", False, 
                                                  "Invalid video response structure")
                                    return False
                            else:
                                self.log_result("Video with TTS Integration", False, 
                                              f"Video request failed: {video_response.status_code}")
                                return False
                        else:
                            self.log_result("Video with TTS Integration", False, 
                                          "TTS completed but no audio path returned")
                            return False
                    else:
                        self.log_result("Video with TTS Integration", False, 
                                      "TTS generation failed")
                        return False
                else:
                    self.log_result("Video with TTS Integration", False, 
                                  "Invalid TTS response structure")
                    return False
            else:
                self.log_result("Video with TTS Integration", False, 
                              f"TTS request failed: {tts_response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Video with TTS Integration", False, f"Test failed: {str(e)}")
            return False
    
    def cleanup_test_data(self):
        """Clean up created test data"""
        print("\n🧹 Cleaning up test data...")
        
        # Note: In a real cleanup, we might delete created content and tasks
        # For now, we'll just log what was created
        if self.created_content_ids:
            print(f"Created content IDs: {self.created_content_ids}")
        
        if self.created_task_ids:
            print(f"Created task IDs: {self.created_task_ids}")
    
    def run_all_tests(self):
        """Run all Video tests"""
        print("🚀 Starting EKOSYSTEMA_FULL Video Generation System Test Suite")
        print(f"🔗 Testing against: {self.api_base}")
        print("=" * 60)
        
        # Test basic connectivity first
        if not self.test_api_connectivity():
            print("❌ API connectivity failed. Stopping tests.")
            return False
        
        # Run all video tests
        tests = [
            ("Video Info Endpoint", self.test_video_info_endpoint),
            ("Video Different Styles/Types", self.test_video_different_styles_and_types),
            ("Video with Russian Text", self.test_video_with_russian_text),
            ("Video File Creation", self.test_video_file_creation),
            ("Content Creation and Video", self.test_content_creation_and_video),
            ("Video Task System Integration", self.test_video_task_system_integration),
            ("Video with TTS Integration", self.test_video_with_tts_integration),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n📋 Running: {test_name}")
            try:
                if test_func():
                    passed += 1
            except Exception as e:
                self.log_result(test_name, False, f"Test threw exception: {str(e)}")
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 TEST SUMMARY: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All Video tests passed!")
        else:
            print(f"⚠️  {total - passed} tests failed")
        
        # Cleanup
        self.cleanup_test_data()
        
        return passed == total

def main():
    """Main test runner"""
    test_suite = VideoTestSuite()
    success = test_suite.run_all_tests()
    
    # Print detailed results
    print("\n" + "=" * 60)
    print("📋 DETAILED TEST RESULTS:")
    print("=" * 60)
    
    for result in test_suite.test_results:
        status = "✅" if result["success"] else "❌"
        print(f"{status} {result['test']}: {result['message']}")
        if result["details"]:
            for key, value in result["details"].items():
                print(f"    {key}: {value}")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())