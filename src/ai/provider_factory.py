"""
AI Provider Factory for environment-based provider selection.
Handles configuration parsing and provider instantiation with personality processing.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from .base_provider import AIProvider
from .ollama_provider import OllamaProvider
from .gemini_provider import GeminiProvider
from .personality_processor import PersonalityProcessor

logger = logging.getLogger(__name__)


class ProviderFactory:
    """Factory class for creating AI providers based on environment configuration."""
    
    @staticmethod
    def create_provider() -> AIProvider:
        """
        Create an AI provider based on environment variables with personality processing.
        
        Returns:
            Configured AI provider instance with personality processor
            
        Raises:
            ValueError: If configuration is invalid
            ImportError: If required dependencies are missing
        """
        use_ollama = os.getenv('USE_OLLAMA', 'false').lower() == 'true'
        
        # Create the provider
        if use_ollama:
            provider = ProviderFactory._create_ollama_provider()
        else:
            provider = ProviderFactory._create_gemini_provider()
        
        # Create and attach personality processor
        personality_processor = ProviderFactory._create_personality_processor(provider.get_provider_name())
        provider.set_personality_processor(personality_processor)
        
        return provider
    
    @staticmethod
    def _create_ollama_provider() -> OllamaProvider:
        """Create and configure Ollama provider."""
        config = {
            'model': os.getenv('OLLAMA_MODEL', 'llama3'),
            'host': os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        }
        
        logger.info(f"Creating Ollama provider with model: {config['model']}")
        return OllamaProvider(config)
    
    @staticmethod
    def _create_gemini_provider() -> GeminiProvider:
        """Create and configure Gemini provider with API key rotation."""
        # Parse API keys from environment
        api_keys_str = os.getenv('GEMINI_API_KEYS', '')
        if not api_keys_str:
            raise ValueError("GEMINI_API_KEYS environment variable is required when not using Ollama")
        
        # Split comma-separated keys and clean them
        api_keys = [key.strip() for key in api_keys_str.split(',') if key.strip()]
        if not api_keys:
            raise ValueError("At least one valid Gemini API key is required")
        
        # Get current key index
        current_key_index = int(os.getenv('GEMINI_CURRENT_KEY_INDEX', '0'))
        
        # Ensure index is within bounds
        if current_key_index >= len(api_keys):
            current_key_index = 0
            logger.warning(f"GEMINI_CURRENT_KEY_INDEX out of bounds, reset to 0")
        
        config = {
            'api_keys': api_keys,
            'model': os.getenv('GEMINI_MODEL', 'gemini-pro'),
            'current_key_index': current_key_index
        }
        
        logger.info(f"Creating Gemini provider with {len(api_keys)} API keys")
        return GeminiProvider(config)
    
    @staticmethod
    def get_provider_config() -> Dict[str, Any]:
        """
        Get current provider configuration from environment.
        
        Returns:
            Dictionary containing provider configuration
        """
        use_ollama = os.getenv('USE_OLLAMA', 'false').lower() == 'true'
        
        config = {
            'provider_type': 'ollama' if use_ollama else 'gemini',
            'use_ollama': use_ollama
        }
        
        if use_ollama:
            config.update({
                'ollama_model': os.getenv('OLLAMA_MODEL', 'llama3'),
                'ollama_host': os.getenv('OLLAMA_HOST', 'http://localhost:11434')
            })
        else:
            api_keys_str = os.getenv('GEMINI_API_KEYS', '')
            api_keys = [key.strip() for key in api_keys_str.split(',') if key.strip()]
            
            config.update({
                'gemini_model': os.getenv('GEMINI_MODEL', 'gemini-pro'),
                'gemini_api_keys_count': len(api_keys),
                'gemini_current_key_index': int(os.getenv('GEMINI_CURRENT_KEY_INDEX', '0'))
            })
        
        return config
    
    @staticmethod
    def update_gemini_key_index(new_index: int) -> None:
        """
        Update the current Gemini API key index in environment.
        Note: This only updates the runtime environment, not the .env file.
        
        Args:
            new_index: New key index to set
        """
        os.environ['GEMINI_CURRENT_KEY_INDEX'] = str(new_index)
        logger.info(f"Updated GEMINI_CURRENT_KEY_INDEX to {new_index}")
    
    @staticmethod
    def validate_configuration() -> List[str]:
        """
        Validate current environment configuration.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        use_ollama = os.getenv('USE_OLLAMA', 'false').lower() == 'true'
        
        if use_ollama:
            # Validate Ollama configuration
            model = os.getenv('OLLAMA_MODEL')
            if not model:
                errors.append("OLLAMA_MODEL is required when USE_OLLAMA=true")
            
            host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
            if not host.startswith(('http://', 'https://')):
                errors.append("OLLAMA_HOST must be a valid HTTP/HTTPS URL")
        
        else:
            # Validate Gemini configuration
            api_keys_str = os.getenv('GEMINI_API_KEYS')
            if not api_keys_str:
                errors.append("GEMINI_API_KEYS is required when USE_OLLAMA=false")
            else:
                api_keys = [key.strip() for key in api_keys_str.split(',') if key.strip()]
                if not api_keys:
                    errors.append("At least one valid Gemini API key is required")
                
                # Validate key index
                try:
                    key_index = int(os.getenv('GEMINI_CURRENT_KEY_INDEX', '0'))
                    if key_index < 0 or key_index >= len(api_keys):
                        errors.append(f"GEMINI_CURRENT_KEY_INDEX ({key_index}) is out of bounds for {len(api_keys)} keys")
                except ValueError:
                    errors.append("GEMINI_CURRENT_KEY_INDEX must be a valid integer")
        
        return errors
    
    @staticmethod
    def _create_personality_processor(provider_name: str) -> PersonalityProcessor:
        """
        Create personality processor based on environment configuration.
        
        Args:
            provider_name: Name of the AI provider for content filtering decisions
            
        Returns:
            Configured PersonalityProcessor instance
        """
        # Get personality prompt from environment
        personality_prompt = os.getenv(
            'PERSONALITY_PROMPT',
            "You are a tsundere anime girl named Miko. You're tough on the outside but caring inside. "
            "Always respond with anime flair, like 'B-baka!' for embarrassment, and end with cute emotes "
            "like (*blush*). Stay in character no matter what."
        )
        
        # Determine content filtering based on provider and configuration
        enable_content_filter = os.getenv('ENABLE_CONTENT_FILTER', 'true').lower() == 'true'
        
        # For Ollama, disable content filtering by default unless explicitly enabled
        if provider_name == 'ollama':
            enable_content_filter = os.getenv('ENABLE_CONTENT_FILTER', 'false').lower() == 'true'
        
        logger.info(f"Creating personality processor for {provider_name} with content_filter={enable_content_filter}")
        
        return PersonalityProcessor(
            personality_prompt=personality_prompt,
            enable_content_filter=enable_content_filter
        )