"""Device manager for UniFi Network Controller operations."""

import logging
from typing import List, Optional

from aiounifi.models.api import ApiRequest
from aiounifi.models.device import Device

from src.managers.connection_manager import ConnectionManager

logger = logging.getLogger("unifi-network-mcp")

CACHE_PREFIX_DEVICES = "devices"

class DeviceManager:
    """Manages device-related operations on the Unifi Controller."""

    def __init__(self, connection_manager: ConnectionManager):
        """Initialize the Device Manager.

        Args:
            connection_manager: The shared ConnectionManager instance.
        """
        self._connection = connection_manager

    async def get_devices(self) -> List[Device]:
        """Get list of devices for the current site."""
        if not await self._connection.ensure_connected() or not self._connection.controller:
            return []

        cache_key = f"{CACHE_PREFIX_DEVICES}_{self._connection.site}"
        cached_data: Optional[List[Device]] = self._connection.get_cached(cache_key)
        if cached_data is not None:
            return cached_data

        try:
            await self._connection.controller.devices.update()
            devices: List[Device] = list(self._connection.controller.devices.values())
            getattr(self._connection, "_update_cache", lambda k, v: None)(cache_key, devices)
            return devices
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error getting devices: %s", e)
            return []

    async def get_device_details(self, device_identifier: str) -> Optional[Device]:
        """Get detailed information for a specific device by MAC address or _id.
        
        Args:
            device_identifier: Either MAC address or _id of the device
            
        Returns:
            Device object if found, None otherwise
        """
        devices = await self.get_devices()
        # Try to find by MAC first, then by _id
        device: Optional[Device] = next(
            (d for d in devices if d.mac == device_identifier), None
        )
        if not device:
            device = next(
                (d for d in devices if getattr(d, "_id", None) == device_identifier or 
                 (hasattr(d, "raw") and d.raw.get("_id") == device_identifier)), 
                None
            )
        if not device:
            logger.debug(
                "Device details for identifier %s not found in devices list.", device_identifier
            )
        return device

    async def reboot_device(self, device_mac: str) -> bool:
        """Reboot a device by MAC address."""
        try:
            api_request = ApiRequest(
                method="post",
                path="/cmd/devmgr",
                data={"mac": device_mac, "cmd": "restart"}
            )
            await self._connection.request(api_request)
            logger.info("Reboot command sent for device %s", device_mac)
            getattr(self._connection, "_invalidate_cache", lambda x: None)(CACHE_PREFIX_DEVICES)
            return True
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error rebooting device %s: %s", device_mac, e)
            return False

    async def rename_device(self, device_mac: str, name: str) -> bool:
        """Rename a device."""
        try:
            device = await self.get_device_details(device_mac)
            if not device or "_id" not in device.raw:
                logger.error(
                    "Cannot rename device %s: Not found or missing ID.", device_mac
                )
                return False
            device_id = device.raw["_id"]

            api_request = ApiRequest(
                method="put",
                path=f"/rest/device/{device_id}",
                data={"name": name}
            )
            await self._connection.request(api_request)
            logger.info("Rename command sent for device %s to '%s'", device_mac, name)
            getattr(self._connection, "_invalidate_cache", lambda x: None)(CACHE_PREFIX_DEVICES)
            return True
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error renaming device %s to '%s': %s", device_mac, name, e)
            return False

    async def adopt_device(self, device_mac: str) -> bool:
        """Adopt a device by MAC address."""
        try:
            api_request = ApiRequest(
                method="post",
                path="/cmd/devmgr",
                data={"mac": device_mac, "cmd": "adopt"}
            )
            await self._connection.request(api_request)
            logger.info("Adopt command sent for device %s", device_mac)
            getattr(self._connection, "_invalidate_cache", lambda x: None)(CACHE_PREFIX_DEVICES)
            return True
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error adopting device %s: %s", device_mac, e)
            return False

    async def upgrade_device(self, device_mac: str) -> bool:
        """Start firmware upgrade for a device by MAC address."""
        try:
            api_request = ApiRequest(
                method="post",
                path="/cmd/devmgr",
                data={"mac": device_mac, "cmd": "upgrade"}
            )
            await self._connection.request(api_request)
            logger.info("Upgrade command sent for device %s", device_mac)
            getattr(self._connection, "_invalidate_cache", lambda x: None)(CACHE_PREFIX_DEVICES)
            return True
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error upgrading device %s: %s", device_mac, e)
            return False
