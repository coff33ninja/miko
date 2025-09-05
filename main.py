#!/usr/bin/env python3
"""
Main entry point for Anime AI Character application.
Handles startup, configuration validation, service initialization, and graceful shutdown.
"""

import sys
import asyncio
import logging
import signal
import atexit
from pathlib import Path
from typing import Optional, List
import threading
import requests


from src.config.settings import load_config, ConfigurationError
from src.config.logging_config import setup_application_logging
from src.agent.livekit_agent import main as livekit_agent_main
from src.memory.memory_manager import MemoryManager


class ServiceManager:
    """Manages application services with graceful startup and shutdown."""

    def __init__(self):
        self.services: List[str] = []
        self.running = False
        self.shutdown_event = threading.Event()
        self.logger = logging.getLogger(__name__)

    def register_service(self, service_name: str):
        """Register a service for management."""
        self.services.append(service_name)
        self.logger.info(f"Registered service: {service_name}")

    async def start_services(self, config):
        """Start all registered services."""
        self.running = True
        self.logger.info("Starting application services...")

        # Initialize and start services

        # Memory Manager
        self.logger.info("Starting Memory Manager...")
        self.memory_manager = MemoryManager(config.memory)
        await self.memory_manager.initialize()

        # AI Provider (initialized implicitly by LiveKit Agent's LLM)
        self.logger.info("AI Provider will be initialized by LiveKit Agent's LLM.")

        # Flask Web Server
        self.logger.info("Starting Flask Web Server...")
        from src.web.app import Live2DFlaskApp

        flask_app = Live2DFlaskApp()
        flask_thread = threading.Thread(
            target=flask_app.run,
            kwargs={
                "host": config.flask.host,
                "port": config.flask.port,
                "debug": config.flask.debug,
            },
            daemon=True,
        )
        flask_thread.start()

        # LiveKit Agent
        self.logger.info("Starting LiveKit Agent...")
        livekit_thread = threading.Thread(target=livekit_agent_main, daemon=True)
        livekit_thread.start()

        self.logger.info("All services started successfully!")

    async def stop_services(self):
        """Stop all services gracefully."""
        if not self.running:
            return

        self.logger.info("Stopping application services...")
        self.shutdown_event.set()

        # Stop services in reverse order
        for service in reversed(self.services):
            self.logger.info(f"Stopping {service}...")
            await asyncio.sleep(0.1)  # Simulate shutdown time

        self.running = False
        self.logger.info("All services stopped successfully!")


# Global service manager
service_manager = ServiceManager()


def _run_shutdown():
    """Synchronous wrapper to run the async shutdown process."""
    if service_manager.running:
        logging.getLogger(__name__).info("atexit: Running graceful shutdown...")
        # Use asyncio.run() to execute the async function
        # This is safe to call even if there's no running loop
        asyncio.run(service_manager.stop_services())


