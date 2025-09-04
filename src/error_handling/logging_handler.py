"""
Specialized logging handlers for error handling and content filtering.

Provides secure logging for content filtering incidents and comprehensive
error logging without exposing sensitive information.
"""

import logging
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from .exceptions import ContentFilterError, AnimeAIError


class ContentFilterLogger:
    """
    Secure logger for content filtering incidents.

    Logs filtering events without storing the actual inappropriate content,
    maintaining privacy while providing monitoring capabilities.
    """

    def __init__(self, log_file: str = "logs/content_filter.log"):
        """
        Initialize content filter logger.

        Args:
            log_file: Path to content filter log file
        """
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Set up dedicated logger
        self.logger = logging.getLogger("content_filter")
        self.logger.setLevel(logging.INFO)

        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Create file handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.INFO)

        # Create formatter
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.propagate = False  # Don't propagate to root logger

    def log_content_filter_incident(
        self,
        provider: str,
        filter_type: str,
        user_id: Optional[str] = None,
        content_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Log content filtering incident without storing inappropriate content.

        Args:
            provider: AI provider that triggered the filter
            filter_type: Type of content filter triggered
            user_id: User ID (anonymized if needed)
            content_hash: Hash of filtered content for tracking
            metadata: Additional metadata (sanitized)
        """
        incident_data = {
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "filter_type": filter_type,
            "user_id": self._anonymize_user_id(user_id) if user_id else None,
            "content_hash": content_hash,
            "metadata": self._sanitize_metadata(metadata or {}),
        }

        self.logger.warning(f"Content filter triggered: {json.dumps(incident_data)}")

    def log_filter_error(
        self, provider: str, error: Exception, user_id: Optional[str] = None
    ):
        """
        Log content filter system error.

        Args:
            provider: AI provider
            error: Error that occurred
            user_id: User ID (anonymized if needed)
        """
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "user_id": self._anonymize_user_id(user_id) if user_id else None,
        }

        self.logger.error(f"Content filter error: {json.dumps(error_data)}")

    def create_content_hash(self, content: str) -> str:
        """
        Create hash of content for tracking without storing content.

        Args:
            content: Content to hash

        Returns:
            str: SHA-256 hash of content
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def _anonymize_user_id(self, user_id: str) -> str:
        """
        Anonymize user ID for privacy.

        Args:
            user_id: Original user ID

        Returns:
            str: Anonymized user ID
        """
        # Create consistent hash for the same user while maintaining privacy
        return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:8]

    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize metadata to remove sensitive information.

        Args:
            metadata: Original metadata

        Returns:
            Dict: Sanitized metadata
        """
        sanitized = {}

        # Allow only safe metadata fields
        safe_fields = {
            "timestamp",
            "session_id",
            "request_id",
            "model_name",
            "response_length",
            "processing_time",
            "filter_confidence",
        }

        for key, value in metadata.items():
            if key in safe_fields:
                sanitized[key] = value

        return sanitized

    def get_filter_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get content filter statistics for the specified time period.

        Args:
            hours: Number of hours to look back

        Returns:
            Dict: Filter statistics
        """
        stats = {
            "total_incidents": 0,
            "by_provider": {},
            "by_filter_type": {},
            "unique_users": set(),
            "time_period_hours": hours,
        }

        try:
            cutoff_time = datetime.now().timestamp() - (hours * 3600)

            with open(self.log_file, "r") as f:
                for line in f:
                    if "Content filter triggered:" in line:
                        try:
                            # Extract JSON data from log line
                            json_start = line.find('{"timestamp"')
                            if json_start != -1:
                                json_data = json.loads(line[json_start:])

                                # Check if within time period
                                incident_time = datetime.fromisoformat(
                                    json_data["timestamp"]
                                ).timestamp()
                                if incident_time >= cutoff_time:
                                    stats["total_incidents"] += 1

                                    provider = json_data.get("provider", "unknown")
                                    filter_type = json_data.get(
                                        "filter_type", "unknown"
                                    )
                                    user_id = json_data.get("user_id")

                                    stats["by_provider"][provider] = (
                                        stats["by_provider"].get(provider, 0) + 1
                                    )
                                    stats["by_filter_type"][filter_type] = (
                                        stats["by_filter_type"].get(filter_type, 0) + 1
                                    )

                                    if user_id:
                                        stats["unique_users"].add(user_id)

                        except (json.JSONDecodeError, ValueError):
                            continue

        except FileNotFoundError:
            pass

        # Convert set to count
        stats["unique_users"] = len(stats["unique_users"])

        return stats


