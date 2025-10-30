"""Unifi Network MCP system tools.

This module provides MCP tools to interact with a Unifi Network Controller's system functions.
"""

import logging
from typing import Any, Dict
from aiounifi.errors import RequestError, ResponseError

from src.runtime import server, system_manager

logger = logging.getLogger(__name__)

# Explicitly retrieve and log the server instance to confirm it's being used
logger.info("System tools module loaded, server instance: %s", server)

@server.tool(
    name="unifi_get_system_info",
    description="Get general system information from the Unifi Network controller (version, uptime, etc)."
)
async def get_system_info() -> Dict[str, Any]:
    """Implementation for getting system info."""
    logger.info("unifi_get_system_info tool called")
    try:
        info = await system_manager.get_system_info()
        connection = (getattr(system_manager, "connection", None) or
                     getattr(system_manager, "_connection", None))
        site = getattr(connection, "site", None) if connection else None
        return {"success": True, "site": site, "system_info": info}
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.error("Error getting system info: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_get_network_health",
    description="Get the current network health summary (WAN status, device counts)."
)
async def get_network_health() -> Dict[str, Any]:
    """Implementation for getting network health."""
    logger.info("unifi_get_network_health tool called")
    try:
        health = await system_manager.get_network_health()
        connection = (getattr(system_manager, "connection", None) or
                     getattr(system_manager, "_connection", None))
        site = getattr(connection, "site", None) if connection else None
        return {"success": True, "site": site, "health_summary": health}
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.error("Error getting network health: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_get_site_settings",
    description=(
        "Get current site settings (e.g., country code, timezone, "
        "connectivity monitoring)."
    )
)
async def get_site_settings() -> Dict[str, Any]:
    """Implementation for getting site settings."""
    logger.info("unifi_get_site_settings tool called")
    try:
        settings = await system_manager.get_site_settings()
        connection = (getattr(system_manager, "connection", None) or
                     getattr(system_manager, "_connection", None))
        site = getattr(connection, "site", None) if connection else None
        return {"success": True, "site": site, "site_settings": settings}
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.error("Error getting site settings: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}

# Print confirmation that all tools have been registered
logger.info(
    "System tools registered: unifi_get_system_info, unifi_get_network_health, "
    "unifi_get_site_settings"
)
