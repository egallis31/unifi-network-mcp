"""Client manager for UniFi Network Controller operations."""

import logging
from typing import List, Optional

from aiounifi.models.api import ApiRequest
from aiounifi.models.client import Client

from src.managers.connection_manager import ConnectionManager

logger = logging.getLogger("unifi-network-mcp")

CACHE_PREFIX_CLIENTS = "clients"

class ClientManager:
    """Manages client-related operations on the Unifi Controller."""

    def __init__(self, connection_manager: ConnectionManager):
        """Initialize the Client Manager.

        Args:
            connection_manager: The shared ConnectionManager instance.
        """
        self._connection = connection_manager

    async def get_clients(self) -> List[Client]:
        """Get list of currently online clients for the current site."""
        if not await self._connection.ensure_connected() or not self._connection.controller:
            return []

        cache_key = f"{CACHE_PREFIX_CLIENTS}_online_{self._connection.site}"
        cached_data: Optional[List[Client]] = self._connection.get_cached(cache_key)
        if cached_data is not None:
            return cached_data

        try:
            await self._connection.controller.clients.update()
            clients: List[Client] = list(self._connection.controller.clients.values())
            # Fallback rationale:
            # - Some controller models/versions may not populate the collection
            #   via controller.clients.update().
            # - UniFi API semantics: active/online clients are served from
            #   /stat/sta, while historical/all clients are under /rest/user.
            #   Therefore for "online" we fallback to GET /stat/sta.
            if not clients:
                try:
                    raw_clients = await self._connection.request(
                        ApiRequest(method="get", path="/stat/sta")
                    )
                    if isinstance(raw_clients, list) and raw_clients:
                        # Cache raw dicts; tool layer handles dict or Client
                        getattr(self._connection, "_update_cache", lambda k, v: None)(cache_key, raw_clients)
                        return raw_clients  # type: ignore[return-value]
                except (ValueError, TypeError, AttributeError, KeyError) as fallback_e:
                    logger.debug("Raw clients fallback failed: %s", fallback_e)
            getattr(self._connection, "_update_cache", lambda k, v: None)(cache_key, clients)
            return clients
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error getting online clients: %s", e)
            return []

    async def get_all_clients(self) -> List[Client]:
        """Get list of all clients (including offline/historical) for the current site."""
        if not await self._connection.ensure_connected() or not self._connection.controller:
            return []

        cache_key = f"{CACHE_PREFIX_CLIENTS}_all_{self._connection.site}"
        cached_data: Optional[List[Client]] = self._connection.get_cached(cache_key)
        if cached_data is not None:
            return cached_data

        try:
            await self._connection.controller.clients_all.update()
            all_clients: List[Client] = list(self._connection.controller.clients_all.values())
            # Fallback rationale:
            # - When the clients_all collection is empty, query the canonical
            #   UniFi endpoint for all/historical client records.
            # - UniFi API semantics: GET /rest/user returns all known clients
            #   (legacy naming "user" == client record), not only currently
            #   connected. This complements GET /stat/sta used for online-only.
            if not all_clients:
                try:
                    raw_all = await self._connection.request(
                        ApiRequest(method="get", path="/rest/user")
                    )
                    if isinstance(raw_all, list) and raw_all:
                        getattr(self._connection, "_update_cache", lambda k, v: None)(cache_key, raw_all)
                        return raw_all  # type: ignore[return-value]
                except (ValueError, TypeError, AttributeError, KeyError) as fallback_e:
                    logger.debug("Raw all-clients fallback failed: %s", fallback_e)
            getattr(self._connection, "_update_cache", lambda k, v: None)(cache_key, all_clients)
            return all_clients
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error getting all clients: %s", e)
            return []

    async def get_client_details(self, client_mac: str) -> Optional[Client]:
        """Get detailed information for a specific client by MAC address."""
        all_clients = await self.get_all_clients()
        client: Optional[Client] = next(
            (c for c in all_clients if c.mac == client_mac), None
        )
        if not client:
            logger.debug(
                "Client details for MAC %s not found in clients_all list.", client_mac
            )
        return client

    async def block_client(self, client_mac: str) -> bool:
        """Block a client by MAC address."""
        try:
            # Construct ApiRequest
            api_request = ApiRequest(
                method="post",
                path="/cmd/stamgr",
                data={"mac": client_mac, "cmd": "block-sta"}
            )
            # Call the updated request method
            await self._connection.request(api_request)
            logger.info("Block command sent for client %s", client_mac)
            # Invalidate all client caches
            cache_key_to_invalidate = f"{CACHE_PREFIX_CLIENTS}"
            getattr(self._connection, "_invalidate_cache", lambda x: None)(cache_key_to_invalidate)
            return True
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error blocking client %s: %s", client_mac, e)
            return False

    async def unblock_client(self, client_mac: str) -> bool:
        """Unblock a client by MAC address."""
        try:
            # Construct ApiRequest
            api_request = ApiRequest(
                method="post",
                path="/cmd/stamgr",
                data={"mac": client_mac, "cmd": "unblock-sta"}
            )
            # Call the updated request method
            await self._connection.request(api_request)
            logger.info("Unblock command sent for client %s", client_mac)
            cache_key_to_invalidate = f"{CACHE_PREFIX_CLIENTS}"
            getattr(self._connection, "_invalidate_cache", lambda x: None)(cache_key_to_invalidate)
            return True
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error unblocking client %s: %s", client_mac, e)
            return False

    async def rename_client(self, client_mac: str, name: str) -> bool:
        """Rename a client device."""
        try:
            client = await self.get_client_details(client_mac)
            if not client or "_id" not in client.raw:
                logger.error(
                    "Cannot rename client %s: Not found or missing ID.", client_mac
                )
                return False
            client_id = client.raw["_id"]

            api_request = ApiRequest(
                method="put",
                path=f"/upd/user/{client_id}",
                data={"name": name}
            )
            await self._connection.request(api_request)
            logger.info("Rename command sent for client %s to '%s'", client_mac, name)
            cache_key_to_invalidate = f"{CACHE_PREFIX_CLIENTS}"
            getattr(self._connection, "_invalidate_cache", lambda x: None)(cache_key_to_invalidate)
            return True
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error renaming client %s to '%s': %s", client_mac, name, e)
            return False

    async def force_reconnect_client(self, client_mac: str) -> bool:
        """Force a client to reconnect (kick)."""
        try:
            api_request = ApiRequest(
                method="post",
                path="/cmd/stamgr",
                data={"mac": client_mac, "cmd": "kick-sta"}
            )
            await self._connection.request(api_request)
            logger.info("Force reconnect (kick) command sent for client %s", client_mac)
            cache_key_to_invalidate = f"{CACHE_PREFIX_CLIENTS}"
            getattr(self._connection, "_invalidate_cache", lambda x: None)(cache_key_to_invalidate)
            return True
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error forcing reconnect for client %s: %s", client_mac, e)
            return False

    async def get_blocked_clients(self) -> List[Client]:
        """Get a list of currently blocked clients."""
        all_clients = await self.get_all_clients()
        blocked: List[Client] = [client for client in all_clients if client.blocked]
        return blocked

    async def authorize_guest(
        self, client_mac: str, minutes: int,
        up_kbps: Optional[int]=None, down_kbps: Optional[int]=None,
        bytes_quota: Optional[int]=None
    ) -> bool:
        """Authorize a guest client."""
        try:
            payload = {
                "mac": client_mac,
                "cmd": "authorize-guest",
                "minutes": minutes
            }
            if up_kbps is not None:
                payload['up'] = up_kbps
            if down_kbps is not None:
                payload['down'] = down_kbps
            if bytes_quota is not None:
                payload['bytes'] = bytes_quota

            # Construct ApiRequest
            api_request = ApiRequest(
                method="post",
                path="/cmd/stamgr",
                data=payload
            )
            # Call the updated request method
            await self._connection.request(api_request)
            logger.info(
                "Authorize command sent for guest %s for %s minutes", client_mac, minutes
            )
            cache_key_to_invalidate = f"{CACHE_PREFIX_CLIENTS}"
            getattr(self._connection, "_invalidate_cache", lambda x: None)(cache_key_to_invalidate)
            return True
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error authorizing guest %s: %s", client_mac, e)
            return False

    async def unauthorize_guest(self, client_mac: str) -> bool:
        """Unauthorize (de-authorize) a guest client."""
        try:
            api_request = ApiRequest(
                method="post",
                path="/cmd/stamgr",
                data={"mac": client_mac, "cmd": "unauthorize-guest"}
            )
            await self._connection.request(api_request)
            logger.info("Unauthorize command sent for guest %s", client_mac)
            cache_key_to_invalidate = f"{CACHE_PREFIX_CLIENTS}"
            getattr(self._connection, "_invalidate_cache", lambda x: None)(cache_key_to_invalidate)
            return True
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error unauthorizing guest %s: %s", client_mac, e)
            return False
