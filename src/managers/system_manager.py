"""System manager for UniFi Network Controller operations."""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from aiounifi.errors import RequestError, ResponseError

from aiounifi.models.api import ApiRequest
from aiounifi.models.site import Site

from src.managers.connection_manager import ConnectionManager

logger = logging.getLogger("unifi-network-mcp")

CACHE_PREFIX_SYSINFO = "system_info"
CACHE_PREFIX_SETTINGS = "settings"
CACHE_PREFIX_SITES = "sites"
CACHE_PREFIX_ADMINS = "admin_users"


class SystemManager:
    """Manages system, site, and user operations on the Unifi Controller."""

    def __init__(self, connection_manager: ConnectionManager):
        """Initialize the System Manager.

        Args:
            connection_manager: The shared ConnectionManager instance.
        """
        self._connection = connection_manager

    def _get_cache_key(self, prefix: str) -> str:
        """Generate a cache key with the given prefix and site."""
        return f"{prefix}_{self._connection.site}"

    async def _ensure_connected(self) -> bool:
        """Ensure we have a valid connection to the controller."""
        return await self._connection.ensure_connected()

    async def get_system_info(self) -> Dict[str, Any]:
        """Get system information including version, uptime, etc."""
        cache_key = self._get_cache_key(CACHE_PREFIX_SYSINFO)
        cached_data = self._connection.get_cached(cache_key, timeout=15)
        if cached_data is not None:
            return cached_data

        try:
            api_request = ApiRequest(method="get", path="/stat/sysinfo")
            response = await self._connection.request(api_request)

            # Enhanced logging to debug empty responses
            logger.info(
                "System info endpoint response type: %s, keys: %s",
                type(response).__name__,
                list(response.keys()) if isinstance(response, dict) else "N/A"
            )

            info = response if isinstance(response, dict) else {}

            # Add controller metadata for debugging
            controller_metadata = {
                "_controller_type": (
                    "UniFi OS (proxy)" if getattr(self._connection, "_unifi_os_override", None)
                    else "Standard (direct)" if self._connection._unifi_os_override is False
                    else "Unknown/Auto-detecting"
                ),
                "_controller_url": self._connection.url_base,
            }

            # If empty, try alternative endpoint for controller status
            if not info:
                logger.warning(
                    "/stat/sysinfo returned empty/non-dict. Trying /stat/status fallback."
                )
                try:
                    status_request = ApiRequest(method="get", path="/stat/status")
                    status_response = await self._connection.request(status_request)
                    if isinstance(status_response, dict) and status_response:
                        logger.info("Using /stat/status as fallback for system info")
                        info = {
                            "_source": "status_fallback",
                            "_note": (
                                "/stat/sysinfo was empty - this is common on UniFi OS controllers. "
                                "Using /stat/status instead."
                            ),
                            **controller_metadata,
                            **status_response
                        }
                    else:
                        # Both endpoints failed/empty
                        info = {
                            "_source": "no_data",
                            "_note": (
                                "Both /stat/sysinfo and /stat/status returned empty. "
                                "This may indicate: (1) UniFi OS controller requiring different endpoints, "
                                "(2) Insufficient permissions, or (3) Older controller version."
                            ),
                            **controller_metadata
                        }
                except Exception as status_error:
                    logger.debug("Status fallback also failed: %s", status_error)
                    info = {
                        "_source": "error",
                        "_note": f"/stat/sysinfo empty, /stat/status error: {status_error}",
                        **controller_metadata
                    }
            else:
                # Merge controller metadata into existing info
                info.update(controller_metadata)

            self._connection.update_cache(cache_key, info, timeout=15)
            return info
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Error getting system info: %s", e)
            return {}

    async def get_controller_status(self) -> Dict[str, Any]:
        """Get status information about the controller."""
        try:
            api_request = ApiRequest(method="get", path="/stat/status")
            response = await self._connection.request(api_request)
            return response if isinstance(response, dict) else {}
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Error getting controller status: %s", e)
            return {}

    async def create_backup(self, filename: Optional[str] = None) -> Optional[bytes]:
        """Create a backup of the controller configuration.

        Args:
            filename: Optional filename for the backup (currently unused by API call)

        Returns:
            Backup data as bytes if successful, None otherwise
        """
        try:
            api_request = ApiRequest(
                method="post",
                path="/cmd/backup",
                data={"cmd": "backup"}
            )
            response = await self._connection.request(api_request, return_raw=True)
            logger.info("Backup creation requested successfully.")
            return response if isinstance(response, bytes) else None
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Error creating backup: {e}")
            return None

    async def restore_backup(self, backup_data: bytes) -> bool:
        """Restore a controller configuration from backup.

        Args:
            backup_data: Backup data as bytes

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # This is a complex operation that requires file upload
            # For now, we'll return False and log that it's not implemented
            logger.warning("Backup restore functionality not implemented - requires file upload")
            return False
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Exception during backup restore: %s", e)
            return False

    async def check_firmware_updates(self) -> Dict[str, Any]:
        """Check for firmware updates for devices."""
        try:
            api_request = ApiRequest(
                method="get",
                path=f"/api/s/{self._connection.site}/stat/fwupdate/latest-version"
            )
            response = await self._connection.request(api_request)
            return response if isinstance(response, dict) else {}
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Error checking firmware updates: {e}")
            return {}

    async def upgrade_controller(self) -> bool:
        """Upgrade the controller to the latest version (requires confirmation)."""
        logger.warning("Initiating controller upgrade. This is a potentially disruptive operation.")
        try:
            api_request = ApiRequest(
                method="post",
                path="/cmd/system",
                data={"cmd": "upgrade"}
            )
            response = await self._connection.request(api_request)

            success = isinstance(response, dict) and response.get("meta", {}).get("rc") == "ok"
            if success:
                logger.info("Controller upgrade initiated successfully.")
                self._connection._initialized = False
            else:
                logger.error(f"Error initiating controller upgrade: {response}")

            return success
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Error upgrading controller: {e}")
            return False

    async def reboot_controller(self) -> bool:
        """Reboot the controller (requires confirmation)."""
        logger.warning("Initiating controller reboot. This is a potentially disruptive operation.")
        try:
            api_request = ApiRequest(
                method="post",
                path="/cmd/system",
                data={"cmd": "reboot"}
            )
            response = await self._connection.request(api_request)

            success = isinstance(response, dict) and response.get("meta", {}).get("rc") == "ok"
            if success:
                logger.info("Controller reboot initiated successfully.")
                self._connection._initialized = False
            else:
                logger.error(f"Error initiating controller reboot: {response}")

            return success
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Error rebooting controller: {e}")
            return False

    async def get_settings(self, section: str) -> List[Dict[str, Any]]: # API returns list
        """Get system settings for a specific section.

        Args:
            section: Settings section (e.g., "super", "guest_access", "mgmt")

        Returns:
            List containing the settings dictionary (usually just one element)
        """
        cache_key = self._get_cache_key(f"{CACHE_PREFIX_SETTINGS}_{section}")
        cached_data = self._connection.get_cached(cache_key)
        if cached_data is not None:
            return cached_data

        try:
            api_request = ApiRequest(method="get", path=f"/get/setting/{section}")
            response = await self._connection.request(api_request)
            settings_list = response if isinstance(response, list) else []
            self._connection.update_cache(cache_key, settings_list)
            return settings_list
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Error getting {section} settings: {e}")
            return []

    async def update_settings(self, section: str, settings_data: Dict[str, Any]) -> bool:
        """Update system settings for a specific section.

        Args:
            section: Settings section (e.g., "super", "guest_access", "mgmt")
            settings_data: Dictionary with updated settings (should include _id if modifying existing)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            current_settings_list = await self.get_settings(section)
            if not current_settings_list or not isinstance(current_settings_list[0], dict):
                logger.warning("Could not get current settings for section '%s' to update, proceeding without _id check.", section)
                settings_id = None
            else:
                settings_id = current_settings_list[0].get("_id")

            if "_id" not in settings_data and settings_id:
                settings_data["_id"] = settings_id
            elif "_id" not in settings_data:
                 logger.warning(f"Attempting to update settings section '{section}' without an _id. This might not work as expected.")

            if "key" not in settings_data:
                 settings_data["key"] = section

            endpoint = f"/set/setting/{section}"

            api_request = ApiRequest(
                method="put",
                path=endpoint,
                data=settings_data
            )
            response = await self._connection.request(api_request)

            self._connection.invalidate_cache(f"{CACHE_PREFIX_SETTINGS}_{section}_{self._connection.site}")

            success = isinstance(response, dict) and response.get("meta", {}).get("rc") == "ok"
            if not success and isinstance(response, list) and len(response) > 0:
                success = True

            if success:
                logger.info(f"{section} settings updated successfully")
            else:
                logger.error(f"Error updating {section} settings: {response}")

            return success
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Error updating {section} settings: {e}")
            return False

    async def get_network_health(self) -> Dict[str, Any]:
        """Return a summary of the controller network health.

        The official UniFi Network controller exposes a convenient endpoint that aggregates
        overall health information (WAN connectivity, number of devices, users, etc.) at
        `/stat/health`.  This helper wraps that call and caches the result for a short period
        because the data is fairly volatile but still expensive to compute for the controller.
        """

        cache_key = f"health_{self._connection.site}"
        cached_data = self._connection.get_cached(cache_key, timeout=10)
        if cached_data is not None:
            return cached_data

        try:
            api_request = ApiRequest(
                method="get",
                path="/stat/health",
            )
            response = await self._connection.request(api_request)

            if isinstance(response, dict):
                health = response
            elif isinstance(response, list) and response:
                health = {"items": response}
            else:
                health = {}

            self._connection.update_cache(cache_key, health, timeout=10)
            return health
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Error getting network health: {e}")
            return {}

    async def get_site_settings(self) -> Dict[str, Any]:
        """Retrieve general settings for the current site.

        This convenience wrapper consults the generic `get_settings` helper with the special
        section key "site" which – according to the Network Application API – returns the site‑
        level settings object.
        """

        try:
            settings_list = await self.get_settings("site")
            if settings_list and isinstance(settings_list[0], dict):
                return {
                    "raw": settings_list,
                    **settings_list[0],
                }
            return {"raw": settings_list}
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Error getting site settings: {e}")
            return {}

    async def get_sites(self) -> List[Site]: # Changed return type
        """Get a list of all sites in the controller."""
        cache_key = self._get_cache_key(CACHE_PREFIX_SITES)
        cached_data: Optional[List[Site]] = self._connection.get_cached(cache_key)
        if cached_data is not None:
            return cached_data

        try:
            api_request = ApiRequest(method="get", path="/api/self/sites")
            response = await self._connection.request(api_request)
            sites_data = response if isinstance(response, list) else []
            sites: List[Site] = [Site(raw_site) for raw_site in sites_data]
            self._connection.update_cache(cache_key, sites)
            return sites
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Error getting sites: {e}")
            return []

    async def get_site_details(self, site_identifier: str) -> Optional[Site]: # Changed return type
        """Get detailed information for a specific site by ID, name, or description.

        Args:
            site_identifier: ID (_id), name, or description (desc) of the site.

        Returns:
            Site object if found, None otherwise.
        """
        sites = await self.get_sites()
        site: Optional[Site] = next((
            s for s in sites if s.site_id == site_identifier # Use site_id property
            or s.name == site_identifier
            or s.description == site_identifier
        ), None)

        if not site:
            logger.warning(f"Site '{site_identifier}' not found.")
        return site

    async def get_current_site(self) -> Optional[Site]: # Changed return type
        """Get information about the currently configured site for the connection."""
        return await self.get_site_details(self._connection.site)

    async def create_site(self, name: str, description: Optional[str] = None) -> Optional[Site]: # Changed return type
        """Create a new site.

        Args:
            name: Name for the new site (will be formatted: lowercase, underscores).
            description: Optional description for the site.

        Returns:
            The created site data if successful, None otherwise.
        """
        try:
            formatted_name = name.lower().replace(' ', '_').replace('-', '_')
            site_desc = description or name

            sites = await self.get_sites()
            if any(s.name == formatted_name for s in sites):
                logger.error(f"Site with internal name '{formatted_name}' already exists")
                return None
            if any(s.description == site_desc for s in sites):
                logger.warning(f"Site with description '{site_desc}' already exists, but proceeding with unique internal name.")

            payload = {
                "cmd": "add-site",
                "name": formatted_name,
                "desc": site_desc
            }

            api_request = ApiRequest(
                method="post",
                path="/cmd/sitemgr",
                data=payload
            )
            response = await self._connection.request(api_request)

            self._connection.invalidate_cache(CACHE_PREFIX_SITES)

            if isinstance(response, dict) and response.get("meta", {}).get("rc") == "ok":
                logger.info(f"Site '{site_desc}' (internal: '{formatted_name}') created successfully.")
                await asyncio.sleep(1.5)
                new_site_details: Optional[Site] = await self.get_site_details(formatted_name)
                if not new_site_details:
                     logger.warning("Could not fetch details of newly created site immediately.")
                return new_site_details
            else:
                logger.error(f"Error creating site: {response}")
                return None
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Error creating site '{name}': {e}")
            return None

    async def update_site(self, site_id: str, description: str) -> bool:
        """Update a site's description.
        Note: Changing the internal 'name' of a site is usually not supported or advised.

        Args:
            site_id: _id of the site to update.
            description: New description for the site.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            site = await self.get_site_details(site_id)
            if not site:
                 logger.warning(f"Site '{site_id}' not found.")
                 return False
            site_internal_id = site.site_id
            if not site_internal_id:
                 logger.error(f"Site found for '{site_id}' but has no _id property.")
                 return False

            payload = {
                "cmd": "update-site",
                "site": site_internal_id,
                "desc": description
            }

            api_request = ApiRequest(
                method="post",
                path="/cmd/sitemgr",
                data=payload
            )
            response = await self._connection.request(api_request)

            self._connection.invalidate_cache(CACHE_PREFIX_SITES)

            success = isinstance(response, dict) and response.get("meta", {}).get("rc") == "ok"
            if success:
                logger.info(f"Site {site_id} description updated successfully.")
            else:
                logger.error(f"Error updating site {site_id}: {response}")

            return success
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Error updating site {site_id}: {e}")
            return False

    async def delete_site(self, site_id: str) -> bool:
        """Delete a site.

        Args:
            site_id: _id of the site to delete.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            site = await self.get_site_details(site_id)
            if not site:
                return False
            site_internal_id = site.site_id
            if not site_internal_id:
                 logger.error(f"Site found for '{site_id}' but has no _id property.")
                 return False

            # Don't allow deleting the default site
            if site.name == "default":
                logger.error("Cannot delete the default site.")
                return False

            payload = {
                "cmd": "delete-site",
                "site": site_internal_id  # API requires _id
            }

            api_request = ApiRequest(
                method="post",
                path="/cmd/sitemgr",
                data=payload
            )
            response = await self._connection.request(api_request)

            self._connection.invalidate_cache(CACHE_PREFIX_SITES)

            success = isinstance(response, dict) and response.get("meta", {}).get("rc") == "ok"
            if success:
                logger.info(f"Site {site_id} deleted successfully.")
                # If deleting the current site, switch back to default?
                if self._connection.site == site.name:
                    logger.warning(f"Deleted the current site '{self._connection.site}'. Consider switching to another site (e.g., default).")
                    # Optionally switch automatically: await self.switch_site("default")
            else:
                logger.error(f"Error deleting site {site_id}: {response}")

            return success
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Error deleting site {site_id}: {e}")
            return False

    async def switch_site(self, site_identifier: str) -> bool:
        """Switch the active site for the connection manager.

        Args:
            site_identifier: ID (_id), name, or description of the site to switch to.

        Returns:
            bool: True if site switch was successful, False otherwise.
        """
        try:
            site = await self.get_site_details(site_identifier)
            if not site:
                return False

            site_name = site.name
            if not site_name:
                logger.error(f"Site identified by '{site_identifier}' has no internal name, cannot switch.")
                return False

            await self._connection.set_site(site_name)
            return True
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Error switching to site '{site_identifier}': {e}")
            return False


    async def get_admin_users(self) -> List[Dict[str, Any]]:
        """Get a list of admin users for the controller."""
        cache_key = self._get_cache_key(CACHE_PREFIX_ADMINS)
        cached_data = self._connection.get_cached(cache_key)
        if cached_data is not None:
            return cached_data

        try:
            api_request = ApiRequest(method="get", path="/api/stat/admin")
            response = await self._connection.request(api_request)
            admins = response if isinstance(response, list) else []
            self._connection.update_cache(cache_key, admins)
            return admins
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Error getting admin users: {e}")
            return []

    async def get_admin_user_details(self, user_identifier: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific admin user by ID or name.

        Args:
            user_identifier: ID (_id) or name of the admin user.

        Returns:
            Admin user dictionary if found, None otherwise.
        """
        admin_users = await self.get_admin_users()
        user = next((u for u in admin_users if u.get("_id") == user_identifier or u.get("name") == user_identifier), None)
        if not user:
            logger.warning(f"Admin user '{user_identifier}' not found.")
        return user

    async def create_admin_user(
        self,
        name: str,
        password: str,
        email: Optional[str] = None,
        is_super: bool = False,
        site_access: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new admin user.

        Args:
            name: Username for the new admin.
            password: Password for the new admin.
            email: Optional email for the admin.
            is_super: Whether the user is a super admin.
            site_access: List of site _ids the user has access to (if not super admin).

        Returns:
            The created admin user data if successful, None otherwise.
        """
        try:
            admin_users = await self.get_admin_users()
            if any(u.get("name") == name for u in admin_users):
                logger.error(f"Admin user with name '{name}' already exists")
                return None

            payload = {
                "cmd": "create-admin",
                "name": name,
                "x_password": password,
                "email": email or "",
                "is_super": is_super
            }

            if not is_super and site_access is not None:
                payload["site_access"] = site_access
            elif not is_super:
                logger.warning(
                    "Creating non-super admin '%s' without site_access. "
                    "They may have no site access initially.", name
                )

            api_request = ApiRequest(
                method="post",
                path="/cmd/sitemgr",
                data=payload
            )
            response = await self._connection.request(api_request)

            self._connection.invalidate_cache(CACHE_PREFIX_ADMINS)

            if isinstance(response, dict) and response.get("meta", {}).get("rc") == "ok":
                logger.info(f"Admin user '{name}' created successfully.")
                self._connection.invalidate_cache(CACHE_PREFIX_ADMINS)
                created_user_data = None
                if "data" in response and isinstance(response["data"], list) and len(response["data"]) > 0:
                    created_user_data = response["data"][0]
                if created_user_data:
                     return created_user_data # Return the dict

                logger.warning("Admin user creation reported success, but could not extract details.")
                return {"success": True} # Return simple success dict
            else:
                logger.error(f"Error creating admin user '{name}': {response}")
                return None
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Error creating admin user '{name}': {e}")
            return None

    async def update_admin_user(
        self,
        user_id: str,
        name: Optional[str] = None,
        password: Optional[str] = None,
        email: Optional[str] = None,
        is_super: Optional[bool] = None,
        site_access: Optional[List[str]] = None
    ) -> bool:
        """Update an admin user.

        Args:
            user_id: _id of the admin user to update.
            name: New username.
            password: New password.
            email: New email.
            is_super: New super admin status.
            site_access: New list of site _ids the user has access to.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            user = await self.get_admin_user_details(user_id)
            if not user:
                return False
            admin_internal_id = user.get("_id")
            if not admin_internal_id:
                logger.error(f"Admin user found for '{user_id}' but has no _id.")
                return False

            payload = {"cmd": "update-admin", "admin_id": admin_internal_id}
            if name is not None:
                if name != user.get("name"):
                    admins = await self.get_admin_users()
                    if any(u.get("name") == name and u.get("_id") != admin_internal_id for u in admins):
                         logger.error(f"Cannot rename admin: Username '{name}' already exists.")
                         return False
                payload["name"] = name
            if password is not None:
                payload["x_password"] = password
            if email is not None:
                payload["email"] = email
            if is_super is not None:
                payload["is_super"] = is_super
            if site_access is not None:
                current_is_super = user.get("is_super", False) if is_super is None else is_super
                if not current_is_super:
                    payload["site_access"] = site_access
                else:
                    logger.info("Ignoring site_access update for super admin.")

            if len(payload) <= 2: # Only cmd and admin_id
                logger.warning(f"No fields provided to update for admin user {user_id}")
                return False

            api_request = ApiRequest(
                method="post",
                path="/cmd/sitemgr",
                data=payload
            )
            response = await self._connection.request(api_request)

            self._connection.invalidate_cache(CACHE_PREFIX_ADMINS)

            success = isinstance(response, dict) and response.get("meta", {}).get("rc") == "ok"
            if success:
                logger.info("Admin user %s updated successfully.", user_id)
                self._connection.invalidate_cache(CACHE_PREFIX_ADMINS)
                return True
            else:
                logger.error(f"Error updating admin user {user_id}: {response}")
                return False
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Error updating admin user {user_id}: {e}")
            return False

    async def delete_admin_user(self, user_id: str) -> bool:
        """Delete an admin user.

        Args:
            user_id: _id of the admin user to delete.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            user = await self.get_admin_user_details(user_id)
            if not user:
                return False
            admin_internal_id = user.get("_id")
            if not admin_internal_id:
                 logger.error(f"Admin user found for '{user_id}' but has no _id.")
                 return False

            if user.get("name") == self._connection.username:
                logger.error("Cannot delete the currently configured admin user for this connection.")
                return False

            api_request = ApiRequest(
                method="delete",
                path=f"/api/stat/admin/{user_id}"
            )
            response = await self._connection.request(api_request)

            success = isinstance(response, dict) and response.get("meta", {}).get("rc") == "ok"
            if success:
                logger.info(f"Admin user {user_id} deleted successfully.")
                self._connection.invalidate_cache(CACHE_PREFIX_ADMINS)
                return True
            else:
                 logger.error(f"Error deleting admin user {user_id}: {response}")
                 return False
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error(f"Error deleting admin user {user_id}: {e}")
            return False

    async def invite_admin_user(self, email: str, is_super: bool = False, site_access: Optional[List[str]] = None) -> bool:
        """Send an invite to a new admin user.

        Args:
            email: Email address to send the invite to.
            is_super: Whether the invited user should be a super admin.
            site_access: List of site _ids the user will have access to.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            payload = {
                "cmd": "invite-admin",
                "email": email,
                "for_super": is_super,
            }
            if site_access:
                logger.warning("Site access payload structure for invite is assumed, verify API requirements.")

            api_request = ApiRequest(
                method="post",
                path="/cmd/sitemgr",
                data=payload
            )
            response = await self._connection.request(api_request)

            success = isinstance(response, dict) and response.get("meta", {}).get("rc") == "ok"
            if success:
                logger.info("Admin invitation sent successfully to %s.", email)
                return True
            else:
                logger.error("Error sending admin invitation to %s: %s", email, response)
                return False
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
            logger.error("Error inviting admin user %s: %s", email, e)
            return False

    async def get_current_admin_user(self) -> Optional[Dict[str, Any]]:
        """Get information about the currently logged in admin user."""
        return await self.get_admin_user_details(self._connection.username)
