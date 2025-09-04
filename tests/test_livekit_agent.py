"""
Integration tests for LiveKit agent functionality.
Tests voice processing, AI integration, and memory management.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from src.agent.livekit_agent import AnimeAIAgent, AnimeAILLM, AnimeAILLMStream
from src.agent.voice_assistant import EnhancedVoiceAssistant, VoiceAssistantFactory
from src.config.settings import (
    AppConfig,
    LiveKitConfig,
    AIConfig,
    MemoryConfig,
    PersonalityConfig,
    AgentsConfig,
)
from src.memory.memory_manager import MemoryManager, ConversationMessage


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return AppConfig(
        livekit=LiveKitConfig(
            url="wss://test.livekit.cloud",
            api_key="test_key",
            api_secret="test_secret",
            room_name="test_room",
        ),
        ai=AIConfig(
            use_ollama=True, ollama_model="llama3", ollama_host="http://localhost:11434"
        ),
        memory=MemoryConfig(
            mem0_api_key="",  # Use session-only memory for tests
            mem0_collection="test_collection",
            memory_history_limit=10,
        ),
        personality=PersonalityConfig(
            personality_prompt="You are a test anime character."
        ),
        agents=AgentsConfig(tts_provider="openai", stt_provider="openai"),
        content_filter=Mock(),
        live2d=Mock(),
        flask=Mock(),
        debug=True,
        log_level="DEBUG",
    )


@pytest.fixture
def mock_memory_manager():
    """Create a mock memory manager for testing."""
    memory_manager = Mock(spec=MemoryManager)
    memory_manager.initialize = AsyncMock(return_value=True)
    memory_manager.store_conversation = AsyncMock(return_value=True)
    memory_manager.get_user_context = AsyncMock()
    memory_manager.search_memories = AsyncMock(return_value=[])
    return memory_manager


@pytest.fixture
def mock_ai_provider():
    """Create a mock AI provider for testing."""
    provider = Mock()
    provider.generate_response = AsyncMock(
        return_value="Test response from AI! (*happy*)"
    )
    return provider


class TestAnimeAILLMStream:
    """Test the LLM stream implementation."""

    def test_stream_initialization(self):
        """Test stream initialization with content."""
        content = "Test response"
        stream = AnimeAILLMStream(content)
        assert stream.content == content
        assert not stream._sent

    @pytest.mark.asyncio
    async def test_stream_iteration(self):
        """Test async iteration over stream content."""
        content = "Test response"
        stream = AnimeAILLMStream(content)

        # First iteration should return content
        result = await stream.__anext__()
        assert result == content
        assert stream._sent

        # Second iteration should raise StopAsyncIteration
        with pytest.raises(StopAsyncIteration):
            await stream.__anext__()


class TestAnimeAILLM:
    """Test the custom LLM implementation."""

    @pytest.mark.asyncio
    async def test_llm_initialization(self, mock_config, mock_memory_manager):
        """Test LLM initialization."""
        with patch(
            "src.agent.livekit_agent.ProviderFactory.create_provider"
        ) as mock_create:
            mock_create.return_value = Mock()

            llm = AnimeAILLM(mock_config, mock_memory_manager)

            assert llm.config == mock_config
            assert llm.memory_manager == mock_memory_manager
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_processing(
        self, mock_config, mock_memory_manager, mock_ai_provider
    ):
        """Test chat message processing."""
        with patch(
            "src.agent.livekit_agent.ProviderFactory.create_provider"
        ) as mock_create:
            mock_create.return_value = mock_ai_provider

            # Mock memory context
            mock_context = Mock()
            mock_context.format_for_ai.return_value = "Previous context"
            mock_memory_manager.get_user_context.return_value = mock_context

            # Mock animation trigger
            with patch("src.agent.livekit_agent.trigger_animation") as mock_trigger:
                mock_trigger.return_value = AsyncMock()

                llm = AnimeAILLM(mock_config, mock_memory_manager)

                # Create mock chat context
                chat_ctx = Mock()
                chat_ctx.user_id = "test_user"

                # Create mock message
                mock_message = Mock()
                mock_message.role = "user"
                mock_message.content = "Hello!"
                chat_ctx.messages = [mock_message]

                # Process chat
                result = await llm.chat(chat_ctx=chat_ctx)

                # Verify result
                assert isinstance(result, AnimeAILLMStream)
                assert result.content == "Test response from AI! (*happy*)"

                # Verify memory operations
                mock_memory_manager.store_conversation.assert_called()
                mock_memory_manager.get_user_context.assert_called_with(
                    "test_user", "Hello!"
                )

                # Verify AI provider call
                mock_ai_provider.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_animation_trigger_logic(self, mock_config, mock_memory_manager):
        """Test animation triggering based on response content."""
        with patch(
            "src.agent.livekit_agent.ProviderFactory.create_provider"
        ) as mock_create:
            mock_create.return_value = Mock()

            llm = AnimeAILLM(mock_config, mock_memory_manager)

            # Test different response types
            test_cases = [
                ("B-baka! You're so stupid!", "angry"),
                ("I'm so happy to see you! (*happy*)", "happy"),
                ("I'm sorry... (*sad*)", "sad"),
                ("*blush* That's embarrassing...", "embarrassed"),
                ("Hello there, how are you?", "neutral"),
            ]

            for response, expected_animation in test_cases:
                with patch("src.agent.livekit_agent.trigger_animation") as mock_trigger:
                    await llm._trigger_animation_for_response(response)
                    mock_trigger.assert_called_once_with(expected_animation)


class TestAnimeAIAgent:
    """Test the main LiveKit agent."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self, mock_config):
        """Test agent initialization."""
        agent = AnimeAIAgent(mock_config)

        assert agent.config == mock_config
        assert isinstance(agent.memory_manager, MemoryManager)
        assert agent.voice_assistant is None

    @pytest.mark.asyncio
    async def test_agent_initialize_method(self, mock_config):
        """Test agent initialize method."""
        agent = AnimeAIAgent(mock_config)

        # Mock memory manager initialization
        with patch.object(agent.memory_manager, "initialize") as mock_init:
            mock_init.return_value = True

            await agent.initialize()

            mock_init.assert_called_once()

    def test_stt_provider_creation(self, mock_config):
        """Test STT provider creation."""
        agent = AnimeAIAgent(mock_config)

        # Test OpenAI STT
        with patch("src.agent.livekit_agent.openai") as mock_openai:
            mock_openai.STT.return_value = Mock()
            stt = agent._create_stt_provider()
            mock_openai.STT.assert_called_once()

        # Test Deepgram STT
        mock_config.agents.stt_provider = "deepgram"
        with patch("src.agent.livekit_agent.deepgram") as mock_deepgram:
            mock_deepgram.STT.return_value = Mock()
            stt = agent._create_stt_provider()
            mock_deepgram.STT.assert_called_once()

    def test_tts_provider_creation(self, mock_config):
        """Test TTS provider creation."""
        agent = AnimeAIAgent(mock_config)

        # Test OpenAI TTS
        with patch("src.agent.livekit_agent.openai") as mock_openai:
            mock_openai.TTS.return_value = Mock()
            tts = agent._create_tts_provider()
            mock_openai.TTS.assert_called_once()

        # Test Silero TTS
        mock_config.agents.tts_provider = "silero"
        with patch("src.agent.livekit_agent.silero") as mock_silero:
            mock_silero.TTS.return_value = Mock()
            tts = agent._create_tts_provider()
            mock_silero.TTS.assert_called_once()

    def test_voice_agent_creation(self, mock_config):
        """Test VoiceAgent creation."""
        agent = AnimeAIAgent(mock_config)

        with patch("src.agent.livekit_agent.VoiceAgent") as mock_va:
            with patch("livekit.plugins.silero.VAD") as mock_vad:
                with patch.object(agent, "_create_stt_provider") as mock_stt:
                    with patch.object(agent, "_create_tts_provider") as mock_tts:
                        mock_va_instance = Mock()
                        mock_va.return_value = mock_va_instance

                        result = agent.create_voice_agent()

                        assert result == mock_va_instance
                        mock_va.assert_called_once()
                        mock_vad.load.assert_called_once()

    @pytest.mark.asyncio
    async def test_participant_event_handlers(self, mock_config):
        """Test participant connection/disconnection handlers."""
        agent = AnimeAIAgent(mock_config)

        # Mock participant
        participant = Mock()
        participant.identity = "test_user"

        # Test connection handler
        await agent.handle_participant_connected(participant)

        # Test disconnection handler
        await agent.handle_participant_disconnected(participant)

        # Should not raise any exceptions


