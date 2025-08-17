#!/usr/bin/env python3
"""
# @file purpose: Sistema di monitoring e tracking task real-time

Sistema avanzato per il monitoring dei task browser-use con:
- Tracking real-time dello stato task
- Rilevamento task stalled/bloccati  
- Metriche di performance e utilizzo risorse
- Sistema di alerting per errori
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Stati possibili di un task"""
    QUEUED = "queued"
    RUNNING = "running" 
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"
    STALLED = "stalled"


@dataclass
class TaskMetrics:
    """Metriche di un task"""
    task_id: str
    user_id: str
    status: TaskStatus
    steps_completed: int
    steps_target: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    duration_seconds: float = 0
    error_message: Optional[str] = None
    stall_count: int = 0
    resource_usage: Dict[str, Any] = None


class TaskMonitor:
    """Monitor avanzato per tracking task real-time"""
    
    def __init__(
        self,
        stall_timeout: int = 60,  # secondi senza attività prima di considerare stalled
        max_stall_checks: int = 3,  # numero massimo controlli stall prima di marcare failed
        cleanup_interval: int = 300  # secondi tra cleanup task completati
    ):
        self.stall_timeout = stall_timeout
        self.max_stall_checks = max_stall_checks  
        self.cleanup_interval = cleanup_interval
        
        # Storage metriche task
        self.task_metrics: Dict[str, TaskMetrics] = {}
        self.monitoring_active = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        logger.info(f"📊 TaskMonitor inizializzato - stall_timeout: {stall_timeout}s")
    
    def register_task(
        self, 
        task_id: str, 
        user_id: str, 
        max_steps: int = 30
    ) -> TaskMetrics:
        """Registra un nuovo task per monitoring"""
        
        metrics = TaskMetrics(
            task_id=task_id,
            user_id=user_id,
            status=TaskStatus.QUEUED,
            steps_completed=0,
            steps_target=max_steps,
            created_at=datetime.now(timezone.utc),
            resource_usage={}
        )
        
        self.task_metrics[task_id] = metrics
        logger.info(f"📝 Task registrato per monitoring: {task_id}")
        
        return metrics
    
    def update_task_status(
        self, 
        task_id: str, 
        status: TaskStatus,
        steps_completed: Optional[int] = None,
        error_message: Optional[str] = None
    ):
        """Aggiorna lo status di un task"""
        
        if task_id not in self.task_metrics:
            logger.warning(f"⚠️ Task non trovato per update: {task_id}")
            return
        
        metrics = self.task_metrics[task_id]
        old_status = metrics.status
        
        # Aggiorna metriche
        metrics.status = status
        metrics.last_activity = datetime.now(timezone.utc)
        
        if steps_completed is not None:
            metrics.steps_completed = steps_completed
        
        if error_message:
            metrics.error_message = error_message
        
        # Timestamp specifici per stati
        if status == TaskStatus.RUNNING and old_status == TaskStatus.QUEUED:
            metrics.started_at = datetime.now(timezone.utc)
            
        elif status in [TaskStatus.COMPLETED, TaskStatus.ERROR, TaskStatus.CANCELLED]:
            metrics.completed_at = datetime.now(timezone.utc)
            if metrics.started_at:
                metrics.duration_seconds = (
                    metrics.completed_at - metrics.started_at
                ).total_seconds()
        
        logger.info(f"📊 Task {task_id}: {old_status.value} -> {status.value}")
    
    def update_task_progress(self, task_id: str, steps_completed: int):
        """Aggiorna il progresso di un task"""
        
        if task_id not in self.task_metrics:
            return
        
        metrics = self.task_metrics[task_id]
        
        # Solo se progresso effettivo
        if steps_completed > metrics.steps_completed:
            metrics.steps_completed = steps_completed
            metrics.last_activity = datetime.now(timezone.utc)
            metrics.stall_count = 0  # Reset stall counter su progresso
            
            progress_pct = (steps_completed / metrics.steps_target) * 100
            logger.info(f"📈 Task {task_id}: step {steps_completed}/{metrics.steps_target} ({progress_pct:.1f}%)")
    
    def get_task_metrics(self, task_id: str) -> Optional[TaskMetrics]:
        """Ottiene le metriche di un task"""
        return self.task_metrics.get(task_id)
    
    def get_user_tasks(self, user_id: str) -> List[TaskMetrics]:
        """Ottiene tutti i task di un utente"""
        return [
            metrics for metrics in self.task_metrics.values()
            if metrics.user_id == user_id
        ]
    
    def get_active_tasks(self) -> List[TaskMetrics]:
        """Ottiene tutti i task attivi (running/queued)"""
        return [
            metrics for metrics in self.task_metrics.values()
            if metrics.status in [TaskStatus.QUEUED, TaskStatus.RUNNING]
        ]
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Ottiene statistiche di sistema"""
        
        total_tasks = len(self.task_metrics)
        active_tasks = len(self.get_active_tasks())
        
        # Conteggi per status
        status_counts = {}
        for status in TaskStatus:
            status_counts[status.value] = len([
                m for m in self.task_metrics.values() 
                if m.status == status
            ])
        
        # Utenti attivi
        active_users = len(set(
            m.user_id for m in self.task_metrics.values()
            if m.status in [TaskStatus.QUEUED, TaskStatus.RUNNING]
        ))
        
        return {
            "total_tasks": total_tasks,
            "active_tasks": active_tasks,
            "active_users": active_users,
            "status_counts": status_counts,
            "monitoring_active": self.monitoring_active
        }
    
    async def start_monitoring(self):
        """Avvia il monitoring loop"""
        
        if self.monitoring_active:
            logger.warning("⚠️ Monitoring già attivo")
            return
        
        self.monitoring_active = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("🔍 Monitoring task avviato")
    
    async def stop_monitoring(self):
        """Ferma il monitoring loop"""
        
        self.monitoring_active = False
        
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("🛑 Monitoring task fermato")
    
    async def _monitoring_loop(self):
        """Loop principale di monitoring"""
        
        logger.info("🔄 Avvio loop monitoring")
        last_cleanup = time.time()
        
        while self.monitoring_active:
            try:
                # Controlla task stalled
                await self._check_stalled_tasks()
                
                # Cleanup periodico
                if time.time() - last_cleanup > self.cleanup_interval:
                    await self._cleanup_old_tasks()
                    last_cleanup = time.time()
                
                # Aspetta prima del prossimo check
                await asyncio.sleep(10)  # Check ogni 10 secondi
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Errore monitoring loop: {e}")
                await asyncio.sleep(5)
        
        logger.info("🏁 Loop monitoring terminato")
    
    async def _check_stalled_tasks(self):
        """Controlla task che potrebbero essere stalled"""
        
        now = datetime.now(timezone.utc)
        
        for task_id, metrics in self.task_metrics.items():
            if metrics.status != TaskStatus.RUNNING:
                continue
            
            if not metrics.last_activity:
                continue
            
            # Calcola tempo senza attività
            inactive_seconds = (now - metrics.last_activity).total_seconds()
            
            if inactive_seconds > self.stall_timeout:
                metrics.stall_count += 1
                
                logger.warning(
                    f"⏰ Task {task_id} inattivo da {inactive_seconds:.0f}s "
                    f"(stall #{metrics.stall_count})"
                )
                
                if metrics.stall_count >= self.max_stall_checks:
                    logger.error(f"🚫 Task {task_id} marcato come STALLED")
                    self.update_task_status(
                        task_id, 
                        TaskStatus.STALLED,
                        error_message=f"Task stalled dopo {inactive_seconds:.0f}s di inattività"
                    )
    
    async def _cleanup_old_tasks(self):
        """Pulisce task completati vecchi per liberare memoria"""
        
        now = datetime.now(timezone.utc)
        cleanup_age = 3600  # 1 ora
        
        to_remove = []
        
        for task_id, metrics in self.task_metrics.items():
            if metrics.status not in [TaskStatus.COMPLETED, TaskStatus.ERROR, TaskStatus.CANCELLED]:
                continue
            
            if not metrics.completed_at:
                continue
            
            age_seconds = (now - metrics.completed_at).total_seconds()
            
            if age_seconds > cleanup_age:
                to_remove.append(task_id)
        
        for task_id in to_remove:
            del self.task_metrics[task_id]
            logger.info(f"🧹 Task rimosso da monitoring: {task_id}")
        
        if to_remove:
            logger.info(f"🧹 Cleanup completato - rimossi {len(to_remove)} task")


# Istanza globale monitor
task_monitor = TaskMonitor()


# Funzioni helper per integrazione facile
def register_task(task_id: str, user_id: str, max_steps: int = 30) -> TaskMetrics:
    """Registra task per monitoring"""
    return task_monitor.register_task(task_id, user_id, max_steps)


def update_task_status(
    task_id: str, 
    status: str,
    steps_completed: Optional[int] = None,
    error_message: Optional[str] = None
):
    """Aggiorna status task"""
    task_status = TaskStatus(status)
    task_monitor.update_task_status(task_id, task_status, steps_completed, error_message)


def update_task_progress(task_id: str, steps_completed: int):
    """Aggiorna progresso task"""
    task_monitor.update_task_progress(task_id, steps_completed)


def get_task_metrics(task_id: str) -> Optional[TaskMetrics]:
    """Ottiene metriche task"""
    return task_monitor.get_task_metrics(task_id)


def get_system_stats() -> Dict[str, Any]:
    """Ottiene statistiche sistema"""
    return task_monitor.get_system_stats()


async def start_monitoring():
    """Avvia monitoring"""
    await task_monitor.start_monitoring()


async def stop_monitoring():
    """Ferma monitoring"""
    await task_monitor.stop_monitoring()
