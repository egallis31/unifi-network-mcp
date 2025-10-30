"""
Unifi Network MCP statistics tools.

This module provides MCP tools to fetch statistics from a Unifi Network Controller.
"""

import logging
from typing import Dict, Any
from aiounifi.errors import RequestError, ResponseError

from src.runtime import server, stats_manager, client_manager, device_manager

logger = logging.getLogger(__name__)

@server.tool(
    name="unifi_get_network_stats",
    description="Get network statistics from the Unifi Network controller"
)
async def get_network_stats(duration: str = "hourly") -> Dict[str, Any]:
    """Implementation for getting network stats."""
    try:
        duration_hours = {
            "hourly": 1, "daily": 24, "weekly": 168, "monthly": 720
        }.get(duration, 1)
        stats = await stats_manager.get_network_stats(duration_hours=duration_hours)
        def _first_non_none(*values):
            for v in values:
                if v is not None:
                    return v
            return 0

        summary = {
            "total_rx_bytes": sum(int(e.get("rx_bytes", 0) or 0) for e in stats),
            "total_tx_bytes": sum(int(e.get("tx_bytes", 0) or 0) for e in stats),
            "total_bytes": sum(
                int(e.get("bytes") or 0) if e.get("bytes") is not None
                else int(e.get("rx_bytes", 0) or 0) + int(e.get("tx_bytes", 0) or 0)
                for e in stats
            ),
            "avg_clients": int(
                sum(
                    _first_non_none(
                        e.get("num_user"),
                        e.get("num_active_user"),
                        e.get("num_sta")
                    )
                    for e in stats
                ) / max(1, len(stats))
            ) if stats else 0,
        }
        return {
            "success": True,
            "site": getattr(
                getattr(stats_manager, "_connection", None), "site", "unknown"
            ),
            "duration": duration,
            "summary": summary,
            "stats": stats
        }
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:  # noqa: BLE001 # pylint: disable=broad-exception-caught
        logger.error("Error getting network stats: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_get_client_stats",
    description="Get statistics for a specific client/device"
)
async def get_client_stats(client_id: str, duration: str = "hourly") -> Dict[str, Any]:
    """Implementation for getting client stats."""
    try:
        duration_hours = {
            "hourly": 1, "daily": 24, "weekly": 168, "monthly": 720
        }.get(duration, 1)
        client_details = await client_manager.get_client_details(client_id)
        if not client_details:
            return {"success": False, "error": f"Client '{client_id}' not found"}

        # Support aiounifi Client objects as well as dicts
        client_raw = (
            client_details.raw if hasattr(client_details, "raw")
            else client_details
        )

        # Handle both dict and object types
        def safe_get(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        client_mac = safe_get(client_raw, "mac", client_id)
        client_name = (
            safe_get(client_raw, "name")
            or safe_get(client_raw, "hostname")
            or client_mac
        )

        # Stats endpoint expects MAC, not _id
        stats = await stats_manager.get_client_stats(
            client_mac, duration_hours=duration_hours
        )
        summary = {
            "total_rx_bytes": sum(e.get("rx_bytes", 0) for e in stats),
            "total_tx_bytes": sum(e.get("tx_bytes", 0) for e in stats),
            "total_bytes": sum(
                e.get("bytes", e.get("rx_bytes", 0) + e.get("tx_bytes", 0))
                for e in stats
            ),
        }
        return {
            "success": True,
            "site": getattr(
                getattr(stats_manager, "_connection", None), "site", "unknown"
            ),
            "client_id": client_id,
            "client_name": client_name,
            "duration": duration,
            "summary": summary,
            "stats": stats
        }
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:  # noqa: BLE001 # pylint: disable=broad-exception-caught
        logger.error(
            "Error getting client stats for %s: %s", client_id, e, exc_info=True
        )
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_get_device_stats",
    description="Get statistics for a specific device (access point, switch, etc.)"
)
async def get_device_stats(device_id: str, duration: str = "hourly") -> Dict[str, Any]:
    """Implementation for getting device stats."""
    try:
        duration_hours = {
            "hourly": 1, "daily": 24, "weekly": 168, "monthly": 720
        }.get(duration, 1)
        device_details = await device_manager.get_device_details(device_id)
        if not device_details:
            return {"success": False, "error": f"Device '{device_id}' not found"}

        # Handle both dict and object types for device details
        def safe_get_device(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        device_name = (
            safe_get_device(device_details, "name")
            or safe_get_device(device_details, "model", "Unknown")
        )
        actual_device_id = safe_get_device(device_details, "_id", device_id)
        device_type = safe_get_device(device_details, "type", "unknown")

        stats = await stats_manager.get_device_stats(
            actual_device_id, duration_hours=duration_hours
        )
        summary = {
            "total_rx_bytes": sum(e.get("rx_bytes", 0) for e in stats),
            "total_tx_bytes": sum(e.get("tx_bytes", 0) for e in stats),
            "total_bytes": sum(
                e.get("bytes", e.get("rx_bytes", 0) + e.get("tx_bytes", 0))
                for e in stats
            ),
        }
        if device_type == "uap" and stats:
            summary["avg_clients"] = int(
                sum(e.get("num_sta", 0) for e in stats) / max(1, len(stats))
            )
            summary["max_clients"] = max(e.get("num_sta", 0) for e in stats)

        return {
            "success": True,
            "site": getattr(
                getattr(stats_manager, "_connection", None), "site", "unknown"
            ),
            "device_id": device_id,
            "device_name": device_name,
            "device_type": device_type,
            "duration": duration,
            "summary": summary,
            "stats": stats
        }
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:  # noqa: BLE001 # pylint: disable=broad-exception-caught
        logger.error(
            "Error getting device stats for %s: %s", device_id, e, exc_info=True
        )
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_get_top_clients",
    description="Get a list of top clients by usage (sorted by total bytes)"
)
async def get_top_clients(duration: str = "daily", limit: int = 10) -> Dict[str, Any]:
    """Implementation for getting top clients by usage."""
    try:
        top_client_stats = await stats_manager.get_top_clients(limit=limit)

        enhanced_clients = []
        for entry in top_client_stats:
            mac = entry.get("mac")
            name = "Unknown"
            if mac:
                details = await client_manager.get_client_details(mac)
                if details:
                    raw = details.raw if hasattr(details, "raw") else details
                    # Handle both dict and object types
                    def safe_get(obj, key, default=None):
                        if isinstance(obj, dict):
                            return obj.get(key, default)
                        return getattr(obj, key, default)
                    name = safe_get(raw, "name") or safe_get(raw, "hostname") or mac
            entry["name"] = name
            enhanced_clients.append(entry)

        return {
            "success": True,
            "site": getattr(
                getattr(stats_manager, "_connection", None), "site", "unknown"
            ),
            "duration": duration,
            "limit": limit,
            "top_clients": enhanced_clients
        }
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:  # noqa: BLE001 # pylint: disable=broad-exception-caught
        logger.error("Error getting top clients: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_get_dpi_stats",
    description=(
        "Get Deep Packet Inspection (DPI) statistics "
        "(applications and categories)"
    )
)
async def get_dpi_stats() -> Dict[str, Any]:
    """Implementation for getting DPI stats."""
    try:
        dpi_stats_result = await stats_manager.get_dpi_stats()

        def serialize_dpi(item):
            return item.raw if hasattr(item, 'raw') else item

        serialized_apps = [
            serialize_dpi(app) for app in dpi_stats_result.get("applications", [])
        ]
        serialized_cats = [
            serialize_dpi(cat) for cat in dpi_stats_result.get("categories", [])
        ]

        return {
            "success": True,
            "site": getattr(
                getattr(stats_manager, "_connection", None), "site", "unknown"
            ),
            "dpi_stats": {
                "applications": serialized_apps,
                "categories": serialized_cats
            }
        }
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:  # noqa: BLE001 # pylint: disable=broad-exception-caught
        logger.error("Error getting DPI stats: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}

@server.tool(
    name="unifi_get_alerts",
    description="Get recent alerts from the Unifi Network controller"
)
async def get_alerts(limit: int = 10, include_archived: bool = False) -> Dict[str, Any]:
    """Implementation for getting alerts."""
    try:
        alerts = await stats_manager.get_alerts(include_archived=include_archived)
        # Apply limit manually since the manager doesn't support it
        if limit and len(alerts) > limit:
            alerts = alerts[:limit]
        
        # Serialize Event objects to dicts using their .raw attribute
        serialized_alerts = [
            event.raw if hasattr(event, 'raw') else event
            for event in alerts
        ]
        
        return {
            "success": True,
            "site": getattr(
                getattr(stats_manager, "_connection", None), "site", "unknown"
            ),
            "limit": limit,
            "include_archived": include_archived,
            "alerts": serialized_alerts
        }
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:  # noqa: BLE001 # pylint: disable=broad-exception-caught
        logger.error("Error getting alerts: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}
