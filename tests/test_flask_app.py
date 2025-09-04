"""
Tests for Flask web server and Live2D model serving.

This module tests:
- Flask application creation and configuration
- Animation API endpoint functionality
- LiveKit token generation
- Static file serving for Live2D models
- Error handling and validation
"""

import os
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from src.web.app import Live2DFlaskApp, create_app
from src.config.settings import AppConfig, LiveKitConfig, Live2DConfig, FlaskConfig


class TestLive2DFlaskApp:
    """Test cases for Live2DFlaskApp class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        return AppConfig(
            livekit=LiveKitConfig(
                url="wss://test.livekit.cloud",
                api_key="test_api_key",
                api_secret="test_api_secret",
                room_name="test_room",
            ),
            ai=MagicMock(),
            content_filter=MagicMock(),
            personality=MagicMock(),
            memory=MagicMock(),
            live2d=Live2DConfig(
                model_url="/static/models/test.moc3", textures_url="/static/textures/"
            ),
            agents=MagicMock(),
            flask=FlaskConfig(host="127.0.0.1", port=5001, debug=True),
            debug=True,
            log_level="DEBUG",
        )

    @pytest.fixture
    def app(self, mock_settings):
        """Create Flask app for testing."""
        with patch("src.web.app.get_settings", return_value=mock_settings):
            flask_app = Live2DFlaskApp()
            flask_app.app.config["TESTING"] = True
            return flask_app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.app.test_client()

    def test_app_initialization(self, app, mock_settings):
        """Test Flask app initialization."""
        assert app.app is not None
        assert app.settings == mock_settings
        assert app.current_animation["expression"] == "neutral"
        assert app.current_animation["intensity"] == 0.5

    def test_index_route(self, client, mock_settings):
        """Test main index route."""
        response = client.get("/")

        assert response.status_code == 200
        assert b"Anime AI Character" in response.data
        assert mock_settings.livekit.url.encode() in response.data
        assert mock_settings.live2d.model_url.encode() in response.data

    def test_animate_endpoint_success(self, client, app):
        """Test successful animation trigger."""
        animation_data = {"expression": "happy", "intensity": 0.8, "duration": 2.0}

        response = client.post(
            "/animate", data=json.dumps(animation_data), content_type="application/json"
        )

        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] is True
        assert data["animation"]["expression"] == "happy"
        assert data["animation"]["intensity"] == 0.8
        assert data["animation"]["duration"] == 2.0

        # Check that app state was updated
        assert app.current_animation["expression"] == "happy"
        assert app.current_animation["intensity"] == 0.8

    def test_animate_endpoint_invalid_intensity(self, client):
        """Test animation endpoint with invalid intensity."""
        animation_data = {
            "expression": "happy",
            "intensity": 1.5,  # Invalid: > 1.0
            "duration": 1.0,
        }

        response = client.post(
            "/animate", data=json.dumps(animation_data), content_type="application/json"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Intensity must be between 0.0 and 1.0" in data["error"]

    def test_animate_endpoint_invalid_duration(self, client):
        """Test animation endpoint with invalid duration."""
        animation_data = {
            "expression": "happy",
            "intensity": 0.5,
            "duration": 15.0,  # Invalid: > 10.0
        }

        response = client.post(
            "/animate", data=json.dumps(animation_data), content_type="application/json"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Duration must be between 0.1 and 10.0 seconds" in data["error"]

    def test_animate_endpoint_no_json(self, client):
        """Test animation endpoint without JSON data."""
        response = client.post("/animate")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "No JSON data provided" in data["error"]

    def test_animate_endpoint_defaults(self, client, app):
        """Test animation endpoint with default values."""
        animation_data = {
            "expression": "sad"
            # intensity and duration should use defaults
        }

        response = client.post(
            "/animate", data=json.dumps(animation_data), content_type="application/json"
        )

        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["animation"]["expression"] == "sad"
        assert data["animation"]["intensity"] == 0.5  # default
        assert data["animation"]["duration"] == 1.0  # default

    def test_animation_status_endpoint(self, client, app):
        """Test animation status endpoint."""
        # First set an animation
        app.current_animation = {
            "expression": "surprised",
            "intensity": 0.7,
            "duration": 1.5,
            "timestamp": datetime.now(),
        }

        response = client.get("/animate/status")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["current_animation"]["expression"] == "surprised"
        assert data["current_animation"]["intensity"] == 0.7
        assert "timestamp" in data

    @patch("src.web.app.api.AccessToken")
    def test_token_generation_success(self, mock_token_class, client, mock_settings):
        """Test successful LiveKit token generation."""
        # Mock the token
        mock_token = MagicMock()
        mock_token.to_jwt.return_value = "test_jwt_token"
        mock_token_class.return_value = mock_token

        token_data = {"room": "test_room", "participant": "test_user"}

        response = client.post(
            "/token", data=json.dumps(token_data), content_type="application/json"
        )

        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["token"] == "test_jwt_token"
        assert data["room"] == "test_room"
        assert data["participant"] == "test_user"
        assert data["url"] == mock_settings.livekit.url

        # Verify token was configured correctly
        mock_token_class.assert_called_once_with(
            api_key=mock_settings.livekit.api_key,
            api_secret=mock_settings.livekit.api_secret,
        )
        mock_token.with_identity.assert_called_once_with("test_user")
        mock_token.with_name.assert_called_once_with("test_user")
        mock_token.with_ttl.assert_called_once()

    @patch("src.web.app.api.AccessToken")
    def test_token_generation_defaults(self, mock_token_class, client):
        """Test token generation with default values."""
        mock_token = MagicMock()
        mock_token.to_jwt.return_value = "test_jwt_token"
        mock_token_class.return_value = mock_token

        response = client.post(
            "/token", data=json.dumps({}), content_type="application/json"
        )

        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["room"] == "anime-character-room"
        assert data["participant"].startswith("user-")

    def test_token_generation_no_json(self, client):
        """Test token generation without JSON data."""
        response = client.post("/token")

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "No JSON data provided" in data["error"]

    @patch("src.web.app.api.AccessToken")
    def test_token_generation_error(self, mock_token_class, client):
        """Test token generation error handling."""
        mock_token_class.side_effect = Exception("Token generation failed")

        token_data = {"room": "test_room", "participant": "test_user"}

        response = client.post(
            "/token", data=json.dumps(token_data), content_type="application/json"
        )

        assert response.status_code == 500
        data = json.loads(response.data)
        assert "Failed to generate token" in data["error"]

    def test_static_file_serving(self, client):
        """Test static file serving."""
        # Create a temporary file for testing
        static_dir = os.path.join(
            os.path.dirname(__file__), "..", "src", "web", "static"
        )
        os.makedirs(static_dir, exist_ok=True)

        test_file = os.path.join(static_dir, "temp_test.txt")
        try:
            with open(test_file, "w") as f:
                f.write("test content")

            response = client.get("/static/temp_test.txt")

            # Should successfully serve the file
            assert response.status_code == 200
            assert b"test content" in response.data

        finally:
            # Clean up
            if os.path.exists(test_file):
                try:
                    os.remove(test_file)
                except PermissionError:
                    # File might be locked on Windows, ignore for test
                    pass

    def test_static_file_not_found(self, client):
        """Test static file serving for non-existent file."""
        response = client.get("/static/nonexistent.txt")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert "File not found" in data["error"]

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "1.0.0"

    def test_404_error_handler(self, client):
        """Test 404 error handler."""
        response = client.get("/nonexistent-route")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert "Not found" in data["error"]

    def test_create_app_factory(self, mock_settings):
        """Test Flask app factory function."""
        with patch("src.web.app.get_settings", return_value=mock_settings):
            app = create_app()
            assert app is not None
            assert hasattr(app, "test_client")


class TestFlaskAppIntegration:
    """Integration tests for Flask app functionality."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for integration testing."""
        return AppConfig(
            livekit=LiveKitConfig(
                url="wss://test.livekit.cloud",
                api_key="test_api_key",
                api_secret="test_api_secret",
            ),
            ai=MagicMock(),
            content_filter=MagicMock(),
            personality=MagicMock(),
            memory=MagicMock(),
            live2d=Live2DConfig(model_url="/static/models/character.moc3"),
            agents=MagicMock(),
            flask=FlaskConfig(),
            debug=False,
            log_level="INFO",
        )

    @patch("src.web.app.api.AccessToken")
    def test_full_animation_workflow(self, mock_token_class, mock_settings):
        """Test complete animation workflow."""
        with patch("src.web.app.get_settings", return_value=mock_settings):
            flask_app = Live2DFlaskApp()
            client = flask_app.app.test_client()

            # 1. Check initial status
            response = client.get("/animate/status")
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["current_animation"]["expression"] == "neutral"

            # 2. Trigger animation
            animation_data = {"expression": "happy", "intensity": 0.9, "duration": 2.5}

            response = client.post(
                "/animate",
                data=json.dumps(animation_data),
                content_type="application/json",
            )
            assert response.status_code == 200

            # 3. Check updated status
            response = client.get("/animate/status")
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["current_animation"]["expression"] == "happy"
            assert data["current_animation"]["intensity"] == 0.9

    @patch("src.web.app.api.AccessToken")
    def test_token_and_animation_integration(self, mock_token_class, mock_settings):
        """Test integration between token generation and animation."""
        mock_token = MagicMock()
        mock_token.to_jwt.return_value = "integration_test_token"
        mock_token_class.return_value = mock_token

        with patch("src.web.app.get_settings", return_value=mock_settings):
            flask_app = Live2DFlaskApp()
            client = flask_app.app.test_client()

            # 1. Generate token
            response = client.post(
                "/token",
                data=json.dumps({"room": "integration_test"}),
                content_type="application/json",
            )
            assert response.status_code == 200
            token_data = json.loads(response.data)

            # 2. Trigger animation (simulating client interaction)
            animation_data = {
                "expression": "surprised",
                "intensity": 0.6,
                "duration": 1.0,
            }

            response = client.post(
                "/animate",
                data=json.dumps(animation_data),
                content_type="application/json",
            )
            assert response.status_code == 200

            # 3. Verify both operations succeeded
            assert token_data["token"] == "integration_test_token"

            status_response = client.get("/animate/status")
            status_data = json.loads(status_response.data)
            assert status_data["current_animation"]["expression"] == "surprised"


if __name__ == "__main__":
    pytest.main([__file__])
