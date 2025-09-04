"""
Custom exception classes for Anime AI Character system.

Provides specific exception types for different system components
to enable targeted error handling and recovery strategies.
"""

from typing import Optional, Dict, Any


class AnimeAIError(Exception):
    """Base exception for all Anime AI Character system errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize base error.

        Args:
            message: Error message
            error_code: Optional error code for categorization
            details: Optional additional error details
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details,
        }


class AIProviderError(AnimeAIError):
    """Errors related to AI provider operations."""

    def __init__(
        self,
        message: str,
        provider: str,
        error_code: Optional[str] = None,
        is_rate_limit: bool = False,
        is_content_filter: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize AI provider error.

        Args:
            message: Error message
            provider: AI provider name ('ollama', 'gemini')
            error_code: Optional error code
            is_rate_limit: Whether this is a rate limit error
            is_content_filter: Whether this is a content filtering error
            details: Optional additional details
        """
        super().__init__(message, error_code, details)
        self.provider = provider
        self.is_rate_limit = is_rate_limit
        self.is_content_filter = is_content_filter


class MemoryError(AnimeAIError):
    """Errors related to memory management operations."""

    def __init__(
        self,
        message: str,
        operation: str,
        user_id: Optional[str] = None,
        is_mem0_error: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize memory error.

        Args:
            message: Error message
            operation: Memory operation that failed
            user_id: User ID if applicable
            is_mem0_error: Whether this is a Mem0 service error
            details: Optional additional details
        """
        super().__init__(message, details=details)
        self.operation = operation
        self.user_id = user_id
        self.is_mem0_error = is_mem0_error


class LiveKitError(AnimeAIError):
    """Errors related to LiveKit operations."""

    def __init__(
        self,
        message: str,
        operation: str,
        room_name: Optional[str] = None,
        participant_id: Optional[str] = None,
        is_connection_error: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize LiveKit error.

        Args:
            message: Error message
            operation: LiveKit operation that failed
            room_name: Room name if applicable
            participant_id: Participant ID if applicable
            is_connection_error: Whether this is a connection error
            details: Optional additional details
        """
        super().__init__(message, details=details)
        self.operation = operation
        self.room_name = room_name
        self.participant_id = participant_id
        self.is_connection_error = is_connection_error


class Live2DError(AnimeAIError):
    """Errors related to Live2D operations."""

    def __init__(
        self,
        message: str,
        operation: str,
        model_path: Optional[str] = None,
        animation_type: Optional[str] = None,
        is_rendering_error: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Live2D error.

        Args:
            message: Error message
            operation: Live2D operation that failed
            model_path: Model file path if applicable
            animation_type: Animation type if applicable
            is_rendering_error: Whether this is a rendering error
            details: Optional additional details
        """
        super().__init__(message, details=details)
        self.operation = operation
        self.model_path = model_path
        self.animation_type = animation_type
        self.is_rendering_error = is_rendering_error


class ConfigurationError(AnimeAIError):
    """Errors related to system configuration."""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_file: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize configuration error.

        Args:
            message: Error message
            config_key: Configuration key that caused the error
            config_file: Configuration file if applicable
            details: Optional additional details
        """
        super().__init__(message, details=details)
        self.config_key = config_key
        self.config_file = config_file


class ContentFilterError(AnimeAIError):
    """Errors related to content filtering."""

    def __init__(
        self,
        message: str,
        provider: str,
        filter_type: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize content filter error.

        Args:
            message: Error message
            provider: AI provider that triggered the filter
            filter_type: Type of content filter triggered
            user_id: User ID if applicable
            details: Optional additional details (should not contain filtered content)
        """
        super().__init__(message, details=details)
        self.provider = provider
        self.filter_type = filter_type
        self.user_id = user_id


class NetworkError(AnimeAIError):
    """Errors related to network operations."""

    def __init__(
        self,
        message: str,
        operation: str,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        is_timeout: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize network error.

        Args:
            message: Error message
            operation: Network operation that failed
            endpoint: API endpoint if applicable
            status_code: HTTP status code if applicable
            is_timeout: Whether this is a timeout error
            details: Optional additional details
        """
        super().__init__(message, details=details)
        self.operation = operation
        self.endpoint = endpoint
        self.status_code = status_code
        self.is_timeout = is_timeout


class ValidationError(AnimeAIError):
    """Errors related to input validation."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        expected_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize validation error.

        Args:
            message: Error message
            field: Field name that failed validation
            value: Invalid value (sanitized)
            expected_type: Expected value type
            details: Optional additional details
        """
        super().__init__(message, details=details)
        self.field = field
        self.value = value
        self.expected_type = expected_type
