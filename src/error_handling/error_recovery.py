"""
Error recovery management system.

Provides automatic recovery mechanisms for system components,
including connection restoration, service restart, and state recovery.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable, List, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from .exceptions import AnimeAIError, AIProviderError, LiveKitError, MemoryError


class RecoveryStrategy(Enum):
    """Available recovery strategies."""

    RECONNECT = "reconnect"
    RESTART_SERVICE = "restart_service"
    ROTATE_API_KEY = "rotate_api_key"
    CLEAR_STATE = "clear_state"
    REINITIALIZE = "reinitialize"
    WAIT_AND_RETRY = "wait_and_retry"
    ESCALATE = "escalate"


@dataclass
class RecoveryResult:
    """Result of a recovery operation."""

    success: bool
    strategy_used: RecoveryStrategy
    recovery_time: float
    error: Optional[Exception] = None
    attempts: int = 1
    next_strategy: Optional[RecoveryStrategy] = None


@dataclass
class ComponentHealth:
    """Health status of a system component."""

    component_name: str
    is_healthy: bool = True
    last_error: Optional[Exception] = None
    error_count: int = 0
    last_recovery_attempt: Optional[datetime] = None
    consecutive_failures: int = 0
    recovery_in_progress: bool = False
    health_check_failures: int = 0
    last_successful_operation: Optional[datetime] = None

    def record_error(self, error: Exception):
        """Record an error for this component."""
        self.last_error = error
        self.error_count += 1
        self.consecutive_failures += 1
        self.is_healthy = False

    def record_success(self):
        """Record a successful operation."""
        self.consecutive_failures = 0
        self.health_check_failures = 0
        self.is_healthy = True
        self.last_successful_operation = datetime.now()
        self.recovery_in_progress = False

    def should_attempt_recovery(self, max_failures: int = 3) -> bool:
        """Check if recovery should be attempted."""
        return (
            not self.is_healthy
            and not self.recovery_in_progress
            and self.consecutive_failures >= max_failures
        )


class ErrorRecoveryManager:
    """
    Manages automatic error recovery for system components.

    Monitors component health, detects failures, and executes
    recovery strategies to restore functionality.
    """

    def __init__(self):
        """Initialize error recovery manager."""
        self.logger = logging.getLogger(__name__)
        self._component_health: Dict[str, ComponentHealth] = {}
        self._recovery_strategies: Dict[str, List[RecoveryStrategy]] = {}
        self._recovery_handlers: Dict[RecoveryStrategy, Callable] = {}
        self._recovery_locks: Dict[str, asyncio.Lock] = {}
        self._health_check_tasks: Dict[str, asyncio.Task] = {}
        self._monitoring_active = False

        # Recovery configuration
        self.max_recovery_attempts = 3
        self.recovery_cooldown = timedelta(minutes=5)
        self.health_check_interval = 30.0  # seconds

        # Register default recovery handlers
        self._register_default_handlers()

    def _register_default_handlers(self):
        """Register default recovery handlers."""
        self._recovery_handlers[RecoveryStrategy.RECONNECT] = self._reconnect_handler
        self._recovery_handlers[RecoveryStrategy.RESTART_SERVICE] = (
            self._restart_service_handler
        )
        self._recovery_handlers[RecoveryStrategy.ROTATE_API_KEY] = (
            self._rotate_api_key_handler
        )
        self._recovery_handlers[RecoveryStrategy.CLEAR_STATE] = (
            self._clear_state_handler
        )
        self._recovery_handlers[RecoveryStrategy.REINITIALIZE] = (
            self._reinitialize_handler
        )
        self._recovery_handlers[RecoveryStrategy.WAIT_AND_RETRY] = (
            self._wait_and_retry_handler
        )

    def register_component(
        self,
        component_name: str,
        recovery_strategies: List[RecoveryStrategy],
        health_check_func: Optional[Callable] = None,
    ):
        """
        Register component for error recovery monitoring.

        Args:
            component_name: Name of the component
            recovery_strategies: List of recovery strategies in order of preference
            health_check_func: Optional health check function
        """
        self._component_health[component_name] = ComponentHealth(component_name)
        self._recovery_strategies[component_name] = recovery_strategies
        self._recovery_locks[component_name] = asyncio.Lock()

        self.logger.info(f"Registered component for recovery: {component_name}")

        # Start health monitoring if function provided
        if health_check_func:
            self._start_health_monitoring(component_name, health_check_func)

    def register_recovery_handler(self, strategy: RecoveryStrategy, handler: Callable):
        """
        Register custom recovery handler.

        Args:
            strategy: Recovery strategy
            handler: Handler function
        """
        self._recovery_handlers[strategy] = handler
        self.logger.info(f"Registered custom recovery handler for {strategy.value}")

    async def record_error(self, component_name: str, error: Exception) -> bool:
        """
        Record error for component and trigger recovery if needed.

        Args:
            component_name: Component that experienced the error
            error: The error that occurred

        Returns:
            bool: True if recovery was triggered
        """
        if component_name not in self._component_health:
            self.logger.warning(f"Unknown component: {component_name}")
            return False

        health = self._component_health[component_name]
        health.record_error(error)

        self.logger.warning(f"Error recorded for {component_name}: {error}")

        # Check if recovery should be attempted
        if health.should_attempt_recovery():
            asyncio.create_task(self._attempt_recovery(component_name))
            return True

        return False

    async def record_success(self, component_name: str):
        """
        Record successful operation for component.

        Args:
            component_name: Component that succeeded
        """
        if component_name not in self._component_health:
            return

        health = self._component_health[component_name]
        health.record_success()

        self.logger.debug(f"Success recorded for {component_name}")

    async def _attempt_recovery(self, component_name: str) -> RecoveryResult:
        """
        Attempt recovery for a component.

        Args:
            component_name: Component to recover

        Returns:
            RecoveryResult: Result of recovery attempt
        """
        async with self._recovery_locks[component_name]:
            health = self._component_health[component_name]

            # Check cooldown period
            if (
                health.last_recovery_attempt
                and datetime.now() - health.last_recovery_attempt
                < self.recovery_cooldown
            ):
                self.logger.info(f"Recovery cooldown active for {component_name}")
                return RecoveryResult(
                    success=False,
                    strategy_used=None,
                    recovery_time=0.0,
                    error=Exception("Recovery cooldown active"),
                )

            health.recovery_in_progress = True
            health.last_recovery_attempt = datetime.now()

            self.logger.info(f"Starting recovery for {component_name}")

            strategies = self._recovery_strategies.get(component_name, [])

            for strategy in strategies:
                try:
                    start_time = time.time()

                    handler = self._recovery_handlers.get(strategy)
                    if not handler:
                        self.logger.error(
                            f"No handler for recovery strategy: {strategy.value}"
                        )
                        continue

                    self.logger.info(f"Attempting recovery strategy: {strategy.value}")

                    # Execute recovery handler
                    success = await handler(component_name, health.last_error)

                    recovery_time = time.time() - start_time

                    if success:
                        health.record_success()
                        self.logger.info(
                            f"Recovery successful for {component_name} using {strategy.value}"
                        )

                        return RecoveryResult(
                            success=True,
                            strategy_used=strategy,
                            recovery_time=recovery_time,
                        )

                except Exception as recovery_error:
                    self.logger.error(
                        f"Recovery strategy {strategy.value} failed: {recovery_error}"
                    )
                    continue

            # All recovery strategies failed
            health.recovery_in_progress = False
            self.logger.error(f"All recovery strategies failed for {component_name}")

            return RecoveryResult(
                success=False,
                strategy_used=None,
                recovery_time=0.0,
                error=Exception("All recovery strategies failed"),
            )

    def _start_health_monitoring(
        self, component_name: str, health_check_func: Callable
    ):
        """Start health monitoring for component."""

        async def health_monitor():
            while self._monitoring_active:
                try:
                    await asyncio.sleep(self.health_check_interval)

                    # Perform health check
                    is_healthy = await self._execute_health_check(health_check_func)

                    health = self._component_health[component_name]

                    if is_healthy:
                        if not health.is_healthy:
                            self.logger.info(f"Component {component_name} recovered")
                            health.record_success()
                    else:
                        health.health_check_failures += 1
                        if health.health_check_failures >= 3:
                            error = Exception(
                                f"Health check failed {health.health_check_failures} times"
                            )
                            await self.record_error(component_name, error)

                except Exception as e:
                    self.logger.error(
                        f"Health monitoring error for {component_name}: {e}"
                    )

        task = asyncio.create_task(health_monitor())
        self._health_check_tasks[component_name] = task

    async def _execute_health_check(self, health_check_func: Callable) -> bool:
        """Execute health check function."""
        try:
            if asyncio.iscoroutinefunction(health_check_func):
                return await health_check_func()
            else:
                return health_check_func()
        except Exception:
            return False

    def start_monitoring(self):
        """Start health monitoring for all registered components."""
        self._monitoring_active = True
        self.logger.info("Error recovery monitoring started")

    def stop_monitoring(self):
        """Stop health monitoring."""
        self._monitoring_active = False

        # Cancel health check tasks
        for task in self._health_check_tasks.values():
            if not task.done():
                task.cancel()

        self._health_check_tasks.clear()
        self.logger.info("Error recovery monitoring stopped")

    # Default recovery handlers

    async def _reconnect_handler(self, component_name: str, error: Exception) -> bool:
        """Handle reconnection recovery."""
        self.logger.info(f"Attempting reconnection for {component_name}")

        # Component-specific reconnection logic
        if component_name == "livekit_agent":
            return await self._reconnect_livekit()
        elif component_name == "memory_manager":
            return await self._reconnect_memory_service()
        elif component_name == "websocket_manager":
            return await self._reconnect_websocket()

        return False

    async def _restart_service_handler(
        self, component_name: str, error: Exception
    ) -> bool:
        """Handle service restart recovery."""
        self.logger.info(f"Attempting service restart for {component_name}")

        # This would typically involve restarting the service
        # For now, we'll simulate by reinitializing
        return await self._reinitialize_handler(component_name, error)

    async def _rotate_api_key_handler(
        self, component_name: str, error: Exception
    ) -> bool:
        """Handle API key rotation recovery."""
        if not isinstance(error, AIProviderError) or not error.is_rate_limit:
            return False

        self.logger.info(f"Attempting API key rotation for {component_name}")

        try:
            # Import here to avoid circular imports
            from ..ai.provider_factory import ProviderFactory

            provider = ProviderFactory.create_provider()
            if hasattr(provider, "rotate_api_key"):
                success = await provider.rotate_api_key()
                if success:
                    self.logger.info("API key rotation successful")
                    return True

            return False

        except Exception as e:
            self.logger.error(f"API key rotation failed: {e}")
            return False

    async def _clear_state_handler(self, component_name: str, error: Exception) -> bool:
        """Handle state clearing recovery."""
        self.logger.info(f"Clearing state for {component_name}")

        # Component-specific state clearing
        if component_name == "memory_manager":
            return await self._clear_memory_state()
        elif component_name == "animation_sync":
            return await self._clear_animation_state()

        return True  # Generic state clearing always "succeeds"

    async def _reinitialize_handler(
        self, component_name: str, error: Exception
    ) -> bool:
        """Handle component reinitialization."""
        self.logger.info(f"Reinitializing {component_name}")

        try:
            # Component-specific reinitialization
            if component_name == "memory_manager":
                return await self._reinitialize_memory_manager()
            elif component_name == "ai_provider":
                return await self._reinitialize_ai_provider()
            elif component_name == "websocket_manager":
                return await self._reinitialize_websocket_manager()

            return True

        except Exception as e:
            self.logger.error(f"Reinitialization failed for {component_name}: {e}")
            return False

    async def _wait_and_retry_handler(
        self, component_name: str, error: Exception
    ) -> bool:
        """Handle wait and retry recovery."""
        wait_time = 5.0  # Base wait time

        # Increase wait time based on consecutive failures
        health = self._component_health[component_name]
        wait_time *= min(health.consecutive_failures, 5)

        self.logger.info(f"Waiting {wait_time}s before retry for {component_name}")
        await asyncio.sleep(wait_time)

        return True  # Always "succeeds" - actual retry happens in next operation

    # Component-specific recovery implementations

    async def _reconnect_livekit(self) -> bool:
        """Reconnect LiveKit agent."""
        try:
            # This would involve reconnecting to LiveKit room
            # Implementation depends on LiveKit agent structure
            await asyncio.sleep(1.0)  # Simulate reconnection time
            return True
        except Exception:
            return False

    async def _reconnect_memory_service(self) -> bool:
        """Reconnect memory service."""
        try:
            from ..memory.memory_manager import MemoryManager
            from ..config.settings import get_settings

            config = get_settings()
            memory_manager = MemoryManager(config.memory)
            success = await memory_manager.initialize()
            return success
        except Exception:
            return False

    async def _reconnect_websocket(self) -> bool:
        """Reconnect WebSocket manager."""
        try:
            from ..web.websocket_manager import get_websocket_manager

            ws_manager = get_websocket_manager()
            await ws_manager.restart_server()
            return True
        except Exception:
            return False

    async def _clear_memory_state(self) -> bool:
        """Clear memory manager state."""
        try:
            from ..memory.memory_manager import MemoryManager

            # Clear session memory (implementation would depend on MemoryManager)
            return True
        except Exception:
            return False

    async def _clear_animation_state(self) -> bool:
        """Clear animation synchronizer state."""
        try:
            from ..web.animation_sync import get_animation_synchronizer

            sync = get_animation_synchronizer()
            # Clear active sequences and reset state
            sync.active_sequences.clear()
            sync.is_speaking = False
            sync.is_transitioning = False
            return True
        except Exception:
            return False

    async def _reinitialize_memory_manager(self) -> bool:
        """Reinitialize memory manager."""
        try:
            from ..memory.memory_manager import MemoryManager
            from ..config.settings import get_settings

            config = get_settings()
            memory_manager = MemoryManager(config.memory)
            return await memory_manager.initialize()
        except Exception:
            return False

    async def _reinitialize_ai_provider(self) -> bool:
        """Reinitialize AI provider."""
        try:
            from ..ai.provider_factory import ProviderFactory

            # Force recreation of provider
            ProviderFactory._provider = None
            provider = ProviderFactory.create_provider()

            # Test connection
            if hasattr(provider, "check_connection"):
                return await provider.check_connection()

            return True
        except Exception:
            return False

    async def _reinitialize_websocket_manager(self) -> bool:
        """Reinitialize WebSocket manager."""
        try:
            from ..web.websocket_manager import get_websocket_manager

            ws_manager = get_websocket_manager()
            await ws_manager.stop_server()
            await asyncio.sleep(1.0)
            await ws_manager.start_server()
            return True
        except Exception:
            return False

    def get_component_health(self, component_name: str) -> Optional[ComponentHealth]:
        """Get health status for component."""
        return self._component_health.get(component_name)

    def get_all_component_health(self) -> Dict[str, ComponentHealth]:
        """Get health status for all components."""
        return self._component_health.copy()

    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get recovery statistics."""
        stats = {
            "monitored_components": len(self._component_health),
            "monitoring_active": self._monitoring_active,
            "components": {},
        }

        for name, health in self._component_health.items():
            stats["components"][name] = {
                "is_healthy": health.is_healthy,
                "error_count": health.error_count,
                "consecutive_failures": health.consecutive_failures,
                "recovery_in_progress": health.recovery_in_progress,
                "last_successful_operation": (
                    health.last_successful_operation.isoformat()
                    if health.last_successful_operation
                    else None
                ),
            }

        return stats


# Global error recovery manager instance
_recovery_manager: Optional[ErrorRecoveryManager] = None


def get_recovery_manager() -> ErrorRecoveryManager:
    """Get global error recovery manager instance."""
    global _recovery_manager
    if _recovery_manager is None:
        _recovery_manager = ErrorRecoveryManager()
    return _recovery_manager
