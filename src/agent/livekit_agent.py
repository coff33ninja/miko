"""
LiveKit agent implementation for Anime AI Character system.
Handles real‑time voice interactions **and** plain‑text chat,
integrates AI providers, memory and Live2D animation synchronisation.
"""

# --------------------------------------------------------------
# Standard library
# --------------------------------------------------------------
import asyncio
import logging
import time
import random
from datetime import datetime
from typing import Optional, Any, Awaitable, Callable

# --------------------------------------------------------------
# LiveKit SDK / Agents
# --------------------------------------------------------------
from livekit import rtc
from livekit.agents import (
    JobContext,
    WorkerOptions,
    cli,
    JobProcess,  # needed for the pre‑warm hook
)
from livekit.agents.voice import Agent as VoiceAgent
from livekit.agents.llm import LLM, ChatContext, ChatMessage, LLMStream
from livekit.agents.stt import STT
from livekit.agents.tts import TTS
from livekit.plugins import openai, silero, deepgram

# --------------------------------------------------------------
# Project‑specific modules
# --------------------------------------------------------------
from src.config.settings import AppConfig, load_config
from src.ai.provider_factory import ProviderFactory
from src.memory.memory_manager import MemoryManager, ConversationMessage
from src.web.app import trigger_animation
from src.web.animation_sync import (
    get_animation_synchronizer,
    AnimationPriority,
)
from src.error_handling.exceptions import LiveKitError, AIProviderError, MemoryError
from src.error_handling.fallback_manager import get_fallback_manager, FallbackStrategy, FallbackResult, FallbackManager  # noqa: F401
from src.error_handling.error_recovery import get_recovery_manager, RecoveryStrategy, ErrorRecoveryManager  # noqa: F401
from src.error_handling.logging_handler import get_error_logger


# --------------------------------------------------------------
# Simple alias – makes the intent clearer in the rest of the file
# --------------------------------------------------------------
VoiceAssistant = VoiceAgent


