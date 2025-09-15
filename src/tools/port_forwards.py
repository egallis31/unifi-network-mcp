"""
Port forward tools for Unifi Network MCP server.
"""

import logging
import json
from typing import Dict, Any

from src.runtime import server, config, firewall_manager 
from src.utils.permissions import parse_permission
from src.validator_registry import UniFiValidatorRegistry # Added for validation

logger = logging.getLogger(__name__) # Changed logger name for consistency

@server.tool(
    name="unifi_list_port_forwards", 
    description="List all port forwarding rules on your Unifi Network controller."
)
async def list_port_forwards() -> Dict[str, Any]: # Removed context, adjusted return type
    """List all port forwarding rules configured on the UniFi Network controller.

    Returns:
        A dictionary containing:
        - success (bool): Indicates if the operation was successful.
        - site (str): The identifier of the UniFi site queried.
        - count (int): The number of port forwarding rules found.
        - port_forwards (List[Dict]): A list of port forward rules, each containing:
            - id (str): The unique identifier of the rule.
            - name (str): The user-defined name of the rule.
            - enabled (bool): Whether the rule is currently active.
            - src_port (str): The destination/external port or range.
            - dst_port (str): The internal port or range to forward to.
            - protocol (str): The network protocol ('tcp', 'udp', 'tcp/udp').
            - dest_ip (str): The internal IP address to forward to.
        - error (str, optional): An error message if the operation failed.

    Example response (success):
    {
        "success": True,
        "site": "default",
        "count": 1,
        "port_forwards": [
            {
                "id": "60f5a9b3e4b0f4a7f7d6e8c1",
                "name": "Web Server",
                "enabled": True,
                "src_port": "80",
                "dst_port": "8080",
                "protocol": "tcp",
                "dest_ip": "192.168.1.100"
            }
        ]
    }
    """
    if not parse_permission(getattr(config, 'permissions', {}), "port_forward", "read"):
        logger.warning("Permission denied for listing port forwards.")
        return {"success": False, "error": "Permission denied to list port forwards."}
    try:
        rules = await firewall_manager.get_port_forwards()
        rules_raw = [r.raw if hasattr(r, "raw") else r for r in rules]
        port_forward_list = [
            {
                "id": getattr(r, "_id", None),
                "name": getattr(r, "name", None),
                "enabled": getattr(r, "enabled", None),
                "src_port": getattr(r, "dst_port", None), # Note: UniFi uses dst_port for external
                "dst_port": getattr(r, "fwd_port", None), # Note: UniFi uses fwd_port for internal
                "protocol": getattr(r, "protocol", None),
                "dest_ip": getattr(r, "fwd_ip", None)
            }
            for r in rules_raw
        ]
        return {"success": True, "site": getattr(getattr(firewall_manager, '_connection', None), 'site', 'default'), "count": len(port_forward_list), "port_forwards": port_forward_list}
    except Exception as e:
        logger.error("Error listing port forwards: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_get_port_forward",
    description="Get a specific port forwarding rule by ID from your Unifi Network controller."
)
async def get_port_forward(port_forward_id: str) -> Dict[str, Any]: # Removed context, added param type hint
    """Get detailed information about a specific port forwarding rule by its ID.

    Args:
        port_forward_id (str): The unique identifier (_id) of the port forwarding rule.

    Returns:
        A dictionary containing:
        - success (bool): Indicates if the operation was successful.
        - port_forward_id (str): The ID of the rule requested.
        - details (Dict[str, Any]): A dictionary containing the raw configuration details
          of the port forwarding rule as returned by the UniFi controller.
        - error (str, optional): An error message if the operation failed (e.g., rule not found).

    Example response (success):
    {
        "success": True,
        "port_forward_id": "60f5a9b3e4b0f4a7f7d6e8c1",
        "details": {
            "_id": "60f5a9b3e4b0f4a7f7d6e8c1",
            "name": "Web Server",
            "enabled": True,
            "dst_port": "80",
            "fwd_port": "8080",
            "fwd_ip": "192.168.1.100",
            "protocol": "tcp",
            "site_id": "...",
            # ... other fields
        }
    }
    """
    if not parse_permission(getattr(config, 'permissions', {}), "port_forward", "read"):
        logger.warning("Permission denied for getting port forward (%s).", port_forward_id)
        return {"success": False, "error": "Permission denied to get port forward details."}
    try:
        if not port_forward_id:
            return {"success": False, "error": "port_forward_id is required"}
        
        rule_obj = await firewall_manager.get_port_forward_by_id(port_forward_id)
        rule = rule_obj.raw if (rule_obj and hasattr(rule_obj, "raw")) else rule_obj
        
        if not rule:
            return {"success": False, "error": f"Port forwarding rule '{port_forward_id}' not found"}
        
        # Return full details, ensure serializable
        return {"success": True, "port_forward_id": port_forward_id, "details": json.loads(json.dumps(rule, default=str))}
    except Exception as e:
        logger.error("Error getting port forward %s: %s", port_forward_id, e, exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_toggle_port_forward",
    description="Toggle a port forwarding rule on or off on your Unifi Network controller."
)
async def toggle_port_forward(port_forward_id: str, confirm: bool = False) -> Dict[str, Any]: # Added confirm param, removed context
    """Enables or disables a specific port forwarding rule. Requires confirmation.

    Args:
        port_forward_id (str): The unique identifier (_id) of the port forwarding rule to toggle.
        confirm (bool): Must be explicitly set to `True` to execute the toggle operation. Defaults to `False`.

    Returns:
        A dictionary containing:
        - success (bool): Indicates if the operation was successful.
        - port_forward_id (str): The ID of the rule that was toggled.
        - enabled (bool): The new state of the rule (True if enabled, False if disabled).
        - message (str): A confirmation message indicating the action taken.
        - error (str, optional): An error message if the operation failed (e.g., permission denied,
          confirmation missing, rule not found, toggle failed).

    Example response (success):
    {
        "success": True,
        "port_forward_id": "60f5a9b3e4b0f4a7f7d6e8c1",
        "enabled": False,
        "message": "Port forward 'Web Server' toggled to disabled."
    }
    """

    if not parse_permission(getattr(config, 'permissions', {}), "port_forward", "update"):
        logger.warning("Permission denied for toggling port forward (%s).", port_forward_id)
        return {"success": False, "error": "Permission denied to toggle port forward."}
        
    if not confirm:
        logger.warning("Confirmation missing for toggling port forward %s.", port_forward_id)
        return {"success": False, "error": "Confirmation required. Set 'confirm' to true."}

    try:
        if not port_forward_id:
            return {"success": False, "error": "port_forward_id is required"}
        
        rule_obj = await firewall_manager.get_port_forward_by_id(port_forward_id)
        rule = rule_obj.raw if (rule_obj and hasattr(rule_obj, "raw")) else rule_obj
        if not rule:
            return {"success": False, "error": f"Port forwarding rule '{port_forward_id}' not found"}

        rule_name = getattr(rule, "name", port_forward_id)
        current_state = getattr(rule, "enabled", False)
        new_state = not current_state

        logger.info("Attempting to toggle port forward '%s' (%s) to %s", rule_name, port_forward_id, new_state)
        # Assuming toggle_port_forward directly updates the rule state.
        # If firewall_manager.toggle_port_forward doesn't exist or works differently,
        # we might need to fetch, modify 'enabled', and call update_port_forward.
        # For now, assuming toggle_port_forward exists and returns success/failure.
        
        # Let's simulate the update pattern more closely: fetch, modify, update
        update_payload = {"enabled": new_state}
        # Assuming firewall_manager has an update_port_forward method
        # This requires checking/adding the update_port_forward method in the manager layer
        success = await firewall_manager.update_port_forward(port_forward_id, update_payload)

        if success:
            logger.info("Successfully toggled port forward '%s' (%s) to %s", rule_name, port_forward_id, new_state)
            return {"success": True, "port_forward_id": port_forward_id, "enabled": new_state, "message": f"Port forward '{rule_name}' toggled to {'enabled' if new_state else 'disabled'}."}
        else:
            # Re-fetch to check the state if the update call failed
            rule_after_toggle_obj = await firewall_manager.get_port_forward_by_id(port_forward_id)
            rule_after_toggle = rule_after_toggle_obj.raw if (rule_after_toggle_obj and hasattr(rule_after_toggle_obj, "raw")) else rule_after_toggle_obj
            state_after = getattr(rule_after_toggle, "enabled", "unknown") if rule_after_toggle else "unknown"
            logger.error("Failed to toggle port forward '%s' (%s). State after attempt: %s. Manager update returned false.", rule_name, port_forward_id, state_after)
            return {"success": False, "error": f"Failed to toggle port forward '{rule_name}'. Check server logs."}

    except Exception as e:
        logger.error("Error toggling port forward %s: %s", port_forward_id, e, exc_info=True)
        return {"success": False, "error": str(e)}

