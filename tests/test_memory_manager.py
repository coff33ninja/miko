"""
Unit tests for memory management system.
Tests MemoryManager functionality including Mem0 integration, session memory, and error handling.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any

from src.memory.memory_manager import (
    MemoryManager,
    ConversationMessage,
    MemoryContext,
    MemoryError,
)
from src.config.settings import MemoryConfig


@pytest.fixture
def memory_config():
    """Create test memory configuration."""
    return MemoryConfig(
        mem0_api_key="test_api_key",
        mem0_collection="test_collection",
        memory_history_limit=10,
    )


@pytest.fixture
def memory_config_no_key():
    """Create test memory configuration without API key."""
    return MemoryConfig(
        mem0_api_key="", mem0_collection="test_collection", memory_history_limit=10
    )


@pytest.fixture
def sample_message():
    """Create a sample conversation message."""
    return ConversationMessage(
        role="user",
        content="Hello, how are you?",
        timestamp=datetime.now(),
        user_id="test_user",
        sentiment="positive",
    )


@pytest.fixture
def sample_messages():
    """Create multiple sample conversation messages."""
    base_time = datetime.now()
    return [
        ConversationMessage(
            role="user", content="Hello!", timestamp=base_time, user_id="test_user"
        ),
        ConversationMessage(
            role="assistant",
            content="Hi there! How can I help you?",
            timestamp=base_time + timedelta(seconds=1),
            user_id="test_user",
            sentiment="friendly",
        ),
        ConversationMessage(
            role="user",
            content="Tell me a joke",
            timestamp=base_time + timedelta(seconds=2),
            user_id="test_user",
        ),
    ]


class TestConversationMessage:
    """Test ConversationMessage data class."""

    def test_message_creation(self, sample_message):
        """Test creating a conversation message."""
        assert sample_message.role == "user"
        assert sample_message.content == "Hello, how are you?"
        assert sample_message.user_id == "test_user"
        assert sample_message.sentiment == "positive"
        assert isinstance(sample_message.timestamp, datetime)

    def test_message_to_dict(self, sample_message):
        """Test converting message to dictionary."""
        msg_dict = sample_message.to_dict()

        assert msg_dict["role"] == "user"
        assert msg_dict["content"] == "Hello, how are you?"
        assert msg_dict["user_id"] == "test_user"
        assert msg_dict["sentiment"] == "positive"
        assert "timestamp" in msg_dict

    def test_message_from_dict(self, sample_message):
        """Test creating message from dictionary."""
        msg_dict = sample_message.to_dict()
        restored_message = ConversationMessage.from_dict(msg_dict)

        assert restored_message.role == sample_message.role
        assert restored_message.content == sample_message.content
        assert restored_message.user_id == sample_message.user_id
        assert restored_message.sentiment == sample_message.sentiment
        assert restored_message.timestamp == sample_message.timestamp


class TestMemoryContext:
    """Test MemoryContext data class."""

    def test_context_creation(self, sample_messages):
        """Test creating memory context."""
        context = MemoryContext(
            user_id="test_user",
            relevant_memories=["Previous conversation about weather"],
            conversation_history=sample_messages,
            personality_state={"mood": "happy"},
        )

        assert context.user_id == "test_user"
        assert len(context.relevant_memories) == 1
        assert len(context.conversation_history) == 3
        assert context.personality_state["mood"] == "happy"

    def test_format_for_ai_with_memories_and_history(self, sample_messages):
        """Test formatting context for AI with both memories and history."""
        context = MemoryContext(
            user_id="test_user",
            relevant_memories=["User likes jokes", "User is friendly"],
            conversation_history=sample_messages,
            personality_state={},
        )

        formatted = context.format_for_ai()

        assert "Previous conversations and memories:" in formatted
        assert "User likes jokes" in formatted
        assert "User is friendly" in formatted
        assert "Recent conversation:" in formatted
        assert "User: Hello!" in formatted
        assert "You: Hi there!" in formatted

    def test_format_for_ai_empty_context(self):
        """Test formatting empty context."""
        context = MemoryContext(
            user_id="test_user",
            relevant_memories=[],
            conversation_history=[],
            personality_state={},
        )

        formatted = context.format_for_ai()
        assert formatted == ""

    def test_format_for_ai_only_recent_messages(self, sample_messages):
        """Test that only recent messages are included in formatting."""
        # Create more than 5 messages
        many_messages = []
        base_time = datetime.now()
        for i in range(10):
            many_messages.append(
                ConversationMessage(
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"Message {i}",
                    timestamp=base_time + timedelta(seconds=i),
                    user_id="test_user",
                )
            )

        context = MemoryContext(
            user_id="test_user",
            relevant_memories=[],
            conversation_history=many_messages,
            personality_state={},
        )

        formatted = context.format_for_ai()

        # Should only include last 5 messages (messages 5-9)
        assert "Message 9" in formatted
        assert "Message 5" in formatted
        assert "Message 4" not in formatted
        assert "Message 0" not in formatted


class TestMemoryManager:
    """Test MemoryManager class."""

    @pytest.mark.asyncio
    async def test_initialization_with_api_key(self, memory_config):
        """Test memory manager initialization with API key."""
        with patch("src.memory.memory_manager.Memory") as mock_memory_class:
            mock_client = Mock()
            mock_memory_class.return_value = mock_client

            # Mock the search method for connection test
            mock_client.search.return_value = []

            manager = MemoryManager(memory_config)
            result = await manager.initialize()

            assert result is True
            assert manager._mem0_client is not None
            mock_memory_class.assert_called_once_with(api_key="test_api_key")

    @pytest.mark.asyncio
    async def test_initialization_without_api_key(self, memory_config_no_key):
        """Test memory manager initialization without API key."""
        manager = MemoryManager(memory_config_no_key)
        result = await manager.initialize()

        assert result is False
        assert manager._mem0_client is None
        assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_initialization_mem0_import_error(self, memory_config):
        """Test initialization when mem0 package is not available."""
        with patch("src.memory.memory_manager.Memory", None):
            manager = MemoryManager(memory_config)
            result = await manager.initialize()

            assert result is False
            assert manager._mem0_client is None

    @pytest.mark.asyncio
    async def test_initialization_connection_error(self, memory_config):
        """Test initialization when Mem0 connection fails."""
        with patch("src.memory.memory_manager.Memory") as mock_memory_class:
            mock_client = Mock()
            mock_memory_class.return_value = mock_client

            # Mock connection test to fail
            mock_client.search.side_effect = Exception("Connection failed")

            manager = MemoryManager(memory_config)

            with pytest.raises(MemoryError):
                await manager.initialize()

    @pytest.mark.asyncio
    async def test_add_memory_with_mem0(self, memory_config):
        """Test adding memory with Mem0 client."""
        with patch("src.memory.memory_manager.Memory") as mock_memory_class:
            mock_client = Mock()
            mock_memory_class.return_value = mock_client
            mock_client.search.return_value = []
            mock_client.add.return_value = {"id": "test_id"}

            manager = MemoryManager(memory_config)
            await manager.initialize()

            result = await manager.add_memory("test_user", "Test memory content")

            assert result is True
            mock_client.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_memory_without_mem0(self, memory_config_no_key):
        """Test adding memory without Mem0 client (session-only)."""
        manager = MemoryManager(memory_config_no_key)
        await manager.initialize()

        result = await manager.add_memory("test_user", "Test memory content")

        assert result is True  # Should succeed in session-only mode

    @pytest.mark.asyncio
    async def test_search_memories_with_mem0(self, memory_config):
        """Test searching memories with Mem0 client."""
        with patch("src.memory.memory_manager.Memory") as mock_memory_class:
            mock_client = Mock()
            mock_memory_class.return_value = mock_client
            mock_client.search.side_effect = [
                [],  # For connection test
                [
                    {"memory": "Found memory 1"},
                    {"memory": "Found memory 2"},
                ],  # For actual search
            ]

            manager = MemoryManager(memory_config)
            await manager.initialize()

            memories = await manager.search_memories("test_user", "test query", limit=5)

            assert len(memories) == 2
            assert "Found memory 1" in memories
            assert "Found memory 2" in memories

    @pytest.mark.asyncio
    async def test_search_memories_without_mem0(self, memory_config_no_key):
        """Test searching memories without Mem0 client."""
        manager = MemoryManager(memory_config_no_key)
        await manager.initialize()

        memories = await manager.search_memories("test_user", "test query")

        assert memories == []

    @pytest.mark.asyncio
    async def test_store_conversation(self, memory_config, sample_message):
        """Test storing conversation message."""
        with patch("src.memory.memory_manager.Memory") as mock_memory_class:
            mock_client = Mock()
            mock_memory_class.return_value = mock_client
            mock_client.search.return_value = []
            mock_client.add.return_value = {"id": "test_id"}

            manager = MemoryManager(memory_config)
            await manager.initialize()

            result = await manager.store_conversation(sample_message)

            assert result is True
            # Check session memory
            assert "test_user" in manager._session_memory
            assert len(manager._session_memory["test_user"]) == 1
            assert manager._session_memory["test_user"][0] == sample_message

    @pytest.mark.asyncio
    async def test_session_memory_pruning(self, memory_config):
        """Test that session memory is pruned when it exceeds limits."""
        manager = MemoryManager(memory_config)
        await manager.initialize()

        # Add more messages than the limit
        base_time = datetime.now()
        for i in range(15):  # Limit is 10
            message = ConversationMessage(
                role="user",
                content=f"Message {i}",
                timestamp=base_time + timedelta(seconds=i),
                user_id="test_user",
            )
            await manager.store_conversation(message)

        # Should only keep the last 10 messages
        assert len(manager._session_memory["test_user"]) == 10
        assert manager._session_memory["test_user"][0].content == "Message 5"
        assert manager._session_memory["test_user"][-1].content == "Message 14"

    @pytest.mark.asyncio
    async def test_get_user_context(self, memory_config, sample_messages):
        """Test getting user context."""
        with patch("src.memory.memory_manager.Memory") as mock_memory_class:
            mock_client = Mock()
            mock_memory_class.return_value = mock_client
            mock_client.search.side_effect = [
                [],  # For connection test
                [{"memory": "Relevant memory"}],  # For context search
            ]

            manager = MemoryManager(memory_config)
            await manager.initialize()

            # Store some conversation history
            for message in sample_messages:
                await manager.store_conversation(message)

            context = await manager.get_user_context("test_user", "test query")

            assert context.user_id == "test_user"
            assert len(context.conversation_history) == 3
            assert len(context.relevant_memories) == 1
            assert "Relevant memory" in context.relevant_memories

    @pytest.mark.asyncio
    async def test_update_personality_state(self, memory_config):
        """Test updating personality state."""
        with patch("src.memory.memory_manager.Memory") as mock_memory_class:
            mock_client = Mock()
            mock_memory_class.return_value = mock_client
            mock_client.search.return_value = []
            mock_client.add.return_value = {"id": "test_id"}

            manager = MemoryManager(memory_config)
            await manager.initialize()

            await manager.update_personality_state(
                "test_user", {"mood": "happy", "energy": "high"}
            )

            # Check that personality state is stored
            context = await manager.get_user_context("test_user")
            assert context.personality_state["mood"] == "happy"
            assert context.personality_state["energy"] == "high"

    @pytest.mark.asyncio
    async def test_delete_user_memories(self, memory_config, sample_messages):
        """Test deleting all memories for a user."""
        with patch("src.memory.memory_manager.Memory") as mock_memory_class:
            mock_client = Mock()
            mock_memory_class.return_value = mock_client
            mock_client.search.return_value = []
            mock_client.delete_all.return_value = True

            manager = MemoryManager(memory_config)
            await manager.initialize()

            # Store some data
            for message in sample_messages:
                await manager.store_conversation(message)

            assert "test_user" in manager._session_memory

            result = await manager.delete_user_memories("test_user")

            assert result is True
            assert "test_user" not in manager._session_memory
            mock_client.delete_all.assert_called_once_with(user_id="test_user")

    @pytest.mark.asyncio
    async def test_prune_old_memories(self, memory_config):
        """Test pruning old memories."""
        with patch("src.memory.memory_manager.Memory") as mock_memory_class:
            mock_client = Mock()
            mock_memory_class.return_value = mock_client
            mock_client.search.return_value = []

            # Mock old memories
            old_date = (datetime.now() - timedelta(days=35)).isoformat() + "Z"
            recent_date = (datetime.now() - timedelta(days=5)).isoformat() + "Z"

            mock_client.get_all.return_value = [
                {"id": "old_1", "created_at": old_date},
                {"id": "recent_1", "created_at": recent_date},
                {"id": "old_2", "created_at": old_date},
            ]
            mock_client.delete.return_value = True

            manager = MemoryManager(memory_config)
            await manager.initialize()

            removed_count = await manager.prune_old_memories("test_user", days_old=30)

            assert removed_count == 2
            assert mock_client.delete.call_count == 2

    def test_get_session_stats(self, memory_config, sample_messages):
        """Test getting session statistics."""
        manager = MemoryManager(memory_config)

        # Add some session data
        for message in sample_messages:
            if message.user_id not in manager._session_memory:
                manager._session_memory[message.user_id] = []
            manager._session_memory[message.user_id].append(message)

        stats = manager.get_session_stats()

        assert stats["total_users"] == 1
        assert stats["total_messages"] == 3
        assert "mem0_available" in stats
        assert "users" in stats
        assert "test_user" in stats["users"]
        assert stats["users"]["test_user"]["message_count"] == 3

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, memory_config):
        """Test health check when system is healthy."""
        with patch("src.memory.memory_manager.Memory") as mock_memory_class:
            mock_client = Mock()
            mock_memory_class.return_value = mock_client
            mock_client.search.return_value = []

            manager = MemoryManager(memory_config)

            health = await manager.health_check()

            assert health["status"] == "healthy"
            assert health["mem0_available"] is True
            assert health["session_memory_active"] is True
            assert len(health["errors"]) == 0

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, memory_config_no_key):
        """Test health check when Mem0 is not available."""
        manager = MemoryManager(memory_config_no_key)

        health = await manager.health_check()

        assert health["status"] == "healthy"  # Still healthy with session-only
        assert health["mem0_available"] is False
        assert health["session_memory_active"] is True
        assert len(health["errors"]) == 1
        assert "Mem0 not available" in health["errors"][0]

    @pytest.mark.asyncio
    async def test_error_handling_in_add_memory(self, memory_config):
        """Test error handling when adding memory fails."""
        with patch("src.memory.memory_manager.Memory") as mock_memory_class:
            mock_client = Mock()
            mock_memory_class.return_value = mock_client
            mock_client.search.return_value = []
            mock_client.add.side_effect = Exception("API Error")

            manager = MemoryManager(memory_config)
            await manager.initialize()

            result = await manager.add_memory("test_user", "Test content")

            assert result is False

    @pytest.mark.asyncio
    async def test_error_handling_in_search_memories(self, memory_config):
        """Test error handling when searching memories fails."""
        with patch("src.memory.memory_manager.Memory") as mock_memory_class:
            mock_client = Mock()
            mock_memory_class.return_value = mock_client
            mock_client.search.side_effect = [
                [],  # For connection test
                Exception("Search failed"),  # For actual search
            ]

            manager = MemoryManager(memory_config)
            await manager.initialize()

            memories = await manager.search_memories("test_user", "test query")

            assert memories == []


if __name__ == "__main__":
    pytest.main([__file__])
