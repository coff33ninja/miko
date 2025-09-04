#!/usr/bin/env python3
"""
Demo script for testing the Flask web server functionality.

This script demonstrates how to:
1. Start the Flask server
2. Test the animation API
3. Generate LiveKit tokens
4. Serve Live2D model files
"""

import os
import sys
import time
import requests
import threading
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config.settings import load_config
from web.app import Live2DFlaskApp


def start_server_thread(app, host="127.0.0.1", port=5001):
    """Start Flask server in a separate thread for testing."""
    app.run(host=host, port=port, debug=False)


def test_flask_endpoints():
    """Test Flask endpoints with sample requests."""
    base_url = "http://127.0.0.1:5001"

    print("Testing Flask Web Server Endpoints")
    print("=" * 50)

    # Wait for server to start
    time.sleep(2)

    try:
        # Test health check
        print("1. Testing health check...")
        response = requests.get(f"{base_url}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        print()

        # Test animation endpoint
        print("2. Testing animation endpoint...")
        animation_data = {"expression": "happy", "intensity": 0.8, "duration": 2.0}
        response = requests.post(f"{base_url}/animate", json=animation_data)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        print()

        # Test animation status
        print("3. Testing animation status...")
        response = requests.get(f"{base_url}/animate/status")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        print()

        # Test token generation (will fail without proper LiveKit config)
        print("4. Testing token generation...")
        token_data = {"room": "demo_room", "participant": "demo_user"}
        response = requests.post(f"{base_url}/token", json=token_data)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Token generated successfully")
        else:
            print(f"   Error: {response.json()}")
        print()

        # Test static file serving
        print("5. Testing static file serving...")
        response = requests.get(f"{base_url}/static/models/sample.model3.json")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Sample model file served successfully")
        else:
            print(f"   Error: {response.json()}")
        print()

        # Test main page
        print("6. Testing main page...")
        response = requests.get(f"{base_url}/")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Main page loaded successfully")
            print(f"   Content length: {len(response.text)} characters")
        print()

    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to Flask server")
    except Exception as e:
        print(f"Error during testing: {e}")


def main():
    """Main demo function."""
    print("Live2D Flask Server Demo")
    print("=" * 30)

    # Check if we have a .env file
    if not os.path.exists(".env"):
        print("Warning: No .env file found. Creating minimal configuration...")
        with open(".env", "w") as f:
            f.write("""# Minimal configuration for Flask demo
LIVEKIT_URL=wss://demo.livekit.cloud
LIVEKIT_API_KEY=demo_key
LIVEKIT_API_SECRET=demo_secret
FLASK_HOST=127.0.0.1
FLASK_PORT=5001
FLASK_DEBUG=false
LIVE2D_MODEL_URL=/static/models/sample.model3.json
DEBUG=false
LOG_LEVEL=INFO
""")
        print("Created .env file with demo configuration")

    try:
        # Load configuration
        config = load_config()
        print(f"Configuration loaded successfully")
        print(f"Flask will run on {config.flask.host}:{config.flask.port}")
        print()

        # Create Flask app
        flask_app = Live2DFlaskApp()

        # Start server in background thread
        server_thread = threading.Thread(
            target=start_server_thread,
            args=(flask_app, config.flask.host, config.flask.port),
            daemon=True,
        )
        server_thread.start()

        print("Starting Flask server...")
        print("Press Ctrl+C to stop the demo")
        print()

        # Test endpoints
        test_flask_endpoints()

        print("Demo completed successfully!")
        print("Server is still running. Press Ctrl+C to stop.")

        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nDemo stopped by user")

    except Exception as e:
        print(f"Demo failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
