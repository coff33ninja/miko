"""
Test suite for Live2D animation integration.

This module provides comprehensive tests for the Live2D animation system,
including parameter validation, expression mapping, and animation triggers.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from src.web.app import Live2DFlaskApp, trigger_animation


class TestLive2DAnimation:
    """Test cases for Live2D animation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.flask_app = Live2DFlaskApp()
        self.app = self.flask_app.get_app()
        self.client = self.app.test_client()

    def test_animate_endpoint_valid_request(self):
        """Test animation endpoint with valid parameters."""
        data = {"expression": "happy", "intensity": 0.8, "duration": 2.0}

        response = self.client.post(
            "/animate", data=json.dumps(data), content_type="application/json"
        )

        assert response.status_code == 200
        result = json.loads(response.data)
        assert result["success"] is True
        assert result["animation"]["expression"] == "happy"
        assert result["animation"]["intensity"] == 0.8
        assert result["animation"]["duration"] == 2.0

    def test_animate_endpoint_invalid_intensity(self):
        """Test animation endpoint with invalid intensity."""
        data = {
            "expression": "happy",
            "intensity": 1.5,  # Invalid: > 1.0
            "duration": 2.0,
        }

        response = self.client.post(
            "/animate", data=json.dumps(data), content_type="application/json"
        )

        assert response.status_code == 400
        result = json.loads(response.data)
        assert "error" in result

    def test_animate_endpoint_invalid_duration(self):
        """Test animation endpoint with invalid duration."""
        data = {
            "expression": "happy",
            "intensity": 0.8,
            "duration": 15.0,  # Invalid: > 10.0
        }

        response = self.client.post(
            "/animate", data=json.dumps(data), content_type="application/json"
        )

        assert response.status_code == 400
        result = json.loads(response.data)
        assert "error" in result

    def test_animate_endpoint_missing_data(self):
        """Test animation endpoint with missing JSON data."""
        response = self.client.post(
            "/animate", data="invalid json", content_type="application/json"
        )

        assert response.status_code == 400
        result = json.loads(response.data)
        assert "error" in result

    def test_animation_status_endpoint(self):
        """Test animation status endpoint."""
        # First trigger an animation
        data = {"expression": "sad", "intensity": 0.6, "duration": 1.5}

        self.client.post(
            "/animate", data=json.dumps(data), content_type="application/json"
        )

        # Then check status
        response = self.client.get("/animate/status")

        assert response.status_code == 200
        result = json.loads(response.data)
        assert "current_animation" in result
        assert result["current_animation"]["expression"] == "sad"

    def test_expression_validation(self):
        """Test various expression types."""
        expressions = ["happy", "sad", "angry", "surprised", "neutral", "speak"]

        for expression in expressions:
            data = {"expression": expression, "intensity": 0.7, "duration": 2.0}

            response = self.client.post(
                "/animate", data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 200
            result = json.loads(response.data)
            assert result["animation"]["expression"] == expression

    def test_default_parameters(self):
        """Test animation with default parameters."""
        data = {"expression": "neutral"}

        response = self.client.post(
            "/animate", data=json.dumps(data), content_type="application/json"
        )

        assert response.status_code == 200
        result = json.loads(response.data)
        assert result["animation"]["intensity"] == 0.5  # Default
        assert result["animation"]["duration"] == 1.0  # Default

    @pytest.mark.asyncio
    async def test_trigger_animation_function(self):
        """Test the async trigger_animation function."""
        with patch("aiohttp.ClientSession") as mock_session:
            # Mock successful response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = (
                mock_response
            )

            result = await trigger_animation("happy", 0.8, 2.0)
            assert result is True

    @pytest.mark.asyncio
    async def test_trigger_animation_function_failure(self):
        """Test the async trigger_animation function with failure."""
        with patch("aiohttp.ClientSession") as mock_session:
            # Mock failed response
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = (
                mock_response
            )

            result = await trigger_animation("happy", 0.8, 2.0)
            assert result is False

    @pytest.mark.asyncio
    async def test_trigger_animation_timeout(self):
        """Test the async trigger_animation function with timeout."""
        with patch("aiohttp.ClientSession") as mock_session:
            # Mock timeout
            mock_session.return_value.__aenter__.return_value.post.side_effect = (
                asyncio.TimeoutError()
            )

            result = await trigger_animation("happy", 0.8, 2.0)
            assert result is False


