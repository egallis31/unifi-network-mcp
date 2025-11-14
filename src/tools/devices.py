"""
Unifi Network MCP device management tools.

This module provides MCP tools to manage devices in a Unifi Network Controller.
"""


import logging
from typing import Dict, List, Any
from datetime import datetime, timedelta
from src.runtime import server, device_manager

logger = logging.getLogger(__name__)

def get_wifi_bands(device: Dict[str, Any]) -> List[str]:
    """Extract active WiFi bands from device radio table."""
    bands = set()
    for radio in device.get("radio_table", []):
        if radio.get("radio") == "na":
            bands.add("5GHz")
        elif radio.get("radio") == "ng":
            bands.add("2.4GHz")
        elif radio.get("radio") == "wifi6e":
            bands.add("6GHz")
    return sorted(list(bands))

@server.tool(
    name="unifi_list_devices",
    description="List devices adopted by the Unifi Network controller for the current site"
)
async def list_devices(
    device_type: str = "all",
    status: str = "all",
    include_details: bool = False
) -> Dict[str, Any]:
    """Implementation for listing devices."""
    try:
        devices = await device_manager.get_devices()
        devices_raw = [d.raw if hasattr(d, "raw") else d for d in devices]

        # Filter by device type
        if device_type != "all":
            prefix_map = {
                "ap": ("uap",),
                "uap": ("uap",),
                "switch": ("usw", "usk"),
                "usw": ("usw", "usk"),
                "gateway": ("ugw", "udm", "uxg"),
                "ugw": ("ugw", "udm", "uxg"),
                "udm": ("udm",),
                "pdu": ("usp",),
                "usp": ("usp",),
            }
            prefixes = prefix_map.get(device_type)
            if prefixes:
                devices_raw = [
                    d for d in devices_raw 
                    if isinstance(d, dict) and any(
                        d.get("type", "").startswith(p) for p in prefixes
                    )
                ]

        # Filter by status
        formatted_devices = []
        state_map = {
            0: "offline",
            1: "online",
            2: "pending_adoption",
            4: "managed_by_other/adopting",
            5: "provisioning",
            6: "upgrading",
            11: "error/heartbeat_missed",
        }

        for device in devices_raw:
            if not isinstance(device, dict):
                continue
            device_state = device.get("state", 0)
            device_status_str = state_map.get(device_state, f"unknown_state ({device_state})")

            device_info = {
                "mac": device.get("mac", ""),
                "name": device.get("name", device.get("model", "Unknown")),
                "model": device.get("model", ""),
                "type": device.get("type", ""),
                "ip": device.get("ip", ""),
                "status": device_status_str,
                "uptime": str(timedelta(seconds=device.get("uptime", 0))) if device.get("uptime") else "N/A",
                "last_seen": (
                    datetime.fromtimestamp(device.get("last_seen", 0)).isoformat()
                    if device.get("last_seen")
                    else "N/A"
                ),
                "firmware": device.get("version", ""),
                "adopted": device.get("adopted", False),
                "_id": device.get("_id", ""),
            }

            details_to_add = {}
            if include_details:
                details_to_add = {
                    "serial": device.get("serial", ""),
                    "hw_revision": device.get("hw_rev", ""),
                    "model_display": device.get("model_display", device.get("model")),
                    "clients": device.get("num_sta", 0),
                }
                device_type_prefix = device.get("type", "")[:3]
                if device_type_prefix == "uap":
                    from typing import cast
                    device_dict = device if isinstance(device, dict) else (device.raw if hasattr(device, "raw") else {})
                    wifi_bands_data = cast(Dict[str, Any], device_dict)
                    details_to_add.update({
                        "radio_table": device.get("radio_table", []),
                        "vap_table": device.get("vap_table", []),
                        "wifi_bands": get_wifi_bands(wifi_bands_data),
                        "experience_score": device.get("satisfaction", 0),
                        "num_clients": device.get("num_sta", 0),
                    })
                elif device_type_prefix in ["usw", "usk"]:
                    details_to_add.update({
                        "ports": device.get("port_table", []),
                        "total_ports": len(device.get("port_table", [])),
                        "num_clients": device.get("user-num_sta", 0) + device.get("guest-num_sta", 0),
                        "poe_info": {
                            "poe_current": device.get("poe_current"),
                            "poe_power": device.get("poe_power"),
                            "poe_voltage": device.get("poe_voltage"),
                        },
                    })
                elif device_type_prefix in ["ugw", "udm", "uxg"]:
                    details_to_add.update({
                        "wan1": device.get("wan1", {}),
                        "wan2": device.get("wan2", {}),
                        "num_clients": device.get("user-num_sta", 0) + device.get("guest-num_sta", 0),
                        "network_table": device.get("network_table", []),
                        "system_stats": device.get("system-stats", {}),
                        "speedtest_status": device.get("speedtest-status", {}),
                    })
            device_info.update(details_to_add)
            formatted_devices.append(device_info)

        connection = getattr(device_manager, "_connection", None)
        site = getattr(connection, "site", None) if connection else None
        return {
            "success": True,
            "site": site,
            "filter_type": device_type,
            "filter_status": status,
            "count": len(formatted_devices),
            "devices": formatted_devices
        }
    except (ValueError, TypeError, AttributeError, KeyError) as e:
        logger.error("Error listing devices: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}