class TestEnhancedVoiceAssistant:
    """Test the enhanced voice assistant wrapper."""

    def test_initialization(self, mock_config, mock_memory_manager):
        """Test enhanced voice assistant initialization."""
        base_agent = Mock()

        enhanced = EnhancedVoiceAssistant(
            voice_agent=base_agent,
            config=mock_config,
            memory_manager=mock_memory_manager,
        )

        assert enhanced.voice_agent == base_agent
        assert enhanced.config == mock_config
        assert enhanced.memory_manager == mock_memory_manager
        assert enhanced.animation_callbacks == []
        assert enhanced.active_users == {}

    @pytest.mark.asyncio
    async def test_user_speech_handling(self, mock_config, mock_memory_manager):
        """Test user speech processing."""
        base_agent = Mock()
        enhanced = EnhancedVoiceAssistant(
            voice_agent=base_agent,
            config=mock_config,
            memory_manager=mock_memory_manager,
        )

        # Mock participant
        participant = Mock()
        participant.identity = "test_user"

        # Test speech handling
        await enhanced._handle_user_speech("Hello!", participant)

        # Verify user session tracking
        assert "test_user" in enhanced.active_users
        assert enhanced.active_users["test_user"]["message_count"] == 1

        # Verify memory storage
        mock_memory_manager.store_conversation.assert_called_once()

    def test_animation_callbacks(self, mock_config, mock_memory_manager):
        """Test animation callback management."""
        base_agent = Mock()
        enhanced = EnhancedVoiceAssistant(
            voice_agent=base_agent,
            config=mock_config,
            memory_manager=mock_memory_manager,
        )

        # Add callback
        callback = Mock()
        enhanced.add_animation_callback(callback)

        assert callback in enhanced.animation_callbacks

    @pytest.mark.asyncio
    async def test_animation_triggering(self, mock_config, mock_memory_manager):
        """Test animation triggering through callbacks."""
        base_agent = Mock()
        enhanced = EnhancedVoiceAssistant(
            voice_agent=base_agent,
            config=mock_config,
            memory_manager=mock_memory_manager,
        )

        # Add sync and async callbacks
        sync_callback = Mock()
        async_callback = AsyncMock()

        enhanced.add_animation_callback(sync_callback)
        enhanced.add_animation_callback(async_callback)

        # Trigger animation
        await enhanced.trigger_animation("happy")

        # Verify callbacks were called
        sync_callback.assert_called_once_with("happy")
        async_callback.assert_called_once_with("happy")

    @pytest.mark.asyncio
    async def test_cleanup_inactive_users(self, mock_config, mock_memory_manager):
        """Test cleanup of inactive user sessions."""
        base_agent = Mock()
        enhanced = EnhancedVoiceAssistant(
            voice_agent=base_agent,
            config=mock_config,
            memory_manager=mock_memory_manager,
        )

        # Add active user
        from datetime import datetime, timedelta

        enhanced.active_users["active_user"] = {
            "last_activity": datetime.now(),
            "message_count": 5,
        }

        # Add inactive user
        enhanced.active_users["inactive_user"] = {
            "last_activity": datetime.now() - timedelta(hours=2),
            "message_count": 3,
        }

        # Cleanup with 30 minute timeout
        await enhanced.cleanup_inactive_users(timeout_minutes=30)

        # Verify inactive user was removed
        assert "active_user" in enhanced.active_users
        assert "inactive_user" not in enhanced.active_users


