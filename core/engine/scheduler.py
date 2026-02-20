"""
NetVault - Task Scheduler
Main scheduler for periodic tasks like device polling and audits.
"""
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from core.config import get_config
from core.engine.logger import get_logger
from core.engine.device_manager import get_device_manager
from core.engine.audit_engine import get_audit_engine

logger = get_logger("netvault.engine.scheduler")

class NetVaultScheduler:
    """
    Singleton wrapper around APScheduler to manage NetVault periodic tasks.
    """
    _instance: Optional['NetVaultScheduler'] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(NetVaultScheduler, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Ensure __init__ only runs once if singleton
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self.config = get_config()
        self.scheduler = AsyncIOScheduler()
        self._initialized = True
        logger.info("NetVault Scheduler initialized")

    @classmethod
    def get_instance(cls) -> 'NetVaultScheduler':
        """Access the singleton instance of the Scheduler."""
        if cls._instance is None:
            cls._instance = NetVaultScheduler()
        return cls._instance

    async def start(self):
        """Register default jobs and start the scheduler."""
        if not self.config.modules.scheduler:
            logger.info("Scheduler module is disabled in config")
            return

        if self.scheduler.running:
            logger.warning("Scheduler is already running")
            return

        # Register default jobs
        self._register_default_jobs()
        
        self.scheduler.start()
        logger.info("NetVault Scheduler started")

    async def stop(self):
        """Graceful shutdown of the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("NetVault Scheduler stopped")

    def _register_default_jobs(self):
        """Register the hardcoded NetVault jobs from config."""
        
        # 1. Poll All Devices
        poll_interval = self.config.polling.interval_minutes
        self.add_custom_job(
            "poll_all_devices",
            self._job_poll_all,
            trigger=IntervalTrigger(minutes=poll_interval)
        )
        
        # 2. Check Agent Heartbeats
        heartbeat_interval = self.config.agents.heartbeat_interval_seconds
        self.add_custom_job(
            "check_agent_heartbeats",
            self._job_check_heartbeats,
            trigger=IntervalTrigger(seconds=heartbeat_interval)
        )
        
        # 3. Scheduled Network Audit
        audit_time = self.config.audit.scheduled_time # e.g. "02:00"
        try:
            hour, minute = map(int, audit_time.split(":"))
            self.add_custom_job(
                "scheduled_audit",
                self._job_scheduled_audit,
                trigger=CronTrigger(hour=hour, minute=minute)
            )
        except Exception as e:
            logger.error(f"Invalid audit scheduled time '{audit_time}': {e}")
            # Fallback to default 02:00
            self.add_custom_job(
                "scheduled_audit",
                self._job_scheduled_audit,
                trigger=CronTrigger(hour=2, minute=0)
            )

        # 4. Cache Cleanup
        self.add_custom_job(
            "cache_cleanup",
            self._job_cache_cleanup,
            trigger=IntervalTrigger(hours=1)
        )

    def add_custom_job(self, job_id: str, func: Callable, trigger, **kwargs):
        """Add a job to the scheduler."""
        try:
            # Wrap function to log execution time and handle exceptions
            async def wrapped_job(*args, **inner_kwargs):
                start_time = time.time()
                logger.debug(f"Starting job: {job_id}")
                try:
                    await func(*args, **inner_kwargs)
                    duration = time.time() - start_time
                    logger.info(f"Job completed: {job_id} in {duration:.2f}s")
                except Exception as e:
                    logger.exception(f"Exception in job {job_id}: {e}")

            self.scheduler.add_job(
                wrapped_job,
                trigger=trigger,
                id=job_id,
                replace_existing=True,
                **kwargs
            )
            logger.debug(f"Registered job: {job_id}")
        except Exception as e:
            logger.error(f"Failed to register job {job_id}: {e}")

    def remove_job(self, job_id: str):
        """Remove a job by ID."""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job: {job_id}")
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")

    def list_jobs(self) -> List[Dict[str, Any]]:
        """Return a list of all scheduled jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        return jobs

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific job."""
        job = self.scheduler.get_job(job_id)
        if not job:
            return None
        return {
            "id": job.id,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        }

    # ─── Job Implementations ───

    async def _job_poll_all(self):
        """Poll all network devices."""
        try:
            dm = get_device_manager()
            await dm.poll_all()
        except Exception as e:
            logger.error(f"Error in poll_all job: {e}")

    async def _job_check_heartbeats(self):
        """Mark agents as disconnected if no heartbeat."""
        # Generic heartbeat check logic
        # In a full implementation, this would iterate over agents in DB
        logger.debug("Checking agent heartbeats...")

    async def _job_scheduled_audit(self):
        """Run the daily network-wide audit."""
        try:
            ae = get_audit_engine()
            await ae.run_network_audit()
        except Exception as e:
            logger.error(f"Error in scheduled_audit job: {e}")

    async def _job_cache_cleanup(self):
        """Clean up stale entries in the device manager cache."""
        try:
            # Placeholder for cache cleanup logic
            logger.debug("Cleaning up Device Manager cache...")
        except Exception as e:
            logger.error(f"Error in cache_cleanup job: {e}")

_SCHEDULER_INSTANCE: Optional[NetVaultScheduler] = None

def get_scheduler() -> NetVaultScheduler:
    """Access the singleton instance of the Scheduler."""
    global _SCHEDULER_INSTANCE
    if _SCHEDULER_INSTANCE is None:
        _SCHEDULER_INSTANCE = NetVaultScheduler()
    return _SCHEDULER_INSTANCE
