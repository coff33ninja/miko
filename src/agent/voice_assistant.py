"""
Voice Assistant utilities and helpers for the Anime AI Character system.
Provides enhanced voice processing capabilities and integration helpers.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime

from livekit import agents, rtc
from livekit.agents import JobContext
from livekit.agents.voice import Agent as VoiceAgent
from livekit.agents.llm import ChatContext, ChatMessage

from ..config.settings import AppConfig
from ..memory.memory_manager import MemoryManager, ConversationMessage


class EnhancedVoiceAssistant:
    """
    Enhanced VoiceAgent wrapper with additional anime character features.
    """

    def __init__(
        self, voice_agent: VoiceAgent, config: AppConfig, memory_manager: MemoryManager
    ):
        """
        Initialize enhanced voice assistant.

        Args:
            voice_agent: Base VoiceAgent instance
            config: Application configuration
            memory_manager: Memory manager for conversation storage
        """
        self.voice_agent = voice_agent
        self.config = config
        self.memory_manager = memory_manager
        self.logger = logging.getLogger(__name__)

        # Animation callbacks
        self.animation_callbacks: List[Callable[[str], None]] = []

        # User session tracking
        self.active_users: Dict[str, Dict[str, Any]] = {}

        # Set up event handlers
        self._setup_event_handlers()

    def _setup_event_handlers(self) -> None:
        """Set up event handlers for the voice agent."""
        # Note: The new VoiceAgent API may have different event handling
        # This is a placeholder for future event handler setup
        pass

    async def _handle_user_speech(
        self, user_msg: str, participant: rtc.RemoteParticipant
    ) -> None:
        """
        Handle user speech with enhanced processing.

        Args:
            user_msg: User's speech text
            participant: Participant who spoke
        """
        try:
            user_id = participant.identity

            # Update user session info
            self.active_users[user_id] = {
                "last_activity": datetime.now(),
                "participant": participant,
                "message_count": self.active_users.get(user_id, {}).get(
                    "message_count", 0
                )
                + 1,
            }

            self.logger.info(f"Processing speech from {user_id}: {user_msg[:50]}...")

            # Store in memory (this will also be done by the LLM, but we want immediate storage)
            user_conv_msg = ConversationMessage(
                role="user", content=user_msg, timestamp=datetime.now(), user_id=user_id
            )
            await self.memory_manager.store_conversation(user_conv_msg)

        except Exception as e:
            self.logger.error(f"Error handling user speech: {e}")

    def add_animation_callback(self, callback: Callable[[str], None]) -> None:
        """
        Add a callback for animation triggers.

        Args:
            callback: Function to call when animation should be triggered
        """
        self.animation_callbacks.append(callback)

    async def trigger_animation(self, animation_type: str) -> None:
        """
        Trigger animation through registered callbacks.

        Args:
            animation_type: Type of animation to trigger
        """
        for callback in self.animation_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(animation_type)
                else:
                    callback(animation_type)
            except Exception as e:
                self.logger.error(f"Animation callback error: {e}")

    def start(self, room: rtc.Room) -> None:
        """
        Start the enhanced voice agent.

        Args:
            room: LiveKit room to operate in
        """
        self.voice_agent.start(room)
        self.logger.info("Enhanced VoiceAgent started")

    async def say(
        self, message: str, participant: Optional[rtc.RemoteParticipant] = None
    ) -> None:
        """
        Make the assistant speak a message.

        Args:
            message: Message to speak
            participant: Optional specific participant to address
        """
        try:
            # Store assistant message in memory
            if participant:
                user_id = participant.identity
                ai_conv_msg = ConversationMessage(
                    role="assistant",
                    content=message,
                    timestamp=datetime.now(),
                    user_id=user_id,
                )
                await self.memory_manager.store_conversation(ai_conv_msg)

            # Use the voice agent's say method if available
            if hasattr(self.voice_agent, "say"):
                await self.voice_agent.say(message)
            else:
                self.logger.warning("VoiceAgent.say method not available")

        except Exception as e:
            self.logger.error(f"Error in say method: {e}")

    def get_active_users(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about currently active users.

        Returns:
            Dict containing active user information
        """
        return self.active_users.copy()

    async def cleanup_inactive_users(self, timeout_minutes: int = 30) -> None:
        """
        Clean up inactive user sessions.

        Args:
            timeout_minutes: Minutes of inactivity before cleanup
        """
        from datetime import timedelta

        cutoff_time = datetime.now() - timedelta(minutes=timeout_minutes)
        inactive_users = []

        for user_id, user_info in self.active_users.items():
            if user_info["last_activity"] < cutoff_time:
                inactive_users.append(user_id)

        for user_id in inactive_users:
            del self.active_users[user_id]
            self.logger.info(f"Cleaned up inactive user session: {user_id}")


