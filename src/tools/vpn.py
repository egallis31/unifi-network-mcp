"""VPN configuration tools for Unifi Network MCP server.

This module provides MCP tools to interact with a Unifi Network Controller's VPN functions,
including managing VPN clients and servers.
"""

import logging
from typing import Any, Dict
from aiounifi.errors import RequestError, ResponseError

from src.runtime import server, config, vpn_manager
from src.utils.permissions import parse_permission

logger = logging.getLogger(__name__)

@server.tool(
    name="unifi_list_vpn_clients",
    description="List all configured VPN clients (Wireguard, OpenVPN, etc)."
)
async def list_vpn_clients() -> Dict[str, Any]:
    """Implementation for listing VPN clients."""
    if not parse_permission(getattr(config, "permissions", {}), "vpn_client", "read"):
        logger.warning("Permission denied for listing VPN clients.")
        return {"success": False, "error": "Permission denied to list VPN clients."}
    try:
        clients = await vpn_manager.get_vpn_clients()
        connection = (getattr(vpn_manager, "connection", None) or
                     getattr(vpn_manager, "_connection", None))
        site = getattr(connection, "site", None) if connection else None
        return {"success": True, "site": site, "count": len(clients), "vpn_clients": clients}
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.error("Error listing VPN clients: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_get_vpn_client_details",
    description="Get details for a specific VPN client by ID."
)
async def get_vpn_client_details(client_id: str) -> Dict[str, Any]:
    """Implementation for getting VPN client details."""
    if not parse_permission(getattr(config, "permissions", {}), "vpn_client", "read"):
        logger.warning("Permission denied for getting VPN client details (%s).", client_id)
        return {"success": False, "error": "Permission denied to get VPN client details."}
    try:
        client = await vpn_manager.get_vpn_client_details(client_id)
        if client:
            connection = (getattr(vpn_manager, "connection", None) or
                         getattr(vpn_manager, "_connection", None))
            site = getattr(connection, "site", None) if connection else None
            return {"success": True, "site": site, "client_id": client_id, "details": client}
        else:
            return {"success": False, "error": f"VPN client '{client_id}' not found."}
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.error("Error getting VPN client details for %s: %s", client_id, e, exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_update_vpn_client_state",
    description="Enable or disable a specific VPN client by ID."
)
async def update_vpn_client_state(client_id: str, enabled: bool) -> Dict[str, Any]:
    """Implementation for updating VPN client state."""
    if not parse_permission(getattr(config, "permissions", {}), "vpn_client", "update"):
        logger.warning("Permission denied for updating VPN client state (%s).", client_id)
        return {"success": False, "error": "Permission denied to update VPN client state."}
    try:
        success = await vpn_manager.update_vpn_client_state(client_id, enabled)
        if success:
            client_details = await vpn_manager.get_vpn_client_details(client_id)
            name = client_details.get("name", client_id) if client_details else client_id
            state = "enabled" if enabled else "disabled"
            return {"success": True, "message": f"VPN client '{name}' ({client_id}) {state}."}
        else:
            client_details = await vpn_manager.get_vpn_client_details(client_id)
            name = client_details.get("name", client_id) if client_details else client_id
        return {"success": False, "error": f"Failed to update state for VPN client '{name}'."}
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.error("Error updating state for VPN client %s: %s", client_id, e, exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_list_vpn_servers",
    description="List all configured VPN servers (Wireguard, OpenVPN, L2TP, etc)."
)
async def list_vpn_servers() -> Dict[str, Any]:
    """Implementation for listing VPN servers."""
    if not parse_permission(getattr(config, "permissions", {}), "vpn_server", "read"):
        logger.warning("Permission denied for listing VPN servers.")
        return {"success": False, "error": "Permission denied to list VPN servers."}
    try:
        servers = await vpn_manager.get_vpn_servers()
        connection = (getattr(vpn_manager, "connection", None) or
                     getattr(vpn_manager, "_connection", None))
        site = getattr(connection, "site", None) if connection else None
        return {"success": True, "site": site, "count": len(servers), "vpn_servers": servers}
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.error("Error listing VPN servers: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_get_vpn_server_details",
    description="Get details for a specific VPN server by ID."
)
async def get_vpn_server_details(server_id: str) -> Dict[str, Any]:
    """Implementation for getting VPN server details."""
    if not parse_permission(getattr(config, "permissions", {}), "vpn_server", "read"):
        logger.warning("Permission denied for getting VPN server details (%s).", server_id)
        return {"success": False, "error": "Permission denied to get VPN server details."}
    try:
        details = await vpn_manager.get_vpn_server_details(server_id)
        connection = (getattr(vpn_manager, "connection", None) or
                     getattr(vpn_manager, "_connection", None))
        site = getattr(connection, "site", None) if connection else None
        if details:
            return {"success": True, "site": site, "server_id": server_id, "details": details}
        return {"success": False, "error": f"VPN server '{server_id}' not found."}
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.error("Error getting VPN server details for %s: %s", server_id, e, exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_update_vpn_server_state",
    description="Enable or disable a specific VPN server by ID."
)
async def update_vpn_server_state(server_id: str, enabled: bool) -> Dict[str, Any]:
    """Implementation for updating VPN server state."""
    if not parse_permission(getattr(config, "permissions", {}), "vpn_server", "update"):
        logger.warning("Permission denied for updating VPN server state (%s).", server_id)
        return {"success": False, "error": "Permission denied to update VPN server state."}
    try:
        success = await vpn_manager.update_vpn_server_state(server_id, enabled)
        if success:
            server_details = await vpn_manager.get_vpn_server_details(server_id)
            name = server_details.get("name", server_id) if server_details else server_id
            state = "enabled" if enabled else "disabled"
            return {"success": True, "message": f"VPN server '{name}' ({server_id}) {state}."}
        else:
            server_details = await vpn_manager.get_vpn_server_details(server_id)
            name = server_details.get("name", server_id) if server_details else server_id
        return {"success": False, "error": f"Failed to update state for VPN server '{name}'."}
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.error("Error updating state for VPN server %s: %s", server_id, e, exc_info=True)
        return {"success": False, "error": str(e)}
