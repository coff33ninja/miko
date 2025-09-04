#!/usr/bin/env python3
"""
Agent runner script for the Anime AI Character LiveKit agent.
This script starts the LiveKit agent with proper configuration.
"""

import sys
import logging
from pathlib import Path
from src.agent.livekit_agent import main

# Add src directory to Python path
src_dir = Path(__file__).parent.parent
sys.path.insert(0, str(src_dir))


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting Anime AI Character LiveKit Agent...")

    try:
        main()
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Agent failed to start: {e}")
        sys.exit(1)