class TestVoiceAssistantFactory:
    """Test the voice assistant factory."""

    def test_create_voice_assistant(self, mock_config, mock_memory_manager):
        """Test voice assistant creation through factory."""
        llm = Mock()
        stt = Mock()
        tts = Mock()

        with patch("src.agent.voice_assistant.VoiceAgent") as mock_va:
            with patch("livekit.plugins.silero.VAD") as mock_vad:
                mock_va_instance = Mock()
                mock_va.return_value = mock_va_instance

                result = VoiceAssistantFactory.create_voice_assistant(
                    config=mock_config,
                    memory_manager=mock_memory_manager,
                    llm=llm,
                    stt=stt,
                    tts=tts,
                )

                assert isinstance(result, EnhancedVoiceAssistant)
                assert result.voice_agent == mock_va_instance
                assert result.config == mock_config
                assert result.memory_manager == mock_memory_manager


@pytest.mark.asyncio
async def test_agent_entrypoint():
    """Test the agent entrypoint function."""
    from src.agent.livekit_agent import entrypoint

    # Mock job context
    ctx = Mock()
    ctx.room = Mock()

    with patch("src.agent.livekit_agent.load_config") as mock_load_config:
        with patch("src.agent.livekit_agent.AnimeAIAgent") as mock_agent_class:
            with patch("asyncio.sleep") as mock_sleep:
                # Configure mocks
                mock_config = Mock()
                mock_load_config.return_value = mock_config

                mock_agent = Mock()
                mock_agent.start_agent = AsyncMock()
                mock_agent_class.return_value = mock_agent

                # Make sleep raise an exception to exit the infinite loop
                mock_sleep.side_effect = KeyboardInterrupt()

                # Test entrypoint
                with pytest.raises(KeyboardInterrupt):
                    await entrypoint(ctx)

                # Verify calls
                mock_load_config.assert_called_once()
                mock_agent_class.assert_called_once_with(mock_config)
                mock_agent.start_agent.assert_called_once_with(ctx.room)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