# Create Port Forward
@server.tool(
    name="unifi_create_port_forward", 
    description="Create a new port forwarding rule on your Unifi Network controller using schema validation." 
)
async def create_port_forward(
    port_forward_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a new port forwarding rule with comprehensive validation.
    
    Required parameters in port_forward_data:
    - name (string): Name for the port forwarding rule
    - dst_port (string): Destination/external port (e.g., "80", "443", "22" or range "10000-10010")
    - fwd_port (string): Internal port to forward to (e.g., "80", "8080" or range "10000-10010")
    - fwd_ip (string): Internal IP address to forward to
    
    Optional parameters in port_forward_data:
    - protocol (string): Network protocol - "tcp", "udp", or "tcp_udp" (default: "tcp_udp")
    - enabled (boolean): Whether rule is enabled initially (default: true)
    - src_ip (string): Source IP/CIDR to match (default: any)
    - log (boolean): Whether to log rule matches (default: false)
    
    Example:
    {
        "name": "Web Server",
        "dst_port": "80",
        "fwd_port": "8080",
        "fwd_ip": "192.168.1.100",
        "protocol": "tcp",
        "enabled": true
    }
    
    Returns:
    - success (boolean): Whether the operation succeeded
    - port_forward_id (string): ID of the created rule if successful
    - details (object): Additional details about the created rule
    - error (string): Error message if unsuccessful
    """
    if not parse_permission(getattr(config, 'permissions', {}), "port_forward", "create"):
        logger.warning("Permission denied for creating port forward.")
        return {"success": False, "error": "Permission denied to create port forward."}
        
    # UniFiValidatorRegistry already imported at module level

    # Validate the input
    is_valid, error_msg, validated_data = UniFiValidatorRegistry.validate("port_forward", port_forward_data)
    if not is_valid or validated_data is None:
        logger.warning("Invalid port forward data: %s", error_msg)
        return {"success": False, "error": error_msg or "Validation failed"}

    # Required fields check
    required_fields = ["name", "dst_port", "fwd_port", "fwd_ip"]
    missing_fields = [field for field in required_fields if field not in validated_data]
    if missing_fields:
        error = f"Missing required fields: {', '.join(missing_fields)}"
        logger.warning(error)
        return {"success": False, "error": error}
        
    try:
        # Prepare data for the manager
        rule_data = {
            "name": validated_data["name"],
            "dst_port": validated_data["dst_port"],
            "fwd_port": validated_data["fwd_port"],
            "fwd_ip": validated_data["fwd_ip"],
            "proto": validated_data.get("protocol", "tcp_udp").replace('_', '/'),  # Manager expects 'tcp/udp'
            "protocol_match_excepted": False,
            "enabled": validated_data.get("enabled", True),
            "log": validated_data.get("log", False)
        }
        
        # Handle optional source IP
        if validated_data.get("src_ip"): 
            rule_data["src"] = validated_data["src_ip"]
        
        logger.info("Attempting to create port forward: %s (%s %s -> %s:%s)", 
                   validated_data['name'], rule_data['proto'], validated_data['dst_port'], 
                   validated_data['fwd_ip'], validated_data['fwd_port'])

        result = await firewall_manager.create_port_forward(rule_data)
        
        if result: 
            new_rule_id = result if isinstance(result, str) else result.get("_id", "unknown")
            details = result if isinstance(result, dict) else { "id": new_rule_id }
            logger.info("Successfully created port forward '%s' with ID %s", validated_data['name'], new_rule_id)
            return {"success": True, 
                    "message": f"Port forward '{validated_data['name']}' created successfully.", 
                    "port_forward_id": new_rule_id, 
                    "details": json.loads(json.dumps(details, default=str))}
        else:
            error_msg = result.get("error", "Manager returned failure") if isinstance(result, dict) else "Manager returned failure"
            logger.error("Failed to create port forward '%s'. Reason: %s", validated_data['name'], error_msg)
            return {"success": False, "error": f"Failed to create port forward '{validated_data['name']}'. {error_msg}"}

    except Exception as e:
        logger.error("Error creating port forward '%s': %s", validated_data.get('name', 'unknown'), e, exc_info=True)
        return {"success": False, "error": str(e)}

# --- NEW UPDATE TOOL ---
@server.tool(
    name="unifi_update_port_forward",
    description="Update specific fields of an existing port forwarding rule using schema validation. Requires confirmation."
)
async def update_port_forward(
    port_forward_id: str,
    update_data: Dict[str, Any],
    confirm: bool = False
) -> Dict[str, Any]:
    """Updates specific fields of an existing port forwarding rule.

    This tool allows modifying one or more properties of a port forward rule
    identified by its ID. All fields in `update_data` are optional; only provided
    fields will be updated. Requires confirmation.

    Args:
        port_forward_id (str): The unique identifier (_id) of the port forwarding rule to update.
        update_data (Dict[str, Any]): A dictionary containing the fields to update.
            Allowed fields (all optional):
            - name (string): New name for the rule.
            - dst_port (string): New destination/external port or range.
            - fwd_port (string): New internal port or range.
            - fwd_ip (string): New internal IP address.
            - protocol (string): New protocol ("tcp", "udp", or "tcp_udp").
            - enabled (boolean): New enabled state (True/False).
            - src_ip (string): New source IP/CIDR match (use empty string "" or null to remove).
            - log (boolean): New logging state (True/False).
        confirm (bool): Must be explicitly set to `True` to execute the update. Defaults to `False`.

    Returns:
        A dictionary containing:
        - success (bool): Indicates if the operation was successful.
        - port_forward_id (str): The ID of the rule that was updated.
        - updated_fields (List[str]): A list of field names that were successfully updated.
        - details (Dict[str, Any]): The full details of the rule after the update.
        - error (str, optional): An error message if the operation failed.

    Example call:
    update_port_forward(
        port_forward_id="60f5a9b3e4b0f4a7f7d6e8c1",
        update_data={
            "name": "Updated Web Server Name",
            "enabled": False,
            "dst_port": "443"
        },
        confirm=True
    )

    Example response (success):
    {
        "success": True,
        "port_forward_id": "60f5a9b3e4b0f4a7f7d6e8c1",
        "updated_fields": ["name", "enabled", "dst_port"],
        "details": { ... updated rule details ... }
    }
    """
    if not parse_permission(getattr(config, 'permissions', {}), "port_forward", "update"):
        logger.warning("Permission denied for updating port forward (%s).", port_forward_id)
        return {"success": False, "error": "Permission denied to update port forward."}

    if not confirm:
        logger.warning("Confirmation missing for updating port forward %s.", port_forward_id)
        return {"success": False, "error": "Confirmation required. Set 'confirm' to true."}

    if not port_forward_id:
        return {"success": False, "error": "port_forward_id is required"}
    if not update_data:
        return {"success": False, "error": "update_data dictionary cannot be empty"}

    # Validate the update data against the update schema
    is_valid, error_msg, validated_data = UniFiValidatorRegistry.validate("port_forward_update", update_data)
    if not is_valid:
        logger.warning("Invalid port forward update data for ID %s: %s", port_forward_id, error_msg)
        return {"success": False, "error": f"Invalid update data: {error_msg}"}
    
    if not validated_data: # Ensure validation didn't return an empty dict if input was invalid
        logger.warning("Port forward update data for ID %s is empty after validation.", port_forward_id)
        return {"success": False, "error": "Update data is effectively empty or invalid."}

    try:
        # Fetch the existing rule first to ensure it exists
        existing_rule_obj = await firewall_manager.get_port_forward_by_id(port_forward_id)
        existing_rule = existing_rule_obj.raw if (existing_rule_obj and hasattr(existing_rule_obj, "raw")) else None
        if not existing_rule:
            return {"success": False, "error": f"Port forwarding rule '{port_forward_id}' not found"}

        rule_name = existing_rule.get("name", port_forward_id)

        # Prepare the payload for the manager update function
        # Map schema fields to manager fields if necessary (like protocol)
        update_payload = {}
        updated_fields_list = []
        for key, value in validated_data.items():
            updated_fields_list.append(key)
            if key == "protocol":
                update_payload["proto"] = value.replace('_', '/')
            elif key == "src_ip":
                # Map src_ip to 'src', handle removal if empty string/null
                update_payload["src"] = value if value else None 
            # Need to handle 'log' if it's part of the schema/manager
            elif key == "log": 
                update_payload["log"] = value
            else:
                update_payload[key] = value
                
        # Add potentially missing fields required by aiounifi update that aren't directly updatable via schema but needed for context?
        # e.g. _id should be passed in the ID parameter, site_id might be handled by manager
        # We only pass the fields being changed to the manager update function

        logger.info("Attempting to update port forward '%s' (%s) with fields: %s", rule_name, port_forward_id, ', '.join(updated_fields_list))

        # Assume firewall_manager.update_port_forward(id, data) exists
        # It should handle merging the update_payload with the existing rule internally or send only the changed fields
        success = await firewall_manager.update_port_forward(port_forward_id, update_payload)

        if success:
            # Fetch the rule again to return the updated state
            updated_rule_obj = await firewall_manager.get_port_forward_by_id(port_forward_id)
            updated_rule = updated_rule_obj.raw if (updated_rule_obj and hasattr(updated_rule_obj, "raw")) else {}

            logger.info("Successfully updated port forward '%s' (%s)", rule_name, port_forward_id)
            return {
                "success": True,
                "port_forward_id": port_forward_id,
                "updated_fields": updated_fields_list,
                "details": json.loads(json.dumps(updated_rule, default=str))
            }
        else:
            logger.error("Failed to update port forward '%s' (%s). Manager returned false.", rule_name, port_forward_id)
            # Attempt to fetch rule again to see if partial update occurred? Or just report failure.
            rule_after_update_obj = await firewall_manager.get_port_forward_by_id(port_forward_id)
            rule_after_update = rule_after_update_obj.raw if (rule_after_update_obj and hasattr(rule_after_update_obj, "raw")) else {}
            return {
                "success": False, 
                "port_forward_id": port_forward_id,
                "error": f"Failed to update port forward '{rule_name}'. Check server logs.",
                "details_after_attempt": json.loads(json.dumps(rule_after_update, default=str)) # Provide state after failed attempt
            }

    except Exception as e:
        logger.error("Error updating port forward %s: %s", port_forward_id, e, exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_create_simple_port_forward",
    description=(
        "Create a port forward using a simplified schema. "
        "Returns a preview unless confirm=true."
    )
)
async def create_simple_port_forward(
    rule: Dict[str, Any],
    confirm: bool = False
) -> Dict[str, Any]:
    """Create port forward with compact input.

    Schema (validated internally):
    {
        "name": "Home Web",
        "ext_port": "8443",
        "to_ip": "192.168.1.10",
        "int_port": "443",          # optional (defaults to ext_port)
        "protocol": "tcp",          # optional (default both)
        "enabled": true              # optional (default true)
    }
    """

    if not parse_permission(getattr(config, 'permissions', {}), "port_forward", "create"):
        return {"success": False, "error": "Permission denied."}

    ok, err, validated = UniFiValidatorRegistry.validate("port_forward_simple", rule)
    if not ok or validated is None:
        return {"success": False, "error": err or "Validation failed"}

    r = validated

    # Build API payload matching existing V1 schema keys
    payload: Dict[str, Any] = {
        "name": r["name"],
        "dst_port": str(r["ext_port"]),
        "fwd_port": str(r.get("int_port", r["ext_port"])),
        "fwd_ip": r["to_ip"],
        "protocol": {
            "tcp": "tcp",
            "udp": "udp",
            "both": "tcp_udp",
        }.get(r.get("protocol", "both"), "tcp_udp"),
        "enabled": r.get("enabled", True),
    }

    if not confirm:
        return {"success": True, "preview": payload, "message": "Set confirm=true to apply."}

    created = await firewall_manager.create_port_forward(payload)
    if created is None or not isinstance(created, dict):
        return {"success": False, "error": "Controller rejected port forward creation. See logs."}

    return {
        "success": True,
        "port_forward_id": created.get("_id"),
        "details": json.loads(json.dumps(created, default=str)),
    }