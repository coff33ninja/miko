"""
LiveKit agent implementation for Anime AI Character system.
Handles real-time voice interactions with AI providers and memory integration.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

import livekit
from livekit import agents, rtc
from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent as VoiceAgent
from livekit.agents.llm import LLM, ChatContext, ChatMessage
from livekit.agents.stt import STT
from livekit.agents.tts import TTS
from livekit.plugins import openai, silero, deepgram

from ..config.settings import AppConfig
from ..ai.provider_factory import ProviderFactory
from ..memory.memory_manager import MemoryManager, ConversationMessage
from ..web.app import trigger_animation
from ..web.animation_sync import get_animation_synchronizer, AnimationPriority
from ..error_handling.exceptions import LiveKitError, AIProviderError, MemoryError
from ..error_handling.fallback_manager import get_fallback_manager, FallbackStrategy
from ..error_handling.error_recovery import get_recovery_manager, RecoveryStrategy
from ..error_handling.logging_handler import get_error_logger


class AnimeAILLM(LLM):
    """
    Custom LLM wrapper that integrates with our AI providers and memory system.
    """
    
    def __init__(self, config: AppConfig, memory_manager: MemoryManager):
        """
        Initialize the custom LLM.
        
        Args:
            config: Application configuration
            memory_manager: Memory manager instance
        """
        self.config = config
        self.memory_manager = memory_manager
        self.ai_provider = ProviderFactory.create_provider()
        self.logger = logging.getLogger(__name__)
        self.animation_sync = get_animation_synchronizer()
        
        # Error handling components
        self.fallback_manager = get_fallback_manager()
        self.recovery_manager = get_recovery_manager()
        self.error_logger = get_error_logger()
        
        # Connection tracking
        self.consecutive_failures = 0
        self.last_successful_response = time.time()
        self.connection_healthy = True
        
    async def chat(
        self,
        *,
        chat_ctx: ChatContext,
        conn_handle: Optional[Any] = None,
        fnc_ctx: Optional[Any] = None,
    ) -> "LLMStream":
        """
        Process chat messages and generate responses with comprehensive error handling.
        
        Args:
            chat_ctx: Chat context with conversation history
            conn_handle: Connection handle (unused)
            fnc_ctx: Function context (unused)
            
        Returns:
            LLMStream: Stream of response content
        """
        user_id = getattr(chat_ctx, 'user_id', 'default_user')
        
        result = await self.fallback_manager.execute_with_fallback(
            component="livekit_llm",
            primary_operation=self._process_chat_internal,
            operation_args=(chat_ctx, user_id),
            context={
                'user_id': user_id,
                'retry_operation': self._process_chat_internal,
                'max_retries': 3
            }
        )
        
        if result.success:
            return result.result
        else:
            return self._handle_chat_failure(result, user_id)
    
    async def _process_chat_internal(self, chat_ctx: ChatContext, user_id: str) -> "AnimeAILLMStream":
        """Internal chat processing with error handling."""
        try:
            # Get the latest user message
            user_message = None
            for msg in reversed(chat_ctx.messages):
                if msg.role == "user":
                    user_message = msg.content
                    break
            
            if not user_message:
                self.logger.warning("No user message found in chat context")
                return AnimeAILLMStream("I didn't hear anything. Could you say that again? (*confused*)")
            
            # Store user message in memory with error handling
            try:
                user_conv_msg = ConversationMessage(
                    role="user",
                    content=user_message,
                    timestamp=datetime.now(),
                    user_id=user_id
                )
                await self.memory_manager.store_conversation(user_conv_msg)
            except Exception as memory_error:
                self.logger.warning(f"Failed to store user message in memory: {memory_error}")
                # Continue without memory storage
            
            # Get memory context for AI processing
            memory_context = None
            try:
                memory_context = await self.memory_manager.get_user_context(user_id, user_message)
            except Exception as memory_error:
                self.logger.warning(f"Failed to get memory context: {memory_error}")
                # Continue without memory context
            
            # Convert chat context to our message format
            from ..ai.base_provider import Message
            messages = []
            for msg in chat_ctx.messages:
                messages.append(Message(
                    role=msg.role,
                    content=msg.content,
                    timestamp=datetime.now()
                ))
            
            # Generate AI response with memory context and error handling
            try:
                response = await asyncio.wait_for(
                    self.ai_provider.generate_response(
                        messages, 
                        self.config.personality.personality_prompt,
                        memory_context
                    ),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                raise AIProviderError(
                    "AI response generation timeout",
                    provider=self.ai_provider.get_provider_name(),
                    details={"timeout": 30.0}
                )
            
            # Store AI response in memory
            try:
                ai_conv_msg = ConversationMessage(
                    role="assistant",
                    content=response,
                    timestamp=datetime.now(),
                    user_id=user_id
                )
                await self.memory_manager.store_conversation(ai_conv_msg)
            except Exception as memory_error:
                self.logger.warning(f"Failed to store AI response in memory: {memory_error}")
                # Continue without memory storage
            
            # Trigger animation based on response sentiment with error handling
            try:
                await self._trigger_synchronized_animation(response, user_message)
            except Exception as animation_error:
                self.logger.warning(f"Failed to trigger animation: {animation_error}")
                # Continue without animation
            
            # Record successful operation
            self.consecutive_failures = 0
            self.last_successful_response = time.time()
            self.connection_healthy = True
            await self.recovery_manager.record_success("livekit_llm")
            
            self.logger.info(f"Generated response for user {user_id}: {response[:50]}...")
            
            return AnimeAILLMStream(response)
            
        except Exception as e:
            self.consecutive_failures += 1
            await self.recovery_manager.record_error("livekit_llm", e)
            
            # Classify and handle different error types
            if isinstance(e, AIProviderError):
                raise e
            elif isinstance(e, MemoryError):
                # Memory errors shouldn't stop chat processing
                self.logger.warning(f"Memory error in chat processing: {e}")
                return AnimeAILLMStream("I'm having some memory issues, but let's keep chatting! (*smile*)")
            else:
                raise LiveKitError(
                    f"Chat processing error: {e}",
                    operation="chat_processing",
                    participant_id=user_id
                )
    
    def _handle_chat_failure(self, result, user_id: str) -> "AnimeAILLMStream":
        """Handle complete chat processing failure."""
        self.error_logger.log_fallback_usage(
            component="livekit_llm",
            fallback_strategy=result.strategy_used.value if result.strategy_used else "none",
            original_error=result.error,
            fallback_success=False
        )
        
        # Return character-appropriate error message
        error_responses = [
            "Gomen! Something went wrong... (*nervous laugh*) Could you try again?",
            "Eh? I'm having trouble understanding right now... (*confused*)",
            "My brain feels a bit fuzzy... Could you repeat that? (*dizzy*)",
            "Something's not working right... But I'm still here! (*determined*)"
        ]
        
        import random
        return AnimeAILLMStream(random.choice(error_responses))
    
    async def _trigger_synchronized_animation(self, response: str, user_message: str) -> None:
        """
        Trigger synchronized Live2D animation with comprehensive error handling.
        
        Args:
            response: AI response text
            user_message: Original user message for context
        """
        result = await self.fallback_manager.execute_with_fallback(
            component="animation_sync",
            primary_operation=self._trigger_animation_internal,
            operation_args=(response, user_message),
            context={
                'retry_operation': self._trigger_animation_internal,
                'max_retries': 2,
                'response_text': response
            }
        )
        
        if not result.success:
            # Log animation failure but don't raise error
            self.error_logger.log_fallback_usage(
                component="animation_sync",
                fallback_strategy=result.strategy_used.value if result.strategy_used else "none",
                original_error=result.error,
                fallback_success=False
            )
    
    async def _trigger_animation_internal(self, response: str, user_message: str) -> bool:
        """Internal animation triggering with error handling."""
        try:
            # Analyze sentiment for expression selection
            expression = self._analyze_response_sentiment(response)
            
            # Calculate response characteristics
            intensity = self._calculate_expression_intensity(response, user_message)
            
            # Estimate TTS processing delay based on response length
            tts_delay = min(0.5, len(response) / 200)  # Rough estimate
            
            # Try synchronized animation first
            try:
                sequence_id = await asyncio.wait_for(
                    self.animation_sync.synchronize_with_tts(
                        text=response,
                        expression=expression,
                        tts_processing_delay=tts_delay
                    ),
                    timeout=5.0
                )
                
                if sequence_id:
                    self.logger.info(f"Synchronized animation triggered: {expression} ({sequence_id})")
                    return True
            except asyncio.TimeoutError:
                self.logger.warning("Animation sync timeout, falling back to direct trigger")
            except Exception as sync_error:
                self.logger.warning(f"Animation sync failed: {sync_error}")
            
            # Fallback to direct API call
            success = await asyncio.wait_for(
                trigger_animation(expression, intensity),
                timeout=3.0
            )
            
            if success:
                self.logger.info(f"Direct animation triggered: {expression}")
                return True
            else:
                raise Exception("Direct animation trigger returned False")
            
        except asyncio.TimeoutError:
            raise Exception("Animation trigger timeout")
        except Exception as e:
            raise Exception(f"Animation trigger failed: {e}")
    
    def _analyze_response_sentiment(self, response: str) -> str:
        """
        Analyze response sentiment for expression selection.
        
        Args:
            response: AI response text
            
        Returns:
            str: Expression name
        """
        response_lower = response.lower()
        
        # Tsundere-specific expressions
        if any(word in response_lower for word in ['baka', 'stupid', 'hmph', 'idiot']):
            return 'angry'
        elif any(word in response_lower for word in ['blush', 'embarrassed', '(*blush*)', 'b-but']):
            return 'embarrassed'
        elif any(word in response_lower for word in ['happy', 'yay', 'excited', '(*happy*)', 'great']):
            return 'happy'
        elif any(word in response_lower for word in ['sad', 'sorry', 'gomen', '(*sad*)', 'worried']):
            return 'sad'
        elif any(word in response_lower for word in ['surprised', 'wow', 'eh?', '(*surprised*)']):
            return 'surprised'
        elif '?' in response or any(word in response_lower for word in ['what', 'huh', 'confused']):
            return 'surprised'
        else:
            return 'speak'  # Default speaking expression
    
    def _calculate_expression_intensity(self, response: str, user_message: str) -> float:
        """
        Calculate expression intensity based on response characteristics.
        
        Args:
            response: AI response text
            user_message: Original user message
            
        Returns:
            float: Expression intensity (0.0-1.0)
        """
        base_intensity = 0.7
        
        # Increase intensity for emotional keywords
        emotional_words = ['baka', 'stupid', 'amazing', 'terrible', 'love', 'hate']
        emotion_count = sum(1 for word in emotional_words if word in response.lower())
        intensity_boost = min(0.3, emotion_count * 0.1)
        
        # Increase intensity for exclamation marks
        exclamation_boost = min(0.2, response.count('!') * 0.05)
        
        # Increase intensity for longer responses (more engagement)
        length_boost = min(0.1, len(response) / 500)
        
        final_intensity = base_intensity + intensity_boost + exclamation_boost + length_boost
        
        return min(1.0, max(0.3, final_intensity))


class AnimeAILLMStream:
    """
    Simple stream implementation for LLM responses.
    """
    
    def __init__(self, content: str):
        """
        Initialize stream with content.
        
        Args:
            content: Response content
        """
        self.content = content
        self._sent = False
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if not self._sent:
            self._sent = True
            return self.content
        else:
            raise StopAsyncIteration


class AnimeAIAgent:
    """
    Main LiveKit agent for Anime AI Character interactions.
    Handles voice processing, AI responses, and memory management.
    """
    
    def __init__(self, config: AppConfig):
        """
        Initialize the Anime AI agent.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.memory_manager = MemoryManager(config.memory)
        self.voice_assistant: Optional[VoiceAssistant] = None
        
    async def initialize(self) -> None:
        """Initialize the agent components."""
        try:
            # Initialize memory manager
            mem0_available = await self.memory_manager.initialize()
            if mem0_available:
                self.logger.info("Memory manager initialized with Mem0")
            else:
                self.logger.info("Memory manager initialized with session-only fallback")
            
            self.logger.info("Anime AI Agent initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize agent: {e}")
            raise
    
    def create_voice_agent(self) -> VoiceAgent:
        """
        Create and configure the VoiceAgent with STT/TTS providers.
        
        Returns:
            VoiceAgent: Configured voice agent
        """
        try:
            # Configure STT provider
            stt_provider = self._create_stt_provider()
            
            # Configure TTS provider  
            tts_provider = self._create_tts_provider()
            
            # Create custom LLM
            llm = AnimeAILLM(self.config, self.memory_manager)
            
            # Create VoiceAgent
            self.voice_assistant = VoiceAgent(
                instructions=self.config.personality.personality_prompt,
                vad=silero.VAD.load(),  # Voice Activity Detection
                stt=stt_provider,
                llm=llm,
                tts=tts_provider,
                chat_ctx=agents.llm.ChatContext(),
            )
            
            self.logger.info("VoiceAgent created successfully")
            return self.voice_assistant
            
        except Exception as e:
            self.logger.error(f"Failed to create VoiceAgent: {e}")
            raise
    
    def _create_stt_provider(self) -> STT:
        """
        Create Speech-to-Text provider based on configuration.
        
        Returns:
            STT: Configured STT provider
        """
        provider_name = self.config.agents.stt_provider.lower()
        
        if provider_name == "openai":
            return openai.STT()
        elif provider_name == "deepgram":
            return deepgram.STT()
        else:
            self.logger.warning(f"Unknown STT provider '{provider_name}', using OpenAI")
            return openai.STT()
    
    def _create_tts_provider(self) -> TTS:
        """
        Create Text-to-Speech provider based on configuration.
        
        Returns:
            TTS: Configured TTS provider
        """
        provider_name = self.config.agents.tts_provider.lower()
        
        if provider_name == "openai":
            return openai.TTS()
        elif provider_name == "silero":
            return silero.TTS()
        else:
            self.logger.warning(f"Unknown TTS provider '{provider_name}', using OpenAI")
            return openai.TTS()
    
    async def handle_participant_connected(self, participant: rtc.RemoteParticipant) -> None:
        """
        Handle new participant connection.
        
        Args:
            participant: Connected participant
        """
        self.logger.info(f"Participant connected: {participant.identity}")
        
        # Set user ID for memory context
        if hasattr(self.voice_assistant, 'chat_ctx'):
            self.voice_assistant.chat_ctx.user_id = participant.identity
    
    async def handle_participant_disconnected(self, participant: rtc.RemoteParticipant) -> None:
        """
        Handle participant disconnection.
        
        Args:
            participant: Disconnected participant
        """
        self.logger.info(f"Participant disconnected: {participant.identity}")
    
    async def start_agent(self, room: rtc.Room) -> None:
        """
        Start the agent in a LiveKit room.
        
        Args:
            room: LiveKit room to join
        """
        try:
            await self.initialize()
            
            # Create voice agent
            voice_agent = self.create_voice_agent()
            
            # Set up event handlers
            room.on("participant_connected", self.handle_participant_connected)
            room.on("participant_disconnected", self.handle_participant_disconnected)
            
            # Start the voice agent
            voice_agent.start(room)
            
            self.logger.info("Anime AI Agent started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start agent: {e}")
            raise


async def entrypoint(ctx: JobContext) -> None:
    """
    Main entrypoint for the LiveKit agent.
    
    Args:
        ctx: Job context from LiveKit
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        from ..config.settings import load_config
        config = load_config()
        
        logger.info("Starting Anime AI Character agent...")
        
        # Create and start agent
        agent = AnimeAIAgent(config)
        await agent.start_agent(ctx.room)
        
        # Keep the agent running
        await asyncio.sleep(float('inf'))
        
    except Exception as e:
        logger.error(f"Agent entrypoint error: {e}")
        raise


def main():
    """Main function to run the agent."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the agent
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=None,
        )
    )


if __name__ == "__main__":
    main()