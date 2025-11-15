"""
Unifi Network MCP statistics tools.

This module provides MCP tools to fetch statistics from a Unifi Network Controller.
"""

import logging
from typing import Dict, Any
from aiounifi.errors import RequestError, ResponseError

from src.runtime import server, stats_manager, client_manager, device_manager, system_manager

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

        # Aggregate WAN bytes from network stats
        total_rx = sum(
            int(e.get("wan-rx_bytes", 0) or 0) + int(e.get("wan2-rx_bytes", 0) or 0)
            for e in stats
        )
        total_tx = sum(
            int(e.get("wan-tx_bytes", 0) or 0) + int(e.get("wan2-tx_bytes", 0) or 0)
            for e in stats
        )

        summary = {
            "total_rx_bytes": total_rx,
            "total_tx_bytes": total_tx,
            "total_bytes": total_rx + total_tx,
            "avg_clients": int(
                sum(
                    _first_non_none(
                        e.get("num_sta")
                    )
                    for e in stats
                ) / max(1, len(stats))
            ) if stats else 0,
        }

        # If stats are empty or zero, use multiple fallback strategies
        warning_message = None
        health_data = None
        aggregated_from_sources = None

        if not stats or (total_rx == 0 and total_tx == 0):
            logger.warning(
                "Network stats returned empty/zero (stats_count=%d, rx=%d, tx=%d). "
                "Attempting fallback strategies...",
                len(stats), total_rx, total_tx
            )

            # Strategy 1: Get health data for current snapshot
            try:
                health = await system_manager.get_network_health()
                if health:
                    health_items = health.get("items", []) if isinstance(health, dict) else health
                    health_data = health_items
                    logger.info("Health fallback retrieved %d subsystem(s)", len(health_items) if isinstance(health_items, list) else 0)

                    # Extract traffic from health data if available
                    if isinstance(health_items, list):
                        for subsystem in health_items:
                            subsystem_name = subsystem.get("subsystem", "unknown")
                            tx_bytes = subsystem.get("tx_bytes")
                            rx_bytes = subsystem.get("rx_bytes")
                            if tx_bytes or rx_bytes:
                                logger.info(
                                    "Health subsystem '%s': tx=%s, rx=%s",
                                    subsystem_name, tx_bytes, rx_bytes
                                )
            except Exception as health_error:
                logger.debug("Failed to fetch health fallback: %s", health_error)

            # Strategy 2: Aggregate from device stats if available
            try:
                logger.info("Attempting to aggregate traffic from device stats...")
                devices = await device_manager.get_devices()
                device_traffic = {"rx": 0, "tx": 0, "devices_counted": 0}

                for device in devices:
                    # Try to get current stats from device object
                    dev_raw = device.raw if hasattr(device, "raw") else device
                    if isinstance(dev_raw, dict):
                        stat_rx = dev_raw.get("stat", {}).get("rx_bytes") or dev_raw.get("rx_bytes")
                        stat_tx = dev_raw.get("stat", {}).get("tx_bytes") or dev_raw.get("tx_bytes")
                        if stat_rx or stat_tx:
                            device_traffic["rx"] += int(stat_rx or 0)
                            device_traffic["tx"] += int(stat_tx or 0)
                            device_traffic["devices_counted"] += 1

                if device_traffic["devices_counted"] > 0:
                    logger.info(
                        "Aggregated from %d devices: rx=%d, tx=%d",
                        device_traffic["devices_counted"],
                        device_traffic["rx"],
                        device_traffic["tx"]
                    )
                    aggregated_from_sources = {
                        "source": "device_aggregation",
                        "rx_bytes": device_traffic["rx"],
                        "tx_bytes": device_traffic["tx"],
                        "total_bytes": device_traffic["rx"] + device_traffic["tx"],
                        "devices_counted": device_traffic["devices_counted"],
                        "note": "Aggregated from current device stats (cumulative since device adoption)"
                    }
            except Exception as device_error:
                logger.debug("Failed to aggregate from devices: %s", device_error)

            # Build warning message
            if health_data or aggregated_from_sources:
                warning_parts = [
                    "Historical network stats endpoint returned empty/zero data.",
                    "This is a known issue with some UniFi controllers when querying site-level aggregates."
                ]
                if aggregated_from_sources:
                    warning_parts.append(
                        f"Showing aggregated traffic from {aggregated_from_sources['devices_counted']} devices instead."
                    )
                if health_data:
                    warning_parts.append("Also showing current health snapshot.")
                warning_message = " ".join(warning_parts)

        # Build comprehensive result with all available data
        result = {
            "success": True,
            "site": getattr(
                getattr(stats_manager, "_connection", None), "site", "unknown"
            ),
            "duration": duration,
            "summary": summary,
            "stats": stats
        }

        # Add fallback data if available
        if warning_message:
            result["warning"] = warning_message
        if health_data:
            result["health_fallback"] = health_data
        if aggregated_from_sources:
            result["aggregated_traffic"] = aggregated_from_sources

        return result
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
        device_mac = safe_get_device(device_details, "mac", device_id)
        device_type = safe_get_device(device_details, "type", "unknown")

        # Use MAC address for stats API call
        stats = await stats_manager.get_device_stats(
            device_mac, duration_hours=duration_hours
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
        total_count = len(alerts)

        # Log alert count before limiting
        logger.info(
            "Retrieved %d total alerts (include_archived=%s), applying limit=%d",
            total_count, include_archived, limit
        )

        # Apply limit - ensure we always limit if limit > 0
        if limit > 0 and len(alerts) > limit:
            alerts = alerts[:limit]
            logger.info("Limited alerts from %d to %d", total_count, len(alerts))

        # Serialize Event objects to dicts using their .raw attribute
        serialized_alerts = [
            event.raw if hasattr(event, 'raw') else event
            for event in alerts
        ]
        returned_count = len(serialized_alerts)

        # Verify serialization didn't change count
        if returned_count != len(alerts):
            logger.warning(
                "Alert count mismatch after serialization: %d alerts -> %d serialized",
                len(alerts), returned_count
            )

        return {
            "success": True,
            "site": getattr(
                getattr(stats_manager, "_connection", None), "site", "unknown"
            ),
            "limit_requested": limit,
            "total_alerts_found": total_count,
            "alerts_returned": returned_count,
            "include_archived": include_archived,
            "alerts": serialized_alerts
        }
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:  # noqa: BLE001 # pylint: disable=broad-exception-caught
        logger.error("Error getting alerts: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}
