"""
Tests for real-time animation synchronization system.

This module tests the WebSocket communication, animation timing,
and synchronization between LiveKit agent and Flask server.
"""

import asyncio
import json
import pytest
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

import websockets
from websockets.exceptions import ConnectionClosed

from src.web.websocket_manager import (
    WebSocketAnimationManager, AnimationEvent, AnimationEventType,
    TimingSyncData, get_websocket_manager
)
from src.web.animation_sync import (
    AnimationSynchronizer, AnimationPriority, ExpressionTransition,
    MouthSyncConfig, get_animation_synchronizer
)
from src.web.app import Live2DFlaskApp


class TestWebSocketAnimationManager:
    """Test WebSocket animation manager functionality."""
    
    @pytest.fixture
    async def manager(self):
        """Create WebSocket manager for testing."""
        manager = WebSocketAnimationManager(host="localhost", port=8765)
        yield manager
        
        # Cleanup
        if manager.is_running:
            await manager.stop_server()
    
    @pytest.fixture
    def animation_event(self):
        """Create test animation event."""
        return AnimationEvent(
            event_type=AnimationEventType.EXPRESSION_CHANGE,
            timestamp=time.time(),
            data={
                "expression": "happy",
                "intensity": 0.8,
                "duration": 2.0
            },
            sequence_id="test-sequence-123",
            duration=2.0,
            priority=5
        )
    
    @pytest.mark.asyncio
    async def test_server_start_stop(self, manager):
        """Test WebSocket server start and stop."""
        # Start server
        await manager.start_server()
        assert manager.is_running
        assert manager.server is not None
        
        # Stop server
        await manager.stop_server()
        assert not manager.is_running
    
    @pytest.mark.asyncio
    async def test_animation_event_broadcasting(self, manager, animation_event):
        """Test animation event broadcasting to clients."""
        await manager.start_server()
        
        # Mock client connections
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()
        manager.clients = {
            "client1": mock_client1,
            "client2": mock_client2
        }
        
        # Broadcast event
        await manager.broadcast_animation_event(animation_event)
        
        # Verify both clients received the event
        expected_message = json.dumps({
            "type": "animation_event",
            "event": {
                "event_type": "expression_change",
                "timestamp": animation_event.timestamp,
                "data": animation_event.data,
                "sequence_id": "test-sequence-123",
                "duration": 2.0,
                "priority": 5
            }
        })
        
        mock_client1.send.assert_called_once()
        mock_client2.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_animation_queue_management(self, manager, animation_event):
        """Test animation queue management and processing."""
        await manager.start_server()
        
        # Queue animation event
        await manager.queue_animation(animation_event)
        
        assert len(manager.animation_queue) == 1
        assert manager.animation_queue[0] == animation_event
    
    @pytest.mark.asyncio
    async def test_queue_size_limit(self, manager):
        """Test animation queue size limit enforcement."""
        await manager.start_server()
        manager.max_queue_size = 3
        
        # Add events beyond limit
        for i in range(5):
            event = AnimationEvent(
                event_type=AnimationEventType.EXPRESSION_CHANGE,
                timestamp=time.time(),
                data={"expression": f"test{i}"},
                priority=i  # Different priorities
            )
            await manager.queue_animation(event)
        
        # Should only keep max_queue_size events
        assert len(manager.animation_queue) == 3
        
        # Should keep highest priority events
        priorities = [event.priority for event in manager.animation_queue]
        assert max(priorities) == 4  # Highest priority should be kept
    
    @pytest.mark.asyncio
    async def test_timing_sync_creation(self, manager):
        """Test timing synchronization data creation."""
        await manager.start_server()
        
        audio_duration = 3.5
        tts_delay = 0.2
        
        timing_sync = manager.create_timing_sync(audio_duration, tts_delay)
        
        assert isinstance(timing_sync, TimingSyncData)
        assert timing_sync.audio_duration == audio_duration
        assert timing_sync.tts_processing_delay == tts_delay
        assert timing_sync.audio_start_time > time.time()
        assert timing_sync.animation_start_time <= time.time()
    
    @pytest.mark.asyncio
    async def test_client_message_handling(self, manager):
        """Test client message handling."""
        await manager.start_server()
        
        # Test ping message
        ping_message = json.dumps({
            "type": "ping",
            "timestamp": time.time()
        })
        
        with patch.object(manager, '_send_to_client') as mock_send:
            await manager._handle_client_message("test_client", ping_message)
            
            # Should respond with pong
            mock_send.assert_called_once()
            call_args = mock_send.call_args[0]
            assert call_args[0] == "test_client"
            assert call_args[1]["type"] == "pong"
    
    @pytest.mark.asyncio
    async def test_latency_measurement(self, manager):
        """Test latency measurement recording."""
        await manager.start_server()
        
        # Record latency measurements
        latencies = [50.0, 75.0, 60.0, 80.0]
        for latency in latencies:
            manager._record_latency(latency)
        
        # Check average calculation
        expected_average = sum(latencies) / len(latencies)
        assert manager.get_average_latency() == expected_average
        
        # Test max samples limit
        manager.max_latency_samples = 2
        manager._record_latency(100.0)
        
        assert len(manager.latency_measurements) == 2
        assert manager.latency_measurements[-1] == 100.0


