"""
Base AI Provider interface for the Anime AI Character system.
Defines the contract that all AI providers must implement.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Message:
    """Represents a conversation message."""

    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: Optional[datetime] = None


@dataclass
class MemoryContext:
    """Memory context for AI processing."""

    user_id: str
    relevant_memories: List[str]
    conversation_history: List["Message"]
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


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the AI provider with configuration."""
        self.config = config
        self.personality_processor = None

    def set_personality_processor(self, processor):
        """Set the personality processor for this provider."""
        self.personality_processor = processor

    @abstractmethod
    async def generate_response(
        self,
        messages: List[Message],
        personality: str = None,
        memory_context: Optional[MemoryContext] = None,
    ) -> str:
        """
        Generate a response based on conversation messages, personality, and memory context.

        Args:
            messages: List of conversation messages
            personality: Personality prompt to inject (optional if processor is set)
            memory_context: Memory context from previous conversations (optional)

        Returns:
            Generated response string
        """
        pass

    async def generate_processed_response(
        self,
        messages: List[Message],
        personality: str = None,
        memory_context: Optional[MemoryContext] = None,
    ):
        """
        Generate and process response with personality injection, memory context, and sentiment analysis.

        Args:
            messages: List of conversation messages
            personality: Personality prompt to inject
            memory_context: Memory context from previous conversations

        Returns:
            ProcessedResponse object with enhanced content and metadata
        """
        if self.personality_processor:
            # Use personality processor for enhanced response
            processed_messages = self.personality_processor.inject_personality(
                messages, memory_context
            )
            raw_response = await self.generate_response(
                processed_messages, personality, memory_context
            )
            return self.personality_processor.process_response(
                raw_response, self.get_provider_name()
            )
        else:
            # Fallback to basic response
            raw_response = await self.generate_response(
                messages, personality, memory_context
            )
            # Create a basic ProcessedResponse-like object
            from src.ai.personality_processor import ProcessedResponse, Sentiment

            return ProcessedResponse(
                content=raw_response,
                sentiment=Sentiment.NEUTRAL,
                animation_trigger="idle",
                confidence=0.5,
            )

    @abstractmethod
    async def validate_content(self, content: str) -> bool:
        """
        Validate if content is appropriate for processing.

        Args:
            content: Content to validate

        Returns:
            True if content is appropriate, False otherwise
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name of the provider."""
        pass

    @abstractmethod
    def supports_content_filtering(self) -> bool:
        """Return whether this provider supports content filtering."""
        pass