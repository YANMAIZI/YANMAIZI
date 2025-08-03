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

class TTSTestSuite:
    """Test suite for TTS module functionality"""
    
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
    
    def test_tts_info_endpoint(self) -> bool:
        """Test GET /api/tts/info endpoint"""
        try:
            response = requests.get(f"{self.api_base}/tts/info", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check response structure
                if data.get('success') and 'data' in data:
                    tts_info = data['data']
                    required_fields = ['available_engines', 'engine_voices', 'supported_languages']
                    
                    missing_fields = [field for field in required_fields if field not in tts_info]
                    if missing_fields:
                        self.log_result("TTS Info Endpoint", False, f"Missing fields: {missing_fields}")
                        return False
                    
                    # Check if engines are available
                    engines = tts_info.get('available_engines', [])
                    if not engines:
                        self.log_result("TTS Info Endpoint", False, "No TTS engines available")
                        return False
                    
                    self.log_result("TTS Info Endpoint", True, f"TTS info retrieved successfully", {
                        "engines": engines,
                        "languages": tts_info.get('supported_languages', []),
                        "coqui_available": tts_info.get('coqui_available', False),
                        "pyttsx3_available": tts_info.get('pyttsx3_available', False)
                    })
                    return True
                else:
                    self.log_result("TTS Info Endpoint", False, "Invalid response structure")
                    return False
            else:
                self.log_result("TTS Info Endpoint", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result("TTS Info Endpoint", False, f"Request failed: {str(e)}")
            return False
    
    def test_tts_generate_endpoint(self, text: str, engine: str = "gtts", language: str = "ru") -> Dict[str, Any]:
        """Test POST /api/tts/generate endpoint"""
        try:
            payload = {
                "text": text,
                "engine": engine,
                "voice": "female",
                "language": language,
                "speed": 1.0
            }
            
            start_time = time.time()
            response = requests.post(f"{self.api_base}/tts/generate", json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success') and 'task_id' in data:
                    task_id = data['task_id']
                    self.created_task_ids.append(task_id)
                    
                    # Wait for task completion and check status
                    task_result = self.wait_for_task_completion(task_id, timeout=30)
                    
                    generation_time = time.time() - start_time
                    
                    if task_result and task_result.get('success'):
                        self.log_result(f"TTS Generate ({engine}, {language})", True, 
                                      f"TTS generated successfully in {generation_time:.2f}s", {
                                          "task_id": task_id,
                                          "audio_path": task_result.get('audio_path'),
                                          "file_size": task_result.get('file_size'),
                                          "engine_used": task_result.get('engine_used')
                                      })
                        return {"success": True, "task_id": task_id, "result": task_result}
                    else:
                        error_msg = task_result.get('error', 'Task failed') if task_result else 'Task timeout'
                        self.log_result(f"TTS Generate ({engine}, {language})", False, error_msg)
                        return {"success": False, "error": error_msg}
                else:
                    self.log_result(f"TTS Generate ({engine}, {language})", False, "Invalid response structure")
                    return {"success": False, "error": "Invalid response"}
            else:
                self.log_result(f"TTS Generate ({engine}, {language})", False, 
                              f"HTTP {response.status_code}: {response.text}")
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            self.log_result(f"TTS Generate ({engine}, {language})", False, f"Request failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def wait_for_task_completion(self, task_id: str, timeout: int = 30) -> Dict[str, Any]:
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
                        time.sleep(1)
                        continue
                    else:
                        return {"success": False, "error": f"Unknown status: {status}"}
                else:
                    return {"success": False, "error": f"Failed to get task status: {response.status_code}"}
                    
            except Exception as e:
                return {"success": False, "error": f"Error checking task status: {str(e)}"}
        
        return {"success": False, "error": "Task timeout"}
    
    def test_content_creation_and_tts(self) -> bool:
        """Test content creation and TTS generation for content"""
        try:
            # Create test content
            content_payload = {
                "type": "video",
                "title": "Тест TTS для контента",
                "topic": "telegram боты",
                "description": "Telegram боты для получения подарков - это современный способ монетизации контента. Пользователи могут получать различные призы и бонусы, участвуя в интерактивных играх и заданиях.",
                "keywords": ["telegram", "боты", "подарки"],
                "target_platforms": ["telegram", "tiktok"]
            }
            
            response = requests.post(f"{self.api_base}/content", json=content_payload, timeout=15)
            
            if response.status_code != 200:
                self.log_result("Content Creation for TTS", False, f"Failed to create content: {response.status_code}")
                return False
            
            content_data = response.json()
            if not content_data.get('success'):
                self.log_result("Content Creation for TTS", False, "Content creation failed")
                return False
            
            content_id = content_data['content_id']
            self.created_content_ids.append(content_id)
            
            # Generate TTS for the content
            tts_params = {
                "engine": "gtts",
                "voice": "female",
                "language": "ru",
                "speed": 1.0
            }
            
            start_time = time.time()
            tts_response = requests.post(f"{self.api_base}/content/{content_id}/generate_tts", 
                                       json=tts_params, timeout=30)
            
            if tts_response.status_code == 200:
                tts_data = tts_response.json()
                
                if tts_data.get('success') and 'task_id' in tts_data:
                    task_id = tts_data['task_id']
                    self.created_task_ids.append(task_id)
                    
                    # Wait for TTS completion
                    task_result = self.wait_for_task_completion(task_id, timeout=30)
                    generation_time = time.time() - start_time
                    
                    if task_result and task_result.get('success'):
                        # Verify content was updated with audio_path
                        content_response = requests.get(f"{self.api_base}/content/{content_id}", timeout=10)
                        if content_response.status_code == 200:
                            updated_content = content_response.json()
                            audio_path = updated_content.get('audio_path')
                            
                            if audio_path:
                                self.log_result("Content TTS Generation", True, 
                                              f"TTS generated and linked to content in {generation_time:.2f}s", {
                                                  "content_id": content_id,
                                                  "task_id": task_id,
                                                  "audio_path": audio_path,
                                                  "file_size": task_result.get('file_size')
                                              })
                                return True
                            else:
                                self.log_result("Content TTS Generation", False, 
                                              "TTS generated but content not updated with audio_path")
                                return False
                        else:
                            self.log_result("Content TTS Generation", False, 
                                          "Failed to verify content update")
                            return False
                    else:
                        error_msg = task_result.get('error', 'Task failed') if task_result else 'Task timeout'
                        self.log_result("Content TTS Generation", False, error_msg)
                        return False
                else:
                    self.log_result("Content TTS Generation", False, "Invalid TTS response structure")
                    return False
            else:
                self.log_result("Content TTS Generation", False, 
                              f"TTS request failed: {tts_response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Content TTS Generation", False, f"Test failed: {str(e)}")
            return False
    
    def test_tts_different_languages_and_voices(self) -> bool:
        """Test TTS with different languages and voice settings"""
        test_cases = [
            {
                "text": "Привет! Это тест TTS системы EKOSYSTEMA_FULL.",
                "engine": "gtts",
                "language": "ru",
                "voice": "female"
            },
            {
                "text": "Hello! This is a TTS system test.",
                "engine": "gtts", 
                "language": "en",
                "voice": "male"
            }
        ]
        
        all_passed = True
        
        for i, test_case in enumerate(test_cases):
            result = self.test_tts_generate_endpoint(
                text=test_case["text"],
                engine=test_case["engine"],
                language=test_case["language"]
            )
            
            if not result.get("success"):
                all_passed = False
        
        return all_passed
    
    def test_tts_speed_variations(self) -> bool:
        """Test TTS with different speed settings"""
        speeds = [0.8, 1.0, 1.2]
        text = "Тест скорости генерации TTS аудио."
        
        all_passed = True
        
        for speed in speeds:
            try:
                payload = {
                    "text": text,
                    "engine": "gtts",
                    "voice": "female", 
                    "language": "ru",
                    "speed": speed
                }
                
                response = requests.post(f"{self.api_base}/tts/generate", json=payload, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        task_id = data['task_id']
                        self.created_task_ids.append(task_id)
                        
                        task_result = self.wait_for_task_completion(task_id, timeout=20)
                        
                        if task_result and task_result.get('success'):
                            self.log_result(f"TTS Speed Test (speed={speed})", True, 
                                          f"TTS generated successfully with speed {speed}")
                        else:
                            self.log_result(f"TTS Speed Test (speed={speed})", False, 
                                          f"TTS generation failed for speed {speed}")
                            all_passed = False
                    else:
                        self.log_result(f"TTS Speed Test (speed={speed})", False, 
                                      f"TTS request failed for speed {speed}")
                        all_passed = False
                else:
                    self.log_result(f"TTS Speed Test (speed={speed})", False, 
                                  f"HTTP error {response.status_code} for speed {speed}")
                    all_passed = False
                    
            except Exception as e:
                self.log_result(f"TTS Speed Test (speed={speed})", False, 
                              f"Exception for speed {speed}: {str(e)}")
                all_passed = False
        
        return all_passed
    
    def test_audio_file_creation(self) -> bool:
        """Test that audio files are actually created in the correct directory"""
        try:
            audio_dir = Path("/app/backend/generated_audio")
            
            # Check if directory exists
            if not audio_dir.exists():
                self.log_result("Audio Directory Check", False, "Generated audio directory does not exist")
                return False
            
            # Count existing files before test
            existing_files = list(audio_dir.glob("*.mp3")) + list(audio_dir.glob("*.wav"))
            initial_count = len(existing_files)
            
            # Generate a test TTS
            result = self.test_tts_generate_endpoint("Тест создания аудиофайла", "gtts", "ru")
            
            if result.get("success"):
                # Check if new files were created
                new_files = list(audio_dir.glob("*.mp3")) + list(audio_dir.glob("*.wav"))
                new_count = len(new_files)
                
                if new_count > initial_count:
                    # Find the newest file
                    newest_file = max(new_files, key=lambda f: f.stat().st_mtime)
                    file_size = newest_file.stat().st_size
                    
                    self.log_result("Audio File Creation", True, 
                                  f"Audio file created successfully", {
                                      "file_path": str(newest_file),
                                      "file_size": file_size,
                                      "files_before": initial_count,
                                      "files_after": new_count
                                  })
                    return True
                else:
                    self.log_result("Audio File Creation", False, 
                                  "TTS succeeded but no new audio file found")
                    return False
            else:
                self.log_result("Audio File Creation", False, 
                              "TTS generation failed, cannot test file creation")
                return False
                
        except Exception as e:
            self.log_result("Audio File Creation", False, f"Test failed: {str(e)}")
            return False
    
    def test_task_system_integration(self) -> bool:
        """Test integration with task system"""
        try:
            # Get initial task count
            response = requests.get(f"{self.api_base}/tasks", timeout=10)
            if response.status_code != 200:
                self.log_result("Task System Integration", False, "Failed to get initial task list")
                return False
            
            initial_tasks = response.json()
            initial_count = len(initial_tasks)
            
            # Create a TTS task
            result = self.test_tts_generate_endpoint("Тест интеграции с системой задач", "gtts", "ru")
            
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
                        if (our_task.get('type') == 'tts_generation' and 
                            our_task.get('status') == 'completed'):
                            
                            self.log_result("Task System Integration", True, 
                                          "TTS task properly integrated with task system", {
                                              "task_id": task_id,
                                              "task_type": our_task.get('type'),
                                              "task_status": our_task.get('status'),
                                              "has_result": bool(our_task.get('result'))
                                          })
                            return True
                        else:
                            self.log_result("Task System Integration", False, 
                                          f"Task found but incorrect properties: type={our_task.get('type')}, status={our_task.get('status')}")
                            return False
                    else:
                        self.log_result("Task System Integration", False, 
                                      "TTS task not found in task list")
                        return False
                else:
                    self.log_result("Task System Integration", False, 
                                  "Failed to get updated task list")
                    return False
            else:
                self.log_result("Task System Integration", False, 
                              "TTS generation failed, cannot test task integration")
                return False
                
        except Exception as e:
            self.log_result("Task System Integration", False, f"Test failed: {str(e)}")
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
        """Run all TTS tests"""
        print("🚀 Starting EKOSYSTEMA_FULL TTS Module Test Suite")
        print(f"🔗 Testing against: {self.api_base}")
        print("=" * 60)
        
        # Test basic connectivity first
        if not self.test_api_connectivity():
            print("❌ API connectivity failed. Stopping tests.")
            return False
        
        # Run all TTS tests
        tests = [
            ("TTS Info Endpoint", self.test_tts_info_endpoint),
            ("TTS Different Languages/Voices", self.test_tts_different_languages_and_voices),
            ("TTS Speed Variations", self.test_tts_speed_variations),
            ("Audio File Creation", self.test_audio_file_creation),
            ("Content Creation and TTS", self.test_content_creation_and_tts),
            ("Task System Integration", self.test_task_system_integration),
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
            print("🎉 All TTS tests passed!")
        else:
            print(f"⚠️  {total - passed} tests failed")
        
        # Cleanup
        self.cleanup_test_data()
        
        return passed == total

def main():
    """Main test runner"""
    test_suite = TTSTestSuite()
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