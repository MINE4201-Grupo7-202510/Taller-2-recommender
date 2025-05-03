import os
import logging
import config # Import config for logging settings

# Setup logging
logging.basicConfig(level=config.LOGGING_LEVEL, format=config.LOGGING_FORMAT)
logger = logging.getLogger(__name__)

def ensure_model_dir():
    """Create model directory if it doesn't exist"""
    if not os.path.exists(config.MODEL_DIR):
        os.makedirs(config.MODEL_DIR)
        logger.info(f"Created model directory: {config.MODEL_DIR}")

def get_day_period(hour):
    """Determine day period based on hour"""
    if 6 <= hour < 12:
        return 'morning'
    elif 12 <= hour < 18:
        return 'afternoon'
    elif 18 <= hour < 24:
        return 'evening'
    else:
        return 'night'

def get_logger(name: str) -> logging.Logger:
    """Gets a logger instance"""
    return logging.getLogger(name)