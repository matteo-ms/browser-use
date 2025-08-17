#!/usr/bin/env python3
"""
# @file purpose: Server HTTP FastAPI per browser-use multi-utente

Server HTTP REST API per automazione browser multi-utente.
Estende l'architettura browser-use esistente per supportare:
- Isolamento utenti con sessioni browser persistenti  
- Autenticazione API key
- Monitoring task real-time
- Gestione file output strutturata
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Header, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Browser-use imports
from browser_use import Agent
from browser_use.browser.session import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.controller.service import Controller
from browser_use.llm import ChatOpenAI
from browser_use.config import load_browser_use_config

# Fix import dependencies
try:
    from fastapi import Depends
except ImportError:
    # Fallback se FastAPI non è installato
    def Depends(func):
        return func


# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurazione da environment
API_KEY = os.environ.get("BROWSER_SERVICE_API_KEY")
if not API_KEY:
    raise ValueError("BROWSER_SERVICE_API_KEY environment variable must be set")

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
DATA_DIR = Path(os.environ.get("BROWSER_USE_DATA_DIR", "./data")).resolve()

# Crea directories necessarie
DATA_DIR.mkdir(exist_ok=True)
(DATA_DIR / "users").mkdir(exist_ok=True)
(DATA_DIR / "tasks").mkdir(exist_ok=True)

logger.info(f"✅ Browser-use API configurato - Data dir: {DATA_DIR}")
logger.info(f"✅ CORS configurato per origins: {ALLOWED_ORIGINS}")


# Modelli Pydantic per API
class TaskRequest(BaseModel):
    """Richiesta per esecuzione task"""
    task: str
    user_id: str
    session_id: Optional[str] = None
    max_steps: Optional[int] = 30
    model: Optional[str] = "gpt-4o-mini"


class TaskResponse(BaseModel):
    """Risposta per task creato"""
    success: bool
    task_id: str
    user_id: str
    session_id: str
    message: str


class TaskStatus(BaseModel):
    """Status di un task"""
    task_id: str
    user_id: str
    status: str  # running, completed, error, cancelled
    steps_completed: int
    created_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    has_files: bool = False
    gif_url: Optional[str] = None
    history_url: Optional[str] = None


# Storage globale per task e sessioni
active_tasks: Dict[str, Dict[str, Any]] = {}
user_sessions: Dict[str, BrowserSession] = {}
task_agents: Dict[str, Agent] = {}


class UserSessionManager:
    """Gestisce sessioni browser persistenti per ogni utente"""
    
    @staticmethod
    async def get_or_create_session(user_id: str) -> BrowserSession:
        """Ottiene o crea una sessione browser per l'utente"""
        if user_id not in user_sessions:
            logger.info(f"🔄 Creando nuova sessione browser per utente: {user_id}")
            
            # Directory per dati utente
            user_dir = DATA_DIR / "users" / user_id
            user_dir.mkdir(exist_ok=True)
            
            # Configurazione browser profile per utente
            profile = BrowserProfile(
                user_data_dir=str(user_dir / "chrome"),
                storage_state=str(user_dir / "session.json"),
                keep_alive=True,  # Mantieni sessione tra task
                headless=False,
                disable_security=True,
                wait_between_actions=0.5,
                extra_browser_args=[
                    "--disable-default-apps",
                    "--disable-infobars", 
                    "--disable-notifications",
                    "--disable-popup-blocking"
                ]
            )
            
            # Crea sessione browser
            session = BrowserSession(browser_profile=profile)
            await session.start()
            user_sessions[user_id] = session
            
            logger.info(f"✅ Sessione browser creata per utente: {user_id}")
            
        return user_sessions[user_id]
    
    @staticmethod
    async def cleanup_session(user_id: str):
        """Pulisce la sessione di un utente"""
        if user_id in user_sessions:
            try:
                await user_sessions[user_id].close()
                del user_sessions[user_id]
                logger.info(f"🧹 Sessione pulita per utente: {user_id}")
            except Exception as e:
                logger.error(f"❌ Errore pulizia sessione {user_id}: {e}")


