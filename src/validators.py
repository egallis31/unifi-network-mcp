"""Validators for UniFi Network resource creation and validation."""

import logging
from typing import Any, Dict, Optional, Tuple
from aiounifi.errors import RequestError, ResponseError

from jsonschema import ValidationError, validate

logger = logging.getLogger("unifi-network-mcp")

class ResourceValidator:
    """Base validator for UniFi Network resource creation."""

    def __init__(self, schema: Dict[str, Any], resource_name: str):
        self.schema = schema
        self.resource_name = resource_name

    def validate(
        self, params: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Validate parameters against schema.

        Args:
            params: The parameters to validate

        Returns:
            Tuple of (is_valid, error_message, validated_params)
        """
        try:
            # Validate against JSON schema
            validate(instance=params, schema=self.schema)

            # Additional custom validation could be added here

            return True, None, params
        except ValidationError as e:
            error_msg = "%s validation error: %s"
            logger.error(error_msg, self.resource_name, e.message)
            return False, error_msg % (self.resource_name, e.message), None
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            error_msg = "Unexpected error validating %s: %s"
            logger.error(error_msg, self.resource_name, str(e), exc_info=True)
            return False, error_msg % (self.resource_name, str(e)), None


def create_response(
                    success: bool,
                    data: Any = None,
                    error: Optional[str] = None
) -> Dict[str, Any]:
    """Create a standardized response format for all creation operations.

    Args:
        success: Whether the operation was successful
        data: The data to include in the response (typically a resource ID or object)
        error: Error message if the operation failed

    Returns:
        A standardized response dictionary
    """
    response: Dict[str, Any] = {"success": success}

    if success and data is not None:
        if isinstance(data, str):
            response["id"] = data
        else:
            response["data"] = data

    if not success and error:
        response["error"] = error

    return response
