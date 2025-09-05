"""
Configuration management for Anime AI Character system.
Handles environment variables, validation, and default values.
"""

import os
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv


@dataclass
class LiveKitConfig:
    """LiveKit server configuration."""

    url: str
    api_key: str
    api_secret: str
    room_name: str = "anime_room"


@dataclass
class AIConfig:
    """AI provider configuration."""

    use_ollama: bool = True
    ollama_model: str = "llama3"
    ollama_host: str = "http://localhost:11434"
    gemini_api_keys: List[str] = field(default_factory=list)
    gemini_current_key_index: int = 0


@dataclass
class ContentFilterConfig:
    """Content filtering configuration."""

    enable_content_filter: bool = True
    strict_mode: bool = False


@dataclass
class PersonalityConfig:
    """Personality and character configuration."""

    personality_prompt: str = "You are a friendly anime character."


@dataclass
class MemoryConfig:
    """Memory management configuration."""

    mem0_api_key: str = ""
    mem0_host: str = "https://api.mem0.ai"
    mem0_collection: str = "anime_character"
    memory_history_limit: int = 20


@dataclass
class Live2DConfig:
    """Live2D model configuration."""

    model_url: Optional[str] = None
    model_folder: Optional[str] = None
    textures_url: str = "/static/models/textures/"


@dataclass
class FlaskConfig:
    """Flask web server configuration."""

    host: str = "0.0.0.0"
    port: int = 5000
    debug: bool = False


@dataclass
class AgentsConfig:
    """LiveKit Agents configuration."""

    tts_provider: str = "openai"
    stt_provider: str = "openai"


