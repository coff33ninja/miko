"""
Flask web server for Live2D model serving and animation control.

This module provides:
- Static file serving for Live2D models and assets
- Animation API endpoint for triggering Live2D expressions
- LiveKit token generation for client authentication
- Main web interface with Live2D canvas
"""

import os
import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import threading
import time

from flask import Flask, render_template, request, jsonify, send_from_directory
from livekit import api

from src.config.settings import get_settings
from src.web.websocket_manager import (
    get_websocket_manager,
    AnimationEvent,
    AnimationEventType,
)
from src.web.animation_sync import get_animation_synchronizer, AnimationPriority
from src.error_handling.exceptions import (
    Live2DError,
    NetworkError,
    ValidationError,
    LiveKitError,
)
from src.error_handling.fallback_manager import get_fallback_manager, FallbackStrategy
from src.error_handling.error_recovery import get_recovery_manager, RecoveryStrategy
from src.error_handling.logging_handler import get_error_logger

# Configure logging
logger = logging.getLogger(__name__)


class Live2DFlaskApp:
    """Flask application for Live2D model serving and animation control."""

    def __init__(self):
        self.app = Flask(__name__, template_folder="templates", static_folder="static")
        self.settings = get_settings()

        # Error handling components
        self.fallback_manager = get_fallback_manager()
        self.recovery_manager = get_recovery_manager()
        self.error_logger = get_error_logger()

        # Animation state tracking
        self.current_animation = {
            "expression": "neutral",
            "intensity": 0.5,
            "timestamp": datetime.now(),
        }

        # WebSocket and synchronization components
        self.websocket_manager = get_websocket_manager()
        self.animation_sync = get_animation_synchronizer()
        self.websocket_thread: Optional[threading.Thread] = None
        self.websocket_loop: Optional[asyncio.AbstractEventLoop] = None

        # Health tracking
        self.consecutive_failures = 0
        self.last_successful_request = time.time()
        self.websocket_healthy = False
        # Register routes and error recovery once
        self._setup_routes()
        self._register_error_recovery()
        # Separate animation routes are set up in their own method
        # to keep route registration organized.
        self._setup_animation_routes()

    def _setup_routes(self):
        """Set up Flask routes for the application."""

        @self.app.route("/")
        def index():
            """Main web interface with Live2D canvas."""
            return render_template(
                "index.html",
                livekit_url=self.settings.livekit.url,
                model_url=self.settings.live2d.model_url,
            )

        @self.app.route("/animate", methods=["POST"])
        def animate():
            """API endpoint for triggering Live2D expressions with comprehensive error handling."""
            try:
                # Parse request data and add extra debug logging for troubleshooting
                logger.debug(f"Received /animate request content-type: {request.content_type}")
                logger.debug(f"Raw request data: {request.data}")

                # Validate and parse request data
                data = request.get_json(force=True, silent=True)
                logger.debug(f"Parsed JSON data for /animate: {data}")

                if data is None:
                    raise ValidationError("No JSON data provided")

                expression = data.get("expression")
                intensity = data.get("intensity")
                duration = data.get("duration")
                priority = data.get("priority")
                sync_with_audio = data.get("sync_with_audio", False)

                # Explicitly check presence of required fields (allow zero values where valid)
                required_fields = ["expression", "intensity", "duration"]
                missing = [f for f in required_fields if f not in data or data.get(f) is None]

                # Priority is optional; default to NORMAL if missing
                if priority is None:
                    logger.debug("Priority not provided in /animate request; defaulting to 'normal'")
                    priority = "normal"

                if missing:
                    raise ValidationError(f"Missing required animation parameters: {missing}")

                # Ensure correct types and coerce priority (accept strings or numeric values)
                try:
                    intensity = float(intensity)
                    duration = float(duration)

                    # Coerce priority
                    if isinstance(priority, str):
                        try:
                            priority = AnimationPriority[priority.upper()]
                        except KeyError:
                            logger.warning(f"Unknown priority string '{priority}', defaulting to NORMAL")
                            priority = AnimationPriority.NORMAL
                    elif isinstance(priority, (int, float)):
                        # Map numeric priority to enum by value if possible
                        try:
                            priority = AnimationPriority(int(priority))
                        except Exception:
                            logger.warning(f"Numeric priority '{priority}' not valid, defaulting to NORMAL")
                            priority = AnimationPriority.NORMAL
                    else:
                        logger.warning(f"Unrecognized priority type {type(priority)}, defaulting to NORMAL")
                        priority = AnimationPriority.NORMAL

                except (ValueError, KeyError) as e:
                    raise ValidationError(f"Invalid parameter type or value: {e}")

                # Execute animation with fallback
                # Run the async animation execution safely from sync context.
                result = self._run_coro_sync(
                    self._execute_animation_with_fallback(
                        expression, intensity, duration, priority, sync_with_audio
                    )
                )

                if result["success"]:
                    self.consecutive_failures = 0
                    self.last_successful_request = time.time()
                    return jsonify(result)
                else:
                    return jsonify(result), 500

            except ValidationError as e:
                return jsonify({"error": str(e), "error_type": "validation"}), 400
            except Exception as e:
                self.consecutive_failures += 1
                logger.exception("Error in animate endpoint:")  # Added for debugging
                self.error_logger.log_error(
                    e, component="web_server", operation="animate"
                )
                return jsonify({"error": "Internal server error"}), 500

    def _run_coro_sync(self, coro):
        """Run coroutine from sync context safely, handling existing event loop.

        This helper will detect if there's an already running event loop
        (for example when using the Flask dev server with reloader tools)
        and will run the coroutine in a new temporary loop in a thread if
        necessary. Otherwise it will use asyncio.run.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Running loop exists; schedule work in a new thread to avoid
            # "asyncio.run() cannot be called from a running event loop" errors.
            result_holder = {}

            def _thread_target():
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    result_holder["result"] = new_loop.run_until_complete(coro)
                    new_loop.close()
                except Exception as thread_exc:
                    result_holder["error"] = thread_exc

            t = threading.Thread(target=_thread_target)
            t.start()
            t.join()

            if "error" in result_holder:
                raise result_holder["error"]

            return result_holder.get("result")
        else:
            return asyncio.run(coro)

    async def _execute_animation_with_fallback(
        self,
        expression: str,
        intensity: float,
        duration: float,
        priority: AnimationPriority,
        sync_with_audio: bool,
    ) -> Dict[str, Any]:
        """Execute animation with fallback strategies."""
        try:
            # Update animation state
            self.current_animation = {
                "expression": expression,
                "intensity": intensity,
                "duration": duration,
                "timestamp": datetime.now(),
                "sync_with_audio": sync_with_audio,
            }

            # Try WebSocket animation first
            sequence_id = None
            if self.websocket_loop and not self.websocket_loop.is_closed():
                try:
                    # Schedule animation in the WebSocket event loop
                    future = asyncio.run_coroutine_threadsafe(
                        self.animation_sync.trigger_expression_change(
                            expression=expression,
                            intensity=intensity,
                            duration=duration,
                            priority=priority,
                        ),
                        self.websocket_loop,
                    )
                    sequence_id = await asyncio.wait_for(
                        asyncio.wrap_future(future), timeout=5.0
                    )

                    self.websocket_healthy = True

                except asyncio.TimeoutError:
                    logger.warning("WebSocket animation timeout, using static fallback")
                    raise Live2DError(
                        "WebSocket animation timeout",
                        operation="trigger_animation",
                        animation_type=expression,
                    )
                except Exception as sync_error:
                    logger.warning(f"WebSocket sync failed: {sync_error}")
                    self.websocket_healthy = False
                    raise Live2DError(
                        f"WebSocket sync failed: {sync_error}",
                        operation="trigger_animation",
                        animation_type=expression,
                    )
            else:
                # WebSocket not available, use static fallback
                logger.info("WebSocket not available, using static animation")
                self.websocket_healthy = False

            logger.info(
                f"Animation triggered: {expression} (intensity: {intensity}, duration: {duration})"
            )

            return {
                "success": True,
                "animation": self.current_animation,
                "sequence_id": sequence_id,
                "websocket_active": self.websocket_loop is not None
                and not self.websocket_loop.is_closed(),
                "websocket_healthy": self.websocket_healthy,
            }

        except Live2DError as e:
            # Handle Live2D specific errors with fallback
            return await self._handle_animation_fallback(expression, intensity, e)
        except Exception as e:
            # Handle unexpected errors
            self.error_logger.log_error(
                e, component="web_server", operation="execute_animation"
            )
            return {
                "success": False,
                "error": "Animation system error",
                "fallback_used": True,
                "animation": self.current_animation,
            }

    async def _handle_animation_fallback(
        self, expression: str, intensity: float, original_error: Exception
    ) -> Dict[str, Any]:
        """Handle animation fallback when WebSocket fails."""
        try:
            # Log fallback usage
            self.error_logger.log_fallback_usage(
                component="live2d_animation",
                fallback_strategy="static_fallback",
                original_error=original_error,
                fallback_success=True,
            )

            # Return static fallback response
            return {
                "success": True,
                "animation": self.current_animation,
                "sequence_id": None,
                "websocket_active": False,
                "websocket_healthy": False,
                "fallback_used": True,
                "fallback_reason": str(original_error),
            }

        except Exception as fallback_error:
            logger.error(f"Animation fallback also failed: {fallback_error}")
            return {
                "success": False,
                "error": "Animation system completely failed",
                "original_error": str(original_error),
                "fallback_error": str(fallback_error),
            }

    def _setup_animation_routes(self):
        """Setup animation-related routes."""
        @self.app.route("/animate/status")
        def animation_status():
            """Get current animation status with sync information."""
            sync_state = {}
            if self.websocket_loop and not self.websocket_loop.is_closed():
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self._get_sync_state(), self.websocket_loop
                    )
                    sync_state = future.result(timeout=0.5)
                except Exception:
                    sync_state = {"error": "Failed to get sync state"}

            return jsonify(
                {
                    "current_animation": self.current_animation,
                    "timestamp": self.current_animation["timestamp"].isoformat(),
                    "websocket_active": self.websocket_loop is not None,
                    "connected_clients": self.websocket_manager.get_connection_count(),
                    "sync_state": sync_state,
                }
            )

        @self.app.route("/animate/sync/tts", methods=["POST"])
        def sync_with_tts():
            """Synchronize animation with TTS audio."""
            try:
                data = request.get_json(force=True, silent=True)
                if data is None:
                    return jsonify({"error": "No JSON data provided"}), 400

                text = data.get("text", "")
                expression = data.get("expression", "speak")
                audio_duration = data.get("audio_duration")
                tts_delay = float(data.get("tts_processing_delay", 0.2))

                if not text:
                    return jsonify({"error": "Text is required for TTS sync"}), 400

                # Trigger TTS synchronization
                sequence_id = None
                if self.websocket_loop and not self.websocket_loop.is_closed():
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            self.animation_sync.synchronize_with_tts(
                                text=text,
                                expression=expression,
                                audio_duration=audio_duration,
                                tts_processing_delay=tts_delay,
                            ),
                            self.websocket_loop,
                        )
                        sequence_id = future.result(timeout=2.0)
                    except Exception as sync_error:
                        logger.error(f"TTS sync failed: {sync_error}")
                        return (
                            jsonify({"error": f"TTS sync failed: {str(sync_error)}"}),
                            500,
                        )
                else:
                    return jsonify({"error": "WebSocket not active"}), 503

                logger.info(f"TTS animation synchronized: {sequence_id}")

                return jsonify(
                    {
                        "success": True,
                        "sequence_id": sequence_id,
                        "text_length": len(text),
                        "estimated_duration": audio_duration
                        or self.animation_sync._estimate_audio_duration(text),
                    }
                )

            except Exception as e:
                logger.error(f"TTS sync error: {e}")
                return jsonify({"error": "Internal server error"}), 500

        @self.app.route("/animate/sync/mouth", methods=["POST"])
        def control_mouth_sync():
            """Control mouth synchronization."""
            try:
                data = request.get_json(force=True, silent=True)
                if data is None:
                    return jsonify({"error": "No JSON data provided"}), 400

                action = data.get("action", "start")  # 'start' or 'stop'
                audio_level = data.get("audio_level", 0.0)
                frequency_data = data.get("frequency_data", [])

                if self.websocket_loop and not self.websocket_loop.is_closed():
                    try:
                        if action == "start":
                            future = asyncio.run_coroutine_threadsafe(
                                self.animation_sync.start_mouth_sync(
                                    duration=data.get("duration")
                                ),
                                self.websocket_loop,
                            )
                            future.result(timeout=1.0)
                        elif action == "stop":
                            future = asyncio.run_coroutine_threadsafe(
                                self.animation_sync.stop_mouth_sync(),
                                self.websocket_loop,
                            )
                            future.result(timeout=1.0)
                        elif action == "update":
                            future = asyncio.run_coroutine_threadsafe(
                                self.animation_sync.update_mouth_parameters(
                                    audio_level=audio_level,
                                    frequency_data=frequency_data,
                                ),
                                self.websocket_loop,
                            )
                            future.result(timeout=1.0)
                        else:
                            return jsonify({"error": f"Unknown action: {action}"}), 400
                    except Exception as sync_error:
                        logger.error(f"Mouth sync control failed: {sync_error}")
                        return (
                            jsonify({"error": f"Mouth sync failed: {str(sync_error)}"}),
                            500,
                        )
                else:
                    return jsonify({"error": "WebSocket not active"}), 503

                return jsonify(
                    {
                        "success": True,
                        "action": action,
                        "is_speaking": self.animation_sync.is_speaking,
                    }
                )

            except Exception as e:
                logger.error(f"Mouth sync control error: {e}")
                return jsonify({"error": "Internal server error"}), 500

        @self.app.route("/token", methods=["POST"])
        def generate_token():
            """Generate LiveKit token for client authentication with error handling."""
            try:
                data = request.get_json(force=True, silent=True)
                if data is None:
                    return jsonify({"error": "No JSON data provided"}), 400

                room_name = data.get("room", "anime-character-room")
                participant_name = data.get(
                    "participant", f"user-{datetime.now().timestamp()}"
                )

                # Validate LiveKit configuration
                if (
                    not self.settings.livekit.api_key
                    or not self.settings.livekit.api_secret
                ):
                    raise ValidationError("LiveKit API credentials not configured")

                # Generate LiveKit access token with error handling
                try:
                    token = api.AccessToken(
                        api_key=self.settings.livekit.api_key,
                        api_secret=self.settings.livekit.api_secret,
                    )

                    # Set token permissions
                    token.with_identity(participant_name)
                    token.with_name(participant_name)
                    token.with_grants(
                        api.VideoGrants(
                            room_join=True,
                            room=room_name,
                            can_publish=True,
                            can_subscribe=True,
                        )
                    )

                    # Set token expiration (1 hour)
                    token.with_ttl(timedelta(hours=1))

                    jwt_token = token.to_jwt()

                except Exception as token_error:
                    raise LiveKitError(
                        f"Failed to generate LiveKit token: {token_error}",
                        operation="generate_token",
                        room_name=room_name,
                        participant_id=participant_name,
                    )

                logger.info(
                    f"Generated token for participant: {participant_name} in room: {room_name}"
                )

                return jsonify(
                    {
                        "token": jwt_token,
                        "room": room_name,
                        "participant": participant_name,
                        "url": self.settings.livekit.url,
                        "expires_in": 3600,  # 1 hour in seconds
                    }
                )

            except ValidationError as e:
                return jsonify({"error": str(e), "error_type": "validation"}), 400
            except LiveKitError as e:
                self.error_logger.log_error(
                    e, component="web_server", operation="generate_token"
                )
                return (
                    jsonify(
                        {"error": "Failed to generate token", "error_type": "livekit"}
                    ),
                    500,
                )
            except Exception as e:
                self.error_logger.log_error(
                    e, component="web_server", operation="generate_token"
                )
                return jsonify({"error": "Internal server error"}), 500

        @self.app.route("/static/<path:filename>")
        def serve_static(filename):
            """Serve static files for Live2D models and assets."""
            try:
                static_dir = os.path.join(os.path.dirname(__file__), "static")
                return send_from_directory(static_dir, filename)
            except Exception as e:
                logger.error(f"Static file serving error: {e}")
                return jsonify({"error": "File not found"}), 404

        @self.app.route("/health")
        def health_check():
            """Comprehensive health check endpoint."""
            try:
                health_status = {
                    "status": "healthy",
                    "timestamp": datetime.now().isoformat(),
                    "version": "1.0.0",
                    "components": {
                        "web_server": {
                            "status": "healthy",
                            "consecutive_failures": self.consecutive_failures,
                            "last_successful_request": datetime.fromtimestamp(
                                self.last_successful_request
                            ).isoformat(),
                        },
                        "websocket": {
                            "status": (
                                "healthy" if self.websocket_healthy else "degraded"
                            ),
                            "active": self.websocket_loop is not None
                            and not self.websocket_loop.is_closed(),
                            "connected_clients": (
                                self.websocket_manager.get_connection_count()
                                if hasattr(
                                    self.websocket_manager, "get_connection_count"
                                )
                                else 0
                            ),
                        },
                        "animation_sync": {
                            "status": "healthy",
                            "active_sequences": (
                                len(self.animation_sync.active_sequences)
                                if hasattr(self.animation_sync, "active_sequences")
                                else 0
                            ),
                        },
                    },
                }

                # Determine overall status
                if self.consecutive_failures > 5:
                    health_status["status"] = "degraded"
                elif not self.websocket_healthy:
                    health_status["status"] = "degraded"

                # Add error recovery stats if available
                try:
                    recovery_stats = self.recovery_manager.get_recovery_stats()
                    health_status["error_recovery"] = recovery_stats
                except Exception:
                    pass

                status_code = 200 if health_status["status"] == "healthy" else 503
                return jsonify(health_status), status_code

            except Exception as e:
                logger.error(f"Health check error: {e}")
                return (
                    jsonify(
                        {
                            "status": "unhealthy",
                            "error": str(e),
                            "timestamp": datetime.now().isoformat(),
                        }
                    ),
                    503,
                )

        # Error handlers
        @self.app.errorhandler(404)
        def not_found(error):
            if request.path.startswith("/static/"):
                return jsonify({"error": "File not found"}), 404
            return jsonify({"error": "Not found"}), 404

        @self.app.errorhandler(500)
        def internal_error(error):
            logger.error(f"Internal server error: {error}")
            return jsonify({"error": "Internal server error"}), 500

        @self.app.route("/debug/animation_types")
        def animation_types_info():
            """Return information about AnimationEvent and AnimationEventType."""
            event_info = {
                "class_name": AnimationEvent.__name__,
                "doc": AnimationEvent.__doc__,
                "fields": list(AnimationEvent.__annotations__.keys())
            }
            event_type_info = {
                "class_name": AnimationEventType.__name__,
                "doc": AnimationEventType.__doc__,
                "members": [member.name for member in AnimationEventType]
            }
            return jsonify({
                "AnimationEvent": event_info,
                "AnimationEventType": event_type_info
            })

    def run(self, host="0.0.0.0", port=5000, debug=False, enable_websocket=True):
        """Run the Flask application with optional WebSocket server."""
        logger.info(f"Starting Flask server on {host}:{port}")

        # Start WebSocket server in background thread if enabled
        if enable_websocket:
            self._start_websocket_server()

        try:
            self.app.run(host=host, port=port, debug=debug)
        finally:
            # Clean up WebSocket server
            if self.websocket_loop:
                self._stop_websocket_server()

    def _start_websocket_server(self):
        """Start WebSocket server in background thread."""

        def websocket_thread():
            try:
                # Create new event loop for WebSocket server
                self.websocket_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.websocket_loop)

                # Configure WebSocket server to listen on the same interface as Flask
                ws_host = self.settings.flask.host or "0.0.0.0"  # Use same host as Flask, default to all interfaces
                ws_port = 8765  # WebSocket port

                # Start WebSocket manager with proper host binding
                self.websocket_manager.host = ws_host
                self.websocket_manager.port = ws_port
                logger.info(f"Configuring WebSocket server on {ws_host}:{ws_port}")
                self.websocket_loop.run_until_complete(
                    self.websocket_manager.start_server()
                )

                logger.info(f"WebSocket server started on {ws_host}:{ws_port}")

                # Keep the loop running
                self.websocket_loop.run_forever()

            except Exception as e:
                logger.error(f"WebSocket server error: {e}")
            finally:
                if self.websocket_loop:
                    self.websocket_loop.close()

        self.websocket_thread = threading.Thread(target=websocket_thread, daemon=True)
        self.websocket_thread.start()

        # Wait a moment for WebSocket server to start
        time.sleep(1.0)

    def _stop_websocket_server(self):
        """Stop WebSocket server."""
        if self.websocket_loop and not self.websocket_loop.is_closed():
            try:
                # Schedule server stop
                asyncio.run_coroutine_threadsafe(
                    self.websocket_manager.stop_server(), self.websocket_loop
                )

                # Stop the event loop
                self.websocket_loop.call_soon_threadsafe(self.websocket_loop.stop)

                # Wait for thread to finish
                if self.websocket_thread and self.websocket_thread.is_alive():
                    self.websocket_thread.join(timeout=5.0)

                logger.info("WebSocket server stopped")

            except Exception as e:
                logger.error(f"Error stopping WebSocket server: {e}")

    async def _get_sync_state(self):
        """Get current synchronization state."""
        return self.animation_sync.get_animation_state()

    def _register_error_recovery(self):
        """Register web server components with error recovery system."""
        self.recovery_manager.register_component(
            component_name="web_server",
            recovery_strategies=[
                RecoveryStrategy.RESTART_SERVICE,
                RecoveryStrategy.CLEAR_STATE,
                RecoveryStrategy.WAIT_AND_RETRY,
            ],
            health_check_func=self._web_server_health_check,
        )

        # Register fallback strategies
        self.fallback_manager.register_fallback_chain(
            component="live2d_animation",
            strategies=[
                FallbackStrategy.RETRY,
                FallbackStrategy.STATIC_FALLBACK,
                FallbackStrategy.ERROR_MESSAGE,
            ],
        )

        self.fallback_manager.register_fallback_chain(
            component="animation_trigger",
            strategies=[FallbackStrategy.RETRY, FallbackStrategy.STATIC_FALLBACK],
        )

    async def _web_server_health_check(self) -> bool:
        """Health check for web server."""
        try:
            # Check if Flask app is responsive
            return (
                self.consecutive_failures < 10
                and time.time() - self.last_successful_request < 300
            )
        except Exception:
            return False

    def get_app(self):
        """Get the Flask application instance for testing."""
        return self.app


def create_app() -> Flask:
    """Factory function to create Flask application."""
    flask_app = Live2DFlaskApp()
    return flask_app.get_app()


async def trigger_animation(
    expression: str, intensity: float = 0.7, duration: float = 2.0
) -> bool:
    """
    Trigger Live2D animation via HTTP API call with comprehensive error handling.

    This function is used by the LiveKit agent to trigger animations
    based on AI response sentiment.

    Args:
        expression: Animation expression ('happy', 'sad', 'angry', 'neutral', etc.)
        intensity: Animation intensity (0.0 to 1.0)
        duration: Animation duration in seconds

    Returns:
        bool: True if animation was triggered successfully
    """
    fallback_manager = get_fallback_manager()
    error_logger = get_error_logger()

    result = await fallback_manager.execute_with_fallback(
        component="animation_trigger",
        primary_operation=_trigger_animation_internal,
        operation_args=(expression, intensity, duration),
        context={
            "retry_operation": _trigger_animation_internal,
            "max_retries": 3,
            "expression": expression,
        },
    )

    if result.success:
        return result.result
    else:
        error_logger.log_fallback_usage(
            component="animation_trigger",
            fallback_strategy=(
                result.strategy_used.value if result.strategy_used else "none"
            ),
            original_error=result.error,
            fallback_success=False,
        )
        return False


async def _trigger_animation_internal(
    expression: str, intensity: float, duration: float
) -> bool:
    """Internal animation trigger with error handling."""
    max_retries = 3

    for attempt in range(max_retries):
        try:
            # Get Flask server configuration
            settings = get_settings()
            flask_url = f"http://{settings.flask.host}:{settings.flask.port}"

            # Prepare animation data
            animation_data = {
                "expression": expression,
                "intensity": intensity,
                "duration": duration,
            }

            # Make async HTTP request to Flask animation endpoint
            timeout = aiohttp.ClientTimeout(
                total=5.0 + attempt * 2
            )  # Increase timeout on retries

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{flask_url}/animate", json=animation_data, timeout=timeout
                ) as response:
                    if response.status == 200:
                        logger.info(f"Animation triggered successfully: {expression}")
                        return True
                    elif response.status == 400:
                        # Client error - don't retry
                        response_text = await response.text()
                        raise ValidationError(
                            f"Invalid animation parameters: {response_text}"
                        )
                    elif response.status >= 500:
                        # Server error - retry
                        if attempt < max_retries - 1:
                            wait_time = 2**attempt
                            logger.warning(
                                f"Server error {response.status}, retrying in {wait_time}s"
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            raise NetworkError(
                                f"Animation server error: {response.status}",
                                operation="trigger_animation",
                                endpoint=flask_url,
                                status_code=response.status,
                            )
                    else:
                        logger.warning(
                            f"Animation trigger failed with status {response.status}"
                        )
                        return False

        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                logger.warning(
                    f"Animation trigger timeout, attempt {attempt + 1}/{max_retries}"
                )
                await asyncio.sleep(1.0)
                continue
            else:
                raise NetworkError(
                    "Animation trigger timeout after all retries",
                    operation="trigger_animation",
                    endpoint=f"http://{settings.flask.host}:{settings.flask.port}",
                    is_timeout=True,
                )
        except aiohttp.ClientError as e:
            if attempt < max_retries - 1:
                logger.warning(f"Animation trigger client error: {e}, retrying...")
                await asyncio.sleep(1.0)
                continue
            else:
                raise NetworkError(
                    f"Animation trigger client error: {e}",
                    operation="trigger_animation",
                    endpoint=f"http://{settings.flask.host}:{settings.flask.port}",
                )
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Animation trigger error: {e}, retrying...")
                await asyncio.sleep(1.0)
                continue
            else:
                raise Live2DError(
                    f"Failed to trigger animation: {e}",
                    operation="trigger_animation",
                    animation_type=expression,
                )

    return False


if __name__ == "__main__":
    app = Live2DFlaskApp()
    app.run(debug=True)
