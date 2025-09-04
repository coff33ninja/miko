"""JSON encoder for custom types in the web application."""

import json
from enum import Enum
from dataclasses import is_dataclass, asdict
from .websocket_manager import AnimationEventType, AnimationEvent


class WebSocketJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for WebSocket messages."""
    
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        if is_dataclass(obj):
            return asdict(obj)
        return super().default(obj)
