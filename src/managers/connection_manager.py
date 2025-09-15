"""Connection manager for UniFi Network Controller."""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

import aiohttp
from aiounifi.controller import Controller
from aiounifi.errors import LoginRequired, RequestError, ResponseError
from aiounifi.models.api import ApiRequest, ApiRequestV2
from aiounifi.models.configuration import Configuration

logger = logging.getLogger("unifi-network-mcp")

class ConnectionManager:
    """Manages the connection and session with the Unifi Network Controller."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 443,
        site: str = "default",
        verify_ssl: bool = False,
        cache_timeout: int = 30,
        max_retries: int = 3,
        retry_delay: int = 5,
    ):
        """Initialize the Connection Manager."""
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.site = site
        self.verify_ssl = verify_ssl
        self.cache_timeout = cache_timeout
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self.controller: Optional[Controller] = None
        self._aiohttp_session: Optional[aiohttp.ClientSession] = None
        self._initialized = False
        self._connect_lock = asyncio.Lock()
        self._cache: Dict[str, Any] = {}
        self._last_cache_update: Dict[str, float] = {}

    @property
    def url_base(self) -> str:
        proto = "https"
        return f"{proto}://{self.host}:{self.port}"

    async def initialize(self) -> bool:
        """Initialize the controller connection (correct for attached aiounifi version)."""
        if self._initialized and self.controller and self._aiohttp_session and not self._aiohttp_session.closed:
            return True

        async with self._connect_lock:
            if (
                self._initialized
                and self.controller
                and self._aiohttp_session
                and not self._aiohttp_session.closed
            ):
                return True

            logger.info("Attempting to connect to Unifi controller at %s...", self.host)
            for attempt in range(self._max_retries):
                session_created = False
                try:
                    if self.controller:
                        self.controller = None
                    if self._aiohttp_session and not self._aiohttp_session.closed:
                        await self._aiohttp_session.close()
                        self._aiohttp_session = None

                    connector = aiohttp.TCPConnector(
                        ssl=False if not self.verify_ssl else True
                    )
                    self._aiohttp_session = aiohttp.ClientSession(
                        connector=connector,
                        cookie_jar=aiohttp.CookieJar(unsafe=True)
                    )
                    session_created = True

                    config = Configuration(
                        session=self._aiohttp_session,
                        host=self.host,
                        username=self.username,
                        password=self.password,
                        port=self.port,
                        site=self.site,
                    )

                    self.controller = Controller(config=config)

                    await self.controller.login()

                    self._initialized = True
                    logger.info("Successfully connected to Unifi controller at %s for site '%s'", self.host, self.site)
                    self._invalidate_cache()
                    return True

                except (
                    LoginRequired,
                    RequestError,
                    ResponseError,
                    asyncio.TimeoutError,
                    aiohttp.ClientError,
                ) as e:
                    logger.warning("Connection attempt %d failed: %s", attempt + 1, e)
                    if (
                        session_created
                        and self._aiohttp_session
                        and not self._aiohttp_session.closed
                    ):
                        await self._aiohttp_session.close()
                        self._aiohttp_session = None
                    self.controller = None
                    if attempt < self._max_retries - 1:
                        await asyncio.sleep(self._retry_delay)
                    else:
                        logger.error(
                            "Failed to initialize Unifi controller after %d attempts: %s",
                            self._max_retries,
                            e,
                        )
                        self._initialized = False
                        return False
                except (ValueError, TypeError, AttributeError, KeyError, OSError) as e:
                    logger.error(
                        "Unexpected error during controller initialization: %s",
                        e,
                        exc_info=True,
                    )
                    if (
                        session_created
                        and self._aiohttp_session
                        and not self._aiohttp_session.closed
                    ):
                        await self._aiohttp_session.close()
                        self._aiohttp_session = None
                    self._initialized = False
                    self.controller = None
                    return False
            return False

    async def ensure_connected(self) -> bool:
        """Ensure the controller is connected, attempting to reconnect if necessary.

        Returns:
            bool: True if connected successfully, False otherwise.
        """

        if (
            not self._initialized
            or not self.controller
            or not self._aiohttp_session
            or self._aiohttp_session.closed
        ):
            logger.warning(
                "Controller not initialized or session lost/closed, attempting to reconnect..."
            )
            return await self.initialize()

        try:
            internal_session = self.controller.connectivity.config.session
            if internal_session.closed:
                logger.warning(
                    "Controller session found closed (via connectivity.config.session), attempting to reconnect..."
                )
                return await self.initialize()
        except AttributeError:
            logger.debug(
                "connectivity.config.session attribute not found – skipping "
                "additional session check."
            )

        return True

    async def cleanup(self):
        """Clean up resources and close connections."""
        if self._aiohttp_session and not self._aiohttp_session.closed:
            await self._aiohttp_session.close()
            logger.info("aiohttp session closed.")
        self._initialized = False
        self.controller = None
        self._aiohttp_session = None
        self._cache = {}
        self._last_cache_update = {}
        logger.info("Unifi connection manager resources cleared.")

    async def request(
        self,
        api_request: ApiRequest | ApiRequestV2,
        return_raw: bool = False
    ) -> Any:
        """Make a request to the controller API, handling raw responses."""
        if not await self.ensure_connected() or not self.controller:
            raise ConnectionError("Unifi Controller is not connected.")

        try:
            # Diagnostics: capture timing and payloads without leaking secrets
            start_ts = time.perf_counter()
            # Use the standard request method for all requests
            response = await self.controller.request(api_request)
            duration_ms = (time.perf_counter() - start_ts) * 1000.0
            try:
                from src.utils.diagnostics import (
                                                  log_api_request,
                                                  diagnostics_enabled  # lazy import to avoid cycles
                                              )
                if diagnostics_enabled():
                    payload = getattr(api_request, "json", None) or getattr(api_request, "data", None)
                    log_api_request(api_request.method, api_request.path, payload, response, duration_ms, True)
            except (ImportError, AttributeError):
                pass
            return response if return_raw else response.get("data")

        except LoginRequired as exc:
            logger.warning("Login required detected during request, attempting re-login...")
            if await self.initialize():
                if not self.controller:
                    raise ConnectionError("Re-login failed, controller not available.") from exc
                logger.info("Re-login successful, retrying original request...")
                try:
                    start_ts = time.perf_counter()
                    # Use the standard request method for retry as well
                    retry_response = await self.controller.request(api_request)
                    duration_ms = (time.perf_counter() - start_ts) * 1000.0
                    try:
                        from src.utils.diagnostics import (
                                                          log_api_request,
                                                          diagnostics_enabled
                                                      )
                        if diagnostics_enabled():
                            payload = getattr(api_request, "json", None) or getattr(api_request, "data", None)
                            log_api_request(api_request.method, api_request.path, payload, retry_response, duration_ms, True)
                    except (ImportError, AttributeError):
                        pass
                    return retry_response if return_raw else retry_response.get("data")
                except (RequestError, ResponseError, aiohttp.ClientError) as retry_e:
                    logger.error(
                        "API request failed even after re-login: %s %s - %s",
                        api_request.method.upper(),
                        api_request.path,
                        retry_e,
                    )
                    raise retry_e from None
            else:
                raise ConnectionError("Re-login failed, cannot proceed with request.") from exc
        except (RequestError, ResponseError, aiohttp.ClientError) as e:
            logger.error(
                "API request error: %s %s - %s",
                api_request.method.upper(),
                api_request.path,
                e,
            )
            try:
                from src.utils.diagnostics import log_api_request, diagnostics_enabled
                if diagnostics_enabled():
                    payload = getattr(api_request, "json", None) or getattr(api_request, "data", None)
                    log_api_request(api_request.method, api_request.path, payload, {"error": str(e)}, 0.0, False)
            except (ImportError, AttributeError):
                pass
            raise
        except (ValueError, TypeError, AttributeError, KeyError, OSError) as e:
            logger.error(
                "Unexpected error during API request: %s %s - %s",
                api_request.method.upper(),
                api_request.path,
                e,
                exc_info=True,
            )
            try:
                from src.utils.diagnostics import log_api_request, diagnostics_enabled
                if diagnostics_enabled():
                    payload = getattr(api_request, "json", None) or getattr(api_request, "data", None)
                    log_api_request(api_request.method, api_request.path, payload, {"error": str(e)}, 0.0, False)
            except (ImportError, AttributeError):
                pass
            raise

    # --- Cache Management ---

    def _update_cache(self, key: str, data: Any, timeout: Optional[int] = None):
        """Update the cache with new data."""
        self._cache[key] = data
        self._last_cache_update[key] = time.time()
        logger.debug(
            "Cache updated for key '%s' with timeout %ss",
            key,
            timeout or self.cache_timeout,
        )

    def _is_cache_valid(self, key: str, timeout: Optional[int] = None) -> bool:
        """Check if the cache for a given key is still valid."""
        if key not in self._cache or key not in self._last_cache_update:
            return False

        effective_timeout = timeout if timeout is not None else self.cache_timeout
        current_time = time.time()
        last_update = self._last_cache_update[key]

        is_valid = (current_time - last_update) < effective_timeout
        logger.debug(
            "Cache check for key '%s': %s (Timeout: %ss)",
            key,
            "Valid" if is_valid else "Expired",
            effective_timeout,
        )
        return is_valid

    def get_cached(self, key: str, timeout: Optional[int] = None) -> Optional[Any]:
        """Get data from cache if valid."""
        if self._is_cache_valid(key, timeout):
            logger.debug("Cache hit for key '%s'", key)
            return self._cache[key]
        logger.debug("Cache miss for key '%s'", key)
        return None

    def _invalidate_cache(self, prefix: Optional[str] = None):
        """Invalidate cache entries, optionally by prefix."""
        if prefix:
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for key in keys_to_remove:
                del self._cache[key]
                if key in self._last_cache_update:
                    del self._last_cache_update[key]
            logger.debug("Invalidated cache for keys starting with '%s'", prefix)
        else:
            self._cache = {}
            self._last_cache_update = {}
            logger.debug("Invalidated entire cache")

    def update_cache(self, key: str, data: Any, timeout: Optional[int] = None):
        """Public method to update the cache with new data."""
        return self._update_cache(key, data, timeout)

    def invalidate_cache(self, prefix: Optional[str] = None):
        """Public method to invalidate cache entries, optionally by prefix."""
        return self._invalidate_cache(prefix)

    async def set_site(self, site: str):
        """Update the target site and invalidate relevant cache.

        Note: This attempts a dynamic switch. Full stability might require
        re-initializing the connection manager or restarting the server.
        """
        if self.controller and hasattr(self.controller.connectivity, 'config'):
            self.controller.connectivity.config.site = site
            self.site = site
            self._invalidate_cache()
            logger.info(
                "Switched target site to '%s'. Cache invalidated. "
                "Re-login might occur on next request.",
                site,
            )
        else:
            logger.warning(
                "Cannot set site dynamically, controller or config not available."
            )