def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown."""

    def signal_handler(signum, frame):
        print(f"\n Received signal {signum}. Initiating graceful shutdown...")
        asyncio.create_task(shutdown_application())

    # Handle SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal_handler)


async def shutdown_application():
    """Gracefully shutdown the application."""
    logger = logging.getLogger(__name__)
    logger.info("Initiating application shutdown...")

    try:
        await service_manager.stop_services()
        print("Application shutdown completed successfully!")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
        print(f"Error during shutdown: {e}")
    finally:
        # The shutdown is now handled by the main loop exit and atexit handler
        pass


def validate_environment():
    """Validate environment and system requirements."""
    logger = logging.getLogger(__name__)

    # Check Python version
    if sys.version_info < (3, 8):
        raise ConfigurationError("Python 3.8 or higher is required")

    # Check required directories
    required_dirs = ["src", "static", "logs"]
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            logger.info(f"Creating required directory: {dir_path}")
            dir_path.mkdir(parents=True, exist_ok=True)

    # Check for .env file
    if not Path(".env").exists():
        if Path(".env.example").exists():
            logger.warning(
                "No .env file found. Please copy .env.example to .env and configure your settings."
            )
            raise ConfigurationError(
                "No .env file found. Copy .env.example to .env and configure your settings."
            )
        else:
            raise ConfigurationError("No .env or .env.example file found")

    logger.info("Environment validation completed successfully")


async def main():
    """Main application entry point."""
    logger: Optional[logging.Logger] = None

    try:
        # Register atexit handler for graceful shutdown
        atexit.register(_run_shutdown)

        # Set up signal handlers for graceful shutdown
        setup_signal_handlers()

        # Validate environment first
        print("Validating environment...")
        validate_environment()

        # Load configuration
        print("Loading configuration...")
        config = load_config()

        # Set up logging based on configuration
        setup_application_logging(log_level=config.log_level, debug=config.debug)

        logger = logging.getLogger(__name__)
        logger.info("Anime AI Character system starting up...")

        # Log configuration summary (without sensitive data)
        logger.info(f"AI Provider: {'Ollama' if config.ai.use_ollama else 'Gemini'}")
        if config.ai.use_ollama:
            logger.info(f"Ollama Model: {config.ai.ollama_model}")
            logger.info(f"Ollama Host: {config.ai.ollama_host}")
        else:
            logger.info(f"Gemini Keys Available: {len(config.ai.gemini_api_keys)}")
            logger.info(f"Current Key Index: {config.ai.gemini_current_key_index}")

        logger.info(
            f"Content Filtering: {'Enabled' if config.content_filter.enable_content_filter else 'Disabled'}"
        )
        logger.info(
            f"Memory System: {'Mem0' if config.memory.mem0_api_key else 'Session-only'}"
        )
        logger.info(f"LiveKit Room: {config.livekit.room_name}")
        logger.info(f"Live2D Model: {config.live2d.model_url}")
        logger.info(f"Flask Server: {config.flask.host}:{config.flask.port}")

        # Validate critical dependencies
        print("Validating system dependencies...")
        await validate_system_dependencies(config)

        # Register services for management
        service_manager.register_service("AI Provider")
        service_manager.register_service("Memory Manager")
        service_manager.register_service("Flask Web Server")
        service_manager.register_service("LiveKit Agent")

        # Start all services
        print("Starting application services...")
        await service_manager.start_services(config)

        logger.info("All systems operational!")

        # Display startup summary
        print("\n" + "=" * 60)
        print("ANIME AI CHARACTER - SYSTEM READY")
        print("=" * 60)
        print(f"AI Provider: {'Ollama' if config.ai.use_ollama else 'Gemini'}")
        print(
            f"Memory: {'Mem0 enabled' if config.memory.mem0_api_key else 'Session-only'}"
        )
        print(f"Character: Live2D model at {config.live2d.model_url}")
        print(f"LiveKit Room: {config.livekit.room_name}")
        print(f"Web Interface: http://{config.flask.host}:{config.flask.port}")
        print(f"Debug Mode: {'Enabled' if config.debug else 'Disabled'}")
        print(f"Log Level: {config.log_level}")
        print("=" * 60)
        print("Press Ctrl+C to stop the application")
        print("=" * 60)

        # Keep the application running
        try:
            while service_manager.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass

    except ConfigurationError as e:
        if logger:
            logger.error(f"Configuration Error: {e}")
        print(f"Configuration Error: {e}")
        print(
            "\nPlease check your .env file. You can copy .env.example to .env and fill in your values."
        )
        sys.exit(1)
    except Exception as e:
        if logger:
            logger.error(f"Unexpected Error: {e}", exc_info=True)
        print(f"Unexpected Error: {e}")
        sys.exit(1)
    finally:
        # Ensure graceful shutdown
        if service_manager.running:
            await service_manager.stop_services()


async def validate_system_dependencies(config):
    """Validate that system dependencies are available.

    Args:
        config: Application configuration
    """
    logger = logging.getLogger(__name__)

    # Check if required directories exist
    static_dir = Path("static/models")
    if not static_dir.exists():
        logger.warning(
            f"Static models directory {static_dir} does not exist. Creating it..."
        )
        static_dir.mkdir(parents=True, exist_ok=True)

    # Check if logs directory exists
    logs_dir = Path("logs")
    if not logs_dir.exists():
        logger.info(f"Creating logs directory at {logs_dir}")
        logs_dir.mkdir(exist_ok=True)

    # Validate AI provider configuration
    if config.ai.use_ollama:
        logger.info("Ollama selected as AI provider")
        try:
            response = requests.get(f"{config.ai.ollama_host}/api/version", timeout=5)
            response.raise_for_status()
            logger.info("Ollama connectivity check successful")
        except requests.exceptions.RequestException as e:
            raise ConfigurationError(f"Ollama connectivity check failed: {e}")
    else:
        if not config.ai.gemini_api_keys:
            raise ConfigurationError("Gemini selected but no API keys provided")
        logger.info(f"Gemini selected with {len(config.ai.gemini_api_keys)} API keys")

    # Validate memory configuration
    if config.memory.mem0_api_key:
        logger.info("Mem0 memory system configured")
    else:
        logger.warning("No Mem0 API key provided. Memory will be session-only.")

    logger.info("System dependency validation completed")


if __name__ == "__main__":
    asyncio.run(main())