class TestAnimationSynchronizer:
    """Test animation synchronization functionality."""
    
    @pytest.fixture
    def mock_websocket_manager(self):
        """Create mock WebSocket manager."""
        manager = Mock()
        manager.queue_animation = AsyncMock()
        manager.create_timing_sync = Mock()
        manager.get_average_latency = Mock(return_value=50.0)
        return manager
    
    @pytest.fixture
    def synchronizer(self, mock_websocket_manager):
        """Create animation synchronizer for testing."""
        return AnimationSynchronizer(mock_websocket_manager)
    
    @pytest.mark.asyncio
    async def test_tts_synchronization(self, synchronizer, mock_websocket_manager):
        """Test TTS animation synchronization."""
        text = "Hello, this is a test message!"
        expression = "speak"
        audio_duration = 2.5
        tts_delay = 0.3
        
        # Mock timing sync creation
        mock_timing_sync = TimingSyncData(
            audio_start_time=time.time() + tts_delay,
            audio_duration=audio_duration,
            animation_start_time=time.time(),
            tts_processing_delay=tts_delay
        )
        mock_websocket_manager.create_timing_sync.return_value = mock_timing_sync
        
        # Execute TTS synchronization
        sequence_id = await synchronizer.synchronize_with_tts(
            text=text,
            expression=expression,
            audio_duration=audio_duration,
            tts_processing_delay=tts_delay
        )
        
        # Verify sequence was created
        assert sequence_id is not None
        assert sequence_id in synchronizer.active_sequences
        
        # Verify WebSocket manager was called to queue animations
        assert mock_websocket_manager.queue_animation.call_count >= 2  # At least start and stop events
        
        # Verify timing data was stored
        assert synchronizer.audio_start_time == mock_timing_sync.audio_start_time
        assert synchronizer.audio_duration == audio_duration
    
    @pytest.mark.asyncio
    async def test_expression_change_trigger(self, synchronizer, mock_websocket_manager):
        """Test expression change triggering."""
        expression = "happy"
        intensity = 0.8
        duration = 2.0
        priority = AnimationPriority.HIGH
        
        # Trigger expression change
        sequence_id = await synchronizer.trigger_expression_change(
            expression=expression,
            intensity=intensity,
            duration=duration,
            priority=priority
        )
        
        # Verify animation was queued
        mock_websocket_manager.queue_animation.assert_called_once()
        
        # Verify event data
        call_args = mock_websocket_manager.queue_animation.call_args[0][0]
        assert call_args.event_type == AnimationEventType.EXPRESSION_CHANGE
        assert call_args.data["expression"] == expression
        assert call_args.data["intensity"] == intensity
        assert call_args.data["duration"] == duration
        assert call_args.priority == priority.value
        
        # Verify state updates
        assert synchronizer.target_expression == expression
        assert synchronizer.is_transitioning
    
    @pytest.mark.asyncio
    async def test_mouth_sync_control(self, synchronizer, mock_websocket_manager):
        """Test mouth synchronization control."""
        # Start mouth sync
        await synchronizer.start_mouth_sync(duration=3.0)
        
        assert synchronizer.is_speaking
        mock_websocket_manager.queue_animation.assert_called()
        
        # Verify start event
        start_call = mock_websocket_manager.queue_animation.call_args[0][0]
        assert start_call.event_type == AnimationEventType.MOUTH_SYNC_START
        
        # Reset mock for stop test
        mock_websocket_manager.queue_animation.reset_mock()
        
        # Stop mouth sync
        await synchronizer.stop_mouth_sync()
        
        assert not synchronizer.is_speaking
        mock_websocket_manager.queue_animation.assert_called()
        
        # Verify stop event
        stop_call = mock_websocket_manager.queue_animation.call_args[0][0]
        assert stop_call.event_type == AnimationEventType.MOUTH_SYNC_STOP
    
    @pytest.mark.asyncio
    async def test_mouth_parameter_updates(self, synchronizer, mock_websocket_manager):
        """Test mouth parameter updates during sync."""
        # Start mouth sync first
        synchronizer.is_speaking = True
        
        audio_level = 0.7
        frequency_data = [0.1, 0.3, 0.5, 0.2, 0.1]
        
        # Update mouth parameters
        await synchronizer.update_mouth_parameters(audio_level, frequency_data)
        
        # Verify parameter update event was queued
        mock_websocket_manager.queue_animation.assert_called()
        
        update_call = mock_websocket_manager.queue_animation.call_args[0][0]
        assert update_call.event_type == AnimationEventType.MOUTH_SYNC_UPDATE
        assert "mouth_open" in update_call.data
        assert "mouth_form" in update_call.data
        assert update_call.data["audio_level"] == audio_level
    
    def test_audio_duration_estimation(self, synchronizer):
        """Test audio duration estimation from text."""
        # Test short text
        short_text = "Hello"
        short_duration = synchronizer._estimate_audio_duration(short_text)
        assert short_duration >= 1.0  # Minimum duration
        
        # Test longer text
        long_text = "This is a much longer text that should take more time to speak and therefore have a longer estimated duration."
        long_duration = synchronizer._estimate_audio_duration(long_text)
        assert long_duration > short_duration
    
    def test_mouth_opening_calculation(self, synchronizer):
        """Test mouth opening parameter calculation."""
        config = synchronizer.mouth_sync_config
        
        # Test various audio levels
        test_levels = [0.0, 0.5, 1.0]
        
        for level in test_levels:
            mouth_open = synchronizer._calculate_mouth_opening(level)
            
            # Should be within configured range
            assert config.min_mouth_open <= mouth_open <= config.max_mouth_open
            
            # Higher audio level should result in more mouth opening
            if level > 0:
                assert mouth_open > config.min_mouth_open
    
    def test_mouth_form_calculation(self, synchronizer):
        """Test mouth form parameter calculation from frequency data."""
        # Test with frequency data
        frequency_data = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        mouth_form = synchronizer._calculate_mouth_form(frequency_data)
        
        # Should be within valid range
        assert -1.0 <= mouth_form <= 1.0
        
        # Test with empty frequency data
        empty_form = synchronizer._calculate_mouth_form([])
        assert empty_form == 0.0
    
    def test_animation_state_tracking(self, synchronizer):
        """Test animation state tracking."""
        # Set some state
        synchronizer.current_expression = "happy"
        synchronizer.target_expression = "sad"
        synchronizer.is_speaking = True
        synchronizer.is_transitioning = True
        
        # Get state
        state = synchronizer.get_animation_state()
        
        assert state["current_expression"] == "happy"
        assert state["target_expression"] == "sad"
        assert state["is_speaking"] is True
        assert state["is_transitioning"] is True
        assert "sync_accuracy" in state
        assert "active_sequences" in state
    
    @pytest.mark.asyncio
    async def test_sequence_cleanup(self, synchronizer):
        """Test cleanup of expired animation sequences."""
        # Add a mock sequence
        sequence_id = "test-sequence"
        mock_sequence = Mock()
        mock_sequence.start_time = time.time() - 100  # Old sequence
        mock_sequence.total_duration = 5.0
        
        synchronizer.active_sequences[sequence_id] = mock_sequence
        
        # Run cleanup
        await synchronizer.cleanup_expired_sequences()
        
        # Sequence should be removed
        assert sequence_id not in synchronizer.active_sequences


