"""
Error handling and fallback mechanisms for Anime AI Character system.

This module provides comprehensive error handling, recovery mechanisms,
and fallback strategies for all system components.
"""

from .exceptions import (
    AnimeAIError,
    AIProviderError,
    MemoryError,
    LiveKitError,
    Live2DError,
    ConfigurationError,
    ContentFilterError
)

from .fallback_manager import (
    FallbackManager,
    FallbackStrategy,
    FallbackResult
)

from .error_recovery import (
    ErrorRecoveryManager,
    RecoveryStrategy,
    RecoveryResult
)

from .logging_handler import (
    ContentFilterLogger,
    ErrorLogger,
    setup_error_logging
)

__all__ = [
    'AnimeAIError',
    'AIProviderError', 
    'MemoryError',
    'LiveKitError',
    'Live2DError',
    'ConfigurationError',
    'ContentFilterError',
    'FallbackManager',
    'FallbackStrategy',
    'FallbackResult',
    'ErrorRecoveryManager',
    'RecoveryStrategy',
    'RecoveryResult',
    'ContentFilterLogger',
    'ErrorLogger',
    'setup_error_logging'
]