# ----------------------------------------------------------------------
# 1️⃣  Custom LLM wrapper (AnimeAILLM)
# ----------------------------------------------------------------------
class AnimeAILLM(LLM):
    """
    Custom LLM implementation that talks to the AI provider you configured,
    stores/retrieves memory, and drives the Live2D animation synchroniser.
    """

    def __init__(self, config: AppConfig, memory_manager: MemoryManager):
        self.config = config
        self.memory_manager = memory_manager
        self.ai_provider = ProviderFactory.create_provider()
        self.logger = logging.getLogger(__name__)

        # one synchroniser per worker process
        self.animation_sync = get_animation_synchronizer()

        # error‑handling helpers
        self.fallback_manager = get_fallback_manager()
        self.recovery_manager: ErrorRecoveryManager = get_recovery_manager()
        self.error_logger = get_error_logger()

        # health‑monitoring
        self.consecutive_failures = 0
        self.last_successful_response = time.time()
        self.connection_healthy = True

    # ------------------------------------------------------------------
    # LiveKit entry point – must return an LLMStream
    # ------------------------------------------------------------------
    async def chat(
        self,
        *,
        chat_ctx: ChatContext,
        conn_handle: Optional[Any] = None,
        fnc_ctx: Optional[Any] = None,
    ) -> LLMStream:
        user_id = getattr(chat_ctx, "user_id", "default_user")

        # Run the core logic via the fallback manager (primary + retries)
        result = await self.fallback_manager.execute_with_fallback(
            component="livekit_llm",
            primary_operation=self._process_chat_internal,
            operation_args=(chat_ctx, user_id),
            context={
                "user_id": user_id,
                "retry_operation": self._process_chat_internal,
                "max_retries": 3,
            },
        )

        if result.success:
            return result.result
        return self._handle_chat_failure(result, user_id)

    # ------------------------------------------------------------------
    # Core processing – everything that can raise an exception lives here
    # ------------------------------------------------------------------
    async def _execute_async_task(
        self, task: Callable[..., Awaitable[Any]], *args, **kwargs
    ) -> Any:
        """Helper to execute an asynchronous task."""
        self.logger.debug(f"Executing async task: {task.__name__}")
        return await task(*args, **kwargs)

    async def _process_chat_internal(
        self, chat_ctx: ChatContext, user_id: str
    ) -> "AnimeAILLMStream":
        try:
            # --------------------------------------------------------------
            # 1️⃣  Pull the latest user utterance
            # --------------------------------------------------------------
            user_message = next(
                (
                    msg.content
                    for msg in reversed(chat_ctx.messages)
                    if msg.role == "user"
                ),
                None,
            )
            if not user_message:
                self.logger.warning("No user message found in chat context")
                return AnimeAILLMStream(
                    "I didn't catch that… could you say it again? (*confused*)"
                )

            # --------------------------------------------------------------
            # 2️⃣  Store the user utterance in the short‑term memory layer
            # --------------------------------------------------------------
            try:
                await self.memory_manager.store_conversation(
                    ConversationMessage(
                        role="user",
                        content=user_message,
                        timestamp=datetime.now(),
                        user_id=user_id,
                    )
                )
            except Exception as e:
                self.logger.warning(f"Memory store failed (user): {e}")

            # --------------------------------------------------------------
            # 3️⃣  Retrieve any long‑term context (optional)
            # --------------------------------------------------------------
            try:
                memory_context = await self.memory_manager.get_user_context(
                    user_id, user_message
                )
            except Exception as e:
                self.logger.warning(f"Memory lookup failed: {e}")
                memory_context = None

            # --------------------------------------------------------------
            # 4️⃣  Convert LiveKit ChatMessage objects to the provider‑agnostic format
            # --------------------------------------------------------------
            from src.ai.base_provider import (
                Message,
            )  # thin wrapper used by ProviderFactory

            llm_messages = [
                Message(role=m.role, content=m.content, timestamp=datetime.now())
                for m in chat_ctx.messages
            ]

            # --------------------------------------------------------------
            # 5️⃣  Call the AI provider (30 s timeout)
            # --------------------------------------------------------------
            try:
                response = await asyncio.wait_for(
                    self._execute_async_task(  # Use the new helper here
                        self.ai_provider.generate_response,
                        llm_messages,
                        self.config.personality.personality_prompt,
                        memory_context,
                    ),
                    timeout=30.0,
                )
            except asyncio.TimeoutError as te:
                raise AIProviderError(
                    "AI response generation timeout",
                    provider=self.ai_provider.get_provider_name(),
                    details={"timeout": 30},
                ) from te

            # --------------------------------------------------------------
            # 6️⃣  Store the assistant reply
            # --------------------------------------------------------------
            try:
                await self.memory_manager.store_conversation(
                    ConversationMessage(
                        role="assistant",
                        content=response,
                        timestamp=datetime.now(),
                        user_id=user_id,
                    )
                )
            except Exception as e:
                self.logger.warning(f"Memory store failed (assistant): {e}")

            # --------------------------------------------------------------
            # 7️⃣  Fire a synchronized Live2D animation (fallback‑aware)
            # --------------------------------------------------------------
            try:
                await self._trigger_synchronized_animation(response, user_message)
            except Exception as e:
                self.logger.warning(f"Animation trigger failed: {e}")

            # --------------------------------------------------------------
            # 8️⃣  Record a successful round‑trip
            # --------------------------------------------------------------
            self.consecutive_failures = 0
            self.last_successful_response = time.time()
            self.connection_healthy = True
            await self.recovery_manager.record_success("livekit_llm")

            self.logger.info(f"LLM reply for {user_id}: {response[:60]}...")
            return AnimeAILLMStream(response)

        # ------------------------------------------------------------------
        # Anything unexpected bubbles up here – we turn it into a LiveKitError
        # ------------------------------------------------------------------
        except Exception as exc:
            self.consecutive_failures += 1
            await self.recovery_manager.record_error("livekit_llm", exc)

            if isinstance(exc, AIProviderError):
                raise exc
            if isinstance(exc, MemoryError):
                self.logger.warning(f"Memory error: {exc}")
                return AnimeAILLMStream(
                    "I'm having memory hiccups, but let's keep talking! (*smile*)"
                )
            raise LiveKitError(
                f"Chat processing error: {exc}",
                operation="chat_processing",
                participant_id=user_id,
            ) from exc

    # ------------------------------------------------------------------
    # Fallback‑only error handling – returns a cute anime‑style apology
    # ------------------------------------------------------------------
    def _handle_chat_failure(self, result: FallbackResult, user_id: str) -> "AnimeAILLMStream":
        self.error_logger.log_fallback_usage(
            component="livekit_llm",
            fallback_strategy=(
                result.strategy_used.value if result.strategy_used else "none"
            ),
            original_error=result.error,
            fallback_success=False,
        )
        return AnimeAILLMStream(
            random.choice(
                [
                    "Gomen! Something went wrong... (*nervous laugh*) Could you try again?",
                    "Eh? I'm having trouble understanding right now... (*confused*)",
                    "My brain feels a bit fuzzy… Could you repeat that? (*dizzy*)",
                    "Something's not working right... But I'm still here! (*determined*)",
                ]
            )
        )

    # ------------------------------------------------------------------
    # Animation synchroniser – primary + fallback via the fallback manager
    # ------------------------------------------------------------------
    async def _trigger_synchronized_animation(
        self, response: str, user_message: str, priority: Optional[AnimationPriority] = None
    ) -> None:
        result = await self.fallback_manager.execute_with_fallback(
            component="animation_sync",
            primary_operation=self._trigger_animation_internal,
            operation_args=(response, user_message, priority),
            context={
                "retry_operation": self._trigger_animation_internal,
                "max_retries": 2,
                "response_text": response,
                "priority": priority,
            },
        )
        if not result.success:
            self.error_logger.log_fallback_usage(
                component="animation_sync",
                fallback_strategy=(
                    result.strategy_used.value if result.strategy_used else "none"
                ),
                original_error=result.error,
                fallback_success=False,
            )

    # ------------------------------------------------------------------
    # Low‑level animation call – tries sync first, then direct API
    # ------------------------------------------------------------------
    def _run_and_log_sync(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Helper to execute a synchronous callable and log its execution."""
        self.logger.debug(f"Executing synchronous function: {func.__name__}")
        return func(*args, **kwargs)

    async def _trigger_animation_internal(
        self, response: str, user_message: str, priority: Optional[AnimationPriority] = None
    ) -> bool:
        try:
            expression = self._run_and_log_sync(
                self._analyze_response_sentiment, response
            )
            intensity = self._run_and_log_sync(
                self._calculate_expression_intensity, response, user_message
            )

            # rough TTS‑delay estimate (helps the synchroniser align lips)
            tts_delay = min(0.5, len(response) / 200)

            # ①  Try the LiveKit synchroniser (if the deployment supports it)
            try:
                seq_id = await asyncio.wait_for(
                    self.animation_sync.synchronize_with_tts(
                        text=response,
                        expression=expression,
                        tts_processing_delay=tts_delay,
                    ),
                    timeout=5.0,
                )
                if seq_id:
                    self.logger.info(
                        f"Synchronized animation triggered: {expression} ({seq_id})"
                    )
                    return True
            except asyncio.TimeoutError:
                self.logger.warning("Animation sync timed out – falling back to expression change")
            except Exception as e:
                self.logger.warning(f"Animation sync error: {e} – falling back to expression change")

            # ② Try triggering expression change with priority if provided
            if priority:
                try:
                    seq_id = await asyncio.wait_for(
                        self.animation_sync.trigger_expression_change(
                            expression=expression,
                            intensity=intensity,
                            priority=priority,
                        ),
                        timeout=3.0,
                    )
                    if seq_id:
                        self.logger.info(
                            f"Expression change triggered with priority: {expression} ({priority.name})"
                        )
                        return True
                except asyncio.TimeoutError:
                    self.logger.warning("Expression change with priority timed out – falling back to direct animation")
                except Exception as e:
                    self.logger.warning(f"Expression change with priority error: {e} – falling back to direct animation")

            # ③  Direct fallback via our own HTTP endpoint
            success = await asyncio.wait_for(
                trigger_animation(expression, intensity), timeout=3.0
            )
            if success:
                self.logger.info(f"Direct animation triggered: {expression}")
                return True
            raise RuntimeError("Direct animation returned False")
        except asyncio.TimeoutError:
            raise RuntimeError("Animation trigger timed out")
        except Exception as e:
            raise RuntimeError(f"Animation trigger failed: {e}") from e

    # ------------------------------------------------------------------
    # Sentiment → Live2D expression mapping (tsundere‑style)
    # ------------------------------------------------------------------
    def _analyze_response_sentiment(self, response: str) -> str:
        r = response.lower()
        if any(w in r for w in ["baka", "stupid", "hmph", "idiot"]):
            return "angry"
        if any(w in r for w in ["blush", "embarrassed", "(*blush*)", "b-but"]):
            return "embarrassed"
        if any(w in r for w in ["happy", "yay", "excited", "(*happy*)", "great"]):
            return "happy"
        if any(w in r for w in ["sad", "sorry", "gomen", "(*sad*)", "worried"]):
            return "sad"
        if any(w in r for w in ["surprised", "wow", "eh?", "(*surprised*)"]):
            return "surprised"
        if "?" in response or any(w in r for w in ["what", "huh", "confused"]):
            return "surprised"
        return "speak"

    # ------------------------------------------------------------------
    # Intensity calculation (0.0‑1.0)
    # ------------------------------------------------------------------
    def _calculate_expression_intensity(
        self, response: str, user_message: str
    ) -> float:
        base = 0.7
        emo_words = ["baka", "stupid", "amazing", "terrible", "love", "hate"]
        emotion_boost = min(0.3, sum(w in response.lower() for w in emo_words) * 0.1)
        exclamation_boost = min(0.2, response.count("!") * 0.05)
        length_boost = min(0.1, len(response) / 500)

        return min(
            1.0, max(0.3, base + emotion_boost + exclamation_boost + length_boost)
        )


# ----------------------------------------------------------------------
# 2️⃣  Stream object required by VoiceAgent
# ----------------------------------------------------------------------
class AnimeAILLMStream(LLMStream):
    """Very small async iterator that yields a single string."""

    def __init__(self, content: str):
        self._content = content
        self._sent = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._sent:
            raise StopAsyncIteration
        self._sent = True
        return self._content


# ----------------------------------------------------------------------
# 3️⃣  Main LiveKit agent wrapper (AnimeAIAgent)
# ----------------------------------------------------------------------
class AnimeAIAgent:
    """Orchestrates memory, the VoiceAgent and LiveKit event handling."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.memory_manager = MemoryManager(config.memory)
        self.voice_assistant: Optional[VoiceAssistant] = None
        self.room: Optional[rtc.Room] = None  # kept for chat handling

    # --------------------------------------------------------------
    async def initialize(self) -> None:
        """Bring up the memory layer (Mem0, Redis, etc.)."""
        try:
            mem0_ready = await self.memory_manager.initialize()
            self.logger.info(
                "Memory manager ready – %s",
                "Mem0" if mem0_ready else "session‑only fallback",
            )
        except Exception as exc:
            self.logger.error(f"Memory init failed: {exc}")
            raise

    # --------------------------------------------------------------
    def _create_stt_provider(self) -> STT:
        name = self.config.agents.stt_provider.lower()
        if name == "openai":
            return openai.STT()
        if name == "deepgram":
            return deepgram.STT()
        self.logger.warning(f"Unknown STT provider '{name}', falling back to OpenAI")
        return openai.STT()

    # --------------------------------------------------------------
    def _create_tts_provider(self) -> TTS:
        name = self.config.agents.tts_provider.lower()
        if name == "openai":
            return openai.TTS()
        if name == "silero":
            return silero.TTS()
        self.logger.warning(f"Unknown TTS provider '{name}', falling back to OpenAI")
        return openai.TTS()

    # --------------------------------------------------------------
    def create_voice_agent(self) -> VoiceAgent:
        """Build the LiveKit VoiceAgent with custom LLM, STT and TTS."""
        try:
            stt = self._create_stt_provider()
            tts = self._create_tts_provider()
            llm = AnimeAILLM(self.config, self.memory_manager)

            self.voice_assistant = VoiceAgent(
                instructions=self.config.personality.personality_prompt,
                vad=silero.VAD.load(),
                stt=stt,
                tts=tts,
                llm=llm,
                chat_ctx=ChatContext(),
            )
            self.logger.info("VoiceAgent created")
            return self.voice_assistant
        except Exception as exc:
            self.logger.error(f"VoiceAgent creation failed: {exc}")
            raise

    # --------------------------------------------------------------
    async def handle_participant_connected(
        self, participant: rtc.RemoteParticipant
    ) -> None:
        self.logger.info(f"Participant joined: {participant.identity}")
        if self.voice_assistant and hasattr(self.voice_assistant, "chat_ctx"):
            self.voice_assistant.chat_ctx.user_id = participant.identity

        # Send welcome message
        welcome_msg = (
            "Konnichiwa! I'm Miko, your anime AI companion! (*excited wave*) "
            "You can talk to me using your voice, and I'll remember our conversations! "
            "What would you like to chat about? (＾◡＾)"
        )

        if self.voice_assistant:
            await self.voice_assistant.say(welcome_msg, participant)

    # --------------------------------------------------------------
    async def handle_participant_disconnected(
        self, participant: rtc.RemoteParticipant
    ) -> None:
        self.logger.info(f"Participant left: {participant.identity}")

        # Clean up user session if needed
        if self.voice_assistant:
            active_users = self.voice_assistant.get_active_users()
            if participant.identity in active_users:
                del active_users[participant.identity]

    # --------------------------------------------------------------
    async def handle_chat_message(self, chat_msg: Any) -> None:
        """
        Called whenever a plain‑text chat message arrives.
        It re‑uses the same LLM pipeline, stores the message in memory,
        and sends the assistant’s reply back as a chat message.
        """
        # ------------------------------------------------------------------
        # 1️⃣  Extract useful fields (different SDK versions expose them
        #      slightly differently – we try the most common ones)
        # ------------------------------------------------------------------
        try:
            user_id = (
                chat_msg.sender.identity
                if hasattr(chat_msg, "sender") and hasattr(chat_msg.sender, "identity")
                else getattr(chat_msg, "identity", "unknown_user")
            )
            content = getattr(chat_msg, "message", "")
        except Exception:
            self.logger.warning("Malformed chat message received – ignoring")
            return

        self.logger.info(f"Chat message from {user_id}: {content}")

        # ------------------------------------------------------------------
        # 2️⃣  Push the message into the VoiceAgent's ChatContext so that
        #      the LLM sees the full history.
        # ------------------------------------------------------------------
        if self.voice_assistant and hasattr(self.voice_assistant, "chat_ctx"):
            ctx = self.voice_assistant.chat_ctx
        else:
            ctx = ChatContext()
            if self.voice_assistant:
                self.voice_assistant.chat_ctx = ctx

        ctx.messages.append(ChatMessage(role="user", content=content))

        # ------------------------------------------------------------------
        # 3️⃣  Ask the LLM for a reply (the same pipeline we use for voice)
        # ------------------------------------------------------------------
        try:
            response_stream = await self.voice_assistant.llm.chat(chat_ctx=ctx)
            reply_text = await response_stream.__anext__()
        except Exception as exc:
            self.logger.error(f"LLM chat failure for text message: {exc}")
            reply_text = "Sorry, I’m having trouble right now…"

        # ------------------------------------------------------------------
        # 4️⃣  Send the reply back via the chat manager (if available)
        # ------------------------------------------------------------------
        try:
            # ``room.chat`` is the helper that knows how to send a ChatMessage
            if self.room and hasattr(self.room, "chat"):
                await self.room.chat.send(reply_text)
            else:
                # fallback – use the low‑level data channel (this works on older SDKs)
                await self.room.local_participant.publish_data(
                    reply_text.encode(),
                    kind=rtc.DataPacketKind.RELIABLE,
                    label="chat",
                )
        except Exception as exc:
            self.logger.error(f"Failed to send chat reply: {exc}")

    # --------------------------------------------------------------
    async def start_agent(self, room: rtc.Room) -> None:
        """Wire everything together and launch the voice pipeline."""
        try:
            self.room = room  # keep a reference for chat handling
            await self.initialize()
            voice_agent = self.create_voice_agent()

            # LiveKit event hooks
            room.on("participant_connected", self.handle_participant_connected)
            room.on("participant_disconnected", self.handle_participant_disconnected)

            # ---- NEW ---- chat‑message hook (compatible with both APIs) ----
            if hasattr(room, "chat"):
                # newer SDK – ChatManager emits "message_received"
                room.chat.on("message_received", self.handle_chat_message)
            else:
                # older SDK – generic event name
                room.on("chat_message_received", self.handle_chat_message)

            # Start processing audio for the whole room
            voice_agent.start(room)

            self.logger.info("Anime AI Agent started")
        except Exception as exc:
            self.logger.error(f"Failed to start agent: {exc}")
            raise


# ----------------------------------------------------------------------
# 4️⃣  LiveKit worker entry point
# ----------------------------------------------------------------------
async def entrypoint(ctx: JobContext) -> None:
    logger = logging.getLogger(__name__)

    try:
        cfg = load_config()
        logger.info("Launching Anime AI Character agent…")
        agent = AnimeAIAgent(cfg)
        await agent.start_agent(ctx.room)

        # Keep the process alive until LiveKit stops the job
        await asyncio.sleep(float("inf"))
    except Exception as exc:
        logger.error(f"Entry‑point error: {exc}")
        raise


# ----------------------------------------------------------------------
# 5️⃣  Pre‑warm – load the VAD model before any participant joins
# ----------------------------------------------------------------------
def prewarm(proc: JobProcess) -> None:
    """
    LiveKit calls this once per worker before any room is attached.
    We simply load the Silero VAD into ``proc.userdata`` so the LLM can reuse it.
    """
    proc.userdata["vad"] = silero.VAD.load()


# ----------------------------------------------------------------------
# 6️⃣  CLI launcher
# ----------------------------------------------------------------------
def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,  # ← now we have a pre‑warm hook
        )
    )


if __name__ == "__main__":
    main()