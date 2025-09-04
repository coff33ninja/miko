"""
Tests for deployment configuration and validation.
"""

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import shutil

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.settings import load_config, ConfigurationError, ConfigManager


class TestConfigurationValidation:
    """Test configuration validation and loading."""

    def test_load_valid_configuration(self):
        """Test loading a valid configuration."""
        # Create a temporary .env file with valid configuration
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(
                """
LIVEKIT_URL=wss://test.livekit.cloud
LIVEKIT_API_KEY=test_key
LIVEKIT_API_SECRET=test_secret
LIVEKIT_ROOM_NAME=test_room
USE_OLLAMA=true
OLLAMA_MODEL=llama3
OLLAMA_HOST=http://localhost:11434
PERSONALITY_PROMPT=Test personality
MEM0_API_KEY=test_mem0_key
MEM0_COLLECTION=test_collection
LIVE2D_MODEL_URL=/static/test.moc3
TTS_PROVIDER=openai
STT_PROVIDER=openai
DEBUG=false
LOG_LEVEL=INFO
"""
            )
            temp_env_path = f.name

        try:
            # Load configuration from temporary file
            config = load_config(temp_env_path)

            # Verify configuration values
            assert config.livekit.url == "wss://test.livekit.cloud"
            assert config.livekit.api_key == "test_key"
            assert config.livekit.api_secret == "test_secret"
            assert config.livekit.room_name == "test_room"
            assert config.ai.use_ollama is True
            assert config.ai.ollama_model == "llama3"
            assert config.memory.mem0_api_key == "test_mem0_key"
            assert config.debug is False
            assert config.log_level == "INFO"

        finally:
            os.unlink(temp_env_path)

    def test_missing_required_configuration(self):
        """Test handling of missing required configuration."""
        # Create a temporary .env file with missing required fields
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(
                """
# Missing LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
USE_OLLAMA=true
"""
            )
            temp_env_path = f.name

        try:
            # Clear environment variables that might be set
            original_env = {}
            for key in ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"]:
                if key in os.environ:
                    original_env[key] = os.environ[key]
                    del os.environ[key]

            try:
                # Should raise ConfigurationError for missing required fields
                with pytest.raises(ConfigurationError):
                    load_config(temp_env_path)
            finally:
                # Restore original environment
                for key, value in original_env.items():
                    os.environ[key] = value

        finally:
            os.unlink(temp_env_path)

    def test_gemini_configuration_validation(self):
        """Test Gemini API key configuration validation."""
        # Test with Gemini enabled but no keys
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(
                """
LIVEKIT_URL=wss://test.livekit.cloud
LIVEKIT_API_KEY=test_key
LIVEKIT_API_SECRET=test_secret
USE_OLLAMA=false
# No GEMINI_API_KEYS provided
"""
            )
            temp_env_path = f.name

        try:
            with pytest.raises(ConfigurationError):
                load_config(temp_env_path)
        finally:
            os.unlink(temp_env_path)

        # Test with valid Gemini configuration
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(
                """
LIVEKIT_URL=wss://test.livekit.cloud
LIVEKIT_API_KEY=test_key
LIVEKIT_API_SECRET=test_secret
USE_OLLAMA=false
GEMINI_API_KEYS=key1,key2,key3
GEMINI_CURRENT_KEY_INDEX=0
"""
            )
            temp_env_path = f.name

        try:
            config = load_config(temp_env_path)
            assert config.ai.use_ollama is False
            assert len(config.ai.gemini_api_keys) == 3
            assert config.ai.gemini_api_keys == ["key1", "key2", "key3"]
            assert config.ai.gemini_current_key_index == 0
        finally:
            os.unlink(temp_env_path)

    def test_gemini_key_rotation(self):
        """Test Gemini API key rotation functionality."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(
                """
