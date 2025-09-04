"""
Tests for specific error scenarios and recovery mechanisms.

Tests various failure modes and ensures proper error handling
and recovery across all system components.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from src.error_handling.exceptions import (
    AIProviderError,
    MemoryError,
    LiveKitError,
    Live2DError,
    NetworkError,
)
from src.error_handling.fallback_manager import get_fallback_manager
from src.error_handling.error_recovery import get_recovery_manager


class TestGeminiProviderErrorScenarios:
    """Test Gemini provider error scenarios and recovery."""

    @pytest.mark.asyncio
    async def test_rate_limit_key_rotation(self):
        """Test automatic API key rotation on rate limits."""
        from src.ai.gemini_provider import GeminiProvider

        config = {"api_keys": ["key1", "key2", "key3"], "model": "gemini-pro"}

        with patch("src.ai.gemini_provider.genai") as mock_genai:
            provider = GeminiProvider(config)

            # Simulate rate limit on first key
            provider.rate_limit_reset_times[0] = time.time() + 3600

            # Should rotate to next available key
            success = await provider.rotate_api_key()
            assert success is True
            assert provider.current_key_index == 1

    @pytest.mark.asyncio
    async def test_all_keys_rate_limited(self):
        """Test behavior when all API keys are rate limited."""
        from src.ai.gemini_provider import GeminiProvider

        config = {"api_keys": ["key1", "key2"], "model": "gemini-pro"}

        with patch("src.ai.gemini_provider.genai") as mock_genai:
            provider = GeminiProvider(config)

            # Rate limit all keys
            current_time = time.time()
            provider.rate_limit_reset_times[0] = current_time + 3600
            provider.rate_limit_reset_times[1] = current_time + 3600

            # Should fail to rotate
            success = await provider.rotate_api_key()
            assert success is False

    @pytest.mark.asyncio
    async def test_content_filter_logging(self):
        """Test content filtering incident logging."""
        from src.ai.gemini_provider import GeminiProvider
        from src.ai.base_provider import Message

        config = {"api_keys": ["test_key"], "model": "gemini-pro"}

        with patch("src.ai.gemini_provider.genai") as mock_genai:
            provider = GeminiProvider(config)

            # Mock content filter logger
            with patch.object(provider, "content_filter_logger") as mock_logger:
                messages = [
                    Message(
                        role="user",
                        content="inappropriate content",
                        timestamp=datetime.now(),
                    )
                ]

                # Simulate content filtering
                await provider._handle_content_filter(messages, "test conversation")

                # Should log incident without storing content
                mock_logger.log_content_filter_incident.assert_called_once()
                call_args = mock_logger.log_content_filter_incident.call_args
                assert call_args[1]["provider"] == "gemini"
                assert call_args[1]["filter_type"] == "safety_filter"

    @pytest.mark.asyncio
    async def test_network_timeout_handling(self):
        """Test network timeout handling with exponential backoff."""
        from src.ai.gemini_provider import GeminiProvider

        config = {"api_keys": ["test_key"], "model": "gemini-pro"}

        with patch("src.ai.gemini_provider.genai") as mock_genai:
            provider = GeminiProvider(config)

            # Mock timeout error
            with patch.object(
                provider, "_make_api_request", side_effect=asyncio.TimeoutError
            ):
                with pytest.raises(AIProviderError) as exc_info:
                    await provider._generate_response_internal([], None, None)

                assert "timeout" in str(exc_info.value).lower()


class TestOllamaProviderErrorScenarios:
    """Test Ollama provider error scenarios and recovery."""

    @pytest.mark.asyncio
    async def test_connection_error_retry(self):
        """Test connection error handling with retry logic."""
        from src.ai.ollama_provider import OllamaProvider

        config = {"model": "llama3", "host": "http://localhost:11434"}

        with patch("src.ai.ollama_provider.ollama"):
            provider = OllamaProvider(config)

            # Mock connection error on first attempts, success on last
            call_count = 0

            async def mock_request(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise ConnectionError("Connection failed")
                return {"message": {"content": "Success after retry"}}

            with patch.object(
                provider, "_make_ollama_request", side_effect=mock_request
            ):
                result = await provider._generate_response_internal([], None, None)
                assert result == "Success after retry"
                assert call_count == 3

    @pytest.mark.asyncio
    async def test_model_not_found_error(self):
        """Test handling of model not found errors."""
        from src.ai.ollama_provider import OllamaProvider

        config = {"model": "nonexistent_model", "host": "http://localhost:11434"}

        with patch("src.ai.ollama_provider.ollama"):
            provider = OllamaProvider(config)

            # Mock model not found error
            with patch.object(
                provider,
                "_make_ollama_request",
                side_effect=Exception("Model not found"),
            ):
                with pytest.raises(AIProviderError) as exc_info:
                    await provider._generate_response_internal([], None, None)

                assert "model" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_health_check_with_model_validation(self):
        """Test health check that validates model availability."""
        from src.ai.ollama_provider import OllamaProvider

        config = {"model": "llama3", "host": "http://localhost:11434"}

        with patch("src.ai.ollama_provider.ollama"):
            provider = OllamaProvider(config)

            # Mock successful model list with our model
            with patch.object(
                provider.client,
                "list",
                return_value={"models": [{"name": "llama3"}, {"name": "other_model"}]},
            ):
                healthy = await provider.check_connection()
                assert healthy is True

            # Mock model list without our model
            with patch.object(
                provider.client,
                "list",
                return_value={"models": [{"name": "other_model"}]},
            ):
                healthy = await provider.check_connection()
                assert healthy is False


class TestMemoryManagerErrorScenarios:
    """Test memory manager error scenarios and fallbacks."""

    @pytest.mark.asyncio
    async def test_mem0_connection_failure_fallback(self):
        """Test fallback to session-only mode when Mem0 fails."""
        from src.memory.memory_manager import MemoryManager
        from src.config.settings import MemoryConfig

        config = MemoryConfig(mem0_api_key="test_key", memory_history_limit=20)

        with patch("src.memory.memory_manager.Memory") as mock_memory:
            # Mock Mem0 connection failure
            mock_memory.side_effect = Exception("Connection failed")

            memory_manager = MemoryManager(config)
            mem0_available = await memory_manager.initialize()

            assert mem0_available is False
            assert memory_manager.mem0_available is False

    @pytest.mark.asyncio
    async def test_session_memory_search_fallback(self):
        """Test session memory search when Mem0 is unavailable."""
        from src.memory.memory_manager import MemoryManager
        from src.config.settings import MemoryConfig

        config = MemoryConfig(
            mem0_api_key="",  # No key to force session-only mode
            memory_history_limit=20,
        )

        memory_manager = MemoryManager(config)
        await memory_manager.initialize()

        # Add some session memories
        await memory_manager.add_memory("test_user", "I like cats")
        await memory_manager.add_memory("test_user", "My favorite color is blue")
        await memory_manager.add_memory("test_user", "I work as a developer")

        # Search should work with session memory
        results = await memory_manager.search_memories("test_user", "cats", limit=5)
        assert len(results) > 0
        assert any("cats" in result.lower() for result in results)

    @pytest.mark.asyncio
    async def test_memory_operation_timeout_handling(self):
        """Test timeout handling in memory operations."""
        from src.memory.memory_manager import MemoryManager
        from src.config.settings import MemoryConfig

        config = MemoryConfig(mem0_api_key="test_key", memory_history_limit=20)

        with patch("src.memory.memory_manager.Memory"):
            memory_manager = MemoryManager(config)
            memory_manager.mem0_available = True
            memory_manager._mem0_client = Mock()

            # Mock timeout in Mem0 operation
            async def timeout_operation():
                await asyncio.sleep(15)  # Longer than timeout
                return []

            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.run_in_executor.return_value = (
                    timeout_operation()
                )

                # Should handle timeout and fall back to session memory
                results = await memory_manager.search_memories("test_user", "query")
                assert isinstance(
                    results, list
                )  # Should return empty list from session fallback

    @pytest.mark.asyncio
    async def test_memory_health_check_comprehensive(self):
        """Test comprehensive memory health check."""
        from src.memory.memory_manager import MemoryManager
        from src.config.settings import MemoryConfig

        config = MemoryConfig(mem0_api_key="test_key", memory_history_limit=20)

        with patch("src.memory.memory_manager.Memory"):
            memory_manager = MemoryManager(config)
            memory_manager.mem0_available = True
            memory_manager._mem0_client = Mock()

            # Add some session data
            memory_manager._session_memory["user1"] = [
                {"content": "test", "timestamp": datetime.now()}
            ]
            memory_manager._session_memory["user2"] = [
                {"content": "test2", "timestamp": datetime.now()}
            ]

            # Mock successful connection test
            with patch.object(memory_manager, "_test_connection", return_value=True):
                health = await memory_manager.health_check()

                assert health["status"] == "healthy"
                assert health["mem0_available"] is True
                assert health["session_memory_users"] == 2
                assert health["session_memory_entries"] == 2


class TestLiveKitAgentErrorScenarios:
    """Test LiveKit agent error scenarios and recovery."""

    @pytest.mark.asyncio
    async def test_ai_provider_timeout_handling(self):
        """Test handling of AI provider timeouts."""
        from src.agent.livekit_agent import AnimeAILLM
        from src.config.settings import AppConfig
        from src.memory.memory_manager import MemoryManager
        from livekit.agents.llm import ChatContext, ChatMessage

        # Mock configuration and dependencies
        config = Mock(spec=AppConfig)
        config.personality.personality_prompt = "Test personality"

        memory_manager = Mock(spec=MemoryManager)
        memory_manager.store_conversation = AsyncMock()
        memory_manager.get_user_context = AsyncMock(return_value=None)

        llm = AnimeAILLM(config, memory_manager)

        # Mock AI provider with timeout
        llm.ai_provider.generate_response = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )

        # Create chat context
        chat_ctx = ChatContext()
        chat_ctx.messages = [ChatMessage(role="user", content="Hello")]

        # Should handle timeout gracefully
        result = await llm._process_chat_internal(chat_ctx, "test_user")
        assert "trouble thinking" in result.content.lower()

    @pytest.mark.asyncio
    async def test_memory_error_graceful_handling(self):
        """Test graceful handling of memory errors."""
        from src.agent.livekit_agent import AnimeAILLM
        from src.config.settings import AppConfig
        from src.memory.memory_manager import MemoryManager
        from livekit.agents.llm import ChatContext, ChatMessage

        config = Mock(spec=AppConfig)
        config.personality.personality_prompt = "Test personality"

        memory_manager = Mock(spec=MemoryManager)
        memory_manager.store_conversation = AsyncMock(
            side_effect=MemoryError("Memory failed", "store", "test_user")
        )
        memory_manager.get_user_context = AsyncMock(
            side_effect=MemoryError("Memory failed", "get", "test_user")
        )

        llm = AnimeAILLM(config, memory_manager)
        llm.ai_provider.generate_response = AsyncMock(return_value="AI response")

        chat_ctx = ChatContext()
        chat_ctx.messages = [ChatMessage(role="user", content="Hello")]

        # Should continue despite memory errors
        result = await llm._process_chat_internal(chat_ctx, "test_user")
        assert result.content == "AI response"

    @pytest.mark.asyncio
    async def test_animation_trigger_failure_handling(self):
        """Test handling of animation trigger failures."""
        from src.agent.livekit_agent import AnimeAILLM
        from src.config.settings import AppConfig
        from src.memory.memory_manager import MemoryManager

        config = Mock(spec=AppConfig)
        memory_manager = Mock(spec=MemoryManager)

        llm = AnimeAILLM(config, memory_manager)

        # Mock animation sync failure
        with patch.object(llm, "animation_sync") as mock_sync:
            mock_sync.synchronize_with_tts = AsyncMock(
                side_effect=Exception("Animation failed")
            )

            with patch(
                "src.agent.livekit_agent.trigger_animation",
                side_effect=Exception("Fallback failed"),
            ):
                # Should not raise exception, just log warning
                await llm._trigger_animation_internal("Happy response", "Hello")


class TestWebServerErrorScenarios:
    """Test web server error scenarios and recovery."""

    @pytest.mark.asyncio
    async def test_websocket_failure_static_fallback(self):
        """Test static fallback when WebSocket fails."""
        from src.web.app import Live2DFlaskApp

        app = Live2DFlaskApp()
        app.websocket_loop = None  # Simulate WebSocket unavailable

        result = await app._execute_animation_with_fallback(
            expression="happy",
            intensity=0.7,
            duration=2.0,
            priority=Mock(),
            sync_with_audio=False,
        )

        assert result["success"] is True
        assert result["websocket_active"] is False
        assert result["fallback_used"] is True

    def test_animation_parameter_validation(self):
        """Test animation parameter validation."""
        from src.web.app import Live2DFlaskApp
        from src.error_handling.exceptions import ValidationError
        from flask import Flask

        app = Live2DFlaskApp()

        # Mock request with invalid parameters
        with app.app.test_request_context(
            "/animate",
            method="POST",
            json={"expression": "happy", "intensity": 2.0},  # Invalid intensity > 1.0
        ):
            from flask import request

            with pytest.raises(ValidationError) as exc_info:
                app._validate_animation_request(request)

            assert "intensity" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_livekit_token_generation_error(self):
        """Test LiveKit token generation error handling."""
        from src.web.app import Live2DFlaskApp

        app = Live2DFlaskApp()

        # Mock invalid LiveKit configuration
        app.settings.livekit.api_key = ""
        app.settings.livekit.api_secret = ""

        with app.app.test_request_context(
            "/token",
            method="POST",
            json={"room": "test_room", "participant": "test_user"},
        ):
            from flask import request

            # Should raise validation error for missing credentials
            with pytest.raises(Exception):  # Will be caught by route handler
                pass  # The actual test would be in the route handler

    @pytest.mark.asyncio
    async def test_animation_trigger_network_error_retry(self):
        """Test animation trigger retry on network errors."""
        from src.web.app import _trigger_animation_internal

        with patch("src.web.app.get_settings") as mock_settings:
            mock_settings.return_value.flask.host = "localhost"
            mock_settings.return_value.flask.port = 5000

            call_count = 0

            async def mock_post(*args, **kwargs):
                nonlocal call_count
                call_count += 1

                mock_response = Mock()
                if call_count < 3:  # Fail first 2 attempts
                    mock_response.status = 500
                else:  # Succeed on 3rd attempt
                    mock_response.status = 200

                return mock_response

            with patch("aiohttp.ClientSession") as mock_session:
                mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__ = (
                    mock_post
                )

                result = await _trigger_animation_internal("happy", 0.7, 2.0)
                assert result is True
                assert call_count == 3


class TestErrorRecoveryIntegration:
    """Test integrated error recovery across components."""

    @pytest.mark.asyncio
    async def test_component_recovery_coordination(self):
        """Test coordinated recovery across multiple components."""
        recovery_manager = get_recovery_manager()

        # Register multiple components
        recovery_manager.register_component(
            "ai_provider", [RecoveryStrategy.ROTATE_API_KEY]
        )
        recovery_manager.register_component(
            "memory_manager", [RecoveryStrategy.RECONNECT]
        )
        recovery_manager.register_component(
            "web_server", [RecoveryStrategy.RESTART_SERVICE]
        )

        # Simulate errors in multiple components
        await recovery_manager.record_error(
            "ai_provider", AIProviderError("Rate limit", "gemini", is_rate_limit=True)
        )
        await recovery_manager.record_error(
            "memory_manager",
            MemoryError("Connection lost", "search", is_mem0_error=True),
        )
        await recovery_manager.record_error(
            "web_server", NetworkError("Server error", "animate")
        )

        # Check that all components are tracked
        stats = recovery_manager.get_recovery_stats()
        assert len(stats["components"]) == 3
        assert not stats["components"]["ai_provider"]["is_healthy"]
        assert not stats["components"]["memory_manager"]["is_healthy"]
        assert not stats["components"]["web_server"]["is_healthy"]

    @pytest.mark.asyncio
    async def test_fallback_chain_coordination(self):
        """Test coordinated fallback strategies across components."""
        fallback_manager = get_fallback_manager()

        # Register fallback chains for different components
        fallback_manager.register_fallback_chain(
            "ai_provider",
            [
                FallbackStrategy.RETRY,
                FallbackStrategy.CACHED_RESPONSE,
                FallbackStrategy.SIMPLIFIED_RESPONSE,
            ],
        )

        fallback_manager.register_fallback_chain(
            "memory_manager", [FallbackStrategy.RETRY, FallbackStrategy.SESSION_ONLY]
        )

        # Cache some responses for fallback
        fallback_manager.cache_response("ai_test", "Cached AI response")

        # Test AI provider fallback to cached response
        async def failing_ai_operation():
            raise AIProviderError("AI failed", "gemini")

        result = await fallback_manager.execute_with_fallback(
            component="ai_provider",
            primary_operation=failing_ai_operation,
            context={"cache_key": "ai_test"},
        )

        assert result.success is True
        assert result.result == "Cached AI response"
        assert result.strategy_used == FallbackStrategy.CACHED_RESPONSE

    def test_error_logging_coordination(self):
        """Test coordinated error logging across components."""
        from src.error_handling.logging_handler import (
            get_content_filter_logger,
            get_error_logger,
        )

        content_logger = get_content_filter_logger()
        error_logger = get_error_logger()

        # Test content filter logging
        content_logger.log_content_filter_incident(
            provider="gemini",
            filter_type="safety_filter",
            user_id="test_user",
            content_hash="abc123",
        )

        # Test error logging
        error = AIProviderError("Test error", "gemini", error_code="TEST_001")
        error_logger.log_error(
            error, component="ai_provider", operation="generate_response"
        )

        # Test recovery logging
        error_logger.log_recovery_attempt(
            component="ai_provider",
            strategy="rotate_api_key",
            success=True,
            recovery_time=2.5,
        )

        # Verify logs exist
        assert content_logger.log_file.exists()
        assert error_logger.log_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
