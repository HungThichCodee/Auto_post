import logging
import os
import sys

# Define some basic colors for console
class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: '\033[94m',      # Blue
        logging.INFO: '\033[92m',       # Green
        logging.WARNING: '\033[93m',    # Yellow
        logging.ERROR: '\033[91m',      # Red
        logging.CRITICAL: '\033[95m'    # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)

def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Sets up a structured logger with both console and file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers if logger is re-initialized
    if logger.handlers:
        return logger
        
    log_format = '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
    
    # File handler
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'output')
    os.makedirs(log_dir, exist_ok=True)
    file_path = os.path.join(log_dir, 'auto_post.log')
    
    file_handler = logging.FileHandler(file_path, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if sys.stdout.isatty():
        console_handler.setFormatter(ColorFormatter(log_format))
    else:
        console_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(console_handler)
    
    return logger

def log_step(logger: logging.Logger, step_name: str, details: str = ""):
    """Helper to track pipeline steps."""
    msg = f"=== STEP: {step_name} ==="
    if details:
        msg += f" | {details}"
    logger.info(msg)
