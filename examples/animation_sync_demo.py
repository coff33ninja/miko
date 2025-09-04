#!/usr/bin/env python3
"""
Real-time Animation Synchronization Demo

This demo showcases the complete real-time animation synchronization system
including WebSocket communication, TTS timing, and Live2D animation coordination.
"""

import asyncio
import logging
import time
import json
from typing import Optional
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add src to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import our synchronization components
from web.websocket_manager import (
    WebSocketAnimationManager, AnimationEvent, AnimationEventType,
    get_websocket_manager
)
from web.animation_sync import (
    AnimationSynchronizer, AnimationPriority, get_animation_synchronizer
)


class AnimationSyncDemo:
    """
    Demonstration of real-time animation synchronization capabilities.
    """
    
    def __init__(self):
        self.websocket_manager = get_websocket_manager()
        self.animation_sync = get_animation_synchronizer()
        self.demo_running = False
        
        # Demo configuration
        self.demo_scenarios = [
            {
                "name": "Basic Expression Change",
                "description": "Simple expression change with smooth transition",
                "action": self.demo_expression_change
            },
            {
                "name": "TTS Synchronization",
                "description": "Synchronized animation with simulated TTS audio",
                "action": self.demo_tts_sync
            },
            {
                "name": "Mouth Sync Simulation",
                "description": "Real-time mouth synchronization with audio levels",
                "action": self.demo_mouth_sync
            },
            {
                "name": "Animation Queue Management",
                "description": "Multiple animations with priority handling",
                "action": self.demo_animation_queue
            },
            {
                "name": "Timing Precision Test",
                "description": "Test timing accuracy and synchronization precision",
                "action": self.demo_timing_precision
            }
        ]
    
    async def start_demo(self):
        """Start the animation synchronization demo."""
        logger.info("Starting Real-time Animation Synchronization Demo")
        
        try:
            # Start WebSocket server
            logger.info("Starting WebSocket server...")
            await self.websocket_manager.start_server()
            
            # Wait for server to be ready
            await asyncio.sleep(1.0)
            
            self.demo_running = True
            
            # Run demo scenarios
            await self.run_demo_scenarios()
            
        except Exception as e:
            logger.error(f"Demo error: {e}")
        finally:
            await self.cleanup()
    
    async def run_demo_scenarios(self):
        """Run all demo scenarios."""
        logger.info("Running animation synchronization demo scenarios...")
        
        for i, scenario in enumerate(self.demo_scenarios, 1):
            if not self.demo_running:
                break
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Demo {i}/{len(self.demo_scenarios)}: {scenario['name']}")
            logger.info(f"Description: {scenario['description']}")
            logger.info(f"{'='*60}")
            
            try:
                await scenario['action']()
                
                # Wait between scenarios
                logger.info("Scenario completed. Waiting before next scenario...")
                await asyncio.sleep(3.0)
                
            except Exception as e:
                logger.error(f"Error in scenario '{scenario['name']}': {e}")
                continue
        
        logger.info("\nAll demo scenarios completed!")
    
    async def demo_expression_change(self):
        """Demo basic expression changes with transitions."""
        logger.info("Demonstrating expression changes...")
        
        expressions = ["happy", "sad", "surprised", "angry", "neutral"]
        
        for expression in expressions:
            logger.info(f"Triggering expression: {expression}")
            
            sequence_id = await self.animation_sync.trigger_expression_change(
                expression=expression,
                intensity=0.8,
                duration=2.0,
                priority=AnimationPriority.NORMAL
            )
            
            logger.info(f"Expression change queued: {sequence_id}")
            
            # Monitor animation state
            await self.monitor_animation_state(duration=2.5)
            
            await asyncio.sleep(1.0)
    
    async def demo_tts_sync(self):
        """Demo TTS synchronization with timing coordination."""
        logger.info("Demonstrating TTS synchronization...")
        
        test_phrases = [
            {
                "text": "Hello! How are you doing today?",
                "expression": "happy",
                "estimated_duration": 2.5
            },
            {
                "text": "I'm sorry to hear that you're feeling sad.",
                "expression": "sad", 
                "estimated_duration": 3.0
            },
            {
                "text": "Wow! That's absolutely amazing news!",
                "expression": "surprised",
                "estimated_duration": 2.8
            }
        ]
        
        for phrase in test_phrases:
            logger.info(f"Synchronizing TTS: '{phrase['text']}'")
            
            # Simulate TTS processing delay
            tts_delay = 0.3
            
            sequence_id = await self.animation_sync.synchronize_with_tts(
                text=phrase["text"],
                expression=phrase["expression"],
                audio_duration=phrase["estimated_duration"],
                tts_processing_delay=tts_delay
            )
            
            logger.info(f"TTS sync sequence created: {sequence_id}")
            
            # Monitor the complete TTS sequence
            total_duration = phrase["estimated_duration"] + tts_delay + 1.0
            await self.monitor_animation_state(duration=total_duration)
            
            await asyncio.sleep(1.0)
    
    async def demo_mouth_sync(self):
        """Demo real-time mouth synchronization."""
        logger.info("Demonstrating mouth synchronization...")
        
        # Start mouth sync
        await self.animation_sync.start_mouth_sync(duration=5.0)
        logger.info("Mouth sync started")
        
        # Simulate varying audio levels
        for i in range(50):  # 5 seconds at 10 FPS
            # Generate simulated audio data
            time_factor = i / 10.0  # Time in seconds
            
            # Simulate speech pattern with varying intensity
            base_level = 0.3 + 0.4 * abs(time.sin(time_factor * 3.0))  # Base speech level
            noise = 0.1 * (time.time() % 1.0 - 0.5)  # Add some noise
            audio_level = max(0.0, min(1.0, base_level + noise))
            
            # Generate frequency data (simplified)
            frequency_data = [
                0.1 + 0.2 * abs(time.sin(time_factor * 2.0 + j)) 
                for j in range(8)
            ]
            
            # Update mouth parameters
            await self.animation_sync.update_mouth_parameters(
                audio_level=audio_level,
                frequency_data=frequency_data
            )
            
            logger.info(f"Mouth sync update: level={audio_level:.2f}")
            
            await asyncio.sleep(0.1)  # 10 FPS update rate
        
        # Stop mouth sync
        await self.animation_sync.stop_mouth_sync()
        logger.info("Mouth sync stopped")
    
    async def demo_animation_queue(self):
        """Demo animation queue management with priorities."""
        logger.info("Demonstrating animation queue management...")
        
        # Queue multiple animations with different priorities
        animations = [
            ("neutral", AnimationPriority.LOW, 1.0),
            ("happy", AnimationPriority.NORMAL, 1.5),
            ("surprised", AnimationPriority.HIGH, 1.0),
            ("angry", AnimationPriority.CRITICAL, 2.0),
            ("sad", AnimationPriority.NORMAL, 1.5)
        ]
        
        logger.info("Queuing multiple animations with different priorities...")
        
        sequence_ids = []
        for expression, priority, duration in animations:
            sequence_id = await self.animation_sync.trigger_expression_change(
                expression=expression,
                intensity=0.7,
                duration=duration,
                priority=priority
            )
            sequence_ids.append(sequence_id)
            logger.info(f"Queued: {expression} (priority: {priority.name}, duration: {duration}s)")
        
        # Monitor queue processing
        logger.info("Monitoring queue processing...")
        
        start_time = time.time()
        while time.time() - start_time < 10.0:  # Monitor for 10 seconds
            queue_length = len(self.websocket_manager.animation_queue)
            active_sequences = len(self.animation_sync.active_sequences)
            
            logger.info(f"Queue: {queue_length} pending, {active_sequences} active")
            
            if queue_length == 0 and active_sequences == 0:
                logger.info("All animations processed!")
                break
            
            await asyncio.sleep(1.0)
    
    async def demo_timing_precision(self):
        """Demo timing precision and synchronization accuracy."""
        logger.info("Demonstrating timing precision...")
        
        # Test precise timing with multiple synchronized events
        base_time = time.time() + 2.0  # Start in 2 seconds
        
        # Schedule multiple events at precise intervals
        events = [
            (base_time + 0.0, "neutral", "Event 1: Start"),
            (base_time + 1.0, "happy", "Event 2: +1.0s"),
            (base_time + 2.5, "surprised", "Event 3: +2.5s"),
            (base_time + 4.0, "sad", "Event 4: +4.0s"),
            (base_time + 5.5, "neutral", "Event 5: +5.5s (end)")
        ]
        
        logger.info("Scheduling precisely timed events...")
        
        for event_time, expression, description in events:
            # Create animation event with precise timing
            animation_event = AnimationEvent(
                event_type=AnimationEventType.EXPRESSION_CHANGE,
                timestamp=event_time,
                data={
                    "expression": expression,
                    "intensity": 0.7,
                    "duration": 1.0,
                    "description": description
                },
                sequence_id=f"timing-test-{int(event_time * 1000)}",
                duration=1.0,
                priority=AnimationPriority.HIGH.value
            )
            
            await self.websocket_manager.queue_animation(animation_event)
            logger.info(f"Scheduled: {description} at {datetime.fromtimestamp(event_time).strftime('%H:%M:%S.%f')[:-3]}")
        
        # Monitor timing accuracy
        logger.info("Monitoring timing accuracy...")
        
        start_monitor = time.time()
        while time.time() - start_monitor < 8.0:  # Monitor for 8 seconds
            current_time = time.time()
            
            # Check for events that should have triggered
            for event_time, expression, description in events:
                if abs(current_time - event_time) < 0.1:  # Within 100ms
                    actual_delay = (current_time - event_time) * 1000  # Convert to ms
                    logger.info(f"TIMING: {description} - Delay: {actual_delay:.1f}ms")
            
            await asyncio.sleep(0.1)
    
    async def monitor_animation_state(self, duration: float):
        """Monitor animation state for a specified duration."""
        start_time = time.time()
        
        while time.time() - start_time < duration:
            state = self.animation_sync.get_animation_state()
            
            logger.info(
                f"Animation State: "
                f"current={state['current_expression']}, "
                f"target={state['target_expression']}, "
                f"speaking={state['is_speaking']}, "
                f"transitioning={state['is_transitioning']}, "
                f"sequences={state['active_sequences']}"
            )
            
            await asyncio.sleep(0.5)
    
    async def cleanup(self):
        """Clean up demo resources."""
        logger.info("Cleaning up demo resources...")
        
        self.demo_running = False
        
        try:
            # Stop WebSocket server
            if self.websocket_manager.is_running:
                await self.websocket_manager.stop_server()
            
            # Clean up active sequences
            self.animation_sync.active_sequences.clear()
            
            logger.info("Demo cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


class WebSocketTestClient:
    """
    Test client to simulate WebSocket connections and verify synchronization.
    """
    
    def __init__(self, server_url: str = "ws://localhost:8765"):
        self.server_url = server_url
        self.websocket = None
        self.connected = False
        self.received_events = []
    
    async def connect(self):
        """Connect to WebSocket server."""
        try:
            import websockets
            
            logger.info(f"Connecting test client to {self.server_url}")
            self.websocket = await websockets.connect(self.server_url)
            self.connected = True
            
            # Start message handler
            asyncio.create_task(self.message_handler())
            
            logger.info("Test client connected successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect test client: {e}")
    
    async def message_handler(self):
        """Handle incoming WebSocket messages."""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                self.received_events.append(data)
                
                logger.info(f"Test client received: {data.get('type', 'unknown')}")
                
                # Respond to specific message types
                if data.get('type') == 'heartbeat':
                    await self.send_heartbeat_response()
                
        except Exception as e:
            logger.error(f"Test client message handler error: {e}")
        finally:
            self.connected = False
    
    async def send_heartbeat_response(self):
        """Send heartbeat response."""
        if self.websocket:
            response = {
                "type": "heartbeat_response",
                "timestamp": time.time()
            }
            await self.websocket.send(json.dumps(response))
    
    async def disconnect(self):
        """Disconnect from WebSocket server."""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            logger.info("Test client disconnected")
    
    def get_received_events(self):
        """Get list of received events."""
        return self.received_events.copy()


async def run_demo_with_client():
    """Run demo with test client to verify WebSocket communication."""
    logger.info("Starting demo with WebSocket test client...")
    
    # Create demo and test client
    demo = AnimationSyncDemo()
    test_client = WebSocketTestClient()
    
    try:
        # Start demo (this starts the WebSocket server)
        demo_task = asyncio.create_task(demo.start_demo())
        
        # Wait for server to start
        await asyncio.sleep(2.0)
        
        # Connect test client
        await test_client.connect()
        
        # Wait for demo to complete
        await demo_task
        
        # Check received events
        events = test_client.get_received_events()
        logger.info(f"Test client received {len(events)} events")
        
        for event in events:
            logger.info(f"Event: {event.get('type')} - {event}")
        
    except Exception as e:
        logger.error(f"Demo with client error: {e}")
    finally:
        # Cleanup
        await test_client.disconnect()
        await demo.cleanup()


def main():
    """Main demo entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Real-time Animation Synchronization Demo")
    parser.add_argument(
        "--with-client", 
        action="store_true", 
        help="Run demo with WebSocket test client"
    )
    parser.add_argument(
        "--scenario", 
        type=int, 
        help="Run specific scenario (1-5)"
    )
    
    args = parser.parse_args()
    
    try:
        if args.with_client:
            asyncio.run(run_demo_with_client())
        else:
            demo = AnimationSyncDemo()
            
            if args.scenario:
                # Run specific scenario
                if 1 <= args.scenario <= len(demo.demo_scenarios):
                    scenario = demo.demo_scenarios[args.scenario - 1]
                    logger.info(f"Running scenario: {scenario['name']}")
                    
                    async def run_single_scenario():
                        await demo.websocket_manager.start_server()
                        await asyncio.sleep(1.0)
                        await scenario['action']()
                        await demo.cleanup()
                    
                    asyncio.run(run_single_scenario())
                else:
                    logger.error(f"Invalid scenario number: {args.scenario}")
            else:
                # Run full demo
                asyncio.run(demo.start_demo())
                
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}")


if __name__ == "__main__":
    main()