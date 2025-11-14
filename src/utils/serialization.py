"""Serialization utilities for aiounifi objects."""
import logging
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)


def serialize_aiounifi_object(obj: Any) -> Union[Dict, List, Any]:
    """
    Safely serialize an aiounifi object to a JSON-compatible format.

    This handles objects with .raw attributes, dicts, lists, and other types.

    Args:
        obj: The object to serialize (can be aiounifi object, dict, list, etc.)

    Returns:
        JSON-serializable version of the object
    """
    # Handle None
    if obj is None:
        return None

    # If object has .raw attribute (aiounifi objects), use it
    if hasattr(obj, 'raw'):
        return obj.raw

    # If already a dict, recursively serialize its values
    if isinstance(obj, dict):
        return {k: serialize_aiounifi_object(v) for k, v in obj.items()}

    # If a list/tuple, recursively serialize items
    if isinstance(obj, (list, tuple)):
        return [serialize_aiounifi_object(item) for item in obj]

    # If it's a primitive type, return as-is
    if isinstance(obj, (str, int, float, bool)):
        return obj

    # Try to convert object to dict using __dict__
    if hasattr(obj, '__dict__'):
        try:
            # Filter out private attributes and methods
            obj_dict = {
                k: serialize_aiounifi_object(v)
                for k, v in obj.__dict__.items()
                if not k.startswith('_') and not callable(v)
            }
            return obj_dict
        except Exception as e:
            logger.warning(f"Failed to serialize object via __dict__: {e}")

    # Last resort: convert to string
    try:
        return str(obj)
    except Exception as e:
        logger.error(f"Failed to serialize object: {e}")
        return None


def serialize_list(items: List[Any]) -> List[Union[Dict, Any]]:
    """
    Serialize a list of aiounifi objects.

    Args:
        items: List of objects to serialize

    Returns:
        List of JSON-serializable objects
    """
    return [serialize_aiounifi_object(item) for item in items]


def safe_serialize_response(data: Any, fallback: Any = None) -> Any:
    """
    Safely serialize response data with fallback.

    Args:
        data: Data to serialize
        fallback: Fallback value if serialization fails

    Returns:
        Serialized data or fallback value
    """
    try:
        return serialize_aiounifi_object(data)
    except Exception as e:
        logger.error(f"Serialization failed: {e}")
        return fallback if fallback is not None else {"error": "Serialization failed"}
