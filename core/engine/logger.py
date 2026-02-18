"""
NetVault - Structured Logging System
Provides colored console output, JSON file logging, and context-aware logging.
"""
import logging
import logging.handlers
import json
import os
import sys
import platform
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# ANSI Color Codes (No external dependencies)
class Colors:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

class ColoredFormatter(logging.Formatter):
    """Formatter for colored console output"""
    LEVEL_COLORS = {
        logging.DEBUG: Colors.BLUE,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.MAGENTA,
    }

    def format(self, record):
        # Create a copy of the record or work with local variables to avoid affecting other handlers
        color = self.LEVEL_COLORS.get(record.levelno, Colors.RESET)
        
        # We temporarily change the record attributes for the super().format call
        orig_levelname = record.levelname
        orig_name = record.name
        
        record.levelname = f"{color}{record.levelname}{Colors.RESET}"
        record.name = f"{Colors.CYAN}{record.name}{Colors.RESET}"
        
        try:
            return super().format(record)
        finally:
            # Restore original values so other handlers (like JSON) get clean data
            record.levelname = orig_levelname
            record.name = orig_name

class JSONFormatter(logging.Formatter):
    """Formatter for JSON-structured logs"""
    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra context if present
        if hasattr(record, "extra_context"):
            log_obj.update(record.extra_context)
            
        # Add standard fields from record
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj)

class ContextLoggerAdapter(logging.LoggerAdapter):
    """Adapter that allows passing context as keyword arguments"""
    def process(self, msg, kwargs):
        # Extract 'extra' from kwargs or create new if not exists
        extra = kwargs.get("extra", {})
        
        # Filter out standard keywords and move others to extra_context
        context = {k: v for k, v in kwargs.items() if k not in ["extra", "exc_info", "stack_info", "stacklevel"]}
        
        # Update extra with our context
        extra["extra_context"] = context
        kwargs["extra"] = extra
        
        # Remove context keys from kwargs so they don't break the log method
        for k in context:
            del kwargs[k]
            
        return msg, kwargs

def setup_logging(config: Any):
    """Configure logging based on application settings"""
    root_logger = logging.getLogger("netvault")
    root_logger.setLevel(config.logging.level)
    
    # Avoid duplicate handlers if setup_logging is called multiple times
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # 1. Console Handler (Colored)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter(config.logging.format))
    root_logger.addHandler(console_handler)

    # 2. File Handler (JSON + Rotation)
    if config.logging.file:
        log_path = Path(config.logging.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            config.logging.file,
            maxBytes=config.logging.max_size_mb * 1024 * 1024,
            backupCount=config.logging.backup_count
        )
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

    root_logger.info("Logging system initialized")

def get_logger(name: str) -> ContextLoggerAdapter:
    """Get a configured context-aware logger"""
    # Ensure name is prefixed with netvault for root settings to apply
    if not name.startswith("netvault.") and name != "netvault":
        name = f"netvault.{name}"
    return ContextLoggerAdapter(logging.getLogger(name), {})

def log_system_info(config: Any):
    """Log system diagnostics on startup"""
    log = get_logger("system")
    
    try:
        import psutil
        mem = psutil.virtual_memory()
        available_gb = round(mem.available / (1024**3), 2)
    except ImportError:
        available_gb = "Unknown (psutil not installed)"

    log.info(
        "System diagnostics",
        app_name=config.app.name,
        app_version=config.app.version,
        python_version=sys.version.split()[0],
        os=f"{platform.system()} {platform.release()}",
        hostname=socket.gethostname(),
        memory_available_gb=available_gb
    )
