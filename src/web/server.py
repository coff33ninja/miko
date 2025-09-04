#!/usr/bin/env python3
"""
Flask server startup script for Live2D Anime AI Character.

This script starts the Flask web server with proper configuration
and error handling for the Live2D model serving and animation API.
"""

import sys
import logging
from pathlib import Path

# Add src directory to Python path for local imports
src_dir = Path(__file__).parent.parent
sys.path.insert(0, str(src_dir))

# Now we can import local modules
from config.settings import load_config, ConfigurationError
from .app import Live2DFlaskApp


def setup_logging(log_level: str = "INFO"):
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/flask_server.log", mode="a"),
        ],
    )


def main():
    """Main entry point for Flask server."""
    try:
        # Load configuration
        config = load_config()

        # Set up logging
        setup_logging(config.log_level)
        logger = logging.getLogger(__name__)

        logger.info("Starting Live2D Anime AI Character Flask Server")
        logger.info(f"Configuration loaded: Debug={config.debug}")
        logger.info(f"LiveKit URL: {config.livekit.url}")
        logger.info(f"Live2D Model: {config.live2d.model_url}")

        # Create Flask application
        flask_app = Live2DFlaskApp()

        # Start server
        logger.info(f"Starting server on {config.flask.host}:{config.flask.port}")
        flask_app.run(
            host=config.flask.host, port=config.flask.port, debug=config.flask.debug
        )

    except ConfigurationError as e:
        print(f"Configuration error: {e}")
        print("Please check your .env file and ensure all required variables are set.")
        sys.exit(1)

    except KeyboardInterrupt:
        print("\nServer stopped by user")
        sys.exit(0)

    except Exception as e:
        print(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