class VoiceAssistantFactory:
    """
    Factory for creating configured VoiceAssistant instances.
    """

    @staticmethod
    def create_voice_assistant(
        config: AppConfig, memory_manager: MemoryManager, llm: Any, stt: Any, tts: Any
    ) -> EnhancedVoiceAssistant:
        """
        Create a configured VoiceAgent instance.

        Args:
            config: Application configuration
            memory_manager: Memory manager instance
            llm: Language model instance
            stt: Speech-to-text provider
            tts: Text-to-speech provider

        Returns:
            EnhancedVoiceAssistant: Configured voice assistant
        """
        from livekit.plugins import silero

        # Create base VoiceAgent
        base_agent = VoiceAgent(
            instructions=config.personality.personality_prompt,
            vad=silero.VAD.load(),
            stt=stt,
            llm=llm,
            tts=tts,
            chat_ctx=ChatContext(),
        )

        # Wrap in enhanced assistant
        enhanced_assistant = EnhancedVoiceAssistant(
            voice_agent=base_agent, config=config, memory_manager=memory_manager
        )

        return enhanced_assistant


class AgentEventHandler:
    """
    Event handler for LiveKit agent events.
    """

    def __init__(self, agent: "AnimeAIAgent"):
        """
        Initialize event handler.

        Args:
            agent: Reference to the main agent
        """
        self.agent = agent
        self.logger = logging.getLogger(__name__)

    async def on_participant_connected(
        self, participant: rtc.RemoteParticipant
    ) -> None:
        """
        Handle participant connection.

        Args:
            participant: Connected participant
        """
        self.logger.info(f"Participant connected: {participant.identity}")

        # Send welcome message
        welcome_msg = (
            "Konnichiwa! I'm Miko, your anime AI companion! (*excited wave*) "
            "You can talk to me using your voice, and I'll remember our conversations! "
            "What would you like to chat about? (＾◡＾)"
        )

        if hasattr(self.agent, "voice_assistant") and self.agent.voice_assistant:
            await self.agent.voice_assistant.say(welcome_msg, participant)

    async def on_participant_disconnected(
        self, participant: rtc.RemoteParticipant
    ) -> None:
        """
        Handle participant disconnection.

        Args:
            participant: Disconnected participant
        """
        self.logger.info(f"Participant disconnected: {participant.identity}")

        # Clean up user session if needed
        if hasattr(self.agent, "voice_assistant") and self.agent.voice_assistant:
            active_users = self.agent.voice_assistant.get_active_users()
            if participant.identity in active_users:
                del active_users[participant.identity]

    async def on_track_subscribed(
        self,
        track: rtc.Track,
        publication: rtc.TrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        """
        Handle track subscription (audio/video).

        Args:
            track: Subscribed track
            publication: Track publication
            participant: Participant who published the track
        """
        self.logger.info(f"Track subscribed: {track.kind} from {participant.identity}")

    async def on_track_unsubscribed(
        self,
        track: rtc.Track,
        publication: rtc.TrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        """
        Handle track unsubscription.

        Args:
            track: Unsubscribed track
            publication: Track publication
            participant: Participant who published the track
        """
        self.logger.info(
            f"Track unsubscribed: {track.kind} from {participant.identity}"
        )
