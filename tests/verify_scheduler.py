import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from core.config import get_config
from core.engine.scheduler import get_scheduler
from core.database.db import DatabaseManager
from core.engine.credential_vault import CredentialVault
from core.engine.device_manager import get_device_manager
from core.engine.audit_engine import get_audit_engine

# Setup basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("verify_scheduler")

async def verify():
    logger.info("Starting scheduler verification...")
    
    config = get_config()
    
    # 1. Initialize Components (Needed for singletons to work)
    db = DatabaseManager(":memory:")
    await db.connect()
    
    # Mocking necessary things for Vault
    vault = CredentialVault(db, "test-master-key-32-chars-long-!!!")
    
    # Initialize singletons
    # Use the 'get_x' helpers to ensure they are registered
    from core.engine.device_manager import get_device_manager
    from core.engine.audit_engine import get_audit_engine
    
    dm = get_device_manager(db, vault)
    ae = get_audit_engine(db, dm)
    
    # 2. Get and Start Scheduler
    scheduler = get_scheduler()
    
    logger.info("Starting scheduler...")
    await scheduler.start()
    
    # 3. Verify Default Jobs
    jobs = scheduler.list_jobs()
    logger.info(f"Registered jobs: {[j['id'] for j in jobs]}")
    
    expected_jobs = ["poll_all_devices", "check_agent_heartbeats", "scheduled_audit", "cache_cleanup"]
    for job_id in expected_jobs:
        status = scheduler.get_job_status(job_id)
        if status:
            logger.info(f"✓ Job '{job_id}' is active. Next run: {status['next_run_time']}")
        else:
            logger.error(f"✗ Job '{job_id}' NOT FOUND")

    # 4. Test Custom Job
    event = asyncio.Event()
    
    async def test_job():
        logger.info("!!! Test job triggered !!!")
        event.set()

    logger.info("Adding custom test job (1s interval)...")
    scheduler.add_custom_job("verify_test_job", test_job, trigger="interval", seconds=1)
    
    try:
        await asyncio.wait_for(event.wait(), timeout=5)
        logger.info("✓ Custom job execution verified")
    except asyncio.TimeoutError:
        logger.error("✗ Custom job failed to trigger within 5 seconds")

    # 5. Test Job Removal
    scheduler.remove_job("verify_test_job")
    if not scheduler.get_job_status("verify_test_job"):
        logger.info("✓ Custom job removal verified")
    else:
        logger.error("✗ Custom job removal failed")

    # 6. Shutdown
    logger.info("Stopping scheduler...")
    await scheduler.stop()
    
    await db.disconnect()
    logger.info("Verification complete")

if __name__ == "__main__":
    asyncio.run(verify())
