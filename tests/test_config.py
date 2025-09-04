"""
Tests for configuration management system.
"""

import os
import tempfile
import pytest
from pathlib import Path
import sys
from unittest.mock import patch

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.settings import ConfigManager, ConfigurationError, AppConfig


class TestConfigManager:
    """Test configuration manager functionality."""
    
    def setup_method(self):
        """Clear environment variables before each test."""
        # Clear all relevant env vars to ensure clean test state
        env_vars_to_clear = [
            'LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET', 'LIVEKIT_ROOM_NAME',
            'USE_OLLAMA', 'OLLAMA_MODEL', 'OLLAMA_HOST', 'GEMINI_API_KEYS', 
            'GEMINI_CURRENT_KEY_INDEX', 'PERSONALITY_PROMPT', 'MEM0_API_KEY',
            'MEM0_COLLECTION', 'MEMORY_HISTORY_LIMIT', 'LIVE2D_MODEL_URL',
            'LIVE2D_TEXTURES_URL', 'TTS_PROVIDER', 'STT_PROVIDER', 'DEBUG', 'LOG_LEVEL'
        ]
        for var in env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]
    
    def test_load_config_with_minimal_env(self):
        """Test loading configuration with minimal required environment variables."""
        # Create temporary .env file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("""
LIVEKIT_URL=wss://test.livekit.cloud
LIVEKIT_API_KEY=test_key
LIVEKIT_API_SECRET=test_secret
""")
            env_file = f.name
        
        try:
            config_manager = ConfigManager(env_file)
            config = config_manager.load_config()
            
            # Verify required fields are set
            assert config.livekit.url == "wss://test.livekit.cloud"
            assert config.livekit.api_key == "test_key"
            assert config.livekit.api_secret == "test_secret"
            
            # Verify defaults are applied
            assert config.livekit.room_name == "anime_room"
            assert config.ai.use_ollama is True
            assert config.ai.ollama_model == "llama3"
            
        finally:
            os.unlink(env_file)
    
    def test_load_config_with_gemini_keys(self):
        """Test loading configuration with multiple Gemini API keys."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("""
LIVEKIT_URL=wss://test.livekit.cloud
LIVEKIT_API_KEY=test_key
LIVEKIT_API_SECRET=test_secret
USE_OLLAMA=false
GEMINI_API_KEYS=key1,key2,key3
GEMINI_CURRENT_KEY_INDEX=1
""")
            env_file = f.name
        
        try:
            config_manager = ConfigManager(env_file)
            config = config_manager.load_config()
            
            assert config.ai.use_ollama is False
            assert config.ai.gemini_api_keys == ["key1", "key2", "key3"]
            assert config.ai.gemini_current_key_index == 1
            
            # Test key rotation
            current_key = config_manager.get_current_gemini_key()
            assert current_key == "key2"
            
            # Test rotation
            next_key = config_manager.rotate_gemini_key()
            assert next_key == "key3"
            assert config_manager.get_current_gemini_key() == "key3"
            
        finally:
            os.unlink(env_file)
    
    def test_missing_required_config(self):
        """Test that missing required configuration raises error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("# Empty config file")
            env_file = f.name
        
        try:
            config_manager = ConfigManager(env_file)
            with pytest.raises(ConfigurationError):
                config_manager.load_config()
        finally:
            os.unlink(env_file)
    
    def test_gemini_without_keys_validation(self):
        """Test validation fails when Gemini is selected but no keys provided."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("""
LIVEKIT_URL=wss://test.livekit.cloud
LIVEKIT_API_KEY=test_key
LIVEKIT_API_SECRET=test_secret
USE_OLLAMA=false
""")
            env_file = f.name
        
        try:
            config_manager = ConfigManager(env_file)
            with pytest.raises(ConfigurationError, match="at least one Gemini API key"):
                config_manager.load_config()
        finally:
            os.unlink(env_file)
    
    def test_key_rotation_bounds(self):
        """Test key rotation handles bounds correctly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("""
LIVEKIT_URL=wss://test.livekit.cloud
LIVEKIT_API_KEY=test_key
LIVEKIT_API_SECRET=test_secret
GEMINI_API_KEYS=key1,key2
GEMINI_CURRENT_KEY_INDEX=1
""")
            env_file = f.name
        
        try:
            config_manager = ConfigManager(env_file)
            config = config_manager.load_config()
            
            # Start at index 1 (key2)
            assert config_manager.get_current_gemini_key() == "key2"
            
            # Rotate should wrap to index 0 (key1)
            next_key = config_manager.rotate_gemini_key()
            assert next_key == "key1"
            
            # Rotate again should go to index 1 (key2)
            next_key = config_manager.rotate_gemini_key()
            assert next_key == "key2"
            
        finally:
            os.unlink(env_file)
    
    def test_personality_configuration(self):
        """Test personality prompt configuration."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("""
LIVEKIT_URL=wss://test.livekit.cloud
LIVEKIT_API_KEY=test_key
LIVEKIT_API_SECRET=test_secret
PERSONALITY_PROMPT=You are a cheerful anime idol named Aiko!
""")
            env_file = f.name
        
        try:
            config_manager = ConfigManager(env_file)
            config = config_manager.load_config()
            
            assert config.personality.personality_prompt == "You are a cheerful anime idol named Aiko!"
            
        finally:
            os.unlink(env_file)


if __name__ == "__main__":
    pytest.main([__file__])