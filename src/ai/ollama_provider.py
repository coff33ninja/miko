"""
Ollama AI Provider implementation for local LLM processing.
Provides unrestricted content processing with no filtering.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from .base_provider import AIProvider, Message

if TYPE_CHECKING:
    from .base_provider import MemoryContext

try:
    import ollama
except ImportError:
    ollama = None

from ..error_handling.exceptions import AIProviderError, NetworkError
from ..error_handling.fallback_manager import get_fallback_manager, FallbackStrategy
from ..error_handling.error_recovery import get_recovery_manager, RecoveryStrategy
from ..error_handling.logging_handler import get_error_logger

logger = logging.getLogger(__name__)


class OllamaProvider(AIProvider):
    """Ollama provider for local LLM processing with no content restrictions."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Ollama provider.
        
        Args:
            config: Configuration dictionary containing:
                - model: Ollama model name (default: 'llama3')
                - host: Ollama server host (default: 'http://localhost:11434')
        """
        super().__init__(config)
        
        if ollama is None:
            raise ImportError("ollama library is required for OllamaProvider")
        
        self.model = config.get('model', 'llama3')
        self.host = config.get('host', 'http://localhost:11434')
        
        # Error handling components
        self.fallback_manager = get_fallback_manager()
        self.recovery_manager = get_recovery_manager()
        self.error_logger = get_error_logger()
        
        # Connection tracking
        self.consecutive_failures = 0
        self.last_successful_request = time.time()
        self.connection_timeout = 30.0
        
        # Configure ollama client
        if self.host != 'http://localhost:11434':
            self.client = ollama.Client(host=self.host)
        else:
            self.client = ollama
        
        # Register with error recovery system
        self._register_error_recovery()
        
        logger.info(f"Initialized OllamaProvider with model: {self.model}")
    
    async def generate_response(self, messages: List[Message], personality: str = None, memory_context: Optional['MemoryContext'] = None) -> str:
        """
        Generate response using Ollama with comprehensive error handling and fallback.
        
        Args:
            messages: Conversation history
            personality: Personality prompt to inject (optional if processor handles it)
            memory_context: Memory context from previous conversations (optional)
            
        Returns:
            Generated response string
        """
        result = await self.fallback_manager.execute_with_fallback(
            component="ollama_provider",
            primary_operation=self._generate_response_internal,
            operation_args=(messages, personality, memory_context),
            context={
                'user_message': messages[-1].content if messages else '',
                'retry_operation': self._generate_response_internal,
                'max_retries': 3,
                'cache_key': f"ollama:{hash(str(messages[-1].content if messages else ''))}"
            }
        )
        
        if result.success:
            return result.result
        else:
            return self._handle_generation_failure(result)
    
    async def _generate_response_internal(self, messages: List[Message], personality: str = None, memory_context: Optional['MemoryContext'] = None) -> str:
        """Internal response generation with error handling."""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Convert messages to Ollama format
                ollama_messages = self._build_ollama_messages(messages, personality, memory_context)
                
                # Generate response with timeout
                response = await asyncio.wait_for(
                    self._make_ollama_request(ollama_messages),
                    timeout=self.connection_timeout
                )
                
                # Handle successful response
                if response and 'message' in response and 'content' in response['message']:
                    content = response['message']['content']
                    if content:
                        self.consecutive_failures = 0
                        self.last_successful_request = time.time()
                        await self.recovery_manager.record_success("ollama_provider")
                        
                        # Cache successful response
                        cache_key = f"ollama:{hash(str(ollama_messages))}"
                        self.fallback_manager.cache_response(cache_key, content)
                        
                        return content
                
                # Empty or invalid response
                raise AIProviderError(
                    "Ollama returned empty or invalid response",
                    provider="ollama"
                )
                
            except asyncio.TimeoutError:
                error = NetworkError(
                    f"Ollama request timeout after {self.connection_timeout}s",
                    operation="generate_response",
                    endpoint=self.host,
                    is_timeout=True
                )
                await self._handle_api_error(error, attempt, max_retries)
                
            except Exception as e:
                await self._handle_api_error(e, attempt, max_retries)
        
        # All attempts failed
        raise AIProviderError(
            f"Failed to generate response after {max_retries} attempts",
            provider="ollama",
            details={"host": self.host, "model": self.model}
        )
    
    def _build_ollama_messages(self, messages: List[Message], personality: str = None, memory_context: Optional['MemoryContext'] = None) -> List[Dict[str, str]]:
        """Build Ollama message format."""
        ollama_messages = []
        
        # Add memory context as system message if available
        if memory_context and not self.personality_processor:
            context_content = memory_context.format_for_ai()
            if context_content:
                ollama_messages.append({
                    'role': 'system',
                    'content': f"Context from previous conversations:\n{context_content}"
                })
        
        # Add personality as system message if provided and no processor is handling it
        if personality and not self.personality_processor:
            ollama_messages.append({
                'role': 'system',
                'content': personality
            })
        
        # Add conversation messages
        for msg in messages:
            ollama_messages.append({
                'role': msg.role,
                'content': msg.content
            })
        
        return ollama_messages
    
    async def _make_ollama_request(self, messages: List[Dict[str, str]]):
        """Make Ollama API request with proper error handling."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.client.chat(
                model=self.model,
                messages=messages
            )
        )
    
    async def _handle_api_error(self, error: Exception, attempt: int, max_retries: int):
        """Handle API errors with appropriate recovery strategies."""
        self.consecutive_failures += 1
        error_msg = str(error).lower()
        
        # Classify error type
        if any(term in error_msg for term in ['connection', 'network', 'timeout']):
            await self._handle_connection_error(error, attempt, max_retries)
        elif any(term in error_msg for term in ['model', 'not found', '404']):
            await self._handle_model_error(error, attempt, max_retries)
        elif any(term in error_msg for term in ['server', '500', 'internal']):
            await self._handle_server_error(error, attempt, max_retries)
        else:
            await self._handle_generic_error(error, attempt, max_retries)
    
    async def _handle_connection_error(self, error: Exception, attempt: int, max_retries: int):
        """Handle connection-related errors."""
        connection_error = NetworkError(
            f"Ollama connection error: {error}",
            operation="generate_response",
            endpoint=self.host,
            is_timeout="timeout" in str(error).lower()
        )
        
        await self.recovery_manager.record_error("ollama_provider", connection_error)
        
        if attempt < max_retries - 1:
            # Exponential backoff for connection issues
            wait_time = min(2 ** attempt, 30)
            logger.info(f"Connection error, waiting {wait_time}s before retry")
            await asyncio.sleep(wait_time)
        else:
            raise connection_error
    
    async def _handle_model_error(self, error: Exception, attempt: int, max_retries: int):
        """Handle model-related errors."""
        model_error = AIProviderError(
            f"Ollama model error: {error}",
            provider="ollama",
            error_code="MODEL_ERROR",
            details={"model": self.model, "host": self.host}
        )
        
        self.error_logger.log_error(
            model_error,
            component="ollama_provider",
            operation="generate_response"
        )
        
        # Model errors are usually not recoverable by retry
        raise model_error
    
    async def _handle_server_error(self, error: Exception, attempt: int, max_retries: int):
        """Handle server-related errors."""
        server_error = AIProviderError(
            f"Ollama server error: {error}",
            provider="ollama",
            error_code="SERVER_ERROR"
        )
        
        await self.recovery_manager.record_error("ollama_provider", server_error)
        
        if attempt < max_retries - 1:
            # Wait longer for server errors
            wait_time = min(5 * (attempt + 1), 30)
            logger.info(f"Server error, waiting {wait_time}s before retry")
            await asyncio.sleep(wait_time)
        else:
            raise server_error
    
    async def _handle_generic_error(self, error: Exception, attempt: int, max_retries: int):
        """Handle generic errors."""
        generic_error = AIProviderError(
            f"Ollama API error: {error}",
            provider="ollama"
        )
        
        await self.recovery_manager.record_error("ollama_provider", generic_error)
        
        if attempt < max_retries - 1:
            await asyncio.sleep(min(2 ** attempt, 10))
        else:
            raise generic_error
    
    def _handle_generation_failure(self, result) -> str:
        """Handle complete generation failure with fallback response."""
        self.error_logger.log_fallback_usage(
            component="ollama_provider",
            fallback_strategy=result.strategy_used.value if result.strategy_used else "none",
            original_error=result.error,
            fallback_success=False
        )
        
        # Return simple fallback response
        return "I'm having trouble thinking right now... Could you try asking again? (*nervous*)"
    
    async def validate_content(self, content: str) -> bool:
        """
        Validate content - Ollama has no content restrictions.
        
        Args:
            content: Content to validate
            
        Returns:
            Always True (no content filtering)
        """
        return True
    
    def get_provider_name(self) -> str:
        """Return provider name."""
        return "ollama"
    
    def supports_content_filtering(self) -> bool:
        """Return whether provider supports content filtering."""
        return False
    
    async def check_connection(self) -> bool:
        """
        Check if Ollama server is accessible and model is available.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Check server connection
            loop = asyncio.get_event_loop()
            models = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self.client.list()),
                timeout=10.0
            )
            
            # Check if our model is available
            if models and 'models' in models:
                available_models = [model['name'] for model in models['models']]
                if self.model in available_models:
                    return True
                else:
                    logger.warning(f"Model {self.model} not found in available models: {available_models}")
                    return False
            
            return True  # Server accessible even if model list format is different
            
        except asyncio.TimeoutError:
            logger.warning("Ollama connection check timeout")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            return False
    
    def _register_error_recovery(self):
        """Register component with error recovery system."""
        self.recovery_manager.register_component(
            component_name="ollama_provider",
            recovery_strategies=[
                RecoveryStrategy.RECONNECT,
                RecoveryStrategy.WAIT_AND_RETRY,
                RecoveryStrategy.REINITIALIZE
            ],
            health_check_func=self.check_connection
        )
        
        # Register fallback strategies
        self.fallback_manager.register_fallback_chain(
            component="ollama_provider",
            strategies=[
                FallbackStrategy.RETRY,
                FallbackStrategy.CACHED_RESPONSE,
                FallbackStrategy.SIMPLIFIED_RESPONSE,
                FallbackStrategy.ERROR_MESSAGE
            ]
        )