# Inizializza FastAPI app
app = FastAPI(
    title="Browser-Use Multi-User API",
    description="API REST per automazione browser multi-utente",
    version="1.0.0"
)

# Configura CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# Mount static files per accesso ai file generati
app.mount("/files", StaticFiles(directory=str(DATA_DIR / "tasks")), name="task_files")


# Dependency per verifica API key
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verifica API key"""
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="API Key header mancante")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="API Key non valida")
    return True


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok", 
        "message": "Browser-use API server attivo",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "active_sessions": len(user_sessions),
        "active_tasks": len(active_tasks)
    }


@app.post("/execute-task", response_model=TaskResponse)
async def execute_task(
    request: TaskRequest,
    background_tasks: BackgroundTasks,
    authorized: bool = Depends(verify_api_key)
) -> TaskResponse:
    """Esegue un task di automazione browser per un utente"""
    
    # Genera ID task univoco
    task_id = f"task-{int(time.time() * 1000)}-{str(uuid.uuid4())[:8]}"
    session_id = request.session_id or f"session-{request.user_id}-{int(time.time())}"
    
    logger.info(f"🚀 Nuovo task ricevuto - ID: {task_id}, Utente: {request.user_id}")
    logger.info(f"📝 Task: {request.task}")
    
    # Controlla se utente ha già task attivo
    user_active_tasks = [
        t for t in active_tasks.values() 
        if t["user_id"] == request.user_id and t["status"] == "running"
    ]
    
    if user_active_tasks:
        raise HTTPException(
            status_code=409, 
            detail=f"Utente {request.user_id} ha già un task attivo. Completare o cancellare prima."
        )
    
    # Registra task
    active_tasks[task_id] = {
        "task_id": task_id,
        "user_id": request.user_id,
        "session_id": session_id,
        "task": request.task,
        "status": "queued",
        "steps_completed": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "max_steps": request.max_steps,
        "model": request.model
    }
    
    # Avvia task in background
    background_tasks.add_task(run_agent_task, task_id, request)
    
    return TaskResponse(
        success=True,
        task_id=task_id,
        user_id=request.user_id,
        session_id=session_id,
        message=f"Task in coda per utente {request.user_id}"
    )


async def run_agent_task(task_id: str, request: TaskRequest):
    """Esegue il task agent in background"""
    
    task_info = active_tasks[task_id]
    
    try:
        logger.info(f"🤖 Avvio esecuzione task: {task_id}")
        task_info["status"] = "running"
        
        # Ottieni sessione browser persistente per utente
        session = await UserSessionManager.get_or_create_session(request.user_id)
        
        # Configura LLM
        config = load_browser_use_config()
        llm = ChatOpenAI(
            model=request.model,
            temperature=0.1
        )
        
        # Crea directory output per task
        task_dir = DATA_DIR / "tasks" / task_id
        task_dir.mkdir(exist_ok=True)
        
        # Crea agent con sessione persistente
        agent = Agent(
            task=request.task,
            llm=llm,
            browser_session=session,
            controller=Controller(),
            max_steps=request.max_steps,
            # generate_gif=str(task_dir / f"{task_id}.gif")  # Configurabile se supportato
        )
        
        # Salva riferimento agent
        task_agents[task_id] = agent
        
        # Callback per aggiornamento step
        def on_step_complete(step_num: int):
            if task_id in active_tasks:
                active_tasks[task_id]["steps_completed"] = step_num
        
        # Esegui agent
        logger.info(f"🏃 Esecuzione agent per task: {task_id}")
        result = await agent.run()
        
        # Salva risultati
        result_data = {
            "task_id": task_id,
            "user_id": request.user_id,
            "task": request.task,
            "result": str(result) if result else "",
            "status": "completed",
            "steps_completed": active_tasks[task_id]["steps_completed"],
            "created_at": task_info["created_at"],
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Salva history JSON
        history_file = task_dir / f"{task_id}.json"
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        # Aggiorna status task
        task_info.update({
            "status": "completed",
            "completed_at": result_data["completed_at"],
            "result": result_data["result"]
        })
        
        logger.info(f"✅ Task completato: {task_id}")
        
    except Exception as e:
        logger.error(f"❌ Errore esecuzione task {task_id}: {e}")
        
        # Aggiorna status con errore
        task_info.update({
            "status": "error",
            "error_message": str(e),
            "completed_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Salva errore
        error_file = DATA_DIR / "tasks" / task_id / f"{task_id}_error.json"
        error_file.parent.mkdir(exist_ok=True)
        with open(error_file, 'w') as f:
            json.dump({
                "task_id": task_id,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, f, indent=2)
    
    finally:
        # Cleanup agent reference
        if task_id in task_agents:
            del task_agents[task_id]


@app.get("/task-status/{task_id}", response_model=TaskStatus)
async def get_task_status(
    task_id: str,
    request: Request,
    authorized: bool = Depends(verify_api_key)
) -> TaskStatus:
    """Ottiene lo status di un task"""
    
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task non trovato")
    
    task_info = active_tasks[task_id]
    
    # Controlla file output
    task_dir = DATA_DIR / "tasks" / task_id
    history_file = task_dir / f"{task_id}.json"
    gif_file = task_dir / f"{task_id}.gif"
    
    has_history = history_file.exists()
    has_gif = gif_file.exists()
    
    # URLs per file se esistono
    base_url = f"{request.url.scheme}://{request.url.netloc}"
    history_url = f"{base_url}/files/{task_id}/{task_id}.json" if has_history else None
    gif_url = f"{base_url}/files/{task_id}/{task_id}.gif" if has_gif else None
    
    return TaskStatus(
        task_id=task_id,
        user_id=task_info["user_id"],
        status=task_info["status"],
        steps_completed=task_info["steps_completed"],
        created_at=task_info["created_at"],
        completed_at=task_info.get("completed_at"),
        error_message=task_info.get("error_message"),
        has_files=has_history or has_gif,
        history_url=history_url,
        gif_url=gif_url
    )


@app.post("/task-cancel/{task_id}")
async def cancel_task(
    task_id: str,
    authorized: bool = Depends(verify_api_key)
):
    """Cancella un task in esecuzione"""
    
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task non trovato")
    
    task_info = active_tasks[task_id]
    
    if task_info["status"] not in ["queued", "running"]:
        raise HTTPException(status_code=400, detail="Task non può essere cancellato")
    
    # Ferma agent se attivo
    if task_id in task_agents:
        try:
            agent = task_agents[task_id]
            if hasattr(agent, 'state'):
                agent.state.stopped = True
        except Exception as e:
            logger.error(f"❌ Errore fermando agent {task_id}: {e}")
    
    # Aggiorna status
    task_info.update({
        "status": "cancelled",
        "completed_at": datetime.now(timezone.utc).isoformat()
    })
    
    logger.info(f"🚫 Task cancellato: {task_id}")
    
    return {"success": True, "message": f"Task {task_id} cancellato"}


@app.get("/user-tasks/{user_id}")
async def get_user_tasks(
    user_id: str,
    authorized: bool = Depends(verify_api_key)
):
    """Ottiene tutti i task di un utente"""
    
    user_tasks = [
        task for task in active_tasks.values() 
        if task["user_id"] == user_id
    ]
    
    return {
        "user_id": user_id,
        "total_tasks": len(user_tasks),
        "tasks": sorted(user_tasks, key=lambda x: x["created_at"], reverse=True)
    }


@app.delete("/user-session/{user_id}")
async def cleanup_user_session(
    user_id: str,
    authorized: bool = Depends(verify_api_key)
):
    """Pulisce la sessione browser di un utente"""
    
    await UserSessionManager.cleanup_session(user_id)
    
    return {"success": True, "message": f"Sessione utente {user_id} pulita"}


# Funzione per avvio server
def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False
):
    """Avvia il server FastAPI"""
    logger.info(f"🚀 Avvio Browser-use API server su {host}:{port}")
    
    uvicorn.run(
        "browser_use.api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Browser-use Multi-User API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address")
    parser.add_argument("--port", type=int, default=8000, help="Port number")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    run_server(host=args.host, port=args.port, reload=args.reload)
