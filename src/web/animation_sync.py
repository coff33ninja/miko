"""
Animation synchronization system for real-time coordination.

This module provides advanced animation synchronization capabilities including:
- TTS audio and mouth animation timing
- Expression transition smoothing
- Animation queue management with priorities
- Real-time parameter updates
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum

from .websocket_manager import (
    WebSocketAnimationManager, AnimationEvent, AnimationEventType, 
    TimingSyncData, get_websocket_manager
)


class AnimationPriority(Enum):
    """Animation priority levels."""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


@dataclass
class ExpressionTransition:
    """Expression transition configuration."""
    from_expression: str
    to_expression: str
    duration: float
    easing_type: str = "easeInOut"
    blend_factor: float = 1.0


@dataclass
class MouthSyncConfig:
    """Mouth synchronization configuration."""
    sensitivity: float = 0.8
    smoothing_factor: float = 0.3
    min_mouth_open: float = 0.1
    max_mouth_open: float = 0.9
    form_variation: float = 0.2


@dataclass
class AnimationSequence:
    """Animation sequence with multiple steps."""
    sequence_id: str
    steps: List[AnimationEvent]
    total_duration: float
    loop: bool = False
    priority: AnimationPriority = AnimationPriority.NORMAL


class AnimationSynchronizer:
    """
    Advanced animation synchronization system.
    
    Handles real-time coordination between AI responses, TTS audio,
    and Live2D animations with precise timing control.
    """
    
    def __init__(self, websocket_manager: Optional[WebSocketAnimationManager] = None):
        """
        Initialize animation synchronizer.
        
        Args:
            websocket_manager: WebSocket manager for real-time communication
        """
        self.websocket_manager = websocket_manager or get_websocket_manager()
        self.logger = logging.getLogger(__name__)
        
        # Animation state
        self.current_expression = "neutral"
        self.target_expression = "neutral"
        self.is_speaking = False
        self.is_transitioning = False
        
        # Timing state
        self.audio_start_time: Optional[float] = None
        self.audio_duration: Optional[float] = None
        self.animation_offset: float = 0.0  # Offset to sync with audio
        
        # Configuration
        self.mouth_sync_config = MouthSyncConfig()
        self.transition_duration = 1.5  # Default transition duration
        self.sync_tolerance = 0.05  # 50ms tolerance for sync
        
        # Active sequences
        self.active_sequences: Dict[str, AnimationSequence] = {}
        
        # Performance tracking
        self.sync_accuracy_samples: List[float] = []
        self.max_accuracy_samples = 50
        
        # Register event handlers
        self._register_event_handlers()
    
    def _register_event_handlers(self) -> None:
        """Register WebSocket event handlers."""
        self.websocket_manager.register_event_handler(
            AnimationEventType.MOUTH_SYNC_START,
            self._handle_mouth_sync_start
        )
        self.websocket_manager.register_event_handler(
            AnimationEventType.MOUTH_SYNC_STOP,
            self._handle_mouth_sync_stop
        )
        self.websocket_manager.register_event_handler(
            AnimationEventType.EXPRESSION_CHANGE,
            self._handle_expression_change
        )
    
    async def synchronize_with_tts(
        self, 
        text: str, 
        expression: str = "speak",
        audio_duration: Optional[float] = None,
        tts_processing_delay: float = 0.2
    ) -> str:
        """
        Synchronize animation with TTS audio output.
        
        Args:
            text: Text being spoken
            expression: Base expression during speech
            audio_duration: Expected audio duration (estimated if None)
            tts_processing_delay: Expected TTS processing delay
            
        Returns:
            str: Sequence ID for tracking
        """
        sequence_id = str(uuid.uuid4())
        
        try:
            # Estimate audio duration if not provided
            if audio_duration is None:
                audio_duration = self._estimate_audio_duration(text)
            
            # Create timing synchronization data
            timing_sync = self.websocket_manager.create_timing_sync(
                audio_duration=audio_duration,
                tts_delay=tts_processing_delay
            )
            
            # Calculate animation timing
            animation_start_delay = max(0, tts_processing_delay - 0.1)  # Start slightly before audio
            mouth_sync_start_delay = tts_processing_delay
            
            # Create animation sequence
            sequence = await self._create_tts_animation_sequence(
                sequence_id=sequence_id,
                text=text,
                expression=expression,
                audio_duration=audio_duration,
                animation_start_delay=animation_start_delay,
                mouth_sync_start_delay=mouth_sync_start_delay
            )
            
            # Store active sequence
            self.active_sequences[sequence_id] = sequence
            
            # Queue animation events
            for step in sequence.steps:
                await self.websocket_manager.queue_animation(step)
            
            # Store timing for sync tracking
            self.audio_start_time = timing_sync.audio_start_time
            self.audio_duration = audio_duration
            
            self.logger.info(f"TTS animation synchronized: {sequence_id} ({audio_duration:.2f}s)")
            
            return sequence_id
            
        except Exception as e:
            self.logger.error(f"Failed to synchronize TTS animation: {e}")
            raise
    
    async def _create_tts_animation_sequence(
        self,
        sequence_id: str,
        text: str,
        expression: str,
        audio_duration: float,
        animation_start_delay: float,
        mouth_sync_start_delay: float
    ) -> AnimationSequence:
        """
        Create animation sequence for TTS synchronization.
        
        Args:
            sequence_id: Unique sequence identifier
            text: Text being spoken
            expression: Base expression
            audio_duration: Audio duration
            animation_start_delay: Delay before starting animation
            mouth_sync_start_delay: Delay before starting mouth sync
            
        Returns:
            AnimationSequence: Created animation sequence
        """
        current_time = time.time()
        steps = []
        
        # Step 1: Transition to speaking expression (if different from current)
        if expression != self.current_expression:
            transition_event = AnimationEvent(
                event_type=AnimationEventType.EXPRESSION_CHANGE,
                timestamp=current_time + animation_start_delay,
                data={
                    "expression": expression,
                    "intensity": 0.7,
                    "duration": self.transition_duration,
                    "transition_type": "smooth"
                },
                sequence_id=sequence_id,
                duration=self.transition_duration,
                priority=AnimationPriority.HIGH.value
            )
            steps.append(transition_event)
        
        # Step 2: Start mouth synchronization
        mouth_sync_start_event = AnimationEvent(
            event_type=AnimationEventType.MOUTH_SYNC_START,
            timestamp=current_time + mouth_sync_start_delay,
            data={
                "text": text,
                "audio_duration": audio_duration,
                "sync_config": asdict(self.mouth_sync_config)
            },
            sequence_id=sequence_id,
            duration=audio_duration,
            priority=AnimationPriority.CRITICAL.value
        )
        steps.append(mouth_sync_start_event)
        
        # Step 3: Stop mouth synchronization
        mouth_sync_stop_event = AnimationEvent(
            event_type=AnimationEventType.MOUTH_SYNC_STOP,
            timestamp=current_time + mouth_sync_start_delay + audio_duration,
            data={
                "return_to_expression": self.current_expression
            },
            sequence_id=sequence_id,
            priority=AnimationPriority.HIGH.value
        )
        steps.append(mouth_sync_stop_event)
        
        # Step 4: Return to previous expression (if needed)
        if expression != self.current_expression:
            return_transition_event = AnimationEvent(
                event_type=AnimationEventType.EXPRESSION_CHANGE,
                timestamp=current_time + mouth_sync_start_delay + audio_duration + 0.2,
                data={
                    "expression": self.current_expression,
                    "intensity": 0.6,
                    "duration": self.transition_duration,
                    "transition_type": "smooth"
                },
                sequence_id=sequence_id,
                duration=self.transition_duration,
                priority=AnimationPriority.NORMAL.value
            )
            steps.append(return_transition_event)
        
        total_duration = audio_duration + self.transition_duration * 2 + 0.5
        
        return AnimationSequence(
            sequence_id=sequence_id,
            steps=steps,
            total_duration=total_duration,
            priority=AnimationPriority.HIGH
        )
    
    async def trigger_expression_change(
        self,
        expression: str,
        intensity: float = 0.7,
        duration: float = 2.0,
        priority: AnimationPriority = AnimationPriority.NORMAL,
        interrupt_current: bool = False
    ) -> str:
        """
        Trigger expression change with smooth transitions.
        
        Args:
            expression: Target expression
            intensity: Expression intensity (0.0-1.0)
            duration: Animation duration
            priority: Animation priority
            interrupt_current: Whether to interrupt current animation
            
        Returns:
            str: Animation sequence ID
        """
        sequence_id = str(uuid.uuid4())
        
        try:
            # Create transition if needed
            transition = None
            if expression != self.current_expression:
                transition = ExpressionTransition(
                    from_expression=self.current_expression,
                    to_expression=expression,
                    duration=duration,
                    easing_type="easeInOut"
                )
            
            # Create animation event
            event = AnimationEvent(
                event_type=AnimationEventType.EXPRESSION_CHANGE,
                timestamp=time.time(),
                data={
                    "expression": expression,
                    "intensity": intensity,
                    "duration": duration,
                    "transition": asdict(transition) if transition else None,
                    "interrupt_current": interrupt_current
                },
                sequence_id=sequence_id,
                duration=duration,
                priority=priority.value
            )
            
            # Queue animation
            await self.websocket_manager.queue_animation(event)
            
            # Update state
            self.target_expression = expression
            if not self.is_transitioning:
                self.is_transitioning = True
                # Schedule transition completion
                asyncio.create_task(self._complete_expression_transition(sequence_id, duration))
            
            self.logger.info(f"Expression change triggered: {expression} ({intensity}, {duration}s)")
            
            return sequence_id
            
        except Exception as e:
            self.logger.error(f"Failed to trigger expression change: {e}")
            raise
    
    async def _complete_expression_transition(self, sequence_id: str, duration: float) -> None:
        """
        Complete expression transition after duration.
        
        Args:
            sequence_id: Sequence ID
            duration: Transition duration
        """
        await asyncio.sleep(duration)
        
        # Update current expression
        self.current_expression = self.target_expression
        self.is_transitioning = False
        
        # Clean up sequence
        if sequence_id in self.active_sequences:
            del self.active_sequences[sequence_id]
    
    async def start_mouth_sync(
        self,
        audio_data: Optional[bytes] = None,
        duration: Optional[float] = None
    ) -> None:
        """
        Start mouth synchronization with audio.
        
        Args:
            audio_data: Audio data for analysis (optional)
            duration: Expected duration (optional)
        """
        if self.is_speaking:
            self.logger.warning("Mouth sync already active")
            return
        
        self.is_speaking = True
        
        # Create mouth sync event
        event = AnimationEvent(
            event_type=AnimationEventType.MOUTH_SYNC_START,
            timestamp=time.time(),
            data={
                "has_audio_data": audio_data is not None,
                "duration": duration,
                "config": asdict(self.mouth_sync_config)
            },
            sequence_id=str(uuid.uuid4()),
            duration=duration,
            priority=AnimationPriority.CRITICAL.value
        )
        
        await self.websocket_manager.queue_animation(event)
        
        self.logger.info("Mouth synchronization started")
    
    async def stop_mouth_sync(self) -> None:
        """Stop mouth synchronization."""
        if not self.is_speaking:
            return
        
        self.is_speaking = False
        
        # Create mouth sync stop event
        event = AnimationEvent(
            event_type=AnimationEventType.MOUTH_SYNC_STOP,
            timestamp=time.time(),
            data={
                "return_to_neutral": True
            },
            sequence_id=str(uuid.uuid4()),
            priority=AnimationPriority.HIGH.value
        )
        
        await self.websocket_manager.queue_animation(event)
        
        self.logger.info("Mouth synchronization stopped")
    
    async def update_mouth_parameters(
        self,
        audio_level: float,
        frequency_data: Optional[List[float]] = None
    ) -> None:
        """
        Update mouth animation parameters based on audio analysis.
        
        Args:
            audio_level: Audio volume level (0.0-1.0)
            frequency_data: Frequency analysis data (optional)
        """
        if not self.is_speaking:
            return
        
        # Calculate mouth opening based on audio level
        mouth_open = self._calculate_mouth_opening(audio_level)
        
        # Calculate mouth form based on frequency data
        mouth_form = self._calculate_mouth_form(frequency_data) if frequency_data else 0.0
        
        # Create parameter update event
        event = AnimationEvent(
            event_type=AnimationEventType.MOUTH_SYNC_UPDATE,
            timestamp=time.time(),
            data={
                "mouth_open": mouth_open,
                "mouth_form": mouth_form,
                "audio_level": audio_level
            },
            sequence_id=str(uuid.uuid4()),
            priority=AnimationPriority.CRITICAL.value
        )
        
        await self.websocket_manager.queue_animation(event)
    
    def _calculate_mouth_opening(self, audio_level: float) -> float:
        """
        Calculate mouth opening parameter from audio level.
        
        Args:
            audio_level: Audio volume level (0.0-1.0)
            
        Returns:
            float: Mouth opening parameter
        """
        config = self.mouth_sync_config
        
        # Apply sensitivity
        adjusted_level = audio_level * config.sensitivity
        
        # Map to mouth opening range
        mouth_open = config.min_mouth_open + (
            adjusted_level * (config.max_mouth_open - config.min_mouth_open)
        )
        
        # Apply smoothing (this would be handled by the client-side animation system)
        return min(config.max_mouth_open, max(config.min_mouth_open, mouth_open))
    
    def _calculate_mouth_form(self, frequency_data: List[float]) -> float:
        """
        Calculate mouth form parameter from frequency analysis.
        
        Args:
            frequency_data: Frequency analysis data
            
        Returns:
            float: Mouth form parameter
        """
        if not frequency_data:
            return 0.0
        
        # Analyze high frequency content for mouth shape
        high_freq_ratio = sum(frequency_data[len(frequency_data)//2:]) / sum(frequency_data)
        
        # Map to mouth form with variation
        form_value = (high_freq_ratio - 0.5) * self.mouth_sync_config.form_variation
        
        return max(-1.0, min(1.0, form_value))
    
    def _estimate_audio_duration(self, text: str) -> float:
        """
        Estimate audio duration from text length.
        
        Args:
            text: Text to be spoken
            
        Returns:
            float: Estimated duration in seconds
        """
        # Simple estimation: ~150 words per minute, ~5 characters per word
        words = len(text) / 5
        duration = (words / 150) * 60
        
        # Add minimum duration and processing overhead
        return max(1.0, duration + 0.5)
    
    async def _handle_mouth_sync_start(self, event: AnimationEvent) -> None:
        """Handle mouth sync start event."""
        self.is_speaking = True
        self.logger.debug("Mouth sync started via event")
    
    async def _handle_mouth_sync_stop(self, event: AnimationEvent) -> None:
        """Handle mouth sync stop event."""
        self.is_speaking = False
        self.logger.debug("Mouth sync stopped via event")
    
    async def _handle_expression_change(self, event: AnimationEvent) -> None:
        """Handle expression change event."""
        expression = event.data.get("expression")
        if expression:
            self.target_expression = expression
            self.logger.debug(f"Expression change handled: {expression}")
    
    def get_sync_accuracy(self) -> float:
        """
        Get average synchronization accuracy.
        
        Returns:
            float: Average sync accuracy (0.0-1.0)
        """
        if not self.sync_accuracy_samples:
            return 1.0
        
        return sum(self.sync_accuracy_samples) / len(self.sync_accuracy_samples)
    
    def record_sync_accuracy(self, accuracy: float) -> None:
        """
        Record synchronization accuracy measurement.
        
        Args:
            accuracy: Accuracy measurement (0.0-1.0)
        """
        self.sync_accuracy_samples.append(accuracy)
        
        # Keep only recent samples
        if len(self.sync_accuracy_samples) > self.max_accuracy_samples:
            self.sync_accuracy_samples.pop(0)
    
    def get_animation_state(self) -> Dict[str, Any]:
        """
        Get current animation state.
        
        Returns:
            Dict: Current animation state
        """
        return {
            "current_expression": self.current_expression,
            "target_expression": self.target_expression,
            "is_speaking": self.is_speaking,
            "is_transitioning": self.is_transitioning,
            "active_sequences": len(self.active_sequences),
            "sync_accuracy": self.get_sync_accuracy(),
            "audio_active": self.audio_start_time is not None
        }
    
    async def cleanup_expired_sequences(self) -> None:
        """Clean up expired animation sequences."""
        current_time = time.time()
        expired_sequences = []
        
        for sequence_id, sequence in self.active_sequences.items():
            # Check if sequence has expired
            if hasattr(sequence, 'start_time'):
                if current_time - sequence.start_time > sequence.total_duration + 5.0:
                    expired_sequences.append(sequence_id)
        
        # Remove expired sequences
        for sequence_id in expired_sequences:
            del self.active_sequences[sequence_id]
            self.logger.debug(f"Cleaned up expired sequence: {sequence_id}")


# Global animation synchronizer instance
animation_synchronizer: Optional[AnimationSynchronizer] = None


def get_animation_synchronizer() -> AnimationSynchronizer:
    """
    Get global animation synchronizer instance.
    
    Returns:
        AnimationSynchronizer: Global synchronizer instance
    """
    global animation_synchronizer
    if animation_synchronizer is None:
        animation_synchronizer = AnimationSynchronizer()
    return animation_synchronizer