class TestFlaskAnimationIntegration:
    """Test Flask server animation integration."""
    
    @pytest.fixture
    def flask_app(self):
        """Create Flask app for testing."""
        app = Live2DFlaskApp()
        app.app.config['TESTING'] = True
        return app.app.test_client()
    
    def test_animate_endpoint(self, flask_app):
        """Test animation trigger endpoint."""
        # Test valid animation request
        response = flask_app.post('/animate', json={
            'expression': 'happy',
            'intensity': 0.8,
            'duration': 2.0,
            'priority': 'high'
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['animation']['expression'] == 'happy'
        assert data['animation']['intensity'] == 0.8
    
    def test_animate_endpoint_validation(self, flask_app):
        """Test animation endpoint parameter validation."""
        # Test invalid intensity
        response = flask_app.post('/animate', json={
            'expression': 'happy',
            'intensity': 1.5,  # Invalid: > 1.0
            'duration': 2.0
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'Intensity' in data['error']
        
        # Test invalid duration
        response = flask_app.post('/animate', json={
            'expression': 'happy',
            'intensity': 0.8,
            'duration': 15.0  # Invalid: > 10.0
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'Duration' in data['error']
    
    def test_animation_status_endpoint(self, flask_app):
        """Test animation status endpoint."""
        response = flask_app.get('/animate/status')
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'current_animation' in data
        assert 'timestamp' in data
        assert 'websocket_active' in data
        assert 'connected_clients' in data
    
    def test_tts_sync_endpoint(self, flask_app):
        """Test TTS synchronization endpoint."""
        response = flask_app.post('/animate/sync/tts', json={
            'text': 'Hello, this is a test message!',
            'expression': 'speak',
            'audio_duration': 2.5,
            'tts_processing_delay': 0.3
        })
        
        # Note: This might return 503 if WebSocket is not active in test
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.get_json()
            assert data['success'] is True
            assert 'sequence_id' in data
    
    def test_mouth_sync_control_endpoint(self, flask_app):
        """Test mouth sync control endpoint."""
        # Test start mouth sync
        response = flask_app.post('/animate/sync/mouth', json={
            'action': 'start',
            'duration': 3.0
        })
        
        # Note: This might return 503 if WebSocket is not active in test
        assert response.status_code in [200, 503]
        
        # Test stop mouth sync
        response = flask_app.post('/animate/sync/mouth', json={
            'action': 'stop'
        })
        
        assert response.status_code in [200, 503]
        
        # Test update mouth sync
        response = flask_app.post('/animate/sync/mouth', json={
            'action': 'update',
            'audio_level': 0.7,
            'frequency_data': [0.1, 0.3, 0.5, 0.2]
        })
        
        assert response.status_code in [200, 503]


class TestRealTimeCoordination:
    """Test real-time coordination between components."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_animation_flow(self):
        """Test complete animation flow from trigger to execution."""
        # Create components
        websocket_manager = WebSocketAnimationManager()
        synchronizer = AnimationSynchronizer(websocket_manager)
        
        try:
            # Start WebSocket server
            await websocket_manager.start_server()
            
            # Simulate TTS synchronization request
            text = "Hello, this is a test!"
            expression = "speak"
            
            sequence_id = await synchronizer.synchronize_with_tts(
                text=text,
                expression=expression,
                audio_duration=2.0,
                tts_processing_delay=0.2
            )
            
            # Verify sequence was created and queued
            assert sequence_id in synchronizer.active_sequences
            assert len(websocket_manager.animation_queue) > 0
            
            # Wait for some processing
            await asyncio.sleep(0.5)
            
            # Verify animation state
            state = synchronizer.get_animation_state()
            assert state["active_sequences"] > 0
            
        finally:
            await websocket_manager.stop_server()
    
    @pytest.mark.asyncio
    async def test_timing_accuracy(self):
        """Test timing accuracy of synchronization."""
        websocket_manager = WebSocketAnimationManager()
        synchronizer = AnimationSynchronizer(websocket_manager)
        
        try:
            await websocket_manager.start_server()
            
            # Record start time
            start_time = time.time()
            
            # Trigger animation with specific timing
            audio_duration = 1.0
            tts_delay = 0.1
            
            await synchronizer.synchronize_with_tts(
                text="Test",
                expression="speak",
                audio_duration=audio_duration,
                tts_processing_delay=tts_delay
            )
            
            # Check timing data
            timing_data = websocket_manager.timing_sync_data
            assert timing_data is not None
            
            # Verify timing calculations
            expected_audio_start = start_time + tts_delay
            actual_audio_start = timing_data.audio_start_time
            
            # Allow for small timing variations (50ms tolerance)
            timing_difference = abs(actual_audio_start - expected_audio_start)
            assert timing_difference < 0.05
            
        finally:
            await websocket_manager.stop_server()
    
    @pytest.mark.asyncio
    async def test_concurrent_animations(self):
        """Test handling of concurrent animation requests."""
        websocket_manager = WebSocketAnimationManager()
        synchronizer = AnimationSynchronizer(websocket_manager)
        
        try:
            await websocket_manager.start_server()
            
            # Trigger multiple animations concurrently
            tasks = []
            for i in range(3):
                task = synchronizer.trigger_expression_change(
                    expression=f"test{i}",
                    intensity=0.5,
                    duration=1.0,
                    priority=AnimationPriority.NORMAL
                )
                tasks.append(task)
            
            # Wait for all animations to be queued
            sequence_ids = await asyncio.gather(*tasks)
            
            # Verify all animations were queued
            assert len(sequence_ids) == 3
            assert all(sid is not None for sid in sequence_ids)
            assert len(websocket_manager.animation_queue) >= 3
            
        finally:
            await websocket_manager.stop_server()


@pytest.mark.integration
class TestLiveKitIntegration:
    """Integration tests with LiveKit agent."""
    
    @pytest.mark.asyncio
    async def test_agent_animation_trigger(self):
        """Test animation triggering from LiveKit agent."""
        from src.agent.livekit_agent import AnimeAILLM
        from src.config.settings import load_config
        from src.memory.memory_manager import MemoryManager
        
        # Mock configuration
        config = Mock()
        config.personality.personality_prompt = "Test personality"
        
        # Mock memory manager
        memory_manager = Mock()
        memory_manager.get_user_context = AsyncMock(return_value="Test context")
        memory_manager.store_conversation = AsyncMock()
        
        # Create LLM instance
        llm = AnimeAILLM(config, memory_manager)
        
        # Mock AI provider
        llm.ai_provider = Mock()
        llm.ai_provider.generate_response = AsyncMock(return_value="Hello! (*happy*)")
        
        # Mock animation sync
        llm.animation_sync = Mock()
        llm.animation_sync.synchronize_with_tts = AsyncMock(return_value="test-sequence")
        
        # Test response generation with animation
        with patch('src.agent.livekit_agent.trigger_animation') as mock_trigger:
            mock_trigger.return_value = True
            
            # Simulate chat context
            from livekit.agents.llm import ChatContext, ChatMessage
            chat_ctx = ChatContext()
            chat_ctx.messages = [
                ChatMessage(role="user", content="Hello there!")
            ]
            
            # Generate response
            stream = await llm.chat(chat_ctx=chat_ctx)
            
            # Verify animation was triggered
            assert llm.animation_sync.synchronize_with_tts.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])