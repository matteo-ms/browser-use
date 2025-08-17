#!/usr/bin/env python3
"""
# @file purpose: Script di test per browser-use API multi-utente

Script completo per testare l'API browser-use con:
- Test creazione task generici
- Monitoring real-time status
- Verifica file output
- Test multi-utente
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any

import httpx


class BrowserUseAPITester:
    """Tester per API browser-use"""
    
    def __init__(
        self, 
        base_url: str = "http://localhost:8000",
        api_key: str = "test-api-key"
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Headers comuni
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        """Test health check"""
        print("🔍 Testing health check...")
        
        response = await self.client.get(f"{self.base_url}/health")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Health check OK - Sessions: {result.get('active_sessions', 0)}")
            return result
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return {}
    
    async def execute_task(
        self, 
        task: str, 
        user_id: str,
        max_steps: int = 10
    ) -> Dict[str, Any]:
        """Esegue un task"""
        print(f"🚀 Executing task for user {user_id}:")
        print(f"   Task: {task}")
        
        payload = {
            "task": task,
            "user_id": user_id,
            "max_steps": max_steps
        }
        
        response = await self.client.post(
            f"{self.base_url}/execute-task",
            json=payload,
            headers=self.headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Task queued: {result['task_id']}")
            return result
        else:
            print(f"❌ Task execution failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return {}
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Ottiene status task"""
        response = await self.client.get(
            f"{self.base_url}/task-status/{task_id}",
            headers=self.headers
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Status check failed: {response.status_code}")
            return {}
    
    async def monitor_task(
        self, 
        task_id: str,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """Monitora un task fino al completamento"""
        print(f"🔍 Monitoring task: {task_id}")
        
        start_time = time.time()
        last_steps = 0
        
        while time.time() - start_time < timeout:
            status = await self.get_task_status(task_id)
            
            if not status:
                break
            
            current_status = status.get("status", "unknown")
            steps = status.get("steps_completed", 0)
            
            # Mostra progresso se cambiato
            if steps != last_steps:
                print(f"   📊 Status: {current_status} - Steps: {steps}")
                last_steps = steps
            
            # Check completamento
            if current_status in ["completed", "error", "cancelled", "stalled"]:
                print(f"🏁 Task finished with status: {current_status}")
                
                if status.get("has_files"):
                    print("📁 Output files available:")
                    if status.get("history_url"):
                        print(f"   📄 History: {status['history_url']}")
                    if status.get("gif_url"):
                        print(f"   🎬 GIF: {status['gif_url']}")
                
                return status
            
            await asyncio.sleep(5)  # Check ogni 5 secondi
        
        print(f"⏰ Task monitoring timed out after {timeout}s")
        return await self.get_task_status(task_id)
    
    async def test_basic_task(self, user_id: str = "test-user-1"):
        """Test task base"""
        print("\n" + "="*50)
        print("🧪 TEST: Basic Task Execution")
        print("="*50)
        
        task = "vai su https://www.google.com e cerca 'browser automation python'"
        
        # Esegui task
        result = await self.execute_task(task, user_id)
        if not result:
            return False
        
        # Monitora completamento
        final_status = await self.monitor_task(result["task_id"])
        
        return final_status.get("status") == "completed"
    
    async def test_form_filling_task(self, user_id: str = "test-user-2"):
        """Test task form filling"""
        print("\n" + "="*50)
        print("🧪 TEST: Form Filling Task")
        print("="*50)
        
        task = """
        Vai su https://httpbin.org/forms/post e compila il form con:
        - Customer name: Test User
        - Telephone: 555-123-4567
        - Email: test@example.com
        - Size: Medium
        - Comments: This is a test form
        Poi invia il form e dimmi il risultato.
        """
        
        result = await self.execute_task(task, user_id)
        if not result:
            return False
        
        final_status = await self.monitor_task(result["task_id"])
        
        return final_status.get("status") == "completed"
    
    async def test_multi_user(self):
        """Test multi-utente"""
        print("\n" + "="*50)
        print("🧪 TEST: Multi-User Concurrent Tasks")
        print("="*50)
        
        # Task per utenti diversi
        tasks = [
            ("user-a", "vai su https://www.python.org e dimmi l'ultima versione di Python"),
            ("user-b", "vai su https://github.com e cerca 'browser automation'"),
            ("user-c", "vai su https://stackoverflow.com e cerca 'selenium vs playwright'")
        ]
        
        # Avvia task in parallelo
        task_results = []
        for user_id, task in tasks:
            result = await self.execute_task(task, user_id, max_steps=5)
            if result:
                task_results.append((user_id, result["task_id"]))
        
        print(f"🚀 Started {len(task_results)} concurrent tasks")
        
        # Monitora tutti in parallelo
        monitoring_tasks = []
        for user_id, task_id in task_results:
            monitoring_tasks.append(
                self.monitor_task(task_id, timeout=60)
            )
        
        # Aspetta completamento tutti
        if monitoring_tasks:
            results = await asyncio.gather(*monitoring_tasks, return_exceptions=True)
            
            completed_count = 0
            for i, result in enumerate(results):
                if isinstance(result, dict) and result.get("status") == "completed":
                    completed_count += 1
            
            print(f"✅ Multi-user test: {completed_count}/{len(task_results)} tasks completed")
            return completed_count == len(task_results)
        
        return False
    
    async def test_user_tasks_listing(self, user_id: str = "test-user-1"):
        """Test listing task utente"""
        print("\n" + "="*50)
        print("🧪 TEST: User Tasks Listing")
        print("="*50)
        
        response = await self.client.get(
            f"{self.base_url}/user-tasks/{user_id}",
            headers=self.headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ User {user_id} has {result['total_tasks']} tasks")
            
            for task in result["tasks"][:3]:  # Mostra prime 3
                print(f"   📋 {task['task_id']}: {task['status']}")
            
            return True
        else:
            print(f"❌ User tasks listing failed: {response.status_code}")
            return False
    
    async def run_all_tests(self):
        """Esegue tutti i test"""
        print("🧪 BROWSER-USE API TESTER")
        print("="*50)
        
        # Health check
        health = await self.health_check()
        if not health:
            print("❌ Health check failed - aborting tests")
            return
        
        test_results = []
        
        # Test base
        try:
            result = await self.test_basic_task()
            test_results.append(("Basic Task", result))
        except Exception as e:
            print(f"❌ Basic task test failed: {e}")
            test_results.append(("Basic Task", False))
        
        # Test form filling
        try:
            result = await self.test_form_filling_task()
            test_results.append(("Form Filling", result))
        except Exception as e:
            print(f"❌ Form filling test failed: {e}")
            test_results.append(("Form Filling", False))
        
        # Test multi-user
        try:
            result = await self.test_multi_user()
            test_results.append(("Multi-User", result))
        except Exception as e:
            print(f"❌ Multi-user test failed: {e}")
            test_results.append(("Multi-User", False))
        
        # Test user tasks
        try:
            result = await self.test_user_tasks_listing()
            test_results.append(("User Tasks Listing", result))
        except Exception as e:
            print(f"❌ User tasks test failed: {e}")
            test_results.append(("User Tasks Listing", False))
        
        # Risultati finali
        print("\n" + "="*50)
        print("📊 TEST RESULTS")
        print("="*50)
        
        passed = 0
        total = len(test_results)
        
        for test_name, success in test_results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} {test_name}")
            if success:
                passed += 1
        
        print(f"\n🎯 Overall: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed!")
        else:
            print(f"⚠️ {total - passed} tests failed")


async def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Browser-use API Tester")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--api-key", default="test-api-key", help="API key")
    parser.add_argument("--test", choices=["all", "basic", "form", "multi", "list"], 
                       default="all", help="Test to run")
    
    args = parser.parse_args()
    
    async with BrowserUseAPITester(args.url, args.api_key) as tester:
        if args.test == "all":
            await tester.run_all_tests()
        elif args.test == "basic":
            await tester.test_basic_task()
        elif args.test == "form":
            await tester.test_form_filling_task()
        elif args.test == "multi":
            await tester.test_multi_user()
        elif args.test == "list":
            await tester.test_user_tasks_listing()


if __name__ == "__main__":
    asyncio.run(main())
