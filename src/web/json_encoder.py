"""JSON encoder for custom types in the web application."""

import json
from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import is_dataclass, asdict
from .websocket_manager import AnimationEventType, AnimationEvent


class WebSocketJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for WebSocket messages."""
    
    def default(self, obj: Any) -> Any:
        try:
            if isinstance(obj, AnimationEventType):
                return {
                    "type": "AnimationEventType",
                    "value": obj.value,
                    "name": obj.name
                }
            if isinstance(obj, AnimationEvent):
                event_dict = asdict(obj)
                # Ensure proper encoding of event_type
                if isinstance(event_dict.get('event_type'), AnimationEventType):
                    event_dict['event_type'] = {
                        "type": "AnimationEventType",
                        "value": event_dict['event_type'].value,
                        "name": event_dict['event_type'].name
                    }
                return event_dict
            if isinstance(obj, Enum):
                return {
                    "type": obj.__class__.__name__,
                    "value": obj.value,
                    "name": obj.name
                }
            if is_dataclass(obj):
                return self._encode_dataclass(obj)
            return super().default(obj)
        except Exception as e:
            return {"error": str(e), "object_type": str(type(obj))}

    def _encode_dataclass(self, obj: Any) -> Dict[str, Any]:
        """Handle dataclass encoding with special enum handling."""
        try:
            data = asdict(obj)
            # Process any enum values in the dataclass
            for key, value in data.items():
                if isinstance(value, Enum):
                    data[key] = {
                        "type": value.__class__.__name__,
                        "value": value.value,
                        "name": value.name
                    }
            return data
        except Exception as e:
            return {"error": str(e), "object_type": str(type(obj))}


def decode_websocket_message(json_str: str) -> Optional[Dict[str, Any]]:
    """Decode WebSocket message with custom type handling."""
    try:
        data = json.loads(json_str)
        return _decode_custom_types(data)
    except json.JSONDecodeError as e:
        return {"error": f"JSON decode error: {str(e)}"}
    except Exception as e:
        return {"error": f"Decode error: {str(e)}"}


def _decode_custom_types(data: Any) -> Any:
    """Recursively decode custom types in decoded JSON."""
    if isinstance(data, dict):
        # Handle custom type objects
        if data.get("type") == "AnimationEventType":
            try:
                return AnimationEventType(data["value"])
            except ValueError:
                return data
        # Recursively process dictionary values
        return {key: _decode_custom_types(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_decode_custom_types(item) for item in data]
    return data
