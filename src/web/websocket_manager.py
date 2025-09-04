"""
WebSocket manager for real-time animation synchronization.

This module provides WebSocket communication between the LiveKit agent
and Flask server for real-time animation coordination and timing synchronization.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum

import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed, WebSocketException


class AnimationEventType(Enum):
    """Types of animation events."""
    EXPRESSION_CHANGE = "expression_change"
    MOUTH_SYNC_START = "mouth_sync_start"
    MOUTH_SYNC_UPDATE = "mouth_sync_update"
    MOUTH_SYNC_STOP = "mouth_sync_stop"
    ANIMATION_QUEUE = "animation_queue"
    PARAMETER_UPDATE = "parameter_update"
    SYNC_TIMING = "sync_timing"


@dataclass
class AnimationEvent:
    """Animation event data structure."""
    event_type: AnimationEventType
    timestamp: float
    data: Dict[str, Any]
    sequence_id: Optional[str] = None
    duration: Optional[float] = None
    priority: int = 0  # Higher priority events are processed first


@dataclass
class TimingSyncData:
    """Timing synchronization data for audio-animation coordination."""
    audio_start_time: float
    audio_duration: float
    animation_start_time: float
    tts_processing_delay: float = 0.0
    network_latency: float = 0.0


class WebSocketAnimationManager:
    """
    Manages WebSocket connections for real-time animation synchronization.
    
    This class handles:
    - WebSocket server for client connections
    - Animation event broadcasting
    - Timing synchronization between audio and animations
    - Animation queue management
    - Connection health monitoring
    """
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        """
        Initialize WebSocket animation manager.
        
        Args:
            host: WebSocket server host
            port: WebSocket server port
        """
        self.host = host
        self.port = port
        self.logger = logging.getLogger(__name__)
        
        # Connection management
        self.clients: Dict[str, WebSocketServerProtocol] = {}
        self.server: Optional[websockets.WebSocketServer] = None
        
        # Animation state
        self.animation_queue: List[AnimationEvent] = []
        self.current_animation: Optional[AnimationEvent] = None
        self.timing_sync_data: Optional[TimingSyncData] = None
        
        # Event handlers
        self.event_handlers: Dict[AnimationEventType, List[Callable]] = {
            event_type: [] for event_type in AnimationEventType
        }
        
        # Performance tracking
        self.latency_measurements: List[float] = []
        self.max_latency_samples = 100
        
        # Configuration
        self.max_queue_size = 50
        self.heartbeat_interval = 30.0  # seconds
        self.connection_timeout = 60.0  # seconds
        
        # Running state
        self.is_running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._queue_processor_task: Optional[asyncio.Task] = None
    
    async def start_server(self) -> None:
        """Start the WebSocket server."""
        try:
            self.logger.info(f"Starting WebSocket server on {self.host}:{self.port}")
            
            self.server = await websockets.serve(
                self._handle_client_connection,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            self.is_running = True
            
            # Start background tasks
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._queue_processor_task = asyncio.create_task(self._process_animation_queue())
            
            self.logger.info("WebSocket server started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start WebSocket server: {e}")
            raise
    
    async def stop_server(self) -> None:
        """Stop the WebSocket server."""
        try:
            self.logger.info("Stopping WebSocket server...")
            
            self.is_running = False
            
            # Cancel background tasks
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            if self._queue_processor_task:
                self._queue_processor_task.cancel()
                try:
                    await self._queue_processor_task
                except asyncio.CancelledError:
                    pass
            
            # Close all client connections
            if self.clients:
                await asyncio.gather(
                    *[client.close() for client in self.clients.values()],
                    return_exceptions=True
                )
                self.clients.clear()
            
            # Close server
            if self.server:
                self.server.close()
                await self.server.wait_closed()
            
            self.logger.info("WebSocket server stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping WebSocket server: {e}")
    
    async def _handle_client_connection(self, websocket: WebSocketServerProtocol, path: str) -> None:
        """
        Handle new client WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            path: Connection path
        """
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}_{int(time.time())}"
        
        try:
            self.logger.info(f"New WebSocket client connected: {client_id}")
            self.clients[client_id] = websocket
            
            # Send welcome message with current state
            await self._send_to_client(client_id, {
                "type": "connection_established",
                "client_id": client_id,
                "current_animation": asdict(self.current_animation) if self.current_animation else None,
                "queue_length": len(self.animation_queue)
            })
            
            # Handle incoming messages
            async for message in websocket:
                await self._handle_client_message(client_id, message)
                
        except ConnectionClosed:
            self.logger.info(f"Client {client_id} disconnected")
        except WebSocketException as e:
            self.logger.warning(f"WebSocket error for client {client_id}: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error handling client {client_id}: {e}")
        finally:
            # Clean up client connection
            if client_id in self.clients:
                del self.clients[client_id]
    
    async def _handle_client_message(self, client_id: str, message: str) -> None:
        """
        Handle message from WebSocket client.
        
        Args:
            client_id: Client identifier
            message: JSON message from client
        """
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "ping":
                # Handle ping for latency measurement
                await self._send_to_client(client_id, {
                    "type": "pong",
                    "timestamp": data.get("timestamp"),
                    "server_timestamp": time.time()
                })
            
            elif message_type == "animation_complete":
                # Handle animation completion notification
                sequence_id = data.get("sequence_id")
                await self._handle_animation_complete(sequence_id)
            
            elif message_type == "parameter_feedback":
                # Handle Live2D parameter feedback from client
                await self._handle_parameter_feedback(data.get("parameters", {}))
            
            elif message_type == "latency_measurement":
                # Record latency measurement
                latency = data.get("latency", 0)
                self._record_latency(latency)
            
            else:
                self.logger.warning(f"Unknown message type from {client_id}: {message_type}")
                
        except json.JSONDecodeError:
            self.logger.warning(f"Invalid JSON from client {client_id}: {message}")
        except Exception as e:
            self.logger.error(f"Error handling message from {client_id}: {e}")
    
    async def _send_to_client(self, client_id: str, data: Dict[str, Any]) -> bool:
        """
        Send data to specific WebSocket client.
        
        Args:
            client_id: Client identifier
            data: Data to send
            
        Returns:
            bool: True if sent successfully
        """
        if client_id not in self.clients:
            return False
        
        try:
            message = json.dumps(data)
            await self.clients[client_id].send(message)
            return True
            
        except ConnectionClosed:
            self.logger.info(f"Client {client_id} connection closed during send")
            if client_id in self.clients:
                del self.clients[client_id]
            return False
        except Exception as e:
            self.logger.error(f"Error sending to client {client_id}: {e}")
            return False
    
    async def broadcast_animation_event(self, event: AnimationEvent) -> None:
        """
        Broadcast animation event to all connected clients.
        
        Args:
            event: Animation event to broadcast
        """
        if not self.clients:
            self.logger.debug("No clients connected for animation broadcast")
            return
        
        message_data = {
            "type": "animation_event",
            "event": asdict(event)
        }
        
        # Send to all clients
        failed_clients = []
        for client_id in self.clients:
            success = await self._send_to_client(client_id, message_data)
            if not success:
                failed_clients.append(client_id)
        
        # Clean up failed connections
        for client_id in failed_clients:
            if client_id in self.clients:
                del self.clients[client_id]
        
        self.logger.debug(f"Broadcasted animation event to {len(self.clients)} clients")
    
    async def queue_animation(self, event: AnimationEvent) -> None:
        """
        Add animation event to the queue.
        
        Args:
            event: Animation event to queue
        """
        # Check queue size limit
        if len(self.animation_queue) >= self.max_queue_size:
            # Remove oldest low-priority event
            self.animation_queue = sorted(self.animation_queue, key=lambda x: x.priority, reverse=True)
            self.animation_queue.pop()
            self.logger.warning("Animation queue full, removed lowest priority event")
        
        # Add event to queue
        self.animation_queue.append(event)
        
        # Sort by priority and timestamp
        self.animation_queue.sort(key=lambda x: (x.priority, x.timestamp), reverse=True)
        
        self.logger.debug(f"Queued animation event: {event.event_type.value}")
    
    async def _process_animation_queue(self) -> None:
        """Process animation queue in background."""
        while self.is_running:
            try:
                if self.animation_queue and not self.current_animation:
                    # Get next animation from queue
                    next_event = self.animation_queue.pop(0)
                    
                    # Set as current animation
                    self.current_animation = next_event
                    
                    # Broadcast to clients
                    await self.broadcast_animation_event(next_event)
                    
                    # Trigger event handlers
                    await self._trigger_event_handlers(next_event)
                    
                    # If animation has duration, schedule completion
                    if next_event.duration:
                        asyncio.create_task(
                            self._schedule_animation_completion(next_event)
                        )
                
                await asyncio.sleep(0.1)  # Process queue every 100ms
                
            except Exception as e:
                self.logger.error(f"Error processing animation queue: {e}")
                await asyncio.sleep(1.0)
    
    async def _schedule_animation_completion(self, event: AnimationEvent) -> None:
        """
        Schedule animation completion after duration.
        
        Args:
            event: Animation event with duration
        """
        if not event.duration:
            return
        
        await asyncio.sleep(event.duration)
        
        # Clear current animation if it's still this event
        if self.current_animation and self.current_animation.sequence_id == event.sequence_id:
            self.current_animation = None
    
    async def _handle_animation_complete(self, sequence_id: Optional[str]) -> None:
        """
        Handle animation completion notification.
        
        Args:
            sequence_id: Sequence ID of completed animation
        """
        if (self.current_animation and 
            self.current_animation.sequence_id == sequence_id):
            self.current_animation = None
            self.logger.debug(f"Animation completed: {sequence_id}")
    
    async def _handle_parameter_feedback(self, parameters: Dict[str, float]) -> None:
        """
        Handle Live2D parameter feedback from client.
        
        Args:
            parameters: Current Live2D parameters
        """
        # This can be used for monitoring animation state
        self.logger.debug(f"Received parameter feedback: {len(parameters)} parameters")
    
    def _record_latency(self, latency: float) -> None:
        """
        Record latency measurement.
        
        Args:
            latency: Latency in milliseconds
        """
        self.latency_measurements.append(latency)
        
        # Keep only recent measurements
        if len(self.latency_measurements) > self.max_latency_samples:
            self.latency_measurements.pop(0)
    
    async def _trigger_event_handlers(self, event: AnimationEvent) -> None:
        """
        Trigger registered event handlers.
        
        Args:
            event: Animation event
        """
        handlers = self.event_handlers.get(event.event_type, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                self.logger.error(f"Error in event handler: {e}")
    
    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat to clients."""
        while self.is_running:
            try:
                if self.clients:
                    heartbeat_data = {
                        "type": "heartbeat",
                        "timestamp": time.time(),
                        "queue_length": len(self.animation_queue),
                        "current_animation": self.current_animation.event_type.value if self.current_animation else None
                    }
                    
                    # Send heartbeat to all clients
                    for client_id in list(self.clients.keys()):
                        await self._send_to_client(client_id, heartbeat_data)
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(5.0)
    
    def register_event_handler(self, event_type: AnimationEventType, handler: Callable) -> None:
        """
        Register event handler for specific animation event type.
        
        Args:
            event_type: Type of animation event
            handler: Handler function (sync or async)
        """
        self.event_handlers[event_type].append(handler)
        self.logger.debug(f"Registered handler for {event_type.value}")
    
    def get_average_latency(self) -> float:
        """
        Get average network latency.
        
        Returns:
            float: Average latency in milliseconds
        """
        if not self.latency_measurements:
            return 0.0
        
        return sum(self.latency_measurements) / len(self.latency_measurements)
    
    def get_connection_count(self) -> int:
        """
        Get number of connected clients.
        
        Returns:
            int: Number of connected clients
        """
        return len(self.clients)
    
    def create_timing_sync(self, audio_duration: float, tts_delay: float = 0.0) -> TimingSyncData:
        """
        Create timing synchronization data for audio-animation coordination.
        
        Args:
            audio_duration: Duration of audio in seconds
            tts_delay: TTS processing delay in seconds
            
        Returns:
            TimingSyncData: Timing synchronization data
        """
        current_time = time.time()
        
        self.timing_sync_data = TimingSyncData(
            audio_start_time=current_time + tts_delay,
            audio_duration=audio_duration,
            animation_start_time=current_time,
            tts_processing_delay=tts_delay,
            network_latency=self.get_average_latency() / 1000.0  # Convert to seconds
        )
        
        return self.timing_sync_data


# Global WebSocket manager instance
websocket_manager: Optional[WebSocketAnimationManager] = None


def get_websocket_manager() -> WebSocketAnimationManager:
    """
    Get global WebSocket manager instance.
    
    Returns:
        WebSocketAnimationManager: Global manager instance
    """
    global websocket_manager
    if websocket_manager is None:
        websocket_manager = WebSocketAnimationManager()
    return websocket_manager


async def initialize_websocket_server(host: str = "localhost", port: int = 8765) -> WebSocketAnimationManager:
    """
    Initialize and start WebSocket server.
    
    Args:
        host: Server host
        port: Server port
        
    Returns:
        WebSocketAnimationManager: Started manager instance
    """
    manager = get_websocket_manager()
    manager.host = host
    manager.port = port
    await manager.start_server()
    return manager