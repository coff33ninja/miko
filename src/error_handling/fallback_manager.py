"""
Fallback management system for graceful degradation.

Provides fallback strategies for different system components
when primary functionality fails.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, List, Union
from dataclasses import dataclass
from enum import Enum

from .exceptions import AnimeAIError


class FallbackStrategy(Enum):
    """Available fallback strategies."""

    RETRY = "retry"
    ALTERNATIVE_PROVIDER = "alternative_provider"
    CACHED_RESPONSE = "cached_response"
    SIMPLIFIED_RESPONSE = "simplified_response"
    SESSION_ONLY = "session_only"
    STATIC_FALLBACK = "static_fallback"
    GRACEFUL_DEGRADATION = "graceful_degradation"
    ERROR_MESSAGE = "error_message"


@dataclass
class FallbackResult:
    """Result of a fallback operation."""

    success: bool
    strategy_used: FallbackStrategy
    result: Any
    error: Optional[Exception] = None
    attempts: int = 1
    fallback_chain: List[str] = None

    def __post_init__(self):
        if self.fallback_chain is None:
            self.fallback_chain = []


class FallbackManager:
    """
    Manages fallback strategies for system components.

    Provides graceful degradation when primary functionality fails,
    ensuring the system remains operational even with component failures.
    """

    def __init__(self):
        """Initialize fallback manager."""
        self.logger = logging.getLogger(__name__)
        self._fallback_strategies: Dict[str, List[FallbackStrategy]] = {}
        self._fallback_handlers: Dict[FallbackStrategy, Callable] = {}
        self._cached_responses: Dict[str, Any] = {}
        self._max_cache_size = 100

        # Register default fallback handlers
        self._register_default_handlers()

    def _register_default_handlers(self):
        """Register default fallback handlers."""
        self._fallback_handlers[FallbackStrategy.RETRY] = self._retry_handler
        self._fallback_handlers[FallbackStrategy.CACHED_RESPONSE] = (
            self._cached_response_handler
        )
        self._fallback_handlers[FallbackStrategy.SIMPLIFIED_RESPONSE] = (
            self._simplified_response_handler
        )
        self._fallback_handlers[FallbackStrategy.SESSION_ONLY] = (
            self._session_only_handler
        )
        self._fallback_handlers[FallbackStrategy.STATIC_FALLBACK] = (
            self._static_fallback_handler
        )
        self._fallback_handlers[FallbackStrategy.ERROR_MESSAGE] = (
            self._error_message_handler
        )

    def register_fallback_chain(
        self, component: str, strategies: List[FallbackStrategy]
    ):
        """
        Register fallback chain for a component.

        Args:
            component: Component name
            strategies: List of fallback strategies in order of preference
        """
        self._fallback_strategies[component] = strategies
        self.logger.info(
            f"Registered fallback chain for {component}: {[s.value for s in strategies]}"
        )

    def register_fallback_handler(self, strategy: FallbackStrategy, handler: Callable):
        """
        Register custom fallback handler.

        Args:
            strategy: Fallback strategy
            handler: Handler function
        """
        self._fallback_handlers[strategy] = handler
        self.logger.info(f"Registered custom handler for {strategy.value}")

    async def execute_with_fallback(
        self,
        component: str,
        primary_operation: Callable,
        operation_args: tuple = (),
        operation_kwargs: Dict[str, Any] = None,
        context: Dict[str, Any] = None,
    ) -> FallbackResult:
        """
        Execute operation with fallback strategies.

        Args:
            component: Component name
            primary_operation: Primary operation to execute
            operation_args: Arguments for primary operation
            operation_kwargs: Keyword arguments for primary operation
            context: Additional context for fallback handlers

        Returns:
            FallbackResult: Result of operation or fallback
        """
        operation_kwargs = operation_kwargs or {}
        context = context or {}

        # Try primary operation first
        try:
            result = await self._execute_operation(
                primary_operation, operation_args, operation_kwargs
            )
            return FallbackResult(
                success=True,
                strategy_used=None,
                result=result,
                fallback_chain=["primary"],
            )
        except Exception as primary_error:
            self.logger.warning(
                f"Primary operation failed for {component}: {primary_error}"
            )

            # Execute fallback chain
            return await self._execute_fallback_chain(
                component, primary_error, context, operation_args, operation_kwargs
            )

    async def _execute_fallback_chain(
        self,
        component: str,
        primary_error: Exception,
        context: Dict[str, Any],
        operation_args: tuple,
        operation_kwargs: Dict[str, Any],
    ) -> FallbackResult:
        """Execute fallback chain for component."""
        strategies = self._fallback_strategies.get(
            component, [FallbackStrategy.ERROR_MESSAGE]
        )
        fallback_chain = ["primary_failed"]

        for strategy in strategies:
            try:
                handler = self._fallback_handlers.get(strategy)
                if not handler:
                    self.logger.error(
                        f"No handler registered for strategy: {strategy.value}"
                    )
                    continue

                self.logger.info(f"Attempting fallback strategy: {strategy.value}")

                # Execute fallback handler
                result = await handler(
                    component=component,
                    error=primary_error,
                    context=context,
                    operation_args=operation_args,
                    operation_kwargs=operation_kwargs,
                )

                fallback_chain.append(strategy.value)

                return FallbackResult(
                    success=True,
                    strategy_used=strategy,
                    result=result,
                    fallback_chain=fallback_chain,
                )

            except Exception as fallback_error:
                self.logger.warning(
                    f"Fallback strategy {strategy.value} failed: {fallback_error}"
                )
                fallback_chain.append(f"{strategy.value}_failed")
                continue

        # All fallbacks failed
        return FallbackResult(
            success=False,
            strategy_used=None,
            result=None,
            error=primary_error,
            fallback_chain=fallback_chain,
        )

    async def _execute_operation(
        self, operation: Callable, args: tuple, kwargs: Dict[str, Any]
    ) -> Any:
        """Execute operation with proper async handling."""
        if asyncio.iscoroutinefunction(operation):
            return await operation(*args, **kwargs)
        else:
            return operation(*args, **kwargs)

    # Default fallback handlers

    async def _retry_handler(
        self,
        component: str,
        error: Exception,
        context: Dict[str, Any],
        operation_args: tuple,
        operation_kwargs: Dict[str, Any],
    ) -> Any:
        """Retry handler with exponential backoff."""
        max_retries = context.get("max_retries", 3)
        base_delay = context.get("base_delay", 1.0)
        operation = context.get("retry_operation")

        if not operation:
            raise ValueError("retry_operation not provided in context")

        for attempt in range(max_retries):
            try:
                await asyncio.sleep(base_delay * (2**attempt))
                return await self._execute_operation(
                    operation, operation_args, operation_kwargs
                )
            except Exception as retry_error:
                if attempt == max_retries - 1:
                    raise retry_error
                self.logger.warning(
                    f"Retry attempt {attempt + 1} failed: {retry_error}"
                )

        raise error

    async def _cached_response_handler(
        self,
        component: str,
        error: Exception,
        context: Dict[str, Any],
        operation_args: tuple,
        operation_kwargs: Dict[str, Any],
    ) -> Any:
        """Return cached response if available."""
        cache_key = context.get("cache_key")
        if not cache_key:
            # Generate cache key from operation args
            cache_key = (
                f"{component}:{hash(str(operation_args) + str(operation_kwargs))}"
            )

        cached_result = self._cached_responses.get(cache_key)
        if cached_result:
            self.logger.info(f"Using cached response for {component}")
            return cached_result

        raise error

    async def _simplified_response_handler(
        self,
        component: str,
        error: Exception,
        context: Dict[str, Any],
        operation_args: tuple,
        operation_kwargs: Dict[str, Any],
    ) -> Any:
        """Return simplified response based on component type."""
        if component == "ai_provider":
            return self._get_simplified_ai_response(context)
        elif component == "memory_manager":
            return self._get_simplified_memory_response(context)
        elif component == "live2d_animation":
            return self._get_simplified_animation_response(context)
        else:
            return {
                "status": "simplified",
                "message": "Service temporarily unavailable",
            }

    async def _session_only_handler(
        self,
        component: str,
        error: Exception,
        context: Dict[str, Any],
        operation_args: tuple,
        operation_kwargs: Dict[str, Any],
    ) -> Any:
        """Handle session-only fallback for memory operations."""
        if component == "memory_manager":
            return {
                "status": "session_only",
                "message": "Using session-only memory",
                "memories": [],
                "context": "",
            }

        raise error

    async def _static_fallback_handler(
        self,
        component: str,
        error: Exception,
        context: Dict[str, Any],
        operation_args: tuple,
        operation_kwargs: Dict[str, Any],
    ) -> Any:
        """Return static fallback content."""
        if component == "live2d_animation":
            return {
                "status": "static",
                "expression": "neutral",
                "message": "Animation unavailable, using static display",
            }
        elif component == "ai_provider":
            return self._get_static_ai_response(context)

        raise error

    async def _error_message_handler(
        self,
        component: str,
        error: Exception,
        context: Dict[str, Any],
        operation_args: tuple,
        operation_kwargs: Dict[str, Any],
    ) -> Any:
        """Return user-friendly error message."""
        error_messages = {
            "ai_provider": "Gomen! I'm having trouble thinking right now... (*nervous laugh*) Could you try again?",
            "memory_manager": "I might not remember everything perfectly right now, but let's keep chatting!",
            "live2d_animation": "My animations are being a bit shy today, but I'm still here to talk!",
            "livekit_agent": "There's a small connection hiccup, but I'm still listening!",
            "web_server": "The web interface is having a moment, please refresh and try again!",
        }

        return {
            "error": True,
            "message": error_messages.get(
                component, "Something went wrong, but I'm still here!"
            ),
            "component": component,
            "can_retry": True,
        }

    def _get_simplified_ai_response(self, context: Dict[str, Any]) -> str:
        """Get simplified AI response."""
        user_message = context.get("user_message", "")

        # Simple keyword-based responses
        if any(word in user_message.lower() for word in ["hello", "hi", "hey"]):
            return "Hello! Nice to meet you! (*smile*)"
        elif any(word in user_message.lower() for word in ["how", "what", "why"]):
            return "That's a great question! I'm still learning, so bear with me! (*cheerful*)"
        elif any(
            word in user_message.lower() for word in ["bye", "goodbye", "see you"]
        ):
            return "Goodbye! It was nice talking with you! (*wave*)"
        else:
            return "I hear you! Let me think about that... (*thoughtful*)"

    def _get_simplified_memory_response(
        self, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get simplified memory response."""
        return {
            "memories": [],
            "context": "Starting fresh conversation",
            "status": "simplified",
        }

    def _get_simplified_animation_response(
        self, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get simplified animation response."""
        return {"expression": "neutral", "intensity": 0.5, "status": "simplified"}

    def _get_static_ai_response(self, context: Dict[str, Any]) -> str:
        """Get static AI response."""
        static_responses = [
            "I'm here and listening! (*smile*)",
            "Tell me more about that!",
            "That sounds interesting!",
            "I'm still learning, but I'm happy to chat!",
            "What would you like to talk about?",
        ]

        import random

        return random.choice(static_responses)

    def cache_response(self, key: str, response: Any):
        """
        Cache response for future fallback use.

        Args:
            key: Cache key
            response: Response to cache
        """
        # Implement LRU-style cache management
        if len(self._cached_responses) >= self._max_cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self._cached_responses))
            del self._cached_responses[oldest_key]

        self._cached_responses[key] = response
        self.logger.debug(f"Cached response for key: {key}")

    def clear_cache(self):
        """Clear response cache."""
        self._cached_responses.clear()
        self.logger.info("Response cache cleared")

    def get_fallback_stats(self) -> Dict[str, Any]:
        """Get fallback usage statistics."""
        return {
            "registered_components": list(self._fallback_strategies.keys()),
            "available_strategies": [s.value for s in FallbackStrategy],
            "cache_size": len(self._cached_responses),
            "max_cache_size": self._max_cache_size,
        }


# Global fallback manager instance
_fallback_manager: Optional[FallbackManager] = None


def get_fallback_manager() -> FallbackManager:
    """Get global fallback manager instance."""
    global _fallback_manager
    if _fallback_manager is None:
        _fallback_manager = FallbackManager()
    return _fallback_manager
