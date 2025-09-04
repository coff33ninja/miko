"""
Logging configuration for Anime AI Character system.
Handles structured logging for debugging, monitoring, and content filtering incidents.
"""

import logging
import logging.handlers
import os
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class LogEvent:
    """Structured log event for important system events."""
    timestamp: str
    event_type: str
    level: str
    message: str
    component: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ContentFilterLogger:
    """Specialized logger for content filtering incidents."""
    
    def __init__(self, logger_name: str = "content_filter"):
        self.logger = logging.getLogger(logger_name)
        self._setup_content_filter_handler()
    
    def _setup_content_filter_handler(self) -> None:
        """Set up dedicated handler for content filtering logs."""
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        
        # Create rotating file handler for content filter logs
        handler = logging.handlers.RotatingFileHandler(
            "logs/content_filter.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        
        # JSON formatter for structured logging
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"component": "content_filter", "message": %(message)s}'
        )
        handler.setFormatter(formatter)
        
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_filter_incident(self, user_id: str, provider: str, reason: str, 
                          session_id: Optional[str] = None) -> None:
        """Log content filtering incident without storing inappropriate content.
        
        Args:
            user_id: User identifier
            provider: AI provider that triggered filtering (gemini/ollama)
            reason: Reason for filtering (e.g., "inappropriate_content")
            session_id: Optional session identifier
        """
        event = LogEvent(
            timestamp=datetime.utcnow().isoformat(),
            event_type="content_filter_triggered",
            level="WARNING",
            message="Content filtering triggered",
            component="content_filter",
            user_id=user_id,
            session_id=session_id,
            metadata={
                "provider": provider,
                "reason": reason,
                "action": "request_rejected"
            }
        )
        
        # Log as JSON without the actual content
        self.logger.warning(json.dumps(asdict(event)))


class SystemEventLogger:
    """Logger for system events like API key rotation, errors, etc."""
    
    def __init__(self, logger_name: str = "system_events"):
        self.logger = logging.getLogger(logger_name)
        self._setup_system_handler()
    
    def _setup_system_handler(self) -> None:
        """Set up handler for system event logs."""
        os.makedirs("logs", exist_ok=True)
        
        handler = logging.handlers.RotatingFileHandler(
            "logs/system_events.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"component": "system", "message": %(message)s}'
        )
        handler.setFormatter(formatter)
        
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_api_key_rotation(self, provider: str, old_index: int, new_index: int,
                           reason: str = "rate_limit") -> None:
        """Log API key rotation event.
        
        Args:
            provider: AI provider (e.g., "gemini")
            old_index: Previous key index
            new_index: New key index
            reason: Reason for rotation
        """
        event = LogEvent(
            timestamp=datetime.utcnow().isoformat(),
            event_type="api_key_rotation",
            level="INFO",
            message=f"API key rotated for {provider}",
            component="ai_provider",
            metadata={
                "provider": provider,
                "old_key_index": old_index,
                "new_key_index": new_index,
                "reason": reason
            }
        )
        
        self.logger.info(json.dumps(asdict(event)))
    
    def log_provider_error(self, provider: str, error_type: str, error_message: str,
                          user_id: Optional[str] = None) -> None:
        """Log AI provider error.
        
        Args:
            provider: AI provider name
            error_type: Type of error (e.g., "connection_error", "rate_limit")
            error_message: Error message
            user_id: Optional user identifier
        """
        event = LogEvent(
            timestamp=datetime.utcnow().isoformat(),
            event_type="provider_error",
            level="ERROR",
            message=f"AI provider error: {error_message}",
            component="ai_provider",
            user_id=user_id,
            metadata={
                "provider": provider,
                "error_type": error_type
            }
        )
        
        self.logger.error(json.dumps(asdict(event)))
    
    def log_memory_operation(self, operation: str, user_id: str, success: bool,
                           details: Optional[Dict[str, Any]] = None) -> None:
        """Log memory operation (store/retrieve).
        
        Args:
            operation: Operation type (e.g., "store", "retrieve", "search")
            user_id: User identifier
            success: Whether operation was successful
            details: Optional additional details
        """
        event = LogEvent(
            timestamp=datetime.utcnow().isoformat(),
            event_type="memory_operation",
            level="INFO" if success else "WARNING",
            message=f"Memory {operation} {'succeeded' if success else 'failed'}",
            component="memory_manager",
            user_id=user_id,
            metadata={
                "operation": operation,
                "success": success,
                **(details or {})
            }
        )
        
        level_method = self.logger.info if success else self.logger.warning
        level_method(json.dumps(asdict(event)))


def setup_application_logging(log_level: str = "INFO", debug: bool = False) -> None:
    """Set up application-wide logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        debug: Enable debug mode with more verbose logging
    """
    # Create logs directory
    os.makedirs("logs", exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    if hasattr(console_handler.stream, 'reconfigure'):
        try:
            console_handler.stream.reconfigure(encoding='utf-8')
        except TypeError:
            pass # In some environments, reconfigure might not accept encoding
    root_logger.addHandler(console_handler)
    
    # File handler for general application logs
    file_handler = logging.handlers.RotatingFileHandler(
        "logs/application.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    
    if debug:
        # More detailed format for debug mode
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
        )
    else:
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Set specific logger levels
    if debug:
        # More verbose logging in debug mode
        logging.getLogger("livekit").setLevel(logging.DEBUG)
        logging.getLogger("ollama").setLevel(logging.DEBUG)
        logging.getLogger("google.generativeai").setLevel(logging.DEBUG)
    else:
        # Reduce noise from external libraries
        logging.getLogger("livekit").setLevel(logging.WARNING)
        logging.getLogger("ollama").setLevel(logging.INFO)
        logging.getLogger("google.generativeai").setLevel(logging.INFO)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)


# Global logger instances
content_filter_logger = ContentFilterLogger()
system_event_logger = SystemEventLogger()


def get_content_filter_logger() -> ContentFilterLogger:
    """Get content filter logger instance."""
    return content_filter_logger


def get_system_event_logger() -> SystemEventLogger:
    """Get system event logger instance."""
    return system_event_logger
