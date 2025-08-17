#!/usr/bin/env python3
"""
# @file purpose: Gestione file output strutturata per task browser-use

Sistema di gestione file per task browser-use con:
- Organizzazione strutturata directory per utente/task
- Gestione GIF, screenshots, history JSON
- Cleanup automatico file vecchi
- Compressione e archiviazione
"""

import asyncio
import json
import logging
import os
import shutil
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TaskFiles:
    """Rappresenta i file associati a un task"""
    task_id: str
    task_dir: Path
    history_file: Optional[Path] = None
    gif_file: Optional[Path] = None
    screenshots: List[Path] = None
    error_file: Optional[Path] = None
    
    def __post_init__(self):
        if self.screenshots is None:
            self.screenshots = []


class FileManager:
    """Gestore file per task browser-use"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir).resolve()
        self.tasks_dir = self.base_dir / "tasks"
        self.users_dir = self.base_dir / "users"
        self.archive_dir = self.base_dir / "archive"
        
        # Crea directory necessarie
        for dir_path in [self.tasks_dir, self.users_dir, self.archive_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📁 FileManager inizializzato - base_dir: {self.base_dir}")
    
    def get_task_dir(self, task_id: str) -> Path:
        """Ottiene la directory di un task"""
        return self.tasks_dir / task_id
    
    def get_user_dir(self, user_id: str) -> Path:
        """Ottiene la directory di un utente"""
        return self.users_dir / user_id
    
    def create_task_dir(self, task_id: str) -> Path:
        """Crea directory per un task"""
        task_dir = self.get_task_dir(task_id)
        task_dir.mkdir(exist_ok=True)
        logger.info(f"📁 Directory task creata: {task_dir}")
        return task_dir
    
    def create_user_dir(self, user_id: str) -> Path:
        """Crea directory per un utente"""
        user_dir = self.get_user_dir(user_id)
        user_dir.mkdir(exist_ok=True)
        
        # Crea sottodirectory utente
        (user_dir / "chrome").mkdir(exist_ok=True)
        (user_dir / "downloads").mkdir(exist_ok=True)
        
        logger.info(f"👤 Directory utente creata: {user_dir}")
        return user_dir
    
    def get_task_files(self, task_id: str) -> TaskFiles:
        """Ottiene tutti i file associati a un task"""
        task_dir = self.get_task_dir(task_id)
        
        if not task_dir.exists():
            return TaskFiles(task_id=task_id, task_dir=task_dir)
        
        # File principali
        history_file = task_dir / f"{task_id}.json"
        gif_file = task_dir / f"{task_id}.gif"
        error_file = task_dir / f"{task_id}_error.json"
        
        # Screenshots
        screenshots = []
        for screenshot_file in task_dir.glob("step_*.jpg"):
            screenshots.append(screenshot_file)
        screenshots.sort()
        
        return TaskFiles(
            task_id=task_id,
            task_dir=task_dir,
            history_file=history_file if history_file.exists() else None,
            gif_file=gif_file if gif_file.exists() else None,
            screenshots=screenshots,
            error_file=error_file if error_file.exists() else None
        )
    
    def save_task_history(
        self, 
        task_id: str, 
        history_data: Dict[str, Any]
    ) -> Path:
        """Salva la history di un task"""
        task_dir = self.create_task_dir(task_id)
        history_file = task_dir / f"{task_id}.json"
        
        # Aggiungi metadata
        history_data.update({
            "task_id": task_id,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "file_version": "1.0"
        })
        
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 History salvata: {history_file}")
        return history_file
    
    def save_task_error(
        self, 
        task_id: str, 
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Salva errore di un task"""
        task_dir = self.create_task_dir(task_id)
        error_file = task_dir / f"{task_id}_error.json"
        
        error_data = {
            "task_id": task_id,
            "error_message": error_message,
            "error_details": error_details or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        with open(error_file, 'w', encoding='utf-8') as f:
            json.dump(error_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"❌ Errore salvato: {error_file}")
        return error_file
    
    def save_screenshot(
        self, 
        task_id: str, 
        step_number: int,
        screenshot_data: bytes
    ) -> Path:
        """Salva screenshot di uno step"""
        task_dir = self.create_task_dir(task_id)
        screenshot_file = task_dir / f"step_{step_number:03d}.jpg"
        
        with open(screenshot_file, 'wb') as f:
            f.write(screenshot_data)
        
        logger.info(f"📸 Screenshot salvato: {screenshot_file}")
        return screenshot_file
    
    def get_task_size(self, task_id: str) -> int:
        """Ottiene la dimensione totale dei file di un task (in bytes)"""
        task_files = self.get_task_files(task_id)
        
        if not task_files.task_dir.exists():
            return 0
        
        total_size = 0
        for file_path in task_files.task_dir.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        
        return total_size
    
    def get_user_storage_usage(self, user_id: str) -> Dict[str, Any]:
        """Ottiene l'utilizzo storage di un utente"""
        user_dir = self.get_user_dir(user_id)
        
        if not user_dir.exists():
            return {"total_bytes": 0, "file_count": 0}
        
        total_bytes = 0
        file_count = 0
        
        for file_path in user_dir.rglob("*"):
            if file_path.is_file():
                total_bytes += file_path.stat().st_size
                file_count += 1
        
        return {
            "user_id": user_id,
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 2),
            "file_count": file_count
        }
    
    def archive_task(self, task_id: str) -> Optional[Path]:
        """Archivia un task in formato ZIP"""
        task_files = self.get_task_files(task_id)
        
        if not task_files.task_dir.exists():
            logger.warning(f"⚠️ Directory task non esiste: {task_id}")
            return None
        
        # Crea archive ZIP
        archive_file = self.archive_dir / f"{task_id}.zip"
        
        with zipfile.ZipFile(archive_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in task_files.task_dir.rglob("*"):
                if file_path.is_file():
                    # Path relativo nella ZIP
                    arcname = file_path.relative_to(task_files.task_dir)
                    zipf.write(file_path, arcname)
        
        logger.info(f"📦 Task archiviato: {archive_file}")
        return archive_file
    
    def cleanup_task(self, task_id: str, archive_first: bool = True) -> bool:
        """Pulisce i file di un task"""
        task_files = self.get_task_files(task_id)
        
        if not task_files.task_dir.exists():
            return True
        
        # Archivia prima se richiesto
        if archive_first:
            self.archive_task(task_id)
        
        # Rimuovi directory task
        try:
            shutil.rmtree(task_files.task_dir)
            logger.info(f"🧹 Task pulito: {task_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Errore pulizia task {task_id}: {e}")
            return False
    
    def cleanup_old_tasks(
        self, 
        max_age_days: int = 7,
        archive_before_delete: bool = True
    ) -> Dict[str, Any]:
        """Pulisce task vecchi"""
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        
        cleaned_tasks = []
        errors = []
        
        for task_dir in self.tasks_dir.iterdir():
            if not task_dir.is_dir():
                continue
            
            # Controlla età directory
            dir_mtime = datetime.fromtimestamp(
                task_dir.stat().st_mtime, 
                tz=timezone.utc
            )
            
            if dir_mtime < cutoff_date:
                task_id = task_dir.name
                
                try:
                    if self.cleanup_task(task_id, archive_first=archive_before_delete):
                        cleaned_tasks.append(task_id)
                    else:
                        errors.append(f"Errore pulizia {task_id}")
                        
                except Exception as e:
                    errors.append(f"Errore {task_id}: {str(e)}")
        
        result = {
            "cleaned_count": len(cleaned_tasks),
            "error_count": len(errors),
            "cleaned_tasks": cleaned_tasks,
            "errors": errors,
            "cutoff_date": cutoff_date.isoformat()
        }
        
        logger.info(f"🧹 Cleanup completato: {result}")
        return result
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Ottiene statistiche storage globali"""
        
        stats = {
            "base_dir": str(self.base_dir),
            "total_tasks": 0,
            "total_users": 0,
            "total_archives": 0,
            "storage_usage": {
                "tasks_bytes": 0,
                "users_bytes": 0,
                "archives_bytes": 0,
                "total_bytes": 0
            }
        }
        
        # Conta task
        if self.tasks_dir.exists():
            stats["total_tasks"] = len([
                d for d in self.tasks_dir.iterdir() if d.is_dir()
            ])
            
            # Calcola dimensione tasks
            for item in self.tasks_dir.rglob("*"):
                if item.is_file():
                    stats["storage_usage"]["tasks_bytes"] += item.stat().st_size
        
        # Conta utenti
        if self.users_dir.exists():
            stats["total_users"] = len([
                d for d in self.users_dir.iterdir() if d.is_dir()
            ])
            
            # Calcola dimensione utenti
            for item in self.users_dir.rglob("*"):
                if item.is_file():
                    stats["storage_usage"]["users_bytes"] += item.stat().st_size
        
        # Conta archivi
        if self.archive_dir.exists():
            stats["total_archives"] = len([
                f for f in self.archive_dir.iterdir() 
                if f.is_file() and f.suffix == '.zip'
            ])
            
            # Calcola dimensione archivi
            for item in self.archive_dir.rglob("*.zip"):
                if item.is_file():
                    stats["storage_usage"]["archives_bytes"] += item.stat().st_size
        
        # Totale
        usage = stats["storage_usage"]
        usage["total_bytes"] = (
            usage["tasks_bytes"] + 
            usage["users_bytes"] + 
            usage["archives_bytes"]
        )
        
        # Converti in MB per leggibilità
        for key in usage:
            if key.endswith("_bytes"):
                mb_key = key.replace("_bytes", "_mb")
                usage[mb_key] = round(usage[key] / (1024 * 1024), 2)
        
        return stats


# Istanza globale file manager
file_manager: Optional[FileManager] = None


def initialize_file_manager(base_dir: Path):
    """Inizializza il file manager globale"""
    global file_manager
    file_manager = FileManager(base_dir)
    return file_manager


def get_file_manager() -> FileManager:
    """Ottiene l'istanza file manager"""
    if file_manager is None:
        raise RuntimeError("FileManager non inizializzato. Chiamare initialize_file_manager() prima.")
    return file_manager


# Funzioni helper per integrazione facile
def create_task_dir(task_id: str) -> Path:
    """Crea directory per task"""
    return get_file_manager().create_task_dir(task_id)


def save_task_history(task_id: str, history_data: Dict[str, Any]) -> Path:
    """Salva history task"""
    return get_file_manager().save_task_history(task_id, history_data)


def get_task_files(task_id: str) -> TaskFiles:
    """Ottiene file di un task"""
    return get_file_manager().get_task_files(task_id)


def get_storage_stats() -> Dict[str, Any]:
    """Ottiene statistiche storage"""
    return get_file_manager().get_storage_stats()