@dataclass
class AppConfig:
    """Main application configuration."""

    livekit: LiveKitConfig
    ai: AIConfig
    content_filter: ContentFilterConfig
    personality: PersonalityConfig
    memory: MemoryConfig
    live2d: Live2DConfig
    agents: AgentsConfig
    flask: FlaskConfig
    debug: bool = False
    log_level: str = "INFO"


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing required values."""

    pass


class ConfigManager:
    """Manages application configuration from environment variables."""

    def __init__(self, env_file: str = ".env"):
        """Initialize configuration manager.

        Args:
            env_file: Path to .env file to load
        """
        self.env_file = env_file
        self._config: Optional[AppConfig] = None
        self.logger = self._setup_logging()

    def _setup_logging(self) -> logging.Logger:
        """Set up basic logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        return logging.getLogger(__name__)

    def load_config(self) -> AppConfig:
        """Load and validate configuration from environment variables.

        Returns:
            AppConfig: Validated configuration object

        Raises:
            ConfigurationError: If required configuration is missing or invalid
        """
        # Load .env file if it exists (override=True to ensure test files take precedence)
        if os.path.exists(self.env_file):
            load_dotenv(self.env_file, override=True)
            self.logger.info(f"Loaded configuration from {self.env_file}")
        else:
            self.logger.warning(f"No .env file found at {self.env_file}")

        try:
            # LiveKit configuration (required)
            livekit_config = LiveKitConfig(
                url=self._get_required_env("LIVEKIT_URL"),
                api_key=self._get_required_env("LIVEKIT_API_KEY"),
                api_secret=self._get_required_env("LIVEKIT_API_SECRET"),
                room_name=os.getenv("LIVEKIT_ROOM_NAME", "anime_room"),
            )

            # AI configuration
            ai_config = AIConfig(
                use_ollama=os.getenv("USE_OLLAMA", "true").lower() == "true",
                ollama_model=os.getenv("OLLAMA_MODEL", "llama3"),
                ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
                gemini_api_keys=self._parse_gemini_keys(),
                gemini_current_key_index=int(
                    os.getenv("GEMINI_CURRENT_KEY_INDEX", "0")
                ),
            )

            # Content filtering configuration
            content_filter_config = ContentFilterConfig(
                enable_content_filter=os.getenv("ENABLE_CONTENT_FILTER", "true").lower()
                == "true",
                strict_mode=os.getenv("CONTENT_FILTER_STRICT_MODE", "false").lower()
                == "true",
            )

            # Personality configuration
            personality_config = PersonalityConfig(
                personality_prompt=os.getenv(
                    "PERSONALITY_PROMPT",
                    "You are a tsundere anime girl named Miko. You're tough on the outside but caring inside. "
                    "Always respond with anime flair, like 'B-baka!' for embarrassment, and end with cute emotes "
                    "like (*blush*). Stay in character no matter what.",
                )
            )

            # Memory configuration
            memory_config = MemoryConfig(
                mem0_api_key=os.getenv("MEM0_API_KEY", ""),
                mem0_host=os.getenv("MEM0_HOST", "https://api.mem0.ai"),
                mem0_collection=os.getenv("MEM0_COLLECTION", "anime_character"),
                memory_history_limit=int(os.getenv("MEMORY_HISTORY_LIMIT", "20")),
            )

            # Live2D configuration
            live2d_config = Live2DConfig(
                model_url=os.getenv("LIVE2D_MODEL_URL"),
                model_folder=os.getenv("LIVE2D_MODEL_FOLDER"),
                textures_url=os.getenv(
                    "LIVE2D_TEXTURES_URL", "/static/models/textures/"
                ),
            )

            # Agents configuration
            agents_config = AgentsConfig(
                tts_provider=os.getenv("TTS_PROVIDER", "openai"),
                stt_provider=os.getenv("STT_PROVIDER", "openai"),
            )

            # Flask configuration
            flask_config = FlaskConfig(
                host=os.getenv("FLASK_HOST", "0.0.0.0"),
                port=int(os.getenv("FLASK_PORT", "5000")),
                debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
            )

            # Main app configuration
            self._config = AppConfig(
                livekit=livekit_config,
                ai=ai_config,
                content_filter=content_filter_config,
                personality=personality_config,
                memory=memory_config,
                live2d=live2d_config,
                agents=agents_config,
                flask=flask_config,
                debug=os.getenv("DEBUG", "false").lower() == "true",
                log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            )

            # Validate configuration
            self._validate_config()

            # Update logging level
            self._update_logging_level()

            self.logger.info("Configuration loaded and validated successfully")
            return self._config

        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {str(e)}")

    def _get_required_env(self, key: str) -> str:
        """Get required environment variable or raise error.

        Args:
            key: Environment variable name

        Returns:
            str: Environment variable value

        Raises:
            ConfigurationError: If environment variable is not set
        """
        value = os.getenv(key)
        if not value:
            raise ConfigurationError(f"Required environment variable {key} is not set")
        return value

    def _parse_gemini_keys(self) -> List[str]:
        """Parse comma-separated Gemini API keys from environment.

        Returns:
            List[str]: List of Gemini API keys
        """
        keys_str = os.getenv("GEMINI_API_KEYS", "")
        if not keys_str:
            return []

        # Split by comma and strip whitespace
        keys = [key.strip() for key in keys_str.split(",") if key.strip()]
        return keys

    def _validate_config(self) -> None:
        """Validate configuration for consistency and completeness.

        Raises:
            ConfigurationError: If configuration is invalid
        """
        if not self._config:
            raise ConfigurationError("Configuration not loaded")

        # Validate AI provider configuration
        if not self._config.ai.use_ollama and not self._config.ai.gemini_api_keys:
            raise ConfigurationError(
                "When USE_OLLAMA=false, at least one Gemini API key must be provided in GEMINI_API_KEYS"
            )

        # Validate Gemini key index
        if self._config.ai.gemini_api_keys:
            if self._config.ai.gemini_current_key_index >= len(
                self._config.ai.gemini_api_keys
            ):
                self.logger.warning(
                    f"GEMINI_CURRENT_KEY_INDEX ({self._config.ai.gemini_current_key_index}) "
                    f"is out of range for available keys ({len(self._config.ai.gemini_api_keys)}). "
                    "Resetting to 0."
                )
                self._config.ai.gemini_current_key_index = 0

        # Validate memory configuration
        if (
            self._config.memory.mem0_api_key
            and self._config.memory.memory_history_limit <= 0
        ):
            raise ConfigurationError("MEMORY_HISTORY_LIMIT must be greater than 0")

        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self._config.log_level not in valid_log_levels:
            self.logger.warning(
                f"Invalid LOG_LEVEL '{self._config.log_level}'. Using 'INFO' instead."
            )
            self._config.log_level = "INFO"

    def _update_logging_level(self) -> None:
        """Update logging level based on configuration."""
        if self._config:
            log_level = getattr(logging, self._config.log_level)
            logging.getLogger().setLevel(log_level)
            self.logger.setLevel(log_level)

    def get_config(self) -> AppConfig:
        """Get current configuration.

        Returns:
            AppConfig: Current configuration

        Raises:
            ConfigurationError: If configuration not loaded
        """
        if not self._config:
            raise ConfigurationError(
                "Configuration not loaded. Call load_config() first."
            )
        return self._config

    def update_gemini_key_index(self, index: int) -> None:
        """Update current Gemini API key index.

        Args:
            index: New key index

        Raises:
            ConfigurationError: If index is out of range
        """
        if not self._config:
            raise ConfigurationError("Configuration not loaded")

        if not self._config.ai.gemini_api_keys:
            raise ConfigurationError("No Gemini API keys configured")

        if index < 0 or index >= len(self._config.ai.gemini_api_keys):
            raise ConfigurationError(
                f"Key index {index} out of range (0-{len(self._config.ai.gemini_api_keys)-1})"
            )

        self._config.ai.gemini_current_key_index = index
        self.logger.info(f"Updated Gemini API key index to {index}")

    def get_current_gemini_key(self) -> Optional[str]:
        """Get current Gemini API key.

        Returns:
            Optional[str]: Current Gemini API key or None if not configured
        """
        if not self._config or not self._config.ai.gemini_api_keys:
            return None

        index = self._config.ai.gemini_current_key_index
        if index < len(self._config.ai.gemini_api_keys):
            return self._config.ai.gemini_api_keys[index]

        return None

    def rotate_gemini_key(self) -> Optional[str]:
        """Rotate to next Gemini API key.

        Returns:
            Optional[str]: New current key or None if no keys available
        """
        if not self._config or not self._config.ai.gemini_api_keys:
            return None

        # Move to next key (wrap around if at end)
        current_index = self._config.ai.gemini_current_key_index
        next_index = (current_index + 1) % len(self._config.ai.gemini_api_keys)

        self.update_gemini_key_index(next_index)
        return self.get_current_gemini_key()


# Global configuration manager instance
config_manager = ConfigManager()


def get_config() -> AppConfig:
    """Get application configuration.

    Returns:
        AppConfig: Application configuration
    """
    return config_manager.get_config()


def load_config(env_file: str = ".env") -> AppConfig:
    """Load application configuration from environment.

    Args:
        env_file: Path to .env file

    Returns:
        AppConfig: Loaded configuration
    """
    global config_manager
    config_manager = ConfigManager(env_file)
    return config_manager.load_config()


def get_settings() -> AppConfig:
    """Get application settings (alias for get_config for Flask compatibility).

    Returns:
        AppConfig: Application configuration
    """
    return get_config()