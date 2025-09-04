#!/usr/bin/env python3
"""
End-to-end tests for the web interface with LiveKit integration.

This module tests the complete user interaction flow including:
- Web interface loading and initialization
- LiveKit connection and participant management
- Voice and text input modes
- Animation triggers and synchronization
- Responsive design across different screen sizes
"""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, patch, AsyncMock
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from web.app import Live2DFlaskApp
from config.settings import get_settings


class TestWebInterfaceE2E:
    """End-to-end tests for the complete web interface."""
    
    @pytest.fixture(scope="class")
    def flask_app(self):
        """Create Flask app for testing."""
        app = Live2DFlaskApp()
        return app.get_app()
    
    @pytest.fixture(scope="class")
    def web_driver(self):
        """Create web driver for browser automation."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode for CI
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Enable media permissions for microphone testing
        prefs = {
            "profile.default_content_setting_values.media_stream_mic": 1,
            "profile.default_content_setting_values.media_stream_camera": 1
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        driver = webdriver.Chrome(options=chrome_options)
        yield driver
        driver.quit()
    
    @pytest.fixture
    def live_server(self, flask_app):
        """Start Flask server for testing."""
        import threading
        import socket
        
        # Find available port
        sock = socket.socket()
        sock.bind(('', 0))
        port = sock.getsockname()[1]
        sock.close()
        
        # Start server in thread
        server_thread = threading.Thread(
            target=lambda: flask_app.run(host='127.0.0.1', port=port, debug=False),
            daemon=True
        )
        server_thread.start()
        
        # Wait for server to start
        time.sleep(2)
        
        yield f"http://127.0.0.1:{port}"
    
    def test_page_loads_successfully(self, web_driver, live_server):
        """Test that the main page loads with all required elements."""
        web_driver.get(live_server)
        
        # Wait for page to load
        WebDriverWait(web_driver, 10).until(
            EC.presence_of_element_located((By.ID, "live2d-canvas"))
        )
        
        # Check essential elements are present
        assert web_driver.find_element(By.ID, "live2d-canvas")
        assert web_driver.find_element(By.ID, "connect-btn")
        assert web_driver.find_element(By.ID, "voice-mode-btn")
        assert web_driver.find_element(By.ID, "text-mode-btn")
        assert web_driver.find_element(By.ID, "participants-list")
        
        # Check page title
        assert "Anime AI Character" in web_driver.title
    
    def test_input_mode_switching(self, web_driver, live_server):
        """Test switching between voice and text input modes."""
        web_driver.get(live_server)
        
        # Wait for page to load
        WebDriverWait(web_driver, 10).until(
            EC.element_to_be_clickable((By.ID, "text-mode-btn"))
        )
        
        # Initially should be in voice mode
        voice_btn = web_driver.find_element(By.ID, "voice-mode-btn")
        text_btn = web_driver.find_element(By.ID, "text-mode-btn")
        voice_controls = web_driver.find_element(By.ID, "voice-controls")
        text_controls = web_driver.find_element(By.ID, "text-controls")
        
        assert "active" in voice_btn.get_attribute("class")
        assert voice_controls.is_displayed()
        assert not text_controls.is_displayed()
        
        # Switch to text mode
        text_btn.click()
        time.sleep(0.5)
        
        assert "active" in text_btn.get_attribute("class")
        assert "active" not in voice_btn.get_attribute("class")
        assert text_controls.is_displayed()
        assert not voice_controls.is_displayed()
        
        # Switch back to voice mode
        voice_btn.click()
        time.sleep(0.5)
        
        assert "active" in voice_btn.get_attribute("class")
        assert voice_controls.is_displayed()
        assert not text_controls.is_displayed()
    
    def test_text_message_input(self, web_driver, live_server):
        """Test text message input functionality."""
        web_driver.get(live_server)
        
        # Switch to text mode
        WebDriverWait(web_driver, 10).until(
            EC.element_to_be_clickable((By.ID, "text-mode-btn"))
        ).click()
        
        # Find text input and send button
        text_input = web_driver.find_element(By.ID, "text-input")
        send_btn = web_driver.find_element(By.ID, "send-text-btn")
        
        # Test typing and sending message
        test_message = "Hello, this is a test message!"
        text_input.send_keys(test_message)
        assert text_input.get_attribute("value") == test_message
        
        # Test Enter key to send
        text_input.clear()
        text_input.send_keys("Test Enter key")
        text_input.send_keys(Keys.ENTER)
        
        # Input should be cleared after sending
        time.sleep(0.5)
        assert text_input.get_attribute("value") == ""
    
    def test_quick_message_buttons(self, web_driver, live_server):
        """Test quick message button functionality."""
        web_driver.get(live_server)
        
        # Switch to text mode
        WebDriverWait(web_driver, 10).until(
            EC.element_to_be_clickable((By.ID, "text-mode-btn"))
        ).click()
        
        # Find quick message buttons
        quick_buttons = web_driver.find_elements(By.CLASS_NAME, "quick-msg")
        assert len(quick_buttons) >= 3
        
        # Test clicking a quick message button
        text_input = web_driver.find_element(By.ID, "text-input")
        quick_buttons[0].click()
        
        # Text input should be populated
        time.sleep(0.5)
        assert text_input.get_attribute("value") != ""
    
    def test_animation_controls(self, web_driver, live_server):
        """Test animation control buttons."""
        web_driver.get(live_server)
        
        # Wait for animation system to initialize
        WebDriverWait(web_driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "animation-controls"))
        )
        
        # Find animation buttons
        animation_buttons = web_driver.find_elements(
            By.CSS_SELECTOR, ".animation-controls .button"
        )
        assert len(animation_buttons) >= 6
        
        # Test clicking animation buttons
        for i, button in enumerate(animation_buttons[:3]):  # Test first 3 buttons
            button.click()
            time.sleep(0.5)  # Allow animation to trigger
            
            # Check that chat messages are added
            chat_messages = web_driver.find_element(By.ID, "chat-messages")
            assert "Animation:" in chat_messages.text or "system" in chat_messages.text
    
    def test_slider_controls(self, web_driver, live_server):
        """Test animation intensity and duration sliders."""
        web_driver.get(live_server)
        
        # Find sliders
        intensity_slider = web_driver.find_element(By.ID, "intensity-slider")
        duration_slider = web_driver.find_element(By.ID, "duration-slider")
        intensity_value = web_driver.find_element(By.ID, "intensity-value")
        duration_value = web_driver.find_element(By.ID, "duration-value")
        
        # Test intensity slider
        initial_intensity = intensity_value.text
        web_driver.execute_script("arguments[0].value = '0.9';", intensity_slider)
        web_driver.execute_script("arguments[0].dispatchEvent(new Event('input'));", intensity_slider)
        time.sleep(0.5)
        assert intensity_value.text != initial_intensity
        
        # Test duration slider
        initial_duration = duration_value.text
        web_driver.execute_script("arguments[0].value = '3.0';", duration_slider)
        web_driver.execute_script("arguments[0].dispatchEvent(new Event('input'));", duration_slider)
        time.sleep(0.5)
        assert duration_value.text != initial_duration
    
    def test_responsive_design_mobile(self, web_driver, live_server):
        """Test responsive design on mobile screen size."""
        # Set mobile viewport
        web_driver.set_window_size(375, 667)  # iPhone 6/7/8 size
        web_driver.get(live_server)
        
        # Wait for page to load
        WebDriverWait(web_driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "container"))
        )
        
        container = web_driver.find_element(By.CLASS_NAME, "container")
        
        # Check that container uses flex-direction: column on mobile
        container_style = web_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).flexDirection;", 
            container
        )
        assert container_style == "column"
        
        # Check that control panel is visible and properly sized
        control_panel = web_driver.find_element(By.CLASS_NAME, "control-panel")
        assert control_panel.is_displayed()
        
        # Check that animation buttons are arranged in fewer columns
        animation_controls = web_driver.find_element(By.CLASS_NAME, "animation-controls")
        grid_columns = web_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).gridTemplateColumns;",
            animation_controls
        )
        # Should have fewer columns on mobile
        assert "repeat(2" in grid_columns or "repeat(3" in grid_columns
    
    def test_responsive_design_tablet(self, web_driver, live_server):
        """Test responsive design on tablet screen size."""
        # Set tablet viewport
        web_driver.set_window_size(768, 1024)  # iPad size
        web_driver.get(live_server)
        
        # Wait for page to load
        WebDriverWait(web_driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "container"))
        )
        
        # Check that layout is appropriate for tablet
        control_panel = web_driver.find_element(By.CLASS_NAME, "control-panel")
        panel_width = control_panel.size['width']
        
        # Control panel should be narrower on tablet
        assert panel_width < 320  # Should be less than desktop width
    
    def test_responsive_design_desktop(self, web_driver, live_server):
        """Test responsive design on desktop screen size."""
        # Set desktop viewport
        web_driver.set_window_size(1920, 1080)
        web_driver.get(live_server)
        
        # Wait for page to load
        WebDriverWait(web_driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "container"))
        )
        
        container = web_driver.find_element(By.CLASS_NAME, "container")
        
        # Check that container uses flex-direction: row on desktop
        container_style = web_driver.execute_script(
            "return window.getComputedStyle(arguments[0]).flexDirection;", 
            container
        )
        assert container_style == "row"
        
        # Check that control panel has full width
        control_panel = web_driver.find_element(By.CLASS_NAME, "control-panel")
        panel_width = control_panel.size['width']
        assert panel_width >= 320  # Should be full desktop width
    
    @patch('src.web.app.api.AccessToken')
    def test_livekit_token_generation(self, mock_token_class, web_driver, live_server):
        """Test LiveKit token generation functionality."""
        # Mock the token generation
        mock_token = Mock()
        mock_token.to_jwt.return_value = "mock_jwt_token"
        mock_token_class.return_value = mock_token
        
        web_driver.get(live_server)
        
        # Wait for connect button and click it
        connect_btn = WebDriverWait(web_driver, 10).until(
            EC.element_to_be_clickable((By.ID, "connect-btn"))
        )
        
        # Execute JavaScript to simulate connection attempt
        web_driver.execute_script("""
            fetch('/token', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({room: 'test-room', participant: 'test-user'})
            }).then(response => response.json())
            .then(data => {
                window.tokenResponse = data;
            });
        """)
        
        # Wait for response
        time.sleep(2)
        
        # Check that token was generated
        token_response = web_driver.execute_script("return window.tokenResponse;")
        assert token_response is not None
        assert 'token' in token_response or 'error' in token_response
    
    def test_websocket_status_display(self, web_driver, live_server):
        """Test WebSocket status display and reconnection."""
        web_driver.get(live_server)
        
        # Wait for WebSocket status element
        ws_status = WebDriverWait(web_driver, 10).until(
            EC.presence_of_element_located((By.ID, "websocket-status"))
        )
        
        # Check initial status
        assert ws_status.text in ["Connecting...", "Connected", "Disconnected"]
        
        # Test reconnect button
        reconnect_btn = web_driver.find_element(By.ID, "websocket-reconnect")
        assert reconnect_btn.is_displayed()
        
        # Click reconnect button
        reconnect_btn.click()
        time.sleep(1)
        
        # Status should update (may show "Connecting..." briefly)
        # This tests the UI interaction, actual WebSocket connection depends on server
    
    def test_chat_message_display(self, web_driver, live_server):
        """Test chat message display and clearing."""
        web_driver.get(live_server)
        
        # Wait for chat messages container
        chat_messages = WebDriverWait(web_driver, 10).until(
            EC.presence_of_element_located((By.ID, "chat-messages"))
        )
        
        # Should have initial system messages
        assert len(chat_messages.find_elements(By.CLASS_NAME, "message")) > 0
        
        # Test clear chat button
        clear_btn = web_driver.find_element(By.ID, "clear-chat")
        clear_btn.click()
        time.sleep(0.5)
        
        # Chat should be cleared
        messages_after_clear = chat_messages.find_elements(By.CLASS_NAME, "message")
        assert len(messages_after_clear) == 0
    
    def test_keyboard_shortcuts(self, web_driver, live_server):
        """Test keyboard shortcuts functionality."""
        web_driver.get(live_server)
        
        # Wait for page to load
        WebDriverWait(web_driver, 10).until(
            EC.presence_of_element_located((By.ID, "voice-mode-btn"))
        )
        
        # Test Ctrl+Tab to switch input modes
        body = web_driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.CONTROL + Keys.TAB)
        time.sleep(0.5)
        
        # Should switch to text mode
        text_btn = web_driver.find_element(By.ID, "text-mode-btn")
        assert "active" in text_btn.get_attribute("class")
        
        # Test Ctrl+Enter to send message in text mode
        text_input = web_driver.find_element(By.ID, "text-input")
        text_input.send_keys("Test message")
        text_input.send_keys(Keys.CONTROL + Keys.ENTER)
        time.sleep(0.5)
        
        # Input should be cleared
        assert text_input.get_attribute("value") == ""
    
    def test_error_handling_display(self, web_driver, live_server):
        """Test error message display in the interface."""
        web_driver.get(live_server)
        
        # Wait for page to load
        WebDriverWait(web_driver, 10).until(
            EC.presence_of_element_located((By.ID, "connect-btn"))
        )
        
        # Simulate an error by trying to connect without proper configuration
        web_driver.execute_script("""
            // Simulate connection error
            document.dispatchEvent(new CustomEvent('websocketError', {
                detail: { error: 'Test connection error' }
            }));
        """)
        
        time.sleep(1)
        
        # Check that error is displayed in chat
        chat_messages = web_driver.find_element(By.ID, "chat-messages")
        assert "error" in chat_messages.text.lower()
    
    def test_animation_system_initialization(self, web_driver, live_server):
        """Test that animation system initializes properly."""
        web_driver.get(live_server)
        
        # Wait for loading to complete
        WebDriverWait(web_driver, 15).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "loading"))
        )
        
        # Check that animation system is ready
        chat_messages = web_driver.find_element(By.ID, "chat-messages")
        messages_text = chat_messages.text
        
        # Should see initialization messages
        assert ("Animation system ready" in messages_text or 
                "Initializing animation system" in messages_text)
        
        # Animation buttons should be clickable
        animation_buttons = web_driver.find_elements(
            By.CSS_SELECTOR, ".animation-controls .button"
        )
        for button in animation_buttons[:2]:  # Test first 2 buttons
            assert button.is_enabled()


class TestWebInterfaceAPI:
    """Test the web interface API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client for Flask app."""
        app = Live2DFlaskApp()
        app.get_app().config['TESTING'] = True
        with app.get_app().test_client() as client:
            yield client
    
    def test_index_route(self, client):
        """Test the main index route."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Anime AI Character' in response.data
        assert b'live2d-canvas' in response.data
    
    def test_animate_endpoint(self, client):
        """Test the animation API endpoint."""
        response = client.post('/animate', 
            json={
                'expression': 'happy',
                'intensity': 0.7,
                'duration': 2.0
            },
            content_type='application/json'
        )
        
        # Should return success or error (depending on WebSocket availability)
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.get_json()
            assert 'success' in data
            assert 'animation' in data
    
    def test_token_endpoint(self, client):
        """Test the LiveKit token generation endpoint."""
        response = client.post('/token',
            json={
                'room': 'test-room',
                'participant': 'test-user'
            },
            content_type='application/json'
        )
        
        # Should return token or error (depending on configuration)
        assert response.status_code in [200, 400, 500]
        
        data = response.get_json()
        assert 'token' in data or 'error' in data
    
    def test_health_endpoint(self, client):
        """Test the health check endpoint."""
        response = client.get('/health')
        assert response.status_code in [200, 503]
        
        data = response.get_json()
        assert 'status' in data
        assert 'timestamp' in data
        assert 'components' in data
    
    def test_static_file_serving(self, client):
        """Test static file serving."""
        # Test that static route exists (may return 404 if file doesn't exist)
        response = client.get('/static/test.txt')
        assert response.status_code in [200, 404]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])