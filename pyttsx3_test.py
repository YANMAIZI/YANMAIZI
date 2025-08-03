#!/usr/bin/env python3
"""
Test pyttsx3 engine specifically
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
                    # Get error details
                    tasks_response = requests.get(f"{API_BASE}/tasks", timeout=10)
                    if tasks_response.status_code == 200:
                        tasks = tasks_response.json()
                        for task in tasks:
                            if task.get('id') == task_id:
                                error_msg = task.get('error_message', 'Task failed')
                                return {"success": False, "error": error_msg}
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

def test_pyttsx3_engine():
    """Test pyttsx3 engine specifically"""
    print("🎯 Testing pyttsx3 Engine")
    print("=" * 40)
    
    payload = {
        "text": "Тест локального движка pyttsx3 для синтеза речи.",
        "engine": "pyttsx3",
        "voice": "female",
        "language": "ru",
        "speed": 1.0
    }
    
    try:
        print("📤 Sending pyttsx3 TTS request...")
        response = requests.post(f"{API_BASE}/tts/generate", json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('success') and 'task_id' in data:
                task_id = data['task_id']
                print(f"✅ pyttsx3 task created: {task_id}")
                
                # Wait for completion
                result = wait_for_task_completion(task_id, timeout=30)
                
                if result and result.get('success'):
                    print(f"✅ pyttsx3 TTS generated successfully")
                    print(f"   Audio path: {result.get('audio_path', 'N/A')}")
                    print(f"   File size: {result.get('file_size', 'N/A')} bytes")
                    print(f"   Engine used: {result.get('engine_used', 'N/A')}")
                else:
                    error_msg = result.get('error', 'Unknown error') if result else 'Task timeout'
                    print(f"❌ pyttsx3 TTS generation failed: {error_msg}")
            else:
                print(f"❌ Invalid response structure: {data}")
        else:
            print(f"❌ HTTP error {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"❌ Request failed: {str(e)}")

def main():
    """Main test runner"""
    print("🚀 pyttsx3 Engine Test for EKOSYSTEMA_FULL")
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
    
    # Test pyttsx3
    test_pyttsx3_engine()
    
    print("\n" + "=" * 40)
    print("🎉 pyttsx3 testing completed!")

if __name__ == "__main__":
    main()