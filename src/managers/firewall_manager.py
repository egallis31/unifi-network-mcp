import logging
from typing import Dict, List, Optional, Any
import json

from aiounifi.models.api import ApiRequest, ApiRequestV2
from aiounifi.models.firewall_policy import FirewallPolicy
from aiounifi.models.traffic_route import TrafficRoute
from aiounifi.models.port_forward import PortForward
from aiounifi.errors import RequestError, ResponseError
from src.managers.connection_manager import ConnectionManager

logger = logging.getLogger("unifi-network-mcp")

CACHE_PREFIX_FIREWALL_POLICIES = "firewall_policies"
CACHE_PREFIX_TRAFFIC_ROUTES = "traffic_routes"
CACHE_PREFIX_PORT_FORWARDS = "port_forwards"
CACHE_PREFIX_FIREWALL_ZONES = "firewall_zones"
CACHE_PREFIX_IP_GROUPS = "ip_groups"

class FirewallManager:
    """Manages Firewall Policies, Traffic Routes, and Port Forwards on the Unifi Controller."""

    def __init__(self, connection_manager: ConnectionManager):
        """Initialize the Firewall Manager.

        Args:
            connection_manager: The shared ConnectionManager instance.
        """
        self._connection = connection_manager

    async def get_firewall_policies(self, include_predefined: bool = False) -> List[FirewallPolicy]:
        """Get firewall policies.

        Args:
            include_predefined: Whether to include predefined policies.

        Returns:
            List of FirewallPolicy objects.
        """
        cache_key = f"{CACHE_PREFIX_FIREWALL_POLICIES}_{include_predefined}_{self._connection.site}"
        cached_data: Optional[List[FirewallPolicy]] = self._connection.get_cached(cache_key)
        if cached_data is not None:
            return cached_data

        if not await self._connection.ensure_connected():
            return []

        try:
            api_request = ApiRequestV2(method="get", path="/firewall-policies")

            response = await self._connection.request(api_request)

            policies_data = response if isinstance(response, list) else response.get('data', []) if isinstance(response, dict) else []

            policies: List[FirewallPolicy] = [FirewallPolicy(p) for p in policies_data]

            if not include_predefined:
                policies = [p for p in policies if not p.predefined]

            result = policies

            self._connection.update_cache(cache_key, result)
            return result
        except (RequestError, ResponseError) as e:
            logger.error("Error getting firewall policies: %s", e)
            return []
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Unexpected error getting firewall policies: %s", e)
            return []

    async def toggle_firewall_policy(self, policy_id: str) -> bool:
        """Toggle a firewall policy on/off.

        Args:
            policy_id: ID of the policy to toggle.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            policies = await self.get_firewall_policies(include_predefined=True)
            policy: Optional[FirewallPolicy] = next((p for p in policies if p.id == policy_id), None)

            if not policy:
                logger.error("Firewall policy %s not found.", policy_id)
                return False

            new_state = not policy.enabled
            logger.info("Toggling firewall policy %s to %s", policy_id, 'enabled' if new_state else 'disabled')

            update_payload = { "enabled": new_state }

            api_request = ApiRequestV2(
                method="put",
                path=f"/firewall-policies/{policy_id}",
                data=update_payload
            )
            await self._connection.request(api_request)

            self._connection.invalidate_cache(f"{CACHE_PREFIX_FIREWALL_POLICIES}_True_{self._connection.site}")
            self._connection.invalidate_cache(f"{CACHE_PREFIX_FIREWALL_POLICIES}_False_{self._connection.site}")

            return True
        except (RequestError, ResponseError) as e:
            logger.error("Error toggling firewall policy %s: %s", policy_id, e)
            return False
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Unexpected error toggling firewall policy %s: %s", policy_id, e)
            return False

    async def update_firewall_policy(self, policy_id: str, updates: Dict[str, Any]) -> bool:
        """Update specific fields of a firewall policy.

        Args:
            policy_id: ID of the policy to update.
            updates: Dictionary of fields and new values to apply.

        Returns:
            bool: True if successful, False otherwise.
        """
        if not await self._connection.ensure_connected():
            return False

        if not updates:
            logger.warning("No updates provided for firewall policy %s.", policy_id)
            return False # Or maybe True, as no action was needed? Returning False for clarity.

        try:
            all_policies = await self.get_firewall_policies(include_predefined=True)
            policy_to_update : Optional[FirewallPolicy] = next((p for p in all_policies if p.id == policy_id), None)

            if not policy_to_update:
                logger.error("Firewall policy %s not found for update.", policy_id)
                return False

            if not hasattr(policy_to_update, 'raw') or not isinstance(policy_to_update.raw, dict):
                logger.error("Could not get raw data for policy %s. Update aborted.", policy_id)
                return False
            policy_data = policy_to_update.raw.copy()

            for key, value in updates.items():
                policy_data[key] = value

            update_payload = [policy_data]

            logger.info("Updating firewall policy %s with full data payload: %s", policy_id, update_payload)

            api_request = ApiRequestV2(
                method="put",
                path="/firewall-policies/batch",
                data=update_payload  # type: ignore # Batch endpoint expects list
            )
            await self._connection.request(api_request)

            self._connection.invalidate_cache(f"{CACHE_PREFIX_FIREWALL_POLICIES}_True_{self._connection.site}")
            self._connection.invalidate_cache(f"{CACHE_PREFIX_FIREWALL_POLICIES}_False_{self._connection.site}")

            logger.info("Successfully submitted update for firewall policy %s.", policy_id)
            return True
        except (RequestError, ResponseError) as e:
            logger.error("Error updating firewall policy %s: %s", policy_id, e, exc_info=True)
            return False
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Unexpected error updating firewall policy %s: %s", policy_id, e, exc_info=True)
            return False

    async def get_traffic_routes(self) -> List[TrafficRoute]:
        """Get all traffic routes.

        Returns:
            List of TrafficRoute objects.
        """
        cache_key = f"{CACHE_PREFIX_TRAFFIC_ROUTES}_{self._connection.site}"
        cached_data: Optional[List[TrafficRoute]] = self._connection.get_cached(cache_key)
        if cached_data is not None:
            return cached_data

        if not await self._connection.ensure_connected():
            return []

        try:
            api_request = ApiRequestV2(method="get", path="/trafficroutes")

            response = await self._connection.request(api_request)

            routes_data = response if isinstance(response, list) else response.get('data', []) if isinstance(response, dict) else []

            routes: List[TrafficRoute] = [TrafficRoute(r) for r in routes_data]

            result = routes

            self._connection.update_cache(cache_key, result)
            return result
        except (RequestError, ResponseError) as e:
            logger.error("Error getting traffic routes: %s", e)
            return []
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Unexpected error getting traffic routes: %s", e)
            return []

    async def update_traffic_route(self, route_id: str, updates: Dict[str, Any]) -> bool:
        """Update specific fields of a traffic route using the V2 API.

        Args:
            route_id: ID of the route to update.
            updates: Dictionary of fields and new values to apply.

        Returns:
            bool: True if successful, False otherwise.
        """
        if not await self._connection.ensure_connected():
            return False
        if not updates:
            logger.warning("No updates provided for traffic route %s.", route_id)
            return True # No action needed, considered success

        try:
            # Fetch existing route data using the V2-based method
            routes = await self.get_traffic_routes()
            route_to_update_obj: Optional[TrafficRoute] = next((r for r in routes if r.id == route_id), None)

            if not route_to_update_obj:
                logger.error("Traffic route %s not found for update.", route_id)
                return False

            if not hasattr(route_to_update_obj, 'raw') or not isinstance(route_to_update_obj.raw, dict):
                logger.error("Could not get raw data for traffic route %s. Update aborted.", route_id)
                return False

            current_data = route_to_update_obj.raw.copy()

            # Merge updates into current data
            updated_data = current_data
            for key, value in updates.items():
                updated_data[key] = value

            api_path = f"/trafficroutes/{route_id}"

            logger.info("Updating traffic route %s via V2 endpoint (%s) with data: %s", route_id, api_path, updated_data)

            # Use ApiRequestV2 for the update
            api_request = ApiRequestV2(
                method="put",
                path=api_path,
                data=updated_data # V2 typically uses the 'data' field
            )

            # The request method should handle potential V2 response structures
            await self._connection.request(api_request)

            # Invalidate cache
            cache_key = f"{CACHE_PREFIX_TRAFFIC_ROUTES}_{self._connection.site}"
            self._connection.invalidate_cache(cache_key)

            logger.info("Successfully submitted V2 update for traffic route %s.", route_id)
            return True
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Error updating traffic route %s via V2: %s", route_id, e, exc_info=True)
            return False

    async def toggle_traffic_route(self, route_id: str) -> bool:
        """Toggle a traffic route on/off.

        Args:
            route_id: ID of the route to toggle.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            routes = await self.get_traffic_routes()
            route: Optional[TrafficRoute] = next((r for r in routes if r.id == route_id), None)

            if not route:
                logger.error("Traffic route %s not found.", route_id)
                return False

            if not hasattr(route, 'raw') or not isinstance(route.raw, dict):
                logger.error("Could not get raw data for traffic route %s. Toggle aborted.", route_id)
                return False

            new_state = not route.enabled
            logger.info("Toggling traffic route %s to %s", route_id, 'enabled' if new_state else 'disabled')

            # Use the update method for consistency
            update_payload = {"enabled": new_state}
            return await self.update_traffic_route(route_id, update_payload)

        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Error toggling traffic route %s: %s", route_id, e, exc_info=True)
            return False

    async def create_traffic_route(self, route_data: Dict[str, Any]) -> Optional[Dict]:
        """Create a new traffic route. Returns the created route data dict or None.

        Args:
            route_data: Dictionary containing the route configuration.
                      Expected keys depend on route type (e.g., name, interface,
                      domain_names or ip_addresses or network_ids, enabled, description).

        Returns:
            The created route data dict, or None if creation failed.
        """
        if not route_data.get("name") or not route_data.get("interface"):
            logger.error("Missing required keys for creating traffic route (name, interface)")
            return None

        try:
            logger.info("Attempting to create traffic route '%s'", route_data['name'])
            api_path = "/trafficroutes" # V2 endpoint for creation
            # Log the exact data being sent for easier debugging
            logger.info("Attempting to create traffic route via V2 endpoint (%s) with payload: %s", api_path, json.dumps(route_data, indent=2))

            # Use ApiRequestV2 for the creation
            api_request = ApiRequestV2(
                method="post",
                path=api_path,
                data=route_data
            )
            response = await self._connection.request(api_request)

            # Check response structure for success and ID (adjust based on actual V2 response)
            # Example V2 success might be a 201 Created with the new object or ID in body/headers
            if isinstance(response, dict) and response.get("_id"): # Simple check if response is the new object
                new_id = response.get("_id")
                logger.info("Successfully created traffic route via V2. New ID: %s", new_id)
                self._connection.invalidate_cache(f"{CACHE_PREFIX_TRAFFIC_ROUTES}_{self._connection.site}")
                # Return a clear success dictionary with the ID
                return {"success": True, "route_id": new_id}
            elif isinstance(response, list) and len(response) == 1 and response[0].get("_id"): # Sometimes APIs return a list containing the single new item
                new_id = response[0].get("_id")
                logger.info("Successfully created traffic route via V2 (list response). New ID: %s", new_id)
                self._connection.invalidate_cache(f"{CACHE_PREFIX_TRAFFIC_ROUTES}_{self._connection.site}")
                # Return a clear success dictionary with the ID
                return {"success": True, "route_id": new_id}
            else:
                # Handle unexpected non-error response
                error_detail = f"Unexpected success response format: {str(response)}"
                logger.error("Failed to create traffic route via V2. %s", error_detail)
                return {"success": False, "error": error_detail}

        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            # Log the exception details
            logger.error("Exception during V2 traffic route creation: %s", e, exc_info=True)

            # Extract specific API error message if available
            api_error_message = str(e)
            if hasattr(e, 'args') and e.args:
                try:
                    # Attempt to parse nested error structure seen in logs
                    error_details = e.args[0]
                    if isinstance(error_details, dict) and 'message' in error_details:
                        api_error_message = error_details['message']
                    elif isinstance(error_details, str): # Fallback if it's just a string
                        api_error_message = error_details
                except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as parse_exc:
                    logger.warning("Could not parse specific API error from exception args: %s. Parse error: %s", e.args, parse_exc)

            # Return a clear failure dictionary with the extracted error message
            return {"success": False, "error": f"API Error: {api_error_message}"}

    async def delete_traffic_route(self, route_id: str) -> bool:
        """Delete a traffic route by ID.

        Args:
            route_id: ID of the route to delete.

        Returns:
            bool: True if successful, False otherwise.
        """
        if not await self._connection.ensure_connected():
            return False
        try:
            # Use V2 endpoint for deletion
            api_request = ApiRequestV2(method="delete", path=f"/trafficroutes/{route_id}")
            await self._connection.request(api_request)

            cache_key = f"{CACHE_PREFIX_TRAFFIC_ROUTES}_{self._connection.site}"
            self._connection.invalidate_cache(cache_key)
            logger.info("Successfully deleted traffic route %s", route_id)
            return True
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            # Handle specific "not found" errors if possible?
            logger.error("Error deleting traffic route %s: %s", route_id, e, exc_info=True)
            return False

    async def get_port_forwards(self) -> List[PortForward]:
        """Get all port forwarding rules.
        Returns:
             List of PortForward objects.
        """
        cache_key = f"{CACHE_PREFIX_PORT_FORWARDS}_{self._connection.site}"
        cached_data: Optional[List[PortForward]] = self._connection.get_cached(cache_key)
        if cached_data is not None:
            return cached_data

        if not await self._connection.ensure_connected():
            return []

        try:
            api_request = ApiRequest(method="get", path="/rest/portforward")
            response = await self._connection.request(api_request)
            rules_data = response if isinstance(response, list) else response.get('data', []) if isinstance(response, dict) else []
            rules: List[PortForward] = [PortForward(r) for r in rules_data]

            result = rules

            self._connection.update_cache(cache_key, result)
            return result
        except (RequestError, ResponseError) as e:
            logger.error("Error getting port forwards: %s", e)
            return []
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Unexpected error getting port forwards: %s", e)
            return []

    async def get_port_forward_by_id(self, rule_id: str) -> Optional[PortForward]:
        """Get a specific port forwarding rule by ID.

        Args:
            rule_id: ID of the rule to get.

        Returns:
            The PortForward object, or None if not found.
        """
        try:
            rules = await self.get_port_forwards()
            return next((rule for rule in rules if rule.id == rule_id), None)
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Error getting port forward by ID %s: %s", rule_id, e)
            return None

    async def update_port_forward(self, rule_id: str, updates: Dict[str, Any]) -> bool:
        """Update specific fields of a port forwarding rule.

        Args:
            rule_id: ID of the rule to update.
            updates: Dictionary of fields and new values to apply.

        Returns:
            bool: True if successful, False otherwise.
        """
        if not await self._connection.ensure_connected():
            return False
        if not updates:
            logger.warning("No updates provided for port forward %s.", rule_id)
            return True # No action needed, considered success

        try:
            # Fetch existing rule data
            rule_to_update_obj = await self.get_port_forward_by_id(rule_id)

            if not rule_to_update_obj:
                logger.error("Port forward %s not found for update.", rule_id)
                return False

            if not hasattr(rule_to_update_obj, 'raw') or not isinstance(rule_to_update_obj.raw, dict):
                logger.error("Could not get raw data for port forward %s. Update aborted.", rule_id)
                return False

            current_data = rule_to_update_obj.raw.copy()

            # Merge updates into current data
            for key, value in updates.items():
                current_data[key] = value

            update_payload = current_data

            logger.info("Updating port forward %s with full data: %s", rule_id, update_payload)

            api_request = ApiRequest(
                method="put",
                path=f"/rest/portforward/{rule_id}", # V1 endpoint path, corrected
                data=update_payload
            )

            await self._connection.request(api_request)

            # Invalidate cache
            cache_key = f"{CACHE_PREFIX_PORT_FORWARDS}_{self._connection.site}"
            self._connection.invalidate_cache(cache_key)

            logger.info("Successfully submitted update for port forward %s.", rule_id)
            return True
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Error updating port forward %s: %s", rule_id, e, exc_info=True)
            return False

    async def toggle_port_forward(self, rule_id: str) -> bool:
        """Toggle a port forwarding rule on/off.

        Args:
            rule_id: ID of the rule to toggle.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            rule = await self.get_port_forward_by_id(rule_id)
            if not rule:
                logger.error("Port forward rule %s not found.", rule_id)
                return False

            if not hasattr(rule, 'raw') or not isinstance(rule.raw, dict):
                logger.error("Could not get raw data for port forward %s. Toggle aborted.", rule_id)
                return False

            new_state = not rule.enabled
            logger.info("Toggling port forward %s to %s", rule_id, 'enabled' if new_state else 'disabled')

            # Use the update method
            update_payload = {"enabled": new_state}
            return await self.update_port_forward(rule_id, update_payload)

        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Error toggling port forward %s: %s", rule_id, e, exc_info=True)
            return False

    async def create_port_forward(self, rule_data: Dict[str, Any]) -> Optional[Dict]:
        """Create a new port forwarding rule. Returns the created rule data dict or None.

        Args:
            rule_data: Dictionary containing the rule configuration. Expected keys:
                       name (str), dst_port (str), fwd_port (str), fwd_ip (str),
                       protocol (str, optional), enabled (bool, optional), etc.

        Returns:
            The created rule data dict, or None if creation failed.
        """
        required_keys = {"name", "dst_port", "fwd_port", "fwd_ip"}
        if not required_keys.issubset(rule_data.keys()):
            missing = required_keys - rule_data.keys()
            logger.error("Missing required keys for creating port forward: %s", missing)
            return None

        try:
            logger.info("Attempting to create port forward rule '%s'", rule_data['name'])
            api_request = ApiRequest(
                method="post",
                path="/rest/portforward", # V1 endpoint path, corrected
                data=rule_data,
            )
            response = await self._connection.request(api_request)

            # V1 POST usually returns a list containing the created object within 'data'
            created_rule = None
            if isinstance(response, dict) and 'data' in response and isinstance(response['data'], list) and len(response['data']) > 0:
                created_rule = response['data'][0]
            else:
                logger.error("Unexpected response format creating port forward: %s", response)
                return None

            cache_key = f"{CACHE_PREFIX_PORT_FORWARDS}_{self._connection.site}"
            self._connection.invalidate_cache(cache_key)
            logger.info("Successfully created port forward '%s'", rule_data.get('name'))
            return created_rule if isinstance(created_rule, dict) else None

        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Error creating port forward '%s': %s", rule_data.get('name', 'unknown'), e, exc_info=True)
            return None

    async def delete_port_forward(self, rule_id: str) -> bool:
        """Delete a port forwarding rule by ID.

        Args:
            rule_id: ID of the rule to delete.

        Returns:
            bool: True if successful, False otherwise.
        """
        if not await self._connection.ensure_connected():
            return False
        try:
            # Use V1 endpoint as aiounifi does
            api_request = ApiRequest(
                method="delete",
                path=f"/rest/portforward/{rule_id}",
            )
            await self._connection.request(api_request)

            cache_key = f"{CACHE_PREFIX_PORT_FORWARDS}_{self._connection.site}"
            self._connection.invalidate_cache(cache_key)
            logger.info("Successfully deleted port forward %s", rule_id)
            return True
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Error deleting port forward %s: %s", rule_id, e, exc_info=True)
            return False

    async def create_firewall_policy(self, policy_data: Dict[str, Any]) -> Optional[FirewallPolicy]:
        """Create a new firewall policy using the V2 API.

        Args:
            policy_data: Dictionary containing the policy configuration conforming
                         to the UniFi API structure for firewall policies.

        Returns:
            The created FirewallPolicy object, or None if creation failed.
        """
        if not await self._connection.ensure_connected():
            return None

        try:
            policy_name = policy_data.get('name', 'Unnamed Policy')
            logger.info("Attempting to create firewall policy '%s' via V2 endpoint.", policy_name)
            # Log the payload for debugging, ensuring sensitive data isn't exposed if necessary
            # logger.debug(f"Firewall policy create payload: {json.dumps(policy_data, indent=2)}")

            api_request = ApiRequestV2(
                method="post",
                path="/firewall-policies",
                data=policy_data
            )

            response = await self._connection.request(api_request)

            # V2 POST often returns the created object directly or within a list
            created_policy_data = None
            if isinstance(response, dict) and response.get("_id"):
                created_policy_data = response
            elif isinstance(response, list) and len(response) == 1 and response[0].get("_id"):
                created_policy_data = response[0]

            if created_policy_data:
                new_policy_id = created_policy_data.get("_id")
                logger.info("Successfully created firewall policy '%s' with ID %s via V2.", policy_name, new_policy_id)
                # Invalidate caches after successful creation
                self._connection.invalidate_cache(f"{CACHE_PREFIX_FIREWALL_POLICIES}_True_{self._connection.site}")
                self._connection.invalidate_cache(f"{CACHE_PREFIX_FIREWALL_POLICIES}_False_{self._connection.site}")
                return FirewallPolicy(created_policy_data)
            else:
                logger.error("Failed to create firewall policy '%s'. Unexpected V2 response format: %s", policy_name, response)
                return None

        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            # Attempt to extract a more specific error message if possible
            api_error_message = str(e)
            if hasattr(e, 'args') and e.args:
                try:
                    error_details = e.args[0]
                    if isinstance(error_details, dict) and 'message' in error_details:
                        api_error_message = error_details['message']
                    elif isinstance(error_details, str):
                        api_error_message = error_details
                except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as parse_exc:
                    logger.warning("Could not parse specific API error from exception args: %s. Parse error: %s", e.args, parse_exc)

            logger.error("Error creating firewall policy '%s' via V2: %s", policy_data.get('name', 'Unnamed Policy'), api_error_message, exc_info=True)
            # Optionally re-raise or return a custom error object instead of None
            return None

    async def delete_firewall_policy(self, policy_id: str) -> bool:
        """Delete a firewall policy by ID.

        Args:
            policy_id: ID of the policy to delete.

        Returns:
            bool: True if successful, False otherwise.
        """
        if not await self._connection.ensure_connected():
            return False
        try:
            api_request = ApiRequestV2(method="delete", path=f"/firewall-policies/{policy_id}")
            await self._connection.request(api_request)

            cache_key_true = f"{CACHE_PREFIX_FIREWALL_POLICIES}_True_{self._connection.site}"
            cache_key_false = f"{CACHE_PREFIX_FIREWALL_POLICIES}_False_{self._connection.site}"
            self._connection.invalidate_cache(cache_key_true)
            self._connection.invalidate_cache(cache_key_false)
            logger.info("Successfully deleted firewall policy %s", policy_id)
            return True
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Error deleting firewall policy %s: %s", policy_id, e, exc_info=True)
            return False

    async def get_firewall_zones(self) -> List[Dict[str, Any]]:
        """Return list of firewall zones via V2 API."""
        cache_key = f"{CACHE_PREFIX_FIREWALL_ZONES}_{self._connection.site}"
        cached = self._connection.get_cached(cache_key)
        if cached is not None:
            return cached
        if not await self._connection.ensure_connected():
            return []
        try:
            api_request = ApiRequestV2(method="get", path="/firewall/zones")
            resp = await self._connection.request(api_request)
            data = resp if isinstance(resp, list) else resp.get("data", []) if isinstance(resp, dict) else []
            self._connection.update_cache(cache_key, data)
            return data
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Error fetching firewall zones: %s", e)
            return []

    async def get_ip_groups(self) -> List[Dict[str, Any]]:
        """Return list of IP groups via V2 API."""
        cache_key = f"{CACHE_PREFIX_IP_GROUPS}_{self._connection.site}"
        cached = self._connection.get_cached(cache_key)
        if cached is not None:
            return cached
        if not await self._connection.ensure_connected():
            return []
        try:
            api_request = ApiRequestV2(method="get", path="/ip-groups")
            resp = await self._connection.request(api_request)
            data = resp if isinstance(resp, list) else resp.get("data", []) if isinstance(resp, dict) else []
            self._connection.update_cache(cache_key, data)
            return data
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Error fetching ip groups: %s", e)
            return []
