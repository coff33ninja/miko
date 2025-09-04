"""
Comprehensive tests for error handling and fallback mechanisms.

Tests all error scenarios, recovery mechanisms, and fallback strategies
for the Anime AI Character system.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from src.error_handling.exceptions import (
    AnimeAIError, AIProviderError, MemoryError, LiveKitError, 
    Live2DError, ContentFilterError, NetworkError, ValidationError
)
from src.error_handling.fallback_manager import (
    FallbackManager, FallbackStrategy, FallbackResult
)
from src.error_handling.error_recovery import (
    ErrorRecoveryManager, RecoveryStrategy, RecoveryResult, ComponentHealth
)
from src.error_handling.logging_handler import (
    ContentFilterLogger, ErrorLogger, setup_error_logging
)


class TestExceptions:
    """Test custom exception classes."""
    
    def test_anime_ai_error_basic(self):
        """Test basic AnimeAIError functionality."""
        error = AnimeAIError("Test error", error_code="TEST_001")
        
        assert str(error) == "Test error"
        assert error.error_code == "TEST_001"
        assert error.details == {}
        
        error_dict = error.to_dict()
        assert error_dict['error_type'] == 'AnimeAIError'
        assert error_dict['message'] == "Test error"
        assert error_dict['error_code'] == "TEST_001"
    
    def test_ai_provider_error(self):
        """Test AIProviderError with specific attributes."""
        error = AIProviderError(
            "Rate limit exceeded",
            provider="gemini",
            is_rate_limit=True,
            details={"retry_after": 3600}
        )
        
        assert error.provider == "gemini"
        assert error.is_rate_limit is True
        assert error.is_content_filter is False
        assert error.details["retry_after"] == 3600
    
    def test_memory_error(self):
        """Test MemoryError with operation context."""
        error = MemoryError(
            "Failed to connect to Mem0",
            operation="initialize",
            user_id="test_user",
            is_mem0_error=True
        )
        
        assert error.operation == "initialize"
        assert error.user_id == "test_user"
        assert error.is_mem0_error is True
    
    def test_livekit_error(self):
        """Test LiveKitError with connection context."""
        error = LiveKitError(
            "Connection lost",
            operation="join_room",
            room_name="test_room",
            participant_id="user123",
            is_connection_error=True
        )
        
        assert error.operation == "join_room"
        assert error.room_name == "test_room"
        assert error.participant_id == "user123"
        assert error.is_connection_error is True
    
    def test_content_filter_error(self):
        """Test ContentFilterError without storing content."""
        error = ContentFilterError(
            "Content blocked",
            provider="gemini",
            filter_type="safety_filter",
            user_id="user123"
        )
        
        assert error.provider == "gemini"
        assert error.filter_type == "safety_filter"
        assert error.user_id == "user123"
        # Ensure no inappropriate content is stored
        assert "inappropriate" not in str(error.details)


class TestFallbackManager:
    """Test fallback management system."""
    
    @pytest.fixture
    def fallback_manager(self):
        """Create fallback manager for testing."""
        return FallbackManager()
    
    def test_register_fallback_chain(self, fallback_manager):
        """Test registering fallback chains."""
        strategies = [FallbackStrategy.RETRY, FallbackStrategy.CACHED_RESPONSE]
        fallback_manager.register_fallback_chain("test_component", strategies)
        
        assert "test_component" in fallback_manager._fallback_strategies
        assert fallback_manager._fallback_strategies["test_component"] == strategies
    
    @pytest.mark.asyncio
    async def test_successful_primary_operation(self, fallback_manager):
        """Test successful primary operation without fallback."""
        async def successful_operation():
            return "success"
        
        result = await fallback_manager.execute_with_fallback(
            component="test",
            primary_operation=successful_operation
        )
        
        assert result.success is True
        assert result.result == "success"
        assert result.strategy_used is None
        assert "primary" in result.fallback_chain
    
    @pytest.mark.asyncio
    async def test_fallback_to_error_message(self, fallback_manager):
        """Test fallback to error message when primary fails."""
        async def failing_operation():
            raise Exception("Primary failed")
        
        fallback_manager.register_fallback_chain(
            "test", [FallbackStrategy.ERROR_MESSAGE]
        )
        
        result = await fallback_manager.execute_with_fallback(
            component="test",
            primary_operation=failing_operation
        )
        
        assert result.success is True
        assert result.strategy_used == FallbackStrategy.ERROR_MESSAGE
        assert isinstance(result.result, dict)
        assert result.result["error"] is True
    
    @pytest.mark.asyncio
    async def test_cached_response_fallback(self, fallback_manager):
        """Test cached response fallback."""
        # Cache a response
        fallback_manager.cache_response("test_key", "cached_result")
        
        async def failing_operation():
            raise Exception("Primary failed")
        
        fallback_manager.register_fallback_chain(
            "test", [FallbackStrategy.CACHED_RESPONSE]
        )
        
        result = await fallback_manager.execute_with_fallback(
            component="test",
            primary_operation=failing_operation,
            context={"cache_key": "test_key"}
        )
        
        assert result.success is True
        assert result.result == "cached_result"
        assert result.strategy_used == FallbackStrategy.CACHED_RESPONSE
    
    @pytest.mark.asyncio
    async def test_retry_fallback(self, fallback_manager):
        """Test retry fallback strategy."""
        call_count = 0
        
        async def retry_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Retry needed")
            return "success_after_retry"
        
        fallback_manager.register_fallback_chain(
            "test", [FallbackStrategy.RETRY]
        )
        
        result = await fallback_manager.execute_with_fallback(
            component="test",
            primary_operation=lambda: None,  # This will fail
            context={
                "retry_operation": retry_operation,
                "max_retries": 3,
                "base_delay": 0.01  # Fast for testing
            }
        )
        
        assert result.success is True
        assert result.result == "success_after_retry"
        assert call_count == 3
    
    def test_cache_management(self, fallback_manager):
        """Test response cache management."""
        # Test caching
        fallback_manager.cache_response("key1", "value1")
        fallback_manager.cache_response("key2", "value2")
        
        assert fallback_manager._cached_responses["key1"] == "value1"
        assert fallback_manager._cached_responses["key2"] == "value2"
        
        # Test cache clearing
        fallback_manager.clear_cache()
        assert len(fallback_manager._cached_responses) == 0
    
    def test_fallback_stats(self, fallback_manager):
        """Test fallback statistics."""
        fallback_manager.register_fallback_chain("comp1", [FallbackStrategy.RETRY])
        fallback_manager.cache_response("test", "value")
        
        stats = fallback_manager.get_fallback_stats()
        
        assert "comp1" in stats["registered_components"]
        assert "retry" in stats["available_strategies"]
        assert stats["cache_size"] == 1


class TestErrorRecoveryManager:
    """Test error recovery management system."""
    
    @pytest.fixture
    def recovery_manager(self):
        """Create recovery manager for testing."""
        return ErrorRecoveryManager()
    
    def test_component_registration(self, recovery_manager):
        """Test component registration for recovery."""
        strategies = [RecoveryStrategy.RECONNECT, RecoveryStrategy.RESTART_SERVICE]
        
        recovery_manager.register_component(
            "test_component",
            strategies,
            health_check_func=lambda: True
        )
        
        assert "test_component" in recovery_manager._component_health
        assert recovery_manager._recovery_strategies["test_component"] == strategies
        assert "test_component" in recovery_manager._recovery_locks
    
    @pytest.mark.asyncio
    async def test_error_recording_and_recovery_trigger(self, recovery_manager):
        """Test error recording and automatic recovery triggering."""
        # Register component
        recovery_manager.register_component(
            "test_component",
            [RecoveryStrategy.WAIT_AND_RETRY]
        )
        
        # Record multiple errors to trigger recovery
        component_health = recovery_manager._component_health["test_component"]
        
        for i in range(3):
            recovery_triggered = await recovery_manager.record_error(
                "test_component", 
                Exception(f"Error {i}")
            )
        
        # Should trigger recovery on 3rd error
        assert recovery_triggered is True
        assert component_health.consecutive_failures >= 3
        assert component_health.is_healthy is False
    
    @pytest.mark.asyncio
    async def test_success_recording(self, recovery_manager):
        """Test success recording and health restoration."""
        recovery_manager.register_component("test_component", [])
        
        # Record error first
        await recovery_manager.record_error("test_component", Exception("Test error"))
        component_health = recovery_manager._component_health["test_component"]
        assert component_health.is_healthy is False
        
        # Record success
        await recovery_manager.record_success("test_component")
        assert component_health.is_healthy is True
        assert component_health.consecutive_failures == 0
    
    def test_component_health_tracking(self, recovery_manager):
        """Test component health status tracking."""
        health = ComponentHealth("test_component")
        
        # Test error recording
        error = Exception("Test error")
        health.record_error(error)
        
        assert health.is_healthy is False
        assert health.error_count == 1
        assert health.consecutive_failures == 1
        assert health.last_error == error
        
        # Test success recording
        health.record_success()
        
        assert health.is_healthy is True
        assert health.consecutive_failures == 0
        assert health.last_successful_operation is not None
    
    def test_recovery_cooldown(self, recovery_manager):
        """Test recovery cooldown mechanism."""
        recovery_manager.recovery_cooldown = timedelta(seconds=1)
        
        health = ComponentHealth("test_component")
        health.last_recovery_attempt = datetime.now()
        
        # Should not attempt recovery during cooldown
        assert not health.should_attempt_recovery()
        
        # Should attempt recovery after cooldown
        health.last_recovery_attempt = datetime.now() - timedelta(seconds=2)
        health.consecutive_failures = 5
        health.is_healthy = False
        
        assert health.should_attempt_recovery()
    
    def test_recovery_stats(self, recovery_manager):
        """Test recovery statistics."""
        recovery_manager.register_component("comp1", [RecoveryStrategy.RECONNECT])
        recovery_manager.register_component("comp2", [RecoveryStrategy.RESTART_SERVICE])
        
        stats = recovery_manager.get_recovery_stats()
        
        assert stats["monitored_components"] == 2
        assert "comp1" in stats["components"]
        assert "comp2" in stats["components"]
        assert stats["components"]["comp1"]["is_healthy"] is True


class TestLoggingHandlers:
    """Test specialized logging handlers."""
    
    @pytest.fixture
    def content_filter_logger(self, tmp_path):
        """Create content filter logger for testing."""
        log_file = tmp_path / "content_filter.log"
        return ContentFilterLogger(str(log_file))
    
    @pytest.fixture
    def error_logger(self, tmp_path):
        """Create error logger for testing."""
        log_file = tmp_path / "system_errors.log"
        return ErrorLogger(str(log_file))
    
    def test_content_filter_logging(self, content_filter_logger):
        """Test content filter incident logging."""
        # Log incident without storing inappropriate content
        content_filter_logger.log_content_filter_incident(
            provider="gemini",
            filter_type="safety_filter",
            user_id="test_user",
            content_hash="abc123",
            metadata={"message_length": 50}
        )
        
        # Verify log file exists and contains incident
        assert content_filter_logger.log_file.exists()
        
        with open(content_filter_logger.log_file, 'r') as f:
            log_content = f.read()
            assert "Content filter triggered" in log_content
            assert "gemini" in log_content
            assert "safety_filter" in log_content
            # Ensure no actual inappropriate content is logged
            assert "inappropriate" not in log_content.lower()
    
    def test_content_hash_creation(self, content_filter_logger):
        """Test content hash creation for tracking."""
        content = "This is test content"
        hash1 = content_filter_logger.create_content_hash(content)
        hash2 = content_filter_logger.create_content_hash(content)
        
        # Same content should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 16  # Truncated SHA-256
        
        # Different content should produce different hash
        hash3 = content_filter_logger.create_content_hash("Different content")
        assert hash1 != hash3
    
    def test_user_id_anonymization(self, content_filter_logger):
        """Test user ID anonymization for privacy."""
        user_id = "user123@example.com"
        anon1 = content_filter_logger._anonymize_user_id(user_id)
        anon2 = content_filter_logger._anonymize_user_id(user_id)
        
        # Same user ID should produce same anonymized ID
        assert anon1 == anon2
        assert len(anon1) == 8  # Truncated hash
        assert anon1 != user_id  # Should be different from original
    
    def test_error_logging(self, error_logger):
        """Test system error logging."""
        error = AIProviderError(
            "Test error",
            provider="gemini",
            error_code="TEST_001"
        )
        
        error_logger.log_error(
            error,
            component="ai_provider",
            operation="generate_response",
            context={"model": "gemini-pro"},
            user_id="test_user"
        )
        
        # Verify log file exists and contains error
        assert error_logger.log_file.exists()
        
        with open(error_logger.log_file, 'r') as f:
            log_content = f.read()
            assert "System error" in log_content
            assert "ai_provider" in log_content
            assert "generate_response" in log_content
    
    def test_recovery_attempt_logging(self, error_logger):
        """Test recovery attempt logging."""
        error_logger.log_recovery_attempt(
            component="memory_manager",
            strategy="reconnect",
            success=True,
            recovery_time=2.5
        )
        
        with open(error_logger.log_file, 'r') as f:
            log_content = f.read()
            assert "Recovery attempt" in log_content
            assert "memory_manager" in log_content
            assert "reconnect" in log_content
            assert "2.5" in log_content
    
    def test_fallback_usage_logging(self, error_logger):
        """Test fallback usage logging."""
        original_error = Exception("Original error")
        
        error_logger.log_fallback_usage(
            component="ai_provider",
            fallback_strategy="cached_response",
            original_error=original_error,
            fallback_success=True
        )
        
        with open(error_logger.log_file, 'r') as f:
            log_content = f.read()
            assert "Fallback used" in log_content
            assert "ai_provider" in log_content
            assert "cached_response" in log_content
    
    def test_metadata_sanitization(self, error_logger):
        """Test sensitive metadata sanitization."""
        sensitive_context = {
            "api_key": "secret123",
            "password": "password123",
            "user_input": "sensitive user data",
            "model": "gemini-pro",  # This should be kept
            "timestamp": "2024-01-01T00:00:00"  # This should be kept
        }
        
        sanitized = error_logger._sanitize_context(sensitive_context)
        
        # Sensitive fields should be removed
        assert "api_key" not in sanitized
        assert "password" not in sanitized
        assert "user_input" not in sanitized
        
        # Safe fields should be kept
        assert "model" in sanitized
        assert "timestamp" in sanitized
    
    def test_setup_error_logging(self, tmp_path):
        """Test error logging system setup."""
        content_filter_log = tmp_path / "content_filter.log"
        system_error_log = tmp_path / "system_errors.log"
        application_log = tmp_path / "application.log"
        
        content_logger, error_logger = setup_error_logging(
            str(content_filter_log),
            str(system_error_log),
            str(application_log)
        )
        
        assert isinstance(content_logger, ContentFilterLogger)
        assert isinstance(error_logger, ErrorLogger)
        assert content_filter_log.parent.exists()
        assert system_error_log.parent.exists()
        assert application_log.parent.exists()


class TestIntegratedErrorHandling:
    """Test integrated error handling across components."""
    
    @pytest.mark.asyncio
    async def test_ai_provider_error_chain(self):
        """Test complete error handling chain for AI provider."""
        from src.ai.gemini_provider import GeminiProvider
        
        # Mock configuration
        config = {
            'api_keys': ['key1', 'key2'],
            'model': 'gemini-pro'
        }
        
        with patch('src.ai.gemini_provider.genai') as mock_genai:
            # Mock rate limit error
            mock_model = Mock()
            mock_model.generate_content.side_effect = Exception("Rate limit exceeded")
            mock_genai.GenerativeModel.return_value = mock_model
            
            provider = GeminiProvider(config)
            
            # Should handle rate limit and attempt key rotation
            with pytest.raises(AIProviderError):
                await provider._generate_response_internal([], None, None)
    
    @pytest.mark.asyncio
    async def test_memory_manager_fallback(self):
        """Test memory manager fallback to session-only mode."""
        from src.memory.memory_manager import MemoryManager
        from src.config.settings import MemoryConfig
        
        # Create config without Mem0 API key
        config = MemoryConfig(
            mem0_api_key="",  # Empty key should trigger fallback
            memory_history_limit=20
        )
        
        memory_manager = MemoryManager(config)
        
        # Should initialize in session-only mode
        mem0_available = await memory_manager.initialize()
        assert mem0_available is False
        assert memory_manager.mem0_available is False
        
        # Should still work with session memory
        success = await memory_manager.add_memory("test_user", "test content")
        assert success is True
    
    @pytest.mark.asyncio
    async def test_livekit_agent_error_recovery(self):
        """Test LiveKit agent error recovery."""
        from src.agent.livekit_agent import AnimeAILLMStream
        
        # Test stream functionality
        stream = AnimeAILLMStream("test response")
        
        # Should return content once
        content = await stream.__anext__()
        assert content == "test response"
        
        # Should raise StopAsyncIteration on second call
        with pytest.raises(StopAsyncIteration):
            await stream.__anext__()
    
    @pytest.mark.asyncio
    async def test_web_server_animation_fallback(self):
        """Test web server animation fallback mechanisms."""
        from src.web.app import _trigger_animation_internal
        
        # Mock settings
        with patch('src.web.app.get_settings') as mock_settings:
            mock_settings.return_value.flask.host = "localhost"
            mock_settings.return_value.flask.port = 5000
            
            # Mock aiohttp session to simulate server error
            with patch('aiohttp.ClientSession') as mock_session:
                mock_response = Mock()
                mock_response.status = 500
                mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
                
                # Should handle server error and retry
                with pytest.raises(NetworkError):
                    await _trigger_animation_internal("happy", 0.7, 2.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])