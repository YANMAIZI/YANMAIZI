#!/usr/bin/env python3
"""
Extended TTS Test with specific test cases from review request
"""

import requests
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/frontend/.env')
BACKEND_URL = os.getenv('REACT_APP_BACKEND_URL', 'http://localhost:8001')
API_BASE = f"{BACKEND_URL}/api"

def wait_for_task_completion(task_id: str, timeout: int = 30):
    """Wait for task completion and return result"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{API_BASE}/tasks/{task_id}", timeout=10)
            
            if response.status_code == 200:
                task_data = response.json()
                status = task_data.get('status', 'unknown')
                
                if status == 'completed':
                    # Get full task details
                    tasks_response = requests.get(f"{API_BASE}/tasks", timeout=10)
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

def test_specific_texts():
    """Test specific texts from review request"""
    
    test_cases = [
        {
            "name": "Russian Short Text",
            "text": "Привет! Это тест TTS системы EKOSYSTEMA_FULL.",
            "language": "ru",
            "engine": "gtts"
        },
        {
            "name": "English Short Text", 
            "text": "Hello! This is a TTS system test.",
            "language": "en",
            "engine": "gtts"
        },
        {
            "name": "Russian Long Text",
            "text": "Telegram боты для получения подарков - это современный способ монетизации контента. Пользователи могут получать различные призы и бонусы, участвуя в интерактивных играх и заданиях.",
            "language": "ru", 
            "engine": "gtts"
        }
    ]
    
    print("🎯 Testing Specific TTS Cases from Review Request")
    print("=" * 60)
    
    for test_case in test_cases:
        print(f"\n📝 Testing: {test_case['name']}")
        print(f"Text: {test_case['text'][:50]}{'...' if len(test_case['text']) > 50 else ''}")
        
        payload = {
            "text": test_case['text'],
            "engine": test_case['engine'],
            "voice": "female",
            "language": test_case['language'],
            "speed": 1.0
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(f"{API_BASE}/tts/generate", json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success') and 'task_id' in data:
                    task_id = data['task_id']
                    print(f"✅ TTS task created: {task_id}")
                    
                    # Wait for completion
                    result = wait_for_task_completion(task_id, timeout=30)
                    generation_time = time.time() - start_time
                    
                    if result and result.get('success'):
                        print(f"✅ TTS generated successfully in {generation_time:.2f}s")
                        print(f"   Audio path: {result.get('audio_path', 'N/A')}")
                        print(f"   File size: {result.get('file_size', 'N/A')} bytes")
                        print(f"   Engine used: {result.get('engine_used', 'N/A')}")
                        
                        # Check if generation was fast (< 5 seconds as requested)
                        if generation_time < 5.0:
                            print(f"✅ Generation time requirement met: {generation_time:.2f}s < 5s")
                        else:
                            print(f"⚠️  Generation time exceeded 5s: {generation_time:.2f}s")
                    else:
                        error_msg = result.get('error', 'Unknown error') if result else 'Task timeout'
                        print(f"❌ TTS generation failed: {error_msg}")
                else:
                    print(f"❌ Invalid response structure: {data}")
            else:
                print(f"❌ HTTP error {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {str(e)}")

def test_voice_variations():
    """Test different voice types"""
    print(f"\n🎤 Testing Voice Variations")
    print("=" * 40)
    
    voices = ["male", "female"]
    text = "Тест различных типов голосов в TTS системе."
    
    for voice in voices:
        print(f"\n🔊 Testing {voice} voice...")
        
        payload = {
            "text": text,
            "engine": "gtts",
            "voice": voice,
            "language": "ru",
            "speed": 1.0
        }
        
        try:
            response = requests.post(f"{API_BASE}/tts/generate", json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    task_id = data['task_id']
                    result = wait_for_task_completion(task_id, timeout=20)
                    
                    if result and result.get('success'):
                        print(f"✅ {voice.capitalize()} voice generated successfully")
                    else:
                        print(f"❌ {voice.capitalize()} voice generation failed")
                else:
                    print(f"❌ {voice.capitalize()} voice request failed")
            else:
                print(f"❌ HTTP error for {voice} voice: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Exception for {voice} voice: {str(e)}")

def check_audio_directory():
    """Check the generated audio directory"""
    print(f"\n📁 Checking Audio Directory")
    print("=" * 40)
    
    import os
    from pathlib import Path
    
    audio_dir = Path("/app/backend/generated_audio")
    
    if audio_dir.exists():
        audio_files = list(audio_dir.glob("*.mp3")) + list(audio_dir.glob("*.wav"))
        print(f"✅ Audio directory exists: {audio_dir}")
        print(f"📊 Total audio files: {len(audio_files)}")
        
        if audio_files:
            # Show recent files
            recent_files = sorted(audio_files, key=lambda f: f.stat().st_mtime, reverse=True)[:5]
            print(f"🕒 Recent files:")
            for file in recent_files:
                size = file.stat().st_size
                print(f"   - {file.name} ({size} bytes)")
        else:
            print("⚠️  No audio files found in directory")
    else:
        print(f"❌ Audio directory does not exist: {audio_dir}")

def main():
    """Main test runner"""
    print("🚀 Extended TTS Testing for EKOSYSTEMA_FULL")
    print(f"🔗 API Base: {API_BASE}")
    
    # Test API connectivity
    try:
        response = requests.get(f"{API_BASE}/", timeout=10)
        if response.status_code == 200:
            print("✅ API connectivity confirmed")
        else:
            print(f"❌ API connectivity failed: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ API connectivity error: {str(e)}")
        return
    
    # Run extended tests
    test_specific_texts()
    test_voice_variations()
    check_audio_directory()
    
    print("\n" + "=" * 60)
    print("🎉 Extended TTS testing completed!")

if __name__ == "__main__":
    main()