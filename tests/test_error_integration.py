"""
Integration tests for comprehensive error handling system.

Tests the complete error handling workflow including detection,
recovery, fallback, and logging across all system components.
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
    ContentFilterError,
    NetworkError,
)
from src.error_handling.fallback_manager import get_fallback_manager, FallbackStrategy
from src.error_handling.error_recovery import get_recovery_manager, RecoveryStrategy
from src.error_handling.logging_handler import (
    get_content_filter_logger,
    get_error_logger,
)


class TestCompleteErrorHandlingWorkflow:
    """Test complete error handling workflow from detection to recovery."""

    @pytest.mark.asyncio
    async def test_ai_provider_complete_failure_recovery(self):
        """Test complete AI provider failure and recovery workflow."""
        # Setup components
        fallback_manager = get_fallback_manager()
        recovery_manager = get_recovery_manager()
        error_logger = get_error_logger()

        # Register AI provider for recovery
        recovery_manager.register_component(
            "ai_provider_test",
            [RecoveryStrategy.ROTATE_API_KEY, RecoveryStrategy.WAIT_AND_RETRY],
            health_check_func=lambda: True,
        )

        # Register fallback chain
        fallback_manager.register_fallback_chain(
            "ai_provider_test",
            [
                FallbackStrategy.RETRY,
                FallbackStrategy.CACHED_RESPONSE,
                FallbackStrategy.ERROR_MESSAGE,
            ],
        )

        # Cache a fallback response
        fallback_manager.cache_response(
            "test_cache_key", "Cached response for fallback"
        )

        # Simulate AI provider failure
        failure_count = 0

        async def failing_ai_operation():
            nonlocal failure_count
            failure_count += 1
            if failure_count <= 2:
                # First two attempts fail with rate limit
                raise AIProviderError(
                    "Rate limit exceeded", provider="gemini", is_rate_limit=True
                )
            else:
                # Third attempt succeeds
                return "AI response after recovery"

        # Execute with fallback
        result = await fallback_manager.execute_with_fallback(
            component="ai_provider_test",
            primary_operation=failing_ai_operation,
            context={
                "retry_operation": failing_ai_operation,
                "max_retries": 3,
                "base_delay": 0.01,  # Fast for testing
                "cache_key": "test_cache_key",
            },
        )

        # Should succeed after retry
        assert result.success is True
        assert result.result == "AI response after recovery"
        assert result.strategy_used == FallbackStrategy.RETRY
        assert failure_count == 3

    @pytest.mark.asyncio
    async def test_memory_service_degradation_and_fallback(self):
        """Test memory service degradation and fallback to session-only mode."""
        from src.memory.memory_manager import MemoryManager
        from src.config.settings import MemoryConfig

        # Create memory manager with Mem0 configured
        config = MemoryConfig(mem0_api_key="test_key", memory_history_limit=20)

        with patch("src.memory.memory_manager.Memory") as mock_memory_class:
            # Mock Mem0 client that fails after initialization
            mock_client = Mock()
            mock_memory_class.return_value = mock_client

            memory_manager = MemoryManager(config)

            # Initialize successfully
            with patch.object(memory_manager, "_test_connection", return_value=True):
                mem0_available = await memory_manager.initialize()
                assert mem0_available is True

            # Simulate Mem0 service failure during operation
            async def failing_mem0_operation(*args, **kwargs):
                raise Exception("Mem0 service unavailable")

            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.run_in_executor.side_effect = (
                    failing_mem0_operation
                )

                # Should fall back to session memory
                success = await memory_manager.add_memory("test_user", "test memory")
                assert success is True  # Session fallback succeeds

                # Search should also work with session fallback
                results = await memory_manager.search_memories("test_user", "test")
                assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_livekit_connection_failure_and_recovery(self):
        """Test LiveKit connection failure and automatic recovery."""
        from src.agent.livekit_agent import AnimeAILLM
        from src.config.settings import AppConfig
        from src.memory.memory_manager import MemoryManager
        from livekit.agents.llm import ChatContext, ChatMessage

        # Mock configuration
        config = Mock(spec=AppConfig)
        config.personality.personality_prompt = "Test personality"

        memory_manager = Mock(spec=MemoryManager)
        memory_manager.store_conversation = AsyncMock()
        memory_manager.get_user_context = AsyncMock(return_value=None)

        llm = AnimeAILLM(config, memory_manager)

        # Register for recovery
        recovery_manager = get_recovery_manager()
        recovery_manager.register_component(
            "livekit_test",
            [RecoveryStrategy.RECONNECT, RecoveryStrategy.WAIT_AND_RETRY],
        )

        # Simulate connection failure then recovery
        connection_attempts = 0

        async def mock_ai_response(*args, **kwargs):
            nonlocal connection_attempts
            connection_attempts += 1
            if connection_attempts <= 2:
                raise LiveKitError(
                    "Connection lost",
                    operation="generate_response",
                    is_connection_error=True,
                )
            return "Response after reconnection"

        llm.ai_provider.generate_response = mock_ai_response

        # Create chat context
        chat_ctx = ChatContext()
        chat_ctx.messages = [ChatMessage(role="user", content="Hello")]

        # Should recover and succeed
        result = await llm._process_chat_internal(chat_ctx, "test_user")
        assert result.content == "Response after reconnection"
        assert connection_attempts == 3

    @pytest.mark.asyncio
    async def test_live2d_animation_failure_static_fallback(self):
        """Test Live2D animation failure with static fallback."""
        from src.web.app import Live2DFlaskApp

        app = Live2DFlaskApp()

        # Mock WebSocket failure
        app.websocket_loop = Mock()
        app.websocket_loop.is_closed.return_value = False

        # Mock animation sync failure
        async def failing_animation(*args, **kwargs):
            raise Live2DError(
                "Animation system failure",
                operation="trigger_animation",
                animation_type="happy",
                is_rendering_error=True,
            )

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            mock_future = Mock()
            mock_future.result.side_effect = failing_animation
            mock_run.return_value = mock_future

            # Should fall back to static response
            result = await app._execute_animation_with_fallback(
                expression="happy",
                intensity=0.7,
                duration=2.0,
                priority=Mock(),
                sync_with_audio=False,
            )

            assert result["success"] is True
            assert result["fallback_used"] is True
            assert result["websocket_healthy"] is False

    @pytest.mark.asyncio
    async def test_content_filtering_incident_complete_workflow(self):
        """Test complete content filtering incident workflow."""
        from src.ai.gemini_provider import GeminiProvider
        from src.ai.base_provider import Message

        config = {"api_keys": ["test_key"], "model": "gemini-pro"}

        with patch("src.ai.gemini_provider.genai") as mock_genai:
            provider = GeminiProvider(config)

            # Mock content filter logger
            content_logger = get_content_filter_logger()
            error_logger = get_error_logger()

            # Simulate content filtering
            messages = [
                Message(
                    role="user",
                    content="inappropriate content that should be filtered",
                    timestamp=datetime.now(),
                )
            ]

            with patch.object(provider, "content_filter_logger", content_logger):
                with patch.object(provider, "error_logger", error_logger):
                    await provider._handle_content_filter(
                        messages, "conversation context"
                    )

            # Verify incident was logged without storing inappropriate content
            assert content_logger.log_file.exists()

            with open(content_logger.log_file, "r") as f:
                log_content = f.read()
                assert "Content filter triggered" in log_content
                assert "gemini" in log_content
                # Ensure inappropriate content is not stored
                assert (
                    "inappropriate content that should be filtered" not in log_content
                )

    @pytest.mark.asyncio
    async def test_cascading_failure_recovery(self):
        """Test recovery from cascading failures across multiple components."""
        fallback_manager = get_fallback_manager()
        recovery_manager = get_recovery_manager()

        # Register multiple components
        components = ["ai_provider", "memory_manager", "animation_system"]
        for component in components:
            recovery_manager.register_component(
                component,
                [RecoveryStrategy.WAIT_AND_RETRY, RecoveryStrategy.REINITIALIZE],
            )
            fallback_manager.register_fallback_chain(
                component,
                [FallbackStrategy.RETRY, FallbackStrategy.SIMPLIFIED_RESPONSE],
            )

        # Simulate cascading failures
        errors = [
            AIProviderError("AI service down", "gemini"),
            MemoryError("Memory service down", "search", is_mem0_error=True),
            Live2DError("Animation service down", "render", is_rendering_error=True),
        ]

        # Record errors for all components
        for i, component in enumerate(components):
            for _ in range(3):  # Trigger recovery threshold
                await recovery_manager.record_error(component, errors[i])

        # Check that all components are marked unhealthy
        stats = recovery_manager.get_recovery_stats()
        for component in components:
            assert not stats["components"][component]["is_healthy"]
            assert stats["components"][component]["consecutive_failures"] >= 3

        # Simulate recovery for all components
        for component in components:
            await recovery_manager.record_success(component)

        # Check that all components are now healthy
        stats = recovery_manager.get_recovery_stats()
        for component in components:
            assert stats["components"][component]["is_healthy"]
            assert stats["components"][component]["consecutive_failures"] == 0

    @pytest.mark.asyncio
    async def test_error_rate_limiting_and_circuit_breaker(self):
        """Test error rate limiting and circuit breaker functionality."""
        recovery_manager = get_recovery_manager()

        # Register component with short cooldown for testing
        recovery_manager.recovery_cooldown = timedelta(seconds=1)
        recovery_manager.register_component(
            "rate_limited_component", [RecoveryStrategy.WAIT_AND_RETRY]
        )

        # Trigger multiple errors rapidly
        component_health = recovery_manager._component_health["rate_limited_component"]

        # First recovery attempt
        for _ in range(3):
            await recovery_manager.record_error(
                "rate_limited_component", Exception("Error")
            )

        assert component_health.last_recovery_attempt is not None
        first_attempt_time = component_health.last_recovery_attempt

        # Immediate second attempt should be blocked by cooldown
        for _ in range(3):
            await recovery_manager.record_error(
                "rate_limited_component", Exception("Error")
            )

        # Should not have updated recovery attempt time due to cooldown
        assert component_health.last_recovery_attempt == first_attempt_time

        # Wait for cooldown to expire
        await asyncio.sleep(1.1)

        # Now recovery should be attempted again
        for _ in range(3):
            await recovery_manager.record_error(
                "rate_limited_component", Exception("Error")
            )

        assert component_health.last_recovery_attempt > first_attempt_time

    def test_comprehensive_health_monitoring(self):
        """Test comprehensive health monitoring across all components."""
        recovery_manager = get_recovery_manager()
        fallback_manager = get_fallback_manager()

        # Register multiple components with different health states
        components_config = {
            "healthy_component": (True, 0),
            "degraded_component": (False, 2),
            "unhealthy_component": (False, 10),
        }

        for component, (healthy, failures) in components_config.items():
            recovery_manager.register_component(
                component, [RecoveryStrategy.WAIT_AND_RETRY]
            )

            health = recovery_manager._component_health[component]
            health.is_healthy = healthy
            health.consecutive_failures = failures
            if not healthy:
                health.last_error = Exception(f"Error in {component}")

        # Get comprehensive stats
        recovery_stats = recovery_manager.get_recovery_stats()
        fallback_stats = fallback_manager.get_fallback_stats()

        # Verify health monitoring
        assert recovery_stats["monitored_components"] == 3
        assert recovery_stats["components"]["healthy_component"]["is_healthy"] is True
        assert recovery_stats["components"]["degraded_component"]["is_healthy"] is False
        assert (
            recovery_stats["components"]["unhealthy_component"]["consecutive_failures"]
            == 10
        )

        # Verify fallback system is ready
        assert len(fallback_stats["available_strategies"]) > 0

    @pytest.mark.asyncio
    async def test_error_logging_and_monitoring_integration(self):
        """Test integrated error logging and monitoring."""
        content_logger = get_content_filter_logger()
        error_logger = get_error_logger()

        # Log various types of incidents

        # Content filter incident
        content_logger.log_content_filter_incident(
            provider="gemini",
            filter_type="safety_filter",
            user_id="user123",
            content_hash="abc123def456",
            metadata={"message_length": 150, "severity": "high"},
        )

        # System error
        ai_error = AIProviderError(
            "Rate limit exceeded",
            provider="gemini",
            is_rate_limit=True,
            error_code="RATE_LIMIT_001",
        )

        error_logger.log_error(
            ai_error,
            component="ai_provider",
            operation="generate_response",
            context={"model": "gemini-pro", "attempt": 3},
            user_id="user123",
        )

        # Recovery attempt
        error_logger.log_recovery_attempt(
            component="ai_provider",
            strategy="rotate_api_key",
            success=True,
            recovery_time=2.5,
            error=None,
        )

        # Fallback usage
        error_logger.log_fallback_usage(
            component="memory_manager",
            fallback_strategy="session_only",
            original_error=MemoryError("Mem0 unavailable", "search"),
            fallback_success=True,
        )

        # Verify all logs were created
        assert content_logger.log_file.exists()
        assert error_logger.log_file.exists()

        # Verify log contents (without exposing sensitive data)
        with open(content_logger.log_file, "r") as f:
            content_log = f.read()
            assert "Content filter triggered" in content_log
            assert "gemini" in content_log
            assert "abc123def456" in content_log  # Hash is safe to log

        with open(error_logger.log_file, "r") as f:
            error_log = f.read()
            assert "System error" in error_log
            assert "Recovery attempt" in error_log
            assert "Fallback used" in error_log
            assert "ai_provider" in error_log


class TestErrorHandlingPerformance:
    """Test error handling system performance under load."""

    @pytest.mark.asyncio
    async def test_concurrent_error_handling(self):
        """Test error handling under concurrent load."""
        fallback_manager = get_fallback_manager()
        recovery_manager = get_recovery_manager()

        # Register component
        recovery_manager.register_component(
            "concurrent_test", [RecoveryStrategy.WAIT_AND_RETRY]
        )

        fallback_manager.register_fallback_chain(
            "concurrent_test", [FallbackStrategy.RETRY, FallbackStrategy.ERROR_MESSAGE]
        )

        # Create multiple concurrent operations
        async def concurrent_operation(operation_id: int):
            try:
                if operation_id % 3 == 0:  # Every 3rd operation fails
                    raise Exception(f"Operation {operation_id} failed")
                return f"Success {operation_id}"
            except Exception as e:
                await recovery_manager.record_error("concurrent_test", e)
                raise

        # Run concurrent operations
        tasks = []
        for i in range(20):
            task = fallback_manager.execute_with_fallback(
                component="concurrent_test",
                primary_operation=lambda op_id=i: concurrent_operation(op_id),
                context={
                    "retry_operation": lambda op_id=i: concurrent_operation(op_id)
                },
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify results
        successful_results = [r for r in results if hasattr(r, "success") and r.success]
        assert len(successful_results) > 0

        # Check component health after concurrent load
        health = recovery_manager.get_component_health("concurrent_test")
        assert health is not None

    @pytest.mark.asyncio
    async def test_error_handling_memory_usage(self):
        """Test error handling system memory usage."""
        fallback_manager = get_fallback_manager()
        recovery_manager = get_recovery_manager()

        # Generate many errors to test memory management
        for i in range(100):
            component_name = f"test_component_{i % 10}"  # 10 different components

            if component_name not in recovery_manager._component_health:
                recovery_manager.register_component(
                    component_name, [RecoveryStrategy.WAIT_AND_RETRY]
                )

            await recovery_manager.record_error(component_name, Exception(f"Error {i}"))

        # Verify memory usage is reasonable
        stats = recovery_manager.get_recovery_stats()
        assert stats["monitored_components"] == 10  # Should only have 10 components

        # Test cache management in fallback manager
        for i in range(150):  # Exceed cache limit
            fallback_manager.cache_response(f"key_{i}", f"value_{i}")

        fallback_stats = fallback_manager.get_fallback_stats()
        assert fallback_stats["cache_size"] <= fallback_manager._max_cache_size

    def test_error_handling_startup_time(self):
        """Test error handling system startup performance."""
        start_time = time.time()

        # Initialize all error handling components
        fallback_manager = get_fallback_manager()
        recovery_manager = get_recovery_manager()
        content_logger = get_content_filter_logger()
        error_logger = get_error_logger()

        # Register multiple components
        for i in range(50):
            component_name = f"startup_test_{i}"
            recovery_manager.register_component(
                component_name,
                [RecoveryStrategy.WAIT_AND_RETRY, RecoveryStrategy.RECONNECT],
            )
            fallback_manager.register_fallback_chain(
                component_name,
                [FallbackStrategy.RETRY, FallbackStrategy.CACHED_RESPONSE],
            )

        startup_time = time.time() - start_time

        # Should start up quickly (less than 1 second for 50 components)
        assert startup_time < 1.0

        # Verify all components are registered
        stats = recovery_manager.get_recovery_stats()
        assert stats["monitored_components"] == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