class TestAnimationParameterValidation:
    """Test cases for animation parameter validation."""

    def test_intensity_bounds(self):
        """Test intensity parameter bounds."""
        app = Live2DFlaskApp()
        client = app.get_app().test_client()

        # Test minimum bound
        data = {"expression": "happy", "intensity": -0.1, "duration": 2.0}
        response = client.post(
            "/animate", data=json.dumps(data), content_type="application/json"
        )
        assert response.status_code == 400

        # Test maximum bound
        data = {"expression": "happy", "intensity": 1.1, "duration": 2.0}
        response = client.post(
            "/animate", data=json.dumps(data), content_type="application/json"
        )
        assert response.status_code == 400

        # Test valid values
        for intensity in [0.0, 0.5, 1.0]:
            data = {"expression": "happy", "intensity": intensity, "duration": 2.0}
            response = client.post(
                "/animate", data=json.dumps(data), content_type="application/json"
            )
            assert response.status_code == 200

    def test_duration_bounds(self):
        """Test duration parameter bounds."""
        app = Live2DFlaskApp()
        client = app.get_app().test_client()

        # Test minimum bound
        data = {"expression": "happy", "intensity": 0.5, "duration": 0.05}
        response = client.post(
            "/animate", data=json.dumps(data), content_type="application/json"
        )
        assert response.status_code == 400

        # Test maximum bound
        data = {"expression": "happy", "intensity": 0.5, "duration": 15.0}
        response = client.post(
            "/animate", data=json.dumps(data), content_type="application/json"
        )
        assert response.status_code == 400

        # Test valid values
        for duration in [0.1, 2.0, 10.0]:
            data = {"expression": "happy", "intensity": 0.5, "duration": duration}
            response = client.post(
                "/animate", data=json.dumps(data), content_type="application/json"
            )
            assert response.status_code == 200


class TestAnimationStateTracking:
    """Test cases for animation state tracking."""

    def setup_method(self):
        """Set up test fixtures."""
        self.flask_app = Live2DFlaskApp()
        self.app = self.flask_app.get_app()
        self.client = self.app.test_client()

    def test_animation_state_updates(self):
        """Test that animation state is properly tracked."""
        # Initial state should be neutral
        response = self.client.get("/animate/status")
        result = json.loads(response.data)
        initial_timestamp = result["current_animation"]["timestamp"]

        # Trigger animation
        data = {"expression": "happy", "intensity": 0.8, "duration": 2.0}
        self.client.post(
            "/animate", data=json.dumps(data), content_type="application/json"
        )

        # Check updated state
        response = self.client.get("/animate/status")
        result = json.loads(response.data)

        assert result["current_animation"]["expression"] == "happy"
        assert result["current_animation"]["intensity"] == 0.8
        assert result["current_animation"]["duration"] == 2.0
        assert result["current_animation"]["timestamp"] != initial_timestamp

    def test_multiple_animation_updates(self):
        """Test multiple animation state updates."""
        expressions = ["happy", "sad", "angry", "neutral"]

        for i, expression in enumerate(expressions):
            data = {
                "expression": expression,
                "intensity": 0.5 + (i * 0.1),
                "duration": 1.0 + i,
            }

            self.client.post(
                "/animate", data=json.dumps(data), content_type="application/json"
            )

            response = self.client.get("/animate/status")
            result = json.loads(response.data)

            assert result["current_animation"]["expression"] == expression
            assert result["current_animation"]["intensity"] == 0.5 + (i * 0.1)


class TestAnimationIntegration:
    """Integration tests for the complete animation system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.flask_app = Live2DFlaskApp()
        self.app = self.flask_app.get_app()
        self.client = self.app.test_client()

    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200

        result = json.loads(response.data)
        assert result["status"] == "healthy"
        assert "timestamp" in result
        assert "version" in result

    def test_static_file_serving(self):
        """Test static file serving for Live2D assets."""
        # Test model file access
        response = self.client.get("/static/models/Poblanc.model3.json")
        # Note: This might return 404 if file doesn't exist, which is expected in test environment
        assert response.status_code in [200, 404]

    def test_main_page_rendering(self):
        """Test main page rendering."""
        with patch("src.config.settings.get_settings") as mock_settings:
            # Mock settings
            mock_settings.return_value.livekit.url = "wss://test.livekit.cloud"
            mock_settings.return_value.live2d.model_url = (
                "/static/models/test.model3.json"
            )

            response = self.client.get("/")
            assert response.status_code == 200
            assert b"Live2D Interactive Experience" in response.data

    def test_error_handling(self):
        """Test error handling for various scenarios."""
        # Test 404 for non-existent endpoint
        response = self.client.get("/nonexistent")
        assert response.status_code == 404

        # Test invalid JSON
        response = self.client.post(
            "/animate", data="invalid", content_type="application/json"
        )
        assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
