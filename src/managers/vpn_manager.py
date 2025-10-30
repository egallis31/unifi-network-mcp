import logging
from typing import Dict, List, Optional, Any

from aiounifi.models.api import ApiRequest
from src.managers.connection_manager import ConnectionManager

logger = logging.getLogger("unifi-network-mcp")

CACHE_PREFIX_VPN_SERVERS = "vpn_servers"
CACHE_PREFIX_VPN_CLIENTS = "vpn_clients"

class VpnManager:
    """Manages VPN-related operations on the Unifi Controller."""

    def __init__(self, connection_manager: ConnectionManager):
        """Initialize the VPN Manager.

        Args:
            connection_manager: The shared ConnectionManager instance.
        """
        self._connection = connection_manager

    async def get_vpn_servers(self) -> List[Dict[str, Any]]:
        """Get list of VPN servers for the current site.
        
        VPN servers are managed as network configurations with specific purpose types.
        This method retrieves networks and filters for VPN server purposes.
        """
        cache_key = f"{CACHE_PREFIX_VPN_SERVERS}_{self._connection.site}"
        cached_data = self._connection.get_cached(cache_key)
        if cached_data is not None:
            return cached_data

        try:
            # VPN servers are part of network configurations
            api_request = ApiRequest(method="get", path="/rest/networkconf")
            response = await self._connection.request(api_request)
            
            # Handle response format (could be list or dict with 'data' key)
            networks_data = []
            if isinstance(response, dict) and 'data' in response and isinstance(response['data'], list):
                networks_data = response['data']
            elif isinstance(response, list):
                networks_data = response
            
            # Filter for VPN server purposes
            # VPN server purposes: remote-user-vpn (L2TP, OpenVPN, WireGuard servers)
            vpn_server_purposes = ['remote-user-vpn']
            servers = [
                net for net in networks_data 
                if net.get('purpose') in vpn_server_purposes
            ]
            
            getattr(self._connection, "_update_cache", lambda k, v: None)(cache_key, servers)
            return servers
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error getting VPN servers: %s", e)
            return []

    async def get_vpn_server_details(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific VPN server."""
        vpn_servers = await self.get_vpn_servers()
        server = next((s for s in vpn_servers if s.get("_id") == server_id), None)
        if not server:
            logger.warning("VPN server %s not found in cached/fetched list.", server_id)
        return server

    async def update_vpn_server_state(self, server_id: str, enabled: bool) -> bool:
        """Update the enabled state of a VPN server.
        
        Since VPN servers are network configurations, this updates the network config.

        Args:
            server_id: ID of the server to update
            enabled: Whether the server should be enabled or disabled

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            server = await self.get_vpn_server_details(server_id)
            if not server:
                logger.error("VPN server %s not found, cannot update state", server_id)
                return False

            update_data = {"enabled": enabled}

            # VPN servers are network configurations, use networkconf endpoint
            api_request = ApiRequest(
                method="put",
                path=f"/rest/networkconf/{server_id}",
                data=update_data
            )
            await self._connection.request(api_request)
            logger.info("Update state command sent for VPN server %s (enabled=%s)", server_id, enabled)
            cache_key_to_invalidate = f"{CACHE_PREFIX_VPN_SERVERS}_{self._connection.site}"
            getattr(self._connection, "_invalidate_cache", lambda x: None)(cache_key_to_invalidate)
            return True
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error updating VPN server state %s: %s", server_id, e)
            return False

    async def get_vpn_clients(self) -> List[Dict[str, Any]]:
        """Get list of active VPN clients for the current site."""
        cache_key = f"{CACHE_PREFIX_VPN_CLIENTS}_{self._connection.site}"
        cached_data = self._connection.get_cached(cache_key, timeout=30)  # 30 second cache
        if cached_data is not None:
            return cached_data

        try:
            api_request = ApiRequest(method="get", path="/stat/vpn")
            response = await self._connection.request(api_request)
            clients = response if isinstance(response, list) else []
            getattr(self._connection, "_update_cache", lambda k, v, **kw: None)(cache_key, clients, timeout=30)
            return clients
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error getting VPN clients: %s", e)
            return []

    async def get_vpn_client_details(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific VPN client.

        Args:
            client_id: ID of the client to get details for

        Returns:
            Client details if found, None otherwise
        """
        vpn_clients = await self.get_vpn_clients()
        client = next((c for c in vpn_clients if c.get("_id") == client_id), None)
        if not client:
            logger.warning("VPN client %s not found in fetched list.", client_id)
        return client

    async def update_vpn_client_state(self, client_id: str, enabled: bool) -> bool:
        """Update the enabled state of a VPN client.

        Args:
            client_id: ID of the client to update
            enabled: Whether the client should be enabled or disabled

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            client = await self.get_vpn_client_details(client_id)
            if not client:
                logger.error("VPN client %s not found, cannot update state", client_id)
                return False

            update_data = {"enabled": enabled}

            api_request = ApiRequest(
                method="put",
                path=f"/rest/vpnclient/{client_id}",
                data=update_data
            )

            try:
                await self._connection.request(api_request)
                logger.info("Update state command sent for VPN client %s (enabled=%s)", client_id, enabled)
                cache_key_to_invalidate = f"{CACHE_PREFIX_VPN_CLIENTS}_{self._connection.site}"
                getattr(self._connection, "_invalidate_cache", lambda x: None)(cache_key_to_invalidate)
                return True
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                logger.error("API error updating VPN client state %s: %s", client_id, e)
                return False

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error updating VPN client state %s: %s", client_id, e)
            return False


    async def generate_vpn_client_profile(
        self,
        server_id: str,
        client_name: str,
        expiration_days: Optional[int] = 365
    ) -> Optional[str]:
        """Generate a client profile configuration for VPN connection.

        Args:
            server_id: ID of the VPN server
            client_name: Name for the client configuration
            expiration_days: Days until the profile expires (default: 365)

        Returns:
            Client profile configuration (often as a string) if successful, None otherwise
        """
        try:
            server = await self.get_vpn_server_details(server_id)
            if not server:
                logger.error("Cannot generate profile for non-existent server %s", server_id)
                return None

            payload = {
                "name": client_name,
                "server_id": server_id,
                "exp": expiration_days
            }

            api_request = ApiRequest(
                method="post",
                path="/rest/vpnprofile",
                data=payload
            )
            response = await self._connection.request(api_request)
            logger.info("Generate profile command sent for VPN client '%s' on server %s", client_name, server_id)

            if isinstance(response, dict) and "data" in response:
                profile_data = response["data"]
                if isinstance(profile_data, list) and len(profile_data) > 0:
                    return str(profile_data[0]) # Return first element as string
                return str(profile_data) # Return data as string
            elif isinstance(response, str):
                return response # Handle cases where API returns profile directly as string

            logger.warning("Could not extract VPN client profile data from response: %s", response)
            return str(response) # Return raw response as string if extraction fails
        except (ValueError, TypeError, AttributeError, KeyError) as e:
            logger.error("Error generating VPN client profile: %s", e)
            return None