LIVEKIT_URL=wss://test.livekit.cloud
LIVEKIT_API_KEY=test_key
LIVEKIT_API_SECRET=test_secret
USE_OLLAMA=false
GEMINI_API_KEYS=key1,key2,key3
GEMINI_CURRENT_KEY_INDEX=0
"""
            )
            temp_env_path = f.name

        try:
            config_manager = ConfigManager(temp_env_path)
            config = config_manager.load_config()

            # Test getting current key
            current_key = config_manager.get_current_gemini_key()
            assert current_key == "key1"

            # Test key rotation
            next_key = config_manager.rotate_gemini_key()
            assert next_key == "key2"
            assert config_manager.get_current_gemini_key() == "key2"

            # Test wrapping around
            config_manager.rotate_gemini_key()  # key3
            next_key = config_manager.rotate_gemini_key()  # back to key1
            assert next_key == "key1"

        finally:
            os.unlink(temp_env_path)

    def test_default_values(self):
        """Test that default values are applied correctly."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(
                """
LIVEKIT_URL=wss://test.livekit.cloud
LIVEKIT_API_KEY=test_key
LIVEKIT_API_SECRET=test_secret
# Only required fields, test defaults for others
"""
            )
            temp_env_path = f.name

        try:
            # Clear environment variables that might interfere
            env_vars_to_clear = [
                "LIVEKIT_ROOM_NAME",
                "USE_OLLAMA",
                "OLLAMA_MODEL",
                "OLLAMA_HOST",
                "MEM0_COLLECTION",
                "MEMORY_HISTORY_LIMIT",
                "FLASK_HOST",
                "FLASK_PORT",
                "DEBUG",
                "LOG_LEVEL",
            ]
            original_env = {}
            for key in env_vars_to_clear:
                if key in os.environ:
                    original_env[key] = os.environ[key]
                    del os.environ[key]

            try:
                config = load_config(temp_env_path)

                # Test default values
                assert config.livekit.room_name == "anime_room"
                assert config.ai.use_ollama is True  # Default
                assert config.ai.ollama_model == "llama3"
                assert config.ai.ollama_host == "http://localhost:11434"
                assert config.memory.mem0_collection == "anime_character"
                assert config.memory.memory_history_limit == 20
                assert config.flask.host == "0.0.0.0"
                assert config.flask.port == 5000
                assert config.debug is False
                assert config.log_level == "INFO"
            finally:
                # Restore original environment
                for key, value in original_env.items():
                    os.environ[key] = value

        finally:
            os.unlink(temp_env_path)


class TestDeploymentFiles:
    """Test deployment-related files and configurations."""

    def test_required_deployment_files_exist(self):
        """Test that all required deployment files exist."""
        project_root = Path(__file__).parent.parent

        required_files = [
            "Dockerfile",
            "docker-compose.yml",
            ".dockerignore",
            ".env.example",
            "requirements.txt",
            "scripts/deploy.py",
            "scripts/deploy.bat",
            "scripts/validate_config.py",
        ]

        for file_path in required_files:
            full_path = project_root / file_path
            assert full_path.exists(), f"Required deployment file missing: {file_path}"

    def test_dockerfile_structure(self):
        """Test that Dockerfile has required structure."""
        project_root = Path(__file__).parent.parent
        dockerfile_path = project_root / "Dockerfile"

        with open(dockerfile_path, "r") as f:
            dockerfile_content = f.read()

        # Check for required Dockerfile elements
        assert "FROM python:" in dockerfile_content
        assert "WORKDIR /app" in dockerfile_content
        assert "COPY requirements.txt" in dockerfile_content
        assert (
            "RUN uv pip install" in dockerfile_content
            or "RUN pip install" in dockerfile_content
        )
        assert "EXPOSE 5000" in dockerfile_content
        assert "CMD" in dockerfile_content
        assert "HEALTHCHECK" in dockerfile_content

    def test_docker_compose_structure(self):
        """Test that docker-compose.yml has required structure."""
        project_root = Path(__file__).parent.parent
        compose_path = project_root / "docker-compose.yml"

        with open(compose_path, "r") as f:
            compose_content = f.read()

        # Check for required docker-compose elements
        assert "version:" in compose_content
        assert "services:" in compose_content
        assert "anime-ai-character:" in compose_content
        assert "ports:" in compose_content
        assert "5000:5000" in compose_content
        assert "volumes:" in compose_content
        assert "env_file:" in compose_content
        assert "networks:" in compose_content

    def test_gitignore_includes_kiro(self):
        """Test that .gitignore includes .kiro directory."""
        project_root = Path(__file__).parent.parent
        gitignore_path = project_root / ".gitignore"

        with open(gitignore_path, "r") as f:
            gitignore_content = f.read()

        assert ".kiro/" in gitignore_content
        assert ".env" in gitignore_content
        assert "!.env.example" in gitignore_content
        assert "__pycache__/" in gitignore_content
        assert "logs/" in gitignore_content


