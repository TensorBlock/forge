"""
Logger configuration using loguru.
"""

import sys
from pathlib import Path

from loguru import logger

# Remove default handler
logger.remove()

# Add console handler with custom format
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG",
    enqueue=True,  # Thread-safe logging
    backtrace=True,  # Detailed traceback
    diagnose=True,  # Enable exception diagnosis
)

# Add file handler for debugging
log_path = Path("logs")
log_path.mkdir(exist_ok=True)

logger.add(
    "logs/forge_{time}.log",
    rotation="1 day",  # Create new file daily
    retention="1 week",  # Keep logs for 1 week
    compression="zip",  # Compress rotated logs
    level="DEBUG",
    enqueue=True,
    backtrace=True,
    diagnose=True,
)

# Export logger instance
get_logger = logger.bind
