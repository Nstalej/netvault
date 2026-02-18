import os
import sys

# Mock required settings for configuration validation
os.environ["MASTER_KEY"] = "dummy-master-key-for-test"
os.environ["AGENT_AUTH_TOKEN"] = "dummy-agent-token"

import json
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from core.engine.logger import setup_logging, get_logger
from core.config import Settings, SecurityConfig

def verify_logging():
    print("Starting Logging Verification...")
    
    # 1. Setup mock config
    # We instantiate Settings directly to avoid issues with missing settings.yml or env vars
    mock_security = SecurityConfig(
        MASTER_KEY="dummy-master-key",
        AGENT_AUTH_TOKEN="dummy-token"
    )
    config = Settings(security=mock_security)
    
    config.logging.file = "logs/test_verify.log"
    config.logging.max_size_mb = 1 # 1MB
    config.logging.backup_count = 2
    
    # Clear previous logs if any
    if os.path.exists(config.logging.file):
        os.remove(config.logging.file)
    
    setup_logging(config)
    log = get_logger("verification")
    
    # 2. Test context-aware logging
    print("Testing context-aware logging...")
    log.info("Testing structured log", device="Switch-01", ip="10.0.0.1", action="verify")
    
    # 3. Verify JSON contents
    print("Verifying JSON contents in file...")
    with open(config.logging.file, "r") as f:
        last_line = f.readlines()[-1]
        log_data = json.loads(last_line)
        
        print(f"   Log entry: {last_line.strip()}")
        
        # Check for ANSI codes in level or module
        if "\u001b" in log_data["level"] or "\u001b" in log_data["module"]:
            print("ERROR: ANSI escape codes leaked into JSON log")
        else:
            print("SUCCESS: JSON log is clean of ANSI escape codes")
            
        expected_fields = ["timestamp", "level", "module", "message", "device", "ip", "action"]
        missing_fields = [f for f in expected_fields if f not in log_data]
        
        if missing_fields:
            print(f"Missing fields in JSON: {missing_fields}")
        else:
            print("All expected structured fields found in JSON")

    # 4. Test log rotation (optional/simplified)
    print("Testing log rotation (writing large amount of data)...")
    large_message = "X" * 1024 # 1KB
    for _ in range(1100): # > 1MB
        log.info(large_message)
    
    if os.path.exists(f"{config.logging.file}.1"):
        print("Log rotation successful (found .1 file)")
    else:
        print("Log rotation failed (.1 file not found)")

    print("\nLogging System Verification Complete!")

if __name__ == "__main__":
    verify_logging()
