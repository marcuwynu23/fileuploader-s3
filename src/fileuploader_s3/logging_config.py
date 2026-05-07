"""Logging configuration module for fileuploader-s3 application."""

import logging
import os
import time
import json
from .config import LOG_LEVEL, LOG_FORMAT, USE_LOKI


class StructuredLogger:
    """Structured logger for Loki/Promtail compatibility."""
    
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        self.use_loki = USE_LOKI
        
    def _log_structured(self, level, message, **kwargs):
        """Log with structured data for Loki compatibility."""
        timestamp = time.time()
        log_data = {
            'timestamp': timestamp,
            'level': level,
            'message': message,
            **kwargs
        }
        
        if self.use_loki:
            # Format as JSON for Loki
            log_msg = json.dumps(log_data)
            getattr(self.logger, level.lower())(log_msg)
        else:
            # Standard logging format
            getattr(self.logger, level.lower())(message, extra=kwargs)
    
    def debug(self, message, **kwargs):
        self._log_structured('DEBUG', message, **kwargs)
    
    def info(self, message, **kwargs):
        self._log_structured('INFO', message, **kwargs)
    
    def warning(self, message, **kwargs):
        self._log_structured('WARNING', message, **kwargs)
    
    def error(self, message, **kwargs):
        self._log_structured('ERROR', message, **kwargs)
    
    def critical(self, message, **kwargs):
        self._log_structured('CRITICAL', message, **kwargs)


def setup_logging():
    """Configure application logging for better debugging."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # JSON format for Loki/Promtail compatibility
    if USE_LOKI:
        log_format = '{"timestamp": %(asctime)s, "level": %(levelname)s, "message": %(message)s}'
    else:
        log_format = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Configure handlers
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    handlers.append(console_handler)
    
    # File handler (optional) - use /app/logs for Docker or fallback to local
    try:
        log_dir = '/app/logs' if os.path.exists('/app/logs') else '.'
        log_file = os.path.join(log_dir, 'fileuploader.log')
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    except Exception:
        pass  # File handler is optional
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        handlers=handlers,
        force=True  # Force reconfiguration
    )
    
    # Suppress Werkzeug development server logs unless in debug mode
    if log_level != 'DEBUG':
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    # Create structured logger for application
    return StructuredLogger(__name__)

