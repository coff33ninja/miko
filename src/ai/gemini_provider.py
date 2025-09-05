"""
Google Gemini AI Provider implementation with content filtering and API key rotation.
Provides cloud-based AI processing with built-in safety features.
"""

import asyncio
import logging
import re
import time
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from .base_provider import AIProvider, Message

if TYPE_CHECKING:
    from .base_provider import MemoryContext

try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
except ImportError:
    genai = None

from src.error_handling.exceptions import (
    AIProviderError,
    ContentFilterError,
    NetworkError,
)
from src.error_handling.fallback_manager import get_fallback_manager, FallbackStrategy
from src.error_handling.error_recovery import get_recovery_manager, RecoveryStrategy
from src.error_handling.logging_handler import get_content_filter_logger, get_error_logger

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """Gemini provider with content filtering and API key rotation."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Gemini provider with API key rotation support.

        Args:
            config: Configuration dictionary containing:
                - api_keys: List of Gemini API keys for rotation
                - model: Gemini model name (default: 'gemini-pro')
                - current_key_index: Current key index (default: 0)
        """
        super().__init__(config)

        if genai is None:
            raise ImportError(
                "google-generativeai library is required for GeminiProvider"
            )

        self.api_keys = config.get("api_keys", [])
        if not self.api_keys:
            raise ValueError("At least one Gemini API key is required")

        self.model_name = config.get("model", "gemini-pro")
        self.current_key_index = config.get("current_key_index", 0)

        # Ensure current_key_index is within bounds
        if self.current_key_index >= len(self.api_keys):
            self.current_key_index = 0

        # Error handling components
        self.fallback_manager = get_fallback_manager()
        self.recovery_manager = get_recovery_manager()
        self.content_filter_logger = get_content_filter_logger()
        self.error_logger = get_error_logger()

        # Rate limiting tracking
        self.rate_limit_reset_times: Dict[int, float] = {}
        self.consecutive_failures = 0
        self.last_successful_request = time.time()

        # Configure initial API key
        self._configure_current_key()

        # Safety settings for content filtering
        if genai:
            self.safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
        else:
            self.safety_settings = {}

        # Register with error recovery system
        self._register_error_recovery()

        logger.info(f"Initialized GeminiProvider with {len(self.api_keys)} API keys")

    def _configure_current_key(self):
        """Configure the current API key."""
        current_key = self.api_keys[self.current_key_index]
        genai.configure(api_key=current_key)
        self.model = genai.GenerativeModel(self.model_name)
        logger.debug(f"Configured Gemini with key index: {self.current_key_index}")

    async def rotate_api_key(self) -> bool:
        """
        Rotate to the next available API key with intelligent selection.

        Returns:
            True if rotation was successful, False if all keys exhausted
        """
        original_index = self.current_key_index
        attempts = 0

        while attempts < len(self.api_keys):
            # Try next key
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            attempts += 1

            # Check if this key is rate limited
            if not self._is_key_rate_limited(self.current_key_index):
                self._configure_current_key()
                logger.info(
                    f"Rotated to Gemini API key index: {self.current_key_index}"
                )
                return True

            # If we've cycled through all keys, check if any have reset
            if self.current_key_index == original_index:
                # Clear expired rate limits
                current_time = time.time()
                expired_keys = [
                    key_idx
                    for key_idx, reset_time in self.rate_limit_reset_times.items()
                    if current_time >= reset_time
                ]

                for key_idx in expired_keys:
                    del self.rate_limit_reset_times[key_idx]
                    logger.info(f"Rate limit expired for key {key_idx}")

                # If we cleared any, try again
                if expired_keys:
                    continue
                else:
                    logger.error("All Gemini API keys are rate limited")
                    return False

        logger.error("Failed to find available Gemini API key")
        return False

    def get_current_key_index(self) -> int:
        """Get the current API key index."""
        return self.current_key_index

    async def generate_response(
        self,
        messages: List[Message],
        personality: str = None,
        memory_context: Optional["MemoryContext"] = None,
    ) -> str:
        """
        Generate response using Gemini with comprehensive error handling and fallback.

        Args:
            messages: Conversation history
            personality: Personality prompt to inject (optional if processor handles it)
            memory_context: Memory context from previous conversations (optional)

        Returns:
            Generated response string
        """
        return await self.fallback_manager.execute_with_fallback(
            component="gemini_provider",
            primary_operation=self._generate_response_internal,
            operation_args=(messages, personality, memory_context),
            context={
                "user_message": messages[-1].content if messages else "",
                "retry_operation": self._generate_response_internal,
                "max_retries": len(self.api_keys),
                "cache_key": f"gemini:{hash(str(messages[-1].content if messages else ''))}",
            },
        ).then(
            lambda result: (
                result.result
                if result.success
                else self._handle_generation_failure(result)
            )
        )

    async def _generate_response_internal(
        self,
        messages: List[Message],
        personality: str = None,
        memory_context: Optional["MemoryContext"] = None,
    ) -> str:
        """Internal response generation with error handling."""
        max_retries = len(self.api_keys)
        original_key_index = self.current_key_index

        for attempt in range(max_retries):
            try:
                # Check if current key is rate limited
                if self._is_key_rate_limited(self.current_key_index):
                    if not await self.rotate_api_key():
                        raise AIProviderError(
                            "All Gemini API keys are rate limited",
                            provider="gemini",
                            is_rate_limit=True,
                        )
                    continue

                # Build conversation context with memory
                conversation_text = self._build_conversation_context(
                    messages, personality, memory_context
                )

                # Generate response with timeout
                response = await asyncio.wait_for(
                    self._make_api_request(conversation_text), timeout=30.0
                )

                # Handle successful response
                if response.text:
                    self.consecutive_failures = 0
                    self.last_successful_request = time.time()
                    await self.recovery_manager.record_success("gemini_provider")

                    # Cache successful response
                    cache_key = f"gemini:{hash(conversation_text)}"
                    self.fallback_manager.cache_response(cache_key, response.text)

                    return response.text
                else:
                    # Content was blocked by safety filters
                    await self._handle_content_filter(messages, conversation_text)
                    return self._get_character_appropriate_rejection()

            except asyncio.TimeoutError:
                error = NetworkError(
                    "Gemini API request timeout",
                    operation="generate_response",
                    is_timeout=True,
                )
                await self._handle_api_error(error, attempt, max_retries)

            except Exception as e:
                await self._handle_api_error(e, attempt, max_retries)

        # All attempts failed
        raise AIProviderError(
            "Failed to generate response after trying all API keys",
            provider="gemini",
            details={"attempts": max_retries, "original_key": original_key_index},
        )

    async def _make_api_request(self, conversation_text: str):
        """Make API request with proper error handling."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.model.generate_content(
                conversation_text, safety_settings=self.safety_settings
            ),
        )

    async def _handle_api_error(self, error: Exception, attempt: int, max_retries: int):
        """Handle API errors with appropriate recovery strategies."""
        error_msg = str(error).lower()

        # Classify error type
        if any(
            term in error_msg for term in ["rate limit", "quota", "too many requests"]
        ):
            await self._handle_rate_limit_error(attempt, max_retries)
        elif any(term in error_msg for term in ["network", "connection", "timeout"]):
            await self._handle_network_error(error, attempt, max_retries)
        elif any(
            term in error_msg for term in ["authentication", "api key", "unauthorized"]
        ):
            await self._handle_auth_error(error, attempt, max_retries)
        else:
            await self._handle_generic_error(error, attempt, max_retries)

    async def _handle_rate_limit_error(self, attempt: int, max_retries: int):
        """Handle rate limit errors with key rotation."""
        self.rate_limit_reset_times[self.current_key_index] = (
            time.time() + 3600
        )  # 1 hour cooldown

        logger.warning(f"Rate limit hit on key {self.current_key_index}, rotating...")

        if not await self.rotate_api_key():
            if attempt < max_retries - 1:
                # Wait before final attempt
                await asyncio.sleep(min(2**attempt, 30))
            raise AIProviderError(
                "All Gemini API keys are rate limited",
                provider="gemini",
                is_rate_limit=True,
            )

    async def _handle_network_error(
        self, error: Exception, attempt: int, max_retries: int
    ):
        """Handle network-related errors."""
        self.consecutive_failures += 1

        network_error = NetworkError(
            f"Gemini network error: {error}",
            operation="generate_response",
            is_timeout="timeout" in str(error).lower(),
        )

        await self.recovery_manager.record_error("gemini_provider", network_error)

        if attempt < max_retries - 1:
            # Exponential backoff
            wait_time = min(2**attempt, 30)
            logger.info(f"Network error, waiting {wait_time}s before retry")
            await asyncio.sleep(wait_time)
        else:
            raise network_error

    async def _handle_auth_error(
        self, error: Exception, attempt: int, max_retries: int
    ):
        """Handle authentication errors."""
        auth_error = AIProviderError(
            f"Gemini authentication error: {error}",
            provider="gemini",
            error_code="AUTH_ERROR",
        )

        self.error_logger.log_error(
            auth_error, component="gemini_provider", operation="generate_response"
        )

        # Try rotating key in case current key is invalid
        if attempt < max_retries - 1:
            await self.rotate_api_key()
        else:
            raise auth_error

    async def _handle_generic_error(
        self, error: Exception, attempt: int, max_retries: int
    ):
        """Handle generic errors."""
        self.consecutive_failures += 1

        generic_error = AIProviderError(f"Gemini API error: {error}", provider="gemini")

        await self.recovery_manager.record_error("gemini_provider", generic_error)

        if attempt < max_retries - 1:
            await asyncio.sleep(min(2**attempt, 10))
        else:
            raise generic_error

    async def _handle_content_filter(
        self, messages: List[Message], conversation_text: str
    ):
        """Handle content filtering incident."""
        user_message = messages[-1].content if messages else ""
        content_hash = self.content_filter_logger.create_content_hash(user_message)

        # Log incident without storing inappropriate content
        self.content_filter_logger.log_content_filter_incident(
            provider="gemini",
            filter_type="safety_filter",
            content_hash=content_hash,
            metadata={
                "message_length": len(user_message),
                "conversation_length": len(messages),
            },
        )

        # Record as content filter error for monitoring
        filter_error = ContentFilterError(
            "Content blocked by Gemini safety filters",
            provider="gemini",
            filter_type="safety_filter",
        )

        await self.recovery_manager.record_error("content_filter", filter_error)

    def _handle_generation_failure(self, result) -> str:
        """Handle complete generation failure with fallback response."""
        self.error_logger.log_fallback_usage(
            component="gemini_provider",
            fallback_strategy=(
                result.strategy_used.value if result.strategy_used else "none"
            ),
            original_error=result.error,
            fallback_success=False,
        )

        # Return character-appropriate error message
        return self._get_character_appropriate_rejection()

    def _is_key_rate_limited(self, key_index: int) -> bool:
        """Check if API key is currently rate limited."""
        reset_time = self.rate_limit_reset_times.get(key_index, 0)
        return time.time() < reset_time

    def _build_conversation_context(
        self,
        messages: List[Message],
        personality: str = None,
        memory_context: Optional["MemoryContext"] = None,
    ) -> str:
        """Build conversation context for Gemini with memory integration."""
        context_parts = []

        # Add memory context if available and no processor is handling it
        if memory_context and not self.personality_processor:
            context_content = memory_context.format_for_ai()
            if context_content:
                context_parts.append(
                    f"System: Context from previous conversations:\n{context_content}"
                )

        # Add personality instruction if provided and no processor is handling it
        if personality and not self.personality_processor:
            context_parts.append(f"System: {personality}")

        # Add conversation history
        for msg in messages:
            if msg.role == "user":
                context_parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                context_parts.append(f"Assistant: {msg.content}")
            elif msg.role == "system":
                context_parts.append(f"System: {msg.content}")

        return "\n\n".join(context_parts)

    def _get_character_appropriate_rejection(self) -> str:
        """Get a character-appropriate rejection message for filtered content."""
        rejections = [
            "B-baka! I can't talk about that kind of thing!",
            "Eh?! That's... that's too embarrassing to discuss!",
            "I-I don't want to talk about that! Let's change the subject!",
            "That's not appropriate! Ask me something else instead!",
            "Mou~ I can't help with that kind of request!",
        ]

        import random

        return random.choice(rejections)

    async def validate_content(self, content: str) -> bool:
        """
        Validate content using Gemini's safety features.

        Args:
            content: Content to validate

        Returns:
            True if content is appropriate, False otherwise
        """
        try:
            # Use a simple prompt to test content safety
            test_prompt = f"Please respond to this message: {content}"

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(
                    test_prompt, safety_settings=self.safety_settings
                ),
            )

            # If we get a response, content is likely safe
            return bool(response.text)

        except Exception as e:
            logger.warning(f"Content validation failed: {e}")
            return False

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "gemini"

    def supports_content_filtering(self) -> bool:
        """Return whether provider supports content filtering."""
        return True

    async def check_connection(self) -> bool:
        """
        Check if Gemini API is accessible with current key.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Use a simple test prompt
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None, lambda: self.model.generate_content("Hello")
                ),
                timeout=10.0,
            )

            # Check if we got a valid response
            if response and (response.text or hasattr(response, "candidates")):
                return True
            else:
                return False

        except asyncio.TimeoutError:
            logger.warning("Gemini connection check timeout")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Gemini: {e}")
            return False

    def _register_error_recovery(self):
        """Register component with error recovery system."""
        self.recovery_manager.register_component(
            component_name="gemini_provider",
            recovery_strategies=[
                RecoveryStrategy.ROTATE_API_KEY,
                RecoveryStrategy.WAIT_AND_RETRY,
                RecoveryStrategy.REINITIALIZE,
            ],
            health_check_func=self.check_connection,
        )

        # Register fallback strategies
        self.fallback_manager.register_fallback_chain(
            component="gemini_provider",
            strategies=[
                FallbackStrategy.RETRY,
                FallbackStrategy.CACHED_RESPONSE,
                FallbackStrategy.SIMPLIFIED_RESPONSE,
                FallbackStrategy.ERROR_MESSAGE,
            ],
        )
