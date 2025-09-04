#!/usr/bin/env python3
"""
Web Interface Demo Script

This script demonstrates the web interface functionality by:
1. Starting the Flask server
2. Opening a browser to the interface
3. Showing key features and capabilities

Usage:
    python examples/web_interface_demo.py
"""

import sys
import time
import threading
import webbrowser
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_dir))

try:
    from web.app import Live2DFlaskApp
    from config.settings import get_settings
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)


def print_banner():
    """Print demo banner."""
    print("=" * 60)
    print("🎌 Anime AI Character - Web Interface Demo")
    print("=" * 60)
    print()


def print_features():
    """Print key features of the web interface."""
    features = [
        "🎤 Voice and Text Input Modes",
        "🎭 Live2D Character Animation",
        "🔗 LiveKit Real-time Communication",
        "👥 Participant Management",
        "📱 Responsive Design (Mobile/Tablet/Desktop)",
        "🎮 Animation Controls and Testing",
        "🔧 WebSocket Integration",
        "📊 Connection Quality Indicators",
        "⌨️ Keyboard Shortcuts",
        "🧪 Built-in Test Suite"
    ]
    
    print("Key Features:")
    for feature in features:
        print(f"  {feature}")
    print()


def print_usage_instructions():
    """Print usage instructions."""
    instructions = [
        "1. 🔗 Click 'Connect to LiveKit' to join the room",
        "2. 🎤 Switch between Voice and Text input modes",
        "3. 💬 In Text mode: Type messages or use quick buttons",
        "4. 🎤 In Voice mode: Use microphone or push-to-talk",
        "5. 🎭 Try animation controls to see Live2D expressions",
        "6. 🧪 Run tests to validate functionality",
        "7. 📱 Resize browser to test responsive design"
    ]
    
    print("How to Use:")
    for instruction in instructions:
        print(f"  {instruction}")
    print()


def print_keyboard_shortcuts():
    """Print keyboard shortcuts."""
    shortcuts = [
        "Ctrl + Tab: Switch input modes",
        "Ctrl + Enter: Send text message (in text mode)",
        "Space: Push-to-talk (in voice mode, when not typing)",
        "Tab: Navigate between controls"
    ]
    
    print("Keyboard Shortcuts:")
    for shortcut in shortcuts:
        print(f"  {shortcut}")
    print()


def start_flask_server():
    """Start Flask server in a separate thread."""
    def run_server():
        try:
            flask_app = Live2DFlaskApp()
            print("🚀 Starting Flask server...")
            flask_app.run(host='127.0.0.1', port=5000, debug=False)
        except Exception as e:
            print(f"❌ Failed to start Flask server: {e}")
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait for server to start
    print("⏳ Waiting for server to start...")
    time.sleep(3)
    
    return server_thread


def open_browser():
    """Open browser to the web interface."""
    url = "http://127.0.0.1:5000"
    print(f"🌐 Opening browser to: {url}")
    
    try:
        webbrowser.open(url)
        return True
    except Exception as e:
        print(f"❌ Failed to open browser: {e}")
        print(f"Please manually open: {url}")
        return False


def main():
    """Main demo function."""
    print_banner()
    print_features()
    print_usage_instructions()
    print_keyboard_shortcuts()
    
    # Check configuration
    try:
        settings = get_settings()
        print("Configuration Status:")
        print(f"  LiveKit URL: {settings.livekit.url}")
        print(f"  Live2D Model: {settings.live2d.model_url}")
        print(f"  Debug Mode: {settings.debug}")
        print()
    except Exception as e:
        print(f"⚠️  Configuration warning: {e}")
        print("Some features may not work properly without proper configuration.")
        print()
    
    # Start server
    server_thread = start_flask_server()
    
    # Open browser
    browser_opened = open_browser()
    
    if browser_opened:
        print("✅ Demo started successfully!")
        print()
        print("The web interface should now be open in your browser.")
        print("Try the following to test the interface:")
        print("  • Switch between voice and text input modes")
        print("  • Click animation buttons to see expressions")
        print("  • Run the built-in tests")
        print("  • Resize the browser window to test responsive design")
        print()
        print("Press Ctrl+C to stop the demo server.")
        
        try:
            # Keep the main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Demo stopped by user")
    else:
        print("❌ Failed to open browser automatically")
        print("Please manually navigate to: http://127.0.0.1:5000")
        print("Press Ctrl+C to stop the server.")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Demo stopped by user")


if __name__ == '__main__':
    main()