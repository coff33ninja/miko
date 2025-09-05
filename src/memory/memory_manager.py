"""
Memory management system with Mem0 integration for Anime AI Character.
Handles conversation history, user-specific memory isolation, and context retrieval.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import json

try:
    from mem0 import Memory
except ImportError:
    # Fallback for development/testing
    Memory = None

from src.config.settings import MemoryConfig
from src.error_handling.exceptions import MemoryError, NetworkError
from src.error_handling.fallback_manager import get_fallback_manager, FallbackStrategy
from src.error_handling.error_recovery import get_recovery_manager, RecoveryStrategy
from src.error_handling.logging_handler import get_error_logger


@dataclass
class ConversationMessage:
    """Represents a single conversation message."""

    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: datetime
    user_id: str
    sentiment: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "sentiment": self.sentiment,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationMessage":
        """Create from dictionary."""
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            user_id=data["user_id"],
            sentiment=data.get("sentiment"),
        )


@dataclass
class MemoryContext:
    """Context retrieved from memory for AI processing."""

    user_id: str
    relevant_memories: List[str]
    conversation_history: List[ConversationMessage]
    personality_state: Dict[str, Any]

    def format_for_ai(self) -> str:
        """Format memory context for AI prompt."""
        context_parts = []

        if self.relevant_memories:
            context_parts.append("Previous conversations and memories:")
            for memory in self.relevant_memories:
                context_parts.append(f"- {memory}")

        if self.conversation_history:
            context_parts.append("\nRecent conversation:")
            for msg in self.conversation_history[-5:]:
                role_display = "You" if msg.role == "assistant" else "User"
                context_parts.append(f"{role_display}: {msg.content}")

        return "\n".join(context_parts) if context_parts else ""


# MemoryError is now imported from error_handling.exceptions


class MemoryManager:
    """
    Manages conversation memory using Mem0 API with user isolation and context retrieval.

    Features:
    - User-specific memory isolation
    - Conversation history storage and retrieval
    - Semantic search for relevant context
    - Memory pruning and management
    - Fallback to session-only memory when Mem0 is unavailable
    """

    def __init__(self, config: MemoryConfig):
        """
        Initialize memory manager.

        Args:
            config: Memory configuration containing API key and settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._mem0_client: Optional[Any] = None
        self._session_memory: Dict[str, List[ConversationMessage]] = {}
        self._user_contexts: Dict[str, MemoryContext] = {}
        self._initialized = False

        # Error handling components
        self.fallback_manager = get_fallback_manager()
        self.recovery_manager = get_recovery_manager()
        self.error_logger = get_error_logger()

        # Connection tracking
        self.consecutive_failures = 0
        self.last_successful_operation = None
        self.mem0_available = False

    async def initialize(self) -> bool:
        """
        Initialize Mem0 client and validate connection with error handling.

        Returns:
            bool: True if Mem0 is available, False if using session-only fallback
        """
        if self._initialized:
            return self.mem0_available

        try:
            if not self.config.mem0_api_key:
                self.logger.warning(
                    "No Mem0 API key provided, using session-only memory"
                )
                self._initialized = True
                self.mem0_available = False
                self._register_error_recovery()
                return False

            if Memory is None:
                self.logger.error(
                    "mem0ai package not available, using session-only memory"
                )
                self._initialized = True
                self.mem0_available = False
                self._register_error_recovery()
                return False

            # Initialize Mem0 client with error handling
            result = await self.fallback_manager.execute_with_fallback(
                component="memory_manager",
                primary_operation=self._initialize_mem0_client,
                context={
                    "retry_operation": self._initialize_mem0_client,
                    "max_retries": 3,
                },
            )

            if result.success:
                self.mem0_available = True
                self.consecutive_failures = 0
                self.last_successful_operation = datetime.now()
                await self.recovery_manager.record_success("memory_manager")
                self.logger.info("Mem0 client initialized successfully")
            else:
                self.mem0_available = False
                self.logger.warning(
                    "Failed to initialize Mem0, using session-only memory"
                )

            self._initialized = True
            self._register_error_recovery()
            return self.mem0_available

        except Exception as e:
            self.logger.error(f"Failed to initialize memory manager: {e}")
            self._initialized = True
            self.mem0_available = False
            self._register_error_recovery()
            return False

    async def _initialize_mem0_client(self) -> bool:
        """Initialize Mem0 client with connection test."""
        try:
            # Initialize Mem0 client
            self._mem0_client = Memory(api_key=self.config.mem0_api_key)

            # Test connection with a simple operation
            await self._test_connection()

            return True

        except Exception as e:
            if "api" in str(e).lower() or "key" in str(e).lower():
                raise MemoryError(
                    f"Mem0 API key error: {e}",
                    operation="initialize",
                    is_mem0_error=True,
                )
            elif "network" in str(e).lower() or "connection" in str(e).lower():
                raise NetworkError(
                    f"Mem0 connection error: {e}",
                    operation="initialize",
                    endpoint="mem0_api",
                )
            else:
                raise MemoryError(
                    f"Mem0 initialization error: {e}",
                    operation="initialize",
                    is_mem0_error=True,
                )

    async def _test_connection(self) -> None:
        """Test Mem0 connection with a simple query."""
        if not self._mem0_client:
            return

        try:
            # Try a simple search to test connection
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._mem0_client.search(
                    query="test", user_id="test_user", limit=1
                ),
            )
        except Exception as e:
            raise MemoryError(f"Mem0 connection test failed: {e}")

    async def add_memory(
        self, user_id: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a memory entry for a specific user with error handling and fallback.

        Args:
            user_id: Unique identifier for the user
            content: Memory content to store
            metadata: Optional metadata to associate with the memory

        Returns:
            bool: True if stored successfully, False otherwise
        """
        if not self._initialized:
            await self.initialize()

        # Always store in session memory as backup
        self._store_in_session_memory(user_id, content, metadata)

        # Try Mem0 if available
        if self.mem0_available and self._mem0_client:
            result = await self.fallback_manager.execute_with_fallback(
                component="memory_manager",
                primary_operation=self._add_memory_to_mem0,
                operation_args=(user_id, content, metadata),
                context={
                    "retry_operation": self._add_memory_to_mem0,
                    "max_retries": 3,
                    "user_id": user_id,
                },
            )

            if result.success:
                self.consecutive_failures = 0
                self.last_successful_operation = datetime.now()
                await self.recovery_manager.record_success("memory_manager")
                self.logger.debug(
                    f"Stored memory for user {user_id}: {content[:50]}..."
                )
                return True
            else:
                # Log fallback usage but continue with session-only
                self.error_logger.log_fallback_usage(
                    component="memory_manager",
                    fallback_strategy="session_only",
                    original_error=result.error,
                    fallback_success=True,
                )
                return True  # Session memory succeeded
        else:
            # Session-only mode
            self.logger.debug(
                f"Session-only memory add for user {user_id}: {content[:50]}..."
            )
            return True

    async def _add_memory_to_mem0(
        self, user_id: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add memory to Mem0 with error handling."""
        try:
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._mem0_client.add(
                        messages=[{"role": "user", "content": content}],
                        user_id=user_id,
                        metadata=metadata or {},
                    ),
                ),
                timeout=10.0,
            )
            return True

        except asyncio.TimeoutError:
            raise NetworkError(
                "Mem0 add operation timeout",
                operation="add_memory",
                endpoint="mem0_api",
                is_timeout=True,
            )
        except Exception as e:
            self.consecutive_failures += 1
            await self.recovery_manager.record_error(
                "memory_manager",
                MemoryError(
                    f"Failed to add memory to Mem0: {e}",
                    operation="add_memory",
                    user_id=user_id,
                    is_mem0_error=True,
                ),
            )
            raise

    def _store_in_session_memory(
        self, user_id: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ):
        """Store memory in session as backup."""
        if user_id not in self._session_memory:
            self._session_memory[user_id] = []

        # Create a simple memory entry for session storage
        memory_entry = {
            "content": content,
            "timestamp": datetime.now(),
            "metadata": metadata or {},
        }

        self._session_memory[user_id].append(memory_entry)

        # Prune if too many entries
        if len(self._session_memory[user_id]) > self.config.memory_history_limit * 2:
            self._session_memory[user_id] = self._session_memory[user_id][
                -self.config.memory_history_limit :
            ]

    async def search_memories(
        self, user_id: str, query: str, limit: int = 5
    ) -> List[str]:
        """
        Search for relevant memories for a user with fallback to session memory.

        Args:
            user_id: User identifier
            query: Search query
            limit: Maximum number of memories to return

        Returns:
            List[str]: List of relevant memory contents
        """
        if not self._initialized:
            await self.initialize()

        # Try Mem0 first if available
        if self.mem0_available and self._mem0_client:
            result = await self.fallback_manager.execute_with_fallback(
                component="memory_manager",
                primary_operation=self._search_memories_in_mem0,
                operation_args=(user_id, query, limit),
                context={
                    "retry_operation": self._search_memories_in_mem0,
                    "max_retries": 2,
                    "user_id": user_id,
                },
            )

            if result.success:
                self.consecutive_failures = 0
                self.last_successful_operation = datetime.now()
                await self.recovery_manager.record_success("memory_manager")
                return result.result
            else:
                # Fall back to session memory search
                return self._search_session_memories(user_id, query, limit)
        else:
            # Session-only mode
            return self._search_session_memories(user_id, query, limit)

    async def _search_memories_in_mem0(
        self, user_id: str, query: str, limit: int
    ) -> List[str]:
        """Search memories in Mem0 with error handling."""
        try:
            results = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._mem0_client.search(
                        query=query, user_id=user_id, limit=limit
                    ),
                ),
                timeout=10.0,
            )

            memories = []
            for result in results:
                if isinstance(result, dict) and "memory" in result:
                    memories.append(result["memory"])
                elif isinstance(result, str):
                    memories.append(result)

            self.logger.debug(f"Found {len(memories)} memories for user {user_id}")
            return memories

        except asyncio.TimeoutError:
            raise NetworkError(
                "Mem0 search operation timeout",
                operation="search_memories",
                endpoint="mem0_api",
                is_timeout=True,
            )
        except Exception as e:
            self.consecutive_failures += 1
            await self.recovery_manager.record_error(
                "memory_manager",
                MemoryError(
                    f"Failed to search memories in Mem0: {e}",
                    operation="search_memories",
                    user_id=user_id,
                    is_mem0_error=True,
                ),
            )
            raise

    def _search_session_memories(
        self, user_id: str, query: str, limit: int
    ) -> List[str]:
        """Search memories in session storage as fallback."""
        if user_id not in self._session_memory:
            return []

        memories = []
        query_lower = query.lower()

        # Simple keyword-based search in session memory
        for entry in reversed(self._session_memory[user_id]):  # Most recent first
            content = entry["content"].lower()
            if any(word in content for word in query_lower.split()):
                memories.append(entry["content"])
                if len(memories) >= limit:
                    break

        self.logger.debug(f"Found {len(memories)} session memories for user {user_id}")
        return memories

    async def store_conversation(self, message: ConversationMessage) -> bool:
        """
        Store a conversation message.

        Args:
            message: Conversation message to store

        Returns:
            bool: True if stored successfully
        """
        # Always store in session memory for immediate access
        if message.user_id not in self._session_memory:
            self._session_memory[message.user_id] = []

        self._session_memory[message.user_id].append(message)

        # Prune session memory if it gets too long
        await self._prune_session_memory(message.user_id)

        # Store in Mem0 if available
        if message.role in ["user", "assistant"]:
            content = f"{message.role}: {message.content}"
            if message.sentiment:
                content += f" (sentiment: {message.sentiment})"

            metadata = {
                "role": message.role,
                "timestamp": message.timestamp.isoformat(),
                "sentiment": message.sentiment,
            }

            return await self.add_memory(message.user_id, content, metadata)

        return True

    async def get_user_context(
        self, user_id: str, query: Optional[str] = None
    ) -> MemoryContext:
        """
        Get comprehensive context for a user including memories and recent conversation.

        Args:
            user_id: User identifier
            query: Optional query to search for relevant memories

        Returns:
            MemoryContext: User's memory context
        """
        if not self._initialized:
            await self.initialize()

        # Get recent conversation history from session memory
        conversation_history = self._session_memory.get(user_id, [])

        # Search for relevant memories if query provided
        relevant_memories = []
        if query:
            relevant_memories = await self.search_memories(user_id, query)

        # Get or create personality state
        existing_context = self._user_contexts.get(user_id)
        personality_state = (
            existing_context.personality_state if existing_context else {}
        )

        context = MemoryContext(
            user_id=user_id,
            relevant_memories=relevant_memories,
            conversation_history=conversation_history,
            personality_state=personality_state,
        )

        # Cache context for future use
        self._user_contexts[user_id] = context

        return context

    async def update_personality_state(
        self, user_id: str, state_updates: Dict[str, Any]
    ) -> None:
        """
        Update personality state for a user.

        Args:
            user_id: User identifier
            state_updates: Dictionary of state updates
        """
        if user_id not in self._user_contexts:
            self._user_contexts[user_id] = MemoryContext(
                user_id=user_id,
                relevant_memories=[],
                conversation_history=[],
                personality_state={},
            )

        self._user_contexts[user_id].personality_state.update(state_updates)

        # Store personality updates in Mem0 if available
        if state_updates:
            content = f"Personality update: {json.dumps(state_updates)}"
            await self.add_memory(user_id, content, {"type": "personality_state"})

    async def _prune_session_memory(self, user_id: str) -> None:
        """
        Prune session memory to stay within limits.

        Args:
            user_id: User identifier
        """
        if user_id not in self._session_memory:
            return

        messages = self._session_memory[user_id]
        limit = self.config.memory_history_limit

        if len(messages) > limit:
            # Keep the most recent messages
            self._session_memory[user_id] = messages[-limit:]
            self.logger.debug(
                f"Pruned session memory for user {user_id} to {limit} messages"
            )

    async def prune_old_memories(self, user_id: str, days_old: int = 30) -> int:
        """
        Prune old memories for a user (Mem0 only).

        Args:
            user_id: User identifier
            days_old: Remove memories older than this many days

        Returns:
            int: Number of memories removed
        """
        if not self._mem0_client:
            return 0

        try:
            # Get all memories for user
            all_memories = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._mem0_client.get_all(user_id=user_id)
            )

            cutoff_date = datetime.now() - timedelta(days=days_old)
            removed_count = 0

            for memory in all_memories:
                if isinstance(memory, dict) and "created_at" in memory:
                    try:
                        # Handle both timezone-aware and naive datetime strings
                        created_at_str = memory["created_at"]
                        if created_at_str.endswith("Z"):
                            created_at_str = created_at_str.replace("Z", "+00:00")

                        created_at = datetime.fromisoformat(created_at_str)

                        # Make cutoff_date timezone-aware if created_at is timezone-aware
                        if created_at.tzinfo is not None and cutoff_date.tzinfo is None:
                            from datetime import timezone

                            cutoff_date = cutoff_date.replace(tzinfo=timezone.utc)
                        elif (
                            created_at.tzinfo is None and cutoff_date.tzinfo is not None
                        ):
                            cutoff_date = cutoff_date.replace(tzinfo=None)

                        if created_at < cutoff_date and "id" in memory:
                            await asyncio.get_event_loop().run_in_executor(
                                None,
                                lambda mem_id=memory["id"]: self._mem0_client.delete(
                                    memory_id=mem_id
                                ),
                            )
                            removed_count += 1
                    except (ValueError, TypeError) as e:
                        self.logger.warning(
                            f"Failed to parse created_at for memory {memory.get('id', 'unknown')}: {e}"
                        )
                        continue

            self.logger.info(f"Pruned {removed_count} old memories for user {user_id}")
            return removed_count

        except Exception as e:
            self.logger.error(f"Failed to prune memories for user {user_id}: {e}")
            return 0

    async def delete_user_memories(self, user_id: str) -> bool:
        """
        Delete all memories for a specific user.

        Args:
            user_id: User identifier

        Returns:
            bool: True if deletion was successful
        """
        try:
            # Clear session memory
            if user_id in self._session_memory:
                del self._session_memory[user_id]

            if user_id in self._user_contexts:
                del self._user_contexts[user_id]

            # Clear Mem0 memories if available
            if self._mem0_client:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self._mem0_client.delete_all(user_id=user_id)
                )

            self.logger.info(f"Deleted all memories for user {user_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to delete memories for user {user_id}: {e}")
            return False

    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get statistics about current session memory usage.

        Returns:
            Dict[str, Any]: Memory usage statistics
        """
        stats = {
            "total_users": len(self._session_memory),
            "total_messages": sum(
                len(messages) for messages in self._session_memory.values()
            ),
            "mem0_available": self._mem0_client is not None,
            "initialized": self._initialized,
        }

        user_stats = {}
        for user_id, messages in self._session_memory.items():
            user_stats[user_id] = {
                "message_count": len(messages),
                "last_activity": (
                    messages[-1].timestamp.isoformat() if messages else None
                ),
            }

        stats["users"] = user_stats
        return stats

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check on memory system.

        Returns:
            Dict[str, Any]: Health check results
        """
        health = {
            "status": "healthy",
            "mem0_available": self.mem0_available,
            "session_memory_active": True,
            "consecutive_failures": self.consecutive_failures,
            "last_successful_operation": (
                self.last_successful_operation.isoformat()
                if self.last_successful_operation
                else None
            ),
            "errors": [],
        }

        try:
            if not self._initialized:
                await self.initialize()

            if self.mem0_available and self._mem0_client:
                # Test Mem0 connection
                try:
                    await asyncio.wait_for(self._test_connection(), timeout=5.0)
                    health["mem0_available"] = True
                except asyncio.TimeoutError:
                    health["status"] = "degraded"
                    health["errors"].append("Mem0 connection timeout")
                    health["mem0_available"] = False
                except Exception as e:
                    health["status"] = "degraded"
                    health["errors"].append(f"Mem0 connection error: {str(e)}")
                    health["mem0_available"] = False
            else:
                health["errors"].append("Mem0 not available, using session-only memory")

            # Check session memory health
            total_session_entries = sum(
                len(messages) for messages in self._session_memory.values()
            )
            health["session_memory_entries"] = total_session_entries
            health["session_memory_users"] = len(self._session_memory)

            # Determine overall status
            if health["errors"] and not health["mem0_available"]:
                health["status"] = "degraded"
            elif self.consecutive_failures > 5:
                health["status"] = "degraded"

        except Exception as e:
            health["status"] = "unhealthy"
            health["errors"].append(f"Health check failed: {str(e)}")

        return health

    def _register_error_recovery(self):
        """Register component with error recovery system."""
        self.recovery_manager.register_component(
            component_name="memory_manager",
            recovery_strategies=[
                RecoveryStrategy.RECONNECT,
                RecoveryStrategy.WAIT_AND_RETRY,
                RecoveryStrategy.CLEAR_STATE,
                RecoveryStrategy.REINITIALIZE,
            ],
            health_check_func=self.health_check,
        )

        # Register fallback strategies
        self.fallback_manager.register_fallback_chain(
            component="memory_manager",
            strategies=[
                FallbackStrategy.RETRY,
                FallbackStrategy.SESSION_ONLY,
                FallbackStrategy.SIMPLIFIED_RESPONSE,
            ],
        )