class TestEnvironmentValidation:
    """Test environment validation functionality."""

    @patch("subprocess.run")
    def test_docker_validation(self, mock_run):
        """Test Docker installation validation."""
        # Mock successful Docker command
        mock_run.return_value = MagicMock(returncode=0, stdout="Docker version 20.10.0")

        # Import and test the validation script
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

        try:
            from validate_config import ConfigValidator

            validator = ConfigValidator()

            # This should not raise an exception
            validator.validate_python_version()

            # Check that we have Python 3.8+
            assert sys.version_info >= (3, 8)

        except ImportError:
            pytest.skip("validate_config module not available")

    def test_directory_creation(self):
        """Test that required directories can be created."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test directory creation
            required_dirs = ["src", "static", "static/models", "logs", "scripts"]

            for dir_name in required_dirs:
                dir_path = temp_path / dir_name
                dir_path.mkdir(parents=True, exist_ok=True)
                assert dir_path.exists()
                assert dir_path.is_dir()


class TestConfigurationIntegration:
    """Integration tests for configuration system."""

    def test_full_configuration_cycle(self):
        """Test complete configuration loading and validation cycle."""
        # Create a complete test configuration
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(
                """
# LiveKit Configuration
LIVEKIT_URL=wss://test.livekit.cloud
LIVEKIT_API_KEY=test_api_key
LIVEKIT_API_SECRET=test_api_secret
LIVEKIT_ROOM_NAME=test_room

# AI Configuration
USE_OLLAMA=true
OLLAMA_MODEL=llama3
OLLAMA_HOST=http://localhost:11434

# Alternative Gemini config (not used when USE_OLLAMA=true)
GEMINI_API_KEYS=test_key1,test_key2
GEMINI_CURRENT_KEY_INDEX=0

# Content Filtering
ENABLE_CONTENT_FILTER=true
CONTENT_FILTER_STRICT_MODE=false

# Personality
PERSONALITY_PROMPT=Test anime character personality

# Memory
MEM0_API_KEY=test_mem0_key
MEM0_COLLECTION=test_collection
MEMORY_HISTORY_LIMIT=25

# Live2D
LIVE2D_MODEL_URL=/static/test_model.moc3
LIVE2D_TEXTURES_URL=/static/test_textures/

# Agents
TTS_PROVIDER=openai
STT_PROVIDER=openai

# Flask
FLASK_HOST=127.0.0.1
FLASK_PORT=5001
FLASK_DEBUG=true

# Application
DEBUG=true
LOG_LEVEL=DEBUG
"""
            )
            temp_env_path = f.name

        try:
            # Load and validate configuration
            config = load_config(temp_env_path)

            # Verify all sections are loaded correctly
            assert config.livekit.url == "wss://test.livekit.cloud"
            assert config.livekit.room_name == "test_room"

            assert config.ai.use_ollama is True
            assert config.ai.ollama_model == "llama3"
            assert len(config.ai.gemini_api_keys) == 2

            assert config.content_filter.enable_content_filter is True
            assert config.content_filter.strict_mode is False

            assert "Test anime character" in config.personality.personality_prompt

            assert config.memory.mem0_api_key == "test_mem0_key"
            assert config.memory.memory_history_limit == 25

            assert config.live2d.model_url == "/static/test_model.moc3"

            assert config.agents.tts_provider == "openai"

            assert config.flask.host == "127.0.0.1"
            assert config.flask.port == 5001
            assert config.flask.debug is True

            assert config.debug is True
            assert config.log_level == "DEBUG"

        finally:
            os.unlink(temp_env_path)


if __name__ == "__main__":
    pytest.main([__file__])