class ErrorLogger:
    """
    Comprehensive error logger for system errors.

    Provides structured logging for all system errors with
    appropriate detail levels and security considerations.
    """

    def __init__(self, log_file: str = "logs/system_errors.log"):
        """
        Initialize error logger.

        Args:
            log_file: Path to error log file
        """
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Set up dedicated logger
        self.logger = logging.getLogger("system_errors")
        self.logger.setLevel(logging.ERROR)

        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Create file handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.ERROR)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        )
        file_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.propagate = False

    def log_error(
        self,
        error: Exception,
        component: str,
        operation: str,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ):
        """
        Log system error with context.

        Args:
            error: Exception that occurred
            component: Component where error occurred
            operation: Operation that was being performed
            context: Additional context information
            user_id: User ID (anonymized if needed)
        """
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "operation": operation,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "user_id": self._anonymize_user_id(user_id) if user_id else None,
            "context": self._sanitize_context(context or {}),
        }

        # Add specific error details for known error types
        if isinstance(error, AnimeAIError):
            error_data.update(
                {"error_code": error.error_code, "error_details": error.details}
            )

        self.logger.error(f"System error: {json.dumps(error_data)}")

    def log_recovery_attempt(
        self,
        component: str,
        strategy: str,
        success: bool,
        recovery_time: float,
        error: Optional[Exception] = None,
    ):
        """
        Log error recovery attempt.

        Args:
            component: Component being recovered
            strategy: Recovery strategy used
            success: Whether recovery was successful
            recovery_time: Time taken for recovery
            error: Error if recovery failed
        """
        recovery_data = {
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "recovery_strategy": strategy,
            "success": success,
            "recovery_time_seconds": recovery_time,
            "error": str(error) if error else None,
        }

        level = "INFO" if success else "ERROR"
        self.logger.log(
            logging.INFO if success else logging.ERROR,
            f"Recovery attempt: {json.dumps(recovery_data)}",
        )

    def log_fallback_usage(
        self,
        component: str,
        fallback_strategy: str,
        original_error: Exception,
        fallback_success: bool,
    ):
        """
        Log fallback strategy usage.

        Args:
            component: Component using fallback
            fallback_strategy: Fallback strategy used
            original_error: Original error that triggered fallback
            fallback_success: Whether fallback was successful
        """
        fallback_data = {
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "fallback_strategy": fallback_strategy,
            "original_error": str(original_error),
            "fallback_success": fallback_success,
        }

        self.logger.warning(f"Fallback used: {json.dumps(fallback_data)}")

    def _anonymize_user_id(self, user_id: str) -> str:
        """Anonymize user ID for privacy."""
        return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:8]

    def _sanitize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize context to remove sensitive information.

        Args:
            context: Original context

        Returns:
            Dict: Sanitized context
        """
        sanitized = {}

        # Fields to exclude from logging
        sensitive_fields = {
            "password",
            "token",
            "api_key",
            "secret",
            "private_key",
            "user_input",
            "message_content",
            "personal_info",
        }

        for key, value in context.items():
            if key.lower() not in sensitive_fields:
                # Truncate long strings
                if isinstance(value, str) and len(value) > 200:
                    sanitized[key] = value[:200] + "..."
                else:
                    sanitized[key] = value

        return sanitized


def setup_error_logging(
    content_filter_log: str = "logs/content_filter.log",
    system_error_log: str = "logs/system_errors.log",
    application_log: str = "logs/application.log",
) -> tuple[ContentFilterLogger, ErrorLogger]:
    """
    Set up comprehensive error logging system.

    Args:
        content_filter_log: Path to content filter log
        system_error_log: Path to system error log
        application_log: Path to application log

    Returns:
        tuple: (ContentFilterLogger, ErrorLogger)
    """
    # Ensure log directories exist
    for log_path in [content_filter_log, system_error_log, application_log]:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    # Set up root application logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create application log handler
    app_handler = logging.FileHandler(application_log)
    app_handler.setLevel(logging.INFO)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    app_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers
    root_logger.addHandler(app_handler)
    root_logger.addHandler(console_handler)

    # Create specialized loggers
    content_filter_logger = ContentFilterLogger(content_filter_log)
    error_logger = ErrorLogger(system_error_log)

    logging.info("Error logging system initialized")

    return content_filter_logger, error_logger


# Global logger instances
_content_filter_logger: Optional[ContentFilterLogger] = None
_error_logger: Optional[ErrorLogger] = None


def get_content_filter_logger() -> ContentFilterLogger:
    """Get global content filter logger instance."""
    global _content_filter_logger
    if _content_filter_logger is None:
        _content_filter_logger = ContentFilterLogger()
    return _content_filter_logger


def get_error_logger() -> ErrorLogger:
    """Get global error logger instance."""
    global _error_logger
    if _error_logger is None:
        _error_logger = ErrorLogger()
    return _error_logger
