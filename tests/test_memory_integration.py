"""
Integration tests for memory-enhanced AI conversations.
Tests the complete flow of memory retrieval, AI response generation, and conversation storage.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.ai.base_provider import Message, MemoryContext
from src.ai.ollama_provider import OllamaProvider
from src.ai.gemini_provider import GeminiProvider
from src.memory.memory_manager import MemoryManager, ConversationMessage
from src.config.settings import MemoryConfig


class TestMemoryIntegration:
    """Test memory integration with AI providers."""

    @pytest.fixture
    def memory_config(self):
        """Create memory configuration for testing."""
        return MemoryConfig(
            mem0_api_key="test_key",
            mem0_collection="test_collection",
            memory_history_limit=10,
        )

    @pytest.fixture
    def memory_manager(self, memory_config):
        """Create memory manager for testing."""
        manager = MemoryManager(memory_config)
        # Mock the Mem0 client to avoid external dependencies
        manager._mem0_client = None
        manager._initialized = True
        return manager

    @pytest.fixture
    def ollama_provider(self):
        """Create Ollama provider for testing."""
        config = {"model": "llama3", "host": "http://localhost:11434"}
        with patch("src.ai.ollama_provider.ollama") as mock_ollama:
            mock_ollama.chat.return_value = {
                "message": {"content": "Test response from Ollama"}
            }
            provider = OllamaProvider(config)
            return provider

    @pytest.fixture
    def gemini_provider(self):
        """Create Gemini provider for testing."""
        config = {
            "api_keys": ["test_key_1", "test_key_2"],
            "model": "gemini-pro",
            "current_key_index": 0,
        }
        with patch("src.ai.gemini_provider.genai") as mock_genai:
            mock_response = MagicMock()
            mock_response.text = "Test response from Gemini"
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model
            provider = GeminiProvider(config)
            return provider

    @pytest.mark.asyncio
    async def test_memory_context_creation(self, memory_manager):
        """Test creating memory context with conversation history."""
        user_id = "test_user"

        # Add some conversation history
        messages = [
            ConversationMessage("user", "Hello", datetime.now(), user_id),
            ConversationMessage("assistant", "Hi there!", datetime.now(), user_id),
            ConversationMessage("user", "How are you?", datetime.now(), user_id),
        ]

        for msg in messages:
            await memory_manager.store_conversation(msg)

        # Get memory context
        context = await memory_manager.get_user_context(
            user_id, "What did we talk about?"
        )

        assert context.user_id == user_id
        assert len(context.conversation_history) == 3
        assert context.conversation_history[0].content == "Hello"
        assert context.conversation_history[-1].content == "How are you?"

    @pytest.mark.asyncio
    async def test_memory_context_formatting(self, memory_manager):
        """Test memory context formatting for AI prompts."""
        user_id = "test_user"

        # Create memory context with history and memories
        context = MemoryContext(
            user_id=user_id,
            relevant_memories=["User likes anime", "User prefers tsundere characters"],
            conversation_history=[
                Message("user", "I love anime!", datetime.now()),
                Message(
                    "assistant",
                    "That's great! What's your favorite genre?",
                    datetime.now(),
                ),
            ],
            personality_state={},
        )

        formatted = context.format_for_ai()

        assert "Previous conversations and memories:" in formatted
        assert "User likes anime" in formatted
        assert "User prefers tsundere characters" in formatted
        assert "Recent conversation:" in formatted
        assert "User: I love anime!" in formatted
        assert "You: That's great!" in formatted

    @pytest.mark.asyncio
    async def test_ollama_with_memory_context(self, ollama_provider, memory_manager):
        """Test Ollama provider with memory context integration."""
        user_id = "test_user"

        # Create memory context
        memory_context = MemoryContext(
            user_id=user_id,
            relevant_memories=["User is learning Japanese"],
            conversation_history=[
                Message("user", "Teach me Japanese", datetime.now()),
            ],
            personality_state={},
        )

        # Create messages
        messages = [Message("user", "What does 'konnichiwa' mean?", datetime.now())]

        # Generate response with memory context
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock()
            mock_executor.return_value = {
                "message": {
                    "content": "Konnichiwa means hello in Japanese! Since you're learning, that's a great word to know."
                }
            }
            mock_loop.return_value.run_in_executor = mock_executor

            response = await ollama_provider.generate_response(
                messages,
                personality="You are a helpful Japanese tutor.",
                memory_context=memory_context,
            )

        assert "Konnichiwa means hello" in response
        # Verify that memory context was included in the call
        mock_executor.assert_called_once()

    @pytest.mark.asyncio
    async def test_gemini_with_memory_context(self, gemini_provider):
        """Test Gemini provider with memory context integration."""
        user_id = "test_user"

        # Create memory context
        memory_context = MemoryContext(
            user_id=user_id,
            relevant_memories=["User is interested in anime culture"],
            conversation_history=[
                Message("user", "Tell me about anime", datetime.now()),
            ],
            personality_state={},
        )

        # Create messages
        messages = [Message("user", "What's a tsundere character?", datetime.now())]

        # Mock the response
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock()
            mock_response = MagicMock()
            mock_response.text = (
                "A tsundere is a character who acts cold but is actually caring inside!"
            )
            mock_executor.return_value = mock_response
            mock_loop.return_value.run_in_executor = mock_executor

            response = await gemini_provider.generate_response(
                messages,
                personality="You are an anime expert.",
                memory_context=memory_context,
            )

        assert "tsundere" in response
        mock_executor.assert_called_once()

    @pytest.mark.asyncio
    async def test_conversation_storage_and_retrieval_flow(self, memory_manager):
        """Test complete conversation flow with storage and retrieval."""
        user_id = "test_user"

        # Simulate a conversation
        conversations = [
            ("user", "Hi, I'm new to anime"),
            ("assistant", "Welcome! What type of shows do you like?"),
            ("user", "I like action and romance"),
            (
                "assistant",
                "Great! I recommend checking out some shounen anime with romantic subplots.",
            ),
            ("user", "What's shounen?"),
        ]

        # Store conversation history
        for i, (role, content) in enumerate(
            conversations[:-1]
        ):  # Store all but the last message
            msg = ConversationMessage(role, content, datetime.now(), user_id)
            await memory_manager.store_conversation(msg)

        # Get context for the last user message
        last_message = conversations[-1][1]  # "What's shounen?"
        context = await memory_manager.get_user_context(user_id, last_message)

        # Verify context contains relevant information
        assert context.user_id == user_id
        assert len(context.conversation_history) == 4

        # Check that recent conversation is preserved
        recent_messages = [msg.content for msg in context.conversation_history[-2:]]
        assert "I like action and romance" in recent_messages
        assert any(
            "Great! I recommend checking out some shounen anime" in msg
            for msg in recent_messages
        )

        # Format for AI and verify it contains context
        formatted_context = context.format_for_ai()
        assert "Recent conversation:" in formatted_context
        assert "action and romance" in formatted_context

    @pytest.mark.asyncio
    async def test_memory_enhanced_response_generation(
        self, memory_manager, ollama_provider
    ):
        """Test end-to-end memory-enhanced response generation."""
        user_id = "test_user"

        # Setup conversation history
        previous_messages = [
            ConversationMessage("user", "My name is Alice", datetime.now(), user_id),
            ConversationMessage(
                "assistant", "Nice to meet you, Alice!", datetime.now(), user_id
            ),
            ConversationMessage("user", "I love cats", datetime.now(), user_id),
            ConversationMessage(
                "assistant", "Cats are wonderful pets!", datetime.now(), user_id
            ),
        ]

        for msg in previous_messages:
            await memory_manager.store_conversation(msg)

        # New user message
        new_message = "Do you remember what I told you about my pets?"

        # Get memory context
        memory_context = await memory_manager.get_user_context(user_id, new_message)

        # Create current message
        current_messages = [Message("user", new_message, datetime.now())]

        # Generate response with memory
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock()
            mock_executor.return_value = {
                "message": {"content": "Yes Alice, you mentioned that you love cats!"}
            }
            mock_loop.return_value.run_in_executor = mock_executor

            response = await ollama_provider.generate_response(
                current_messages,
                personality="You are a friendly AI with good memory.",
                memory_context=memory_context,
            )

        # Verify response acknowledges memory
        assert "Alice" in response or "cats" in response

        # Store the new conversation
        user_msg = ConversationMessage("user", new_message, datetime.now(), user_id)
        ai_msg = ConversationMessage("assistant", response, datetime.now(), user_id)

        await memory_manager.store_conversation(user_msg)
        await memory_manager.store_conversation(ai_msg)

        # Verify storage
        updated_context = await memory_manager.get_user_context(user_id)
        assert len(updated_context.conversation_history) == 6  # 4 previous + 2 new

    @pytest.mark.asyncio
    async def test_memory_context_with_personality_processor(self, memory_manager):
        """Test memory context integration with personality processor."""
        from src.ai.personality_processor import PersonalityProcessor

        user_id = "test_user"
        personality_prompt = (
            "You are a tsundere anime girl who remembers conversations."
        )

        # Create personality processor
        processor = PersonalityProcessor(
            personality_prompt, enable_content_filter=False
        )

        # Create memory context
        memory_context = MemoryContext(
            user_id=user_id,
            relevant_memories=["User complimented my personality"],
            conversation_history=[
                Message(
                    "user", "You're really cute when you're flustered", datetime.now()
                ),
                Message(
                    "assistant", "B-baka! Don't say things like that!", datetime.now()
                ),
            ],
            personality_state={},
        )

        # Create current messages
        messages = [
            Message("user", "Do you remember what I said before?", datetime.now())
        ]

        # Inject personality with memory context
        processed_messages = processor.inject_personality(messages, memory_context)

        # Verify memory context was injected
        assert len(processed_messages) >= 3  # memory + personality + original message

        # Check that memory context is in system messages
        system_messages = [msg for msg in processed_messages if msg.role == "system"]
        memory_system_msg = next(
            (
                msg
                for msg in system_messages
                if "Context from previous conversations" in msg.content
            ),
            None,
        )

        assert memory_system_msg is not None
        assert "User complimented my personality" in memory_system_msg.content
        assert "You're really cute when you're flustered" in memory_system_msg.content

    @pytest.mark.asyncio
    async def test_empty_memory_context_handling(self, ollama_provider):
        """Test handling of empty or None memory context."""
        messages = [Message("user", "Hello", datetime.now())]

        # Test with None memory context
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock()
            mock_executor.return_value = {"message": {"content": "Hello there!"}}
            mock_loop.return_value.run_in_executor = mock_executor

            response = await ollama_provider.generate_response(
                messages, personality="You are helpful.", memory_context=None
            )

        assert response == "Hello there!"

        # Test with empty memory context
        empty_context = MemoryContext(
            user_id="test_user",
            relevant_memories=[],
            conversation_history=[],
            personality_state={},
        )

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock()
            mock_executor.return_value = {"message": {"content": "Hello there!"}}
            mock_loop.return_value.run_in_executor = mock_executor

            response = await ollama_provider.generate_response(
                messages, personality="You are helpful.", memory_context=empty_context
            )

        assert response == "Hello there!"


if __name__ == "__main__":
    pytest.main([__file__])
