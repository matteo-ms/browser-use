#!/usr/bin/env python3
"""
Script per testare l'esecuzione di un task tramite API con monitoraggio status
"""

import asyncio
import json
import time
import httpx

API_URL = "http://localhost:8080"
API_KEY = "AuanyrvoRIKzmIjw3saCmO5LWRE07X7IRu1"

async def execute_and_monitor_task():
    """Esegue un task e monitora il suo status"""
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        }
        
        # 1. Health check
        print("🔍 Controllo health API...")
        try:
            response = await client.get(f"{API_URL}/health")
            if response.status_code == 200:
                health = response.json()
                print(f"✅ API attiva - Sessioni attive: {health.get('active_sessions', 0)}")
            else:
                print(f"❌ Health check fallito: {response.status_code}")
                return
        except Exception as e:
            print(f"❌ Errore health check: {e}")
            return
        
        # 2. Esegui task
        print("\n🚀 Esecuzione task...")
        task_payload = {
            "task": "vai su google.com e cerca 'browser automation python', poi dimmi quanti risultati trovi",
            "user_id": "test-user-demo",
            "max_steps": 15
        }
        
        try:
            response = await client.post(
                f"{API_URL}/execute-task",
                json=task_payload,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                task_id = result["task_id"]
                print(f"✅ Task avviato: {task_id}")
                print(f"   User: {result['user_id']}")
                print(f"   Session: {result.get('session_id', 'N/A')}")
            else:
                print(f"❌ Errore esecuzione task: {response.status_code}")
                print(f"   Risposta: {response.text}")
                return
        except Exception as e:
            print(f"❌ Errore esecuzione task: {e}")
            return
        
        # 3. Monitora status
        print(f"\n🔍 Monitoraggio task {task_id}...")
        print("=" * 60)
        
        start_time = time.time()
        last_steps = 0
        check_count = 0
        
        while time.time() - start_time < 300:  # Timeout 5 minuti
            check_count += 1
            
            try:
                response = await client.get(
                    f"{API_URL}/task-status/{task_id}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    status = response.json()
                    
                    current_status = status.get("status", "unknown")
                    steps = status.get("steps_completed", 0)
                    created_at = status.get("created_at", "N/A")
                    
                    # Mostra aggiornamenti
                    if steps != last_steps or check_count == 1:
                        elapsed = int(time.time() - start_time)
                        print(f"[{elapsed:3d}s] Status: {current_status:12} | Steps: {steps:2d} | Check: {check_count}")
                        last_steps = steps
                    
                    # Check completamento
                    if current_status in ["completed", "error", "cancelled", "stalled"]:
                        print("=" * 60)
                        print(f"🏁 Task completato con status: {current_status}")
                        
                        if current_status == "completed":
                            print("✅ Task eseguito con successo!")
                        elif current_status == "error":
                            print("❌ Task fallito con errore")
                            error_msg = status.get("error_message", "Nessun dettaglio errore")
                            print(f"   Errore: {error_msg}")
                        elif current_status == "stalled":
                            print("⏸️ Task bloccato (possibile timeout)")
                        
                        # Mostra info finali
                        completed_at = status.get("completed_at")
                        if completed_at:
                            print(f"   Completato: {completed_at}")
                        
                        # Mostra file output se disponibili
                        if status.get("has_files"):
                            print("\n📁 File output disponibili:")
                            if status.get("history_url"):
                                print(f"   📄 History JSON: {status['history_url']}")
                            if status.get("gif_url"):
                                print(f"   🎬 GIF recording: {status['gif_url']}")
                            if status.get("screenshots"):
                                print(f"   📸 Screenshots: {len(status['screenshots'])} disponibili")
                        
                        return status
                        
                else:
                    print(f"❌ Errore controllo status: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Errore monitoraggio: {e}")
            
            # Aspetta prima del prossimo check (intervallo crescente)
            if check_count < 10:
                await asyncio.sleep(3)  # Prime 10 volte: ogni 3 secondi
            elif check_count < 30:
                await asyncio.sleep(5)  # Successive 20 volte: ogni 5 secondi
            else:
                await asyncio.sleep(10) # Dopo: ogni 10 secondi
        
        print(f"⏰ Timeout monitoraggio dopo {int(time.time() - start_time)}s")
        
        # Ultimo check dello status
        try:
            response = await client.get(f"{API_URL}/task-status/{task_id}", headers=headers)
            if response.status_code == 200:
                final_status = response.json()
                print(f"📊 Status finale: {final_status.get('status', 'unknown')}")
                return final_status
        except Exception as e:
            print(f"❌ Errore check finale: {e}")
        
        return None

if __name__ == "__main__":
    print("🧪 BROWSER-USE API TASK TESTER")
    print("=" * 60)
    
    result = asyncio.run(execute_and_monitor_task())
    
    if result:
        print(f"\n✅ Test completato - Status finale: {result.get('status', 'unknown')}")
    else:
        print(f"\n❌ Test fallito o interrotto")
