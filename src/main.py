# ruff: noqa: E402
"""Main entry‑point for the UniFi‑Network MCP server.

Responsibilities:
• configure permissions wrappers
• initialise UniFi connection
• start FastMCP (stdio)
"""

import asyncio
import logging
import os
import sys
import traceback

from aiounifi.errors import RequestError, ResponseError
from src.bootstrap import logger  # ensures logging/env setup early

# Shared singletons
from src.runtime import (
    server,
    config,
    connection_manager,
)

from src.utils.tool_loader import auto_load_tools
from src.utils.diagnostics import diagnostics_enabled, wrap_tool
from src.utils.permissions import parse_permission  # noqa: E402

_original_tool_decorator = server.tool  # keep reference to wrap later

def is_mutating_tool(tool_name: str) -> bool:
    """Check if a tool performs mutating operations.
    
    Mutating tools include:
    - create_*, update_*, toggle_* operations
    - block, unblock, rename, force_reconnect operations
    - authorize, unauthorize operations
    - reboot, adopt, upgrade operations
    """
    if not tool_name:
        return False
    
    # Patterns for mutating operations
    mutating_prefixes = ("create_", "update_", "toggle_")
    mutating_operations = (
        "block_", "unblock_", "rename_", "force_reconnect_",
        "authorize_", "unauthorize_",
        "reboot_", "adopt_", "upgrade_"
    )
    
    # Check if tool name contains mutating patterns
    tool_lower = tool_name.lower()
    for prefix in mutating_prefixes:
        if prefix in tool_lower:
            return True
    for operation in mutating_operations:
        if operation in tool_lower:
            return True
    
    return False

def is_read_only_mode() -> bool:
    """Check if read-only mode is enabled in the configuration."""
    read_only_raw = config.server.get("read_only_mode", False)
    if isinstance(read_only_raw, str):
        return read_only_raw.strip().lower() in {"1", "true", "yes", "on"}
    return bool(read_only_raw)

def permissioned_tool(*d_args, **d_kwargs):  # acts like @server.tool
    """Decorator that only registers the tool if permission allows."""

    tool_name = (
        d_kwargs.get("name") if d_kwargs.get("name")
        else (d_args[0] if d_args else None)
    )

    category = d_kwargs.pop("permission_category", None)
    action = d_kwargs.pop("permission_action", None)

    def decorator(func):
        """Inner decorator actually registering the tool if allowed."""
        nonlocal category, action

        # Check read-only mode first - skip all mutating tools
        if is_read_only_mode() and is_mutating_tool(tool_name):
            logger.info(
                "[read-only mode] Skipping registration of mutating tool '%s'",
                tool_name
            )
            # Still return original function (unregistered) for import side-effects/testing
            return func

        # Fast path: no permissions requested, just register.
        if not category or not action:
            return _original_tool_decorator(*d_args, **d_kwargs)(func)

        try:
            allowed = parse_permission(config.permissions, category, action)
        except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as exc:  # mis‑config should not crash server
            logger.error("Permission check failed for tool %s: %s", tool_name, exc)
            allowed = False

        if allowed:
            # Wrap with diagnostics if enabled
            wrapped = (
                wrap_tool(func, tool_name or getattr(func, "__name__", "<tool>"))
                if diagnostics_enabled() else func
            )
            return _original_tool_decorator(*d_args, **d_kwargs)(wrapped)

        logger.info(
            "[permissions] Skipping registration of tool '%s' (category=%s, action=%s)",
            tool_name,
            category,
            action,
        )
        # Still return original function (unregistered) for import side-effects/testing
        return func

    return decorator

server.tool = permissioned_tool  # type: ignore

# Log server version and capabilities
try:
    import mcp
    logger.info("MCP Python SDK version: %s", getattr(mcp, '__version__', 'unknown'))
    logger.info("Server methods: %s", dir(server))
    logger.info("Server tool methods: %s", [m for m in dir(server) if 'tool' in m.lower()])
except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
    logger.error("Error inspecting server: %s", e)

# Config is loaded globally via bootstrap helper
logger.info("Loaded configuration globally.")

# Log read-only mode status
if is_read_only_mode():
    logger.warning(
        "⚠️  READ-ONLY MODE ENABLED - All mutating tools (create, update, toggle, etc.) "
        "will be disabled. Only read/list/get operations are available."
    )
else:
    logger.info("Read-only mode is disabled. All tools available based on permissions.")

# --- Global Connection and Managers ---
# ConnectionManager is instantiated globally by src.runtime import
logger.info("Using global ConnectionManager instance.")

# Other Managers are instantiated globally by src.runtime import
logger.info("Using global Manager instances.")

# Dynamic tool loader helper already imported above

async def main_async():
    """Main asynchronous function to setup and run the server."""

    # ---- VERY EARLY ASYNC LOG TEST ----
    try:
        logger.critical("ASYNCHRONOUS main_async() FUNCTION ENTERED - TEST MESSAGE")
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
        print(f"Logging in main_async() failed: {e}", file=sys.stderr)  # Fallback
    # ---- END VERY EARLY ASYNC LOG TEST ----

    # --- Add asyncio global exception handler ---
    loop = asyncio.get_event_loop()

    def handle_asyncio_exception(_loop, context):
        exc = context.get("exception", context["message"])
        log_message = "Global asyncio exception handler caught: %s"
        logger.error(log_message, exc)
        if 'future' in context and context['future']:
            logger.error("Future: %s", context['future'])
        if 'handle' in context and context['handle']:
            logger.error("Handle: %s", context['handle'])
        if context.get("exception"):
            orig_traceback = ''.join(traceback.format_exception(
                type(context["exception"]),
                context["exception"],
                context["exception"].__traceback__
            ))
            logger.error("Original traceback for global asyncio exception:\n%s", orig_traceback)

    loop.set_exception_handler(handle_asyncio_exception)
    logger.info("Global asyncio exception handler set.")
    # --- End asyncio global exception handler ---

    # Config is now loaded globally (from src.runtime -> src.bootstrap)
    log_level = config.server.get("log_level", "INFO").upper()
    # Ensure logging is configured (might be redundant if already set by bootstrap)
    # but this ensures the level is applied if changed post-bootstrap.
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO), force=True
    )  # Use default format
    logger.info("Log level set to %s in main_async.", log_level)

    # Initialize the global Unifi connection
    logger.info("Initializing global Unifi connection from main_async...")
    if not await connection_manager.initialize():
        logger.error(
            "Failed to connect to Unifi Controller from main_async. "
            "Tool functionality may be impaired."
        )
    else:
        logger.info("Global Unifi connection initialized successfully from main_async.")

    # Load tool modules after connection is established (or attempted)
    auto_load_tools()

    # List all registered tools for debugging
    try:
        tools = await server.list_tools()
        logger.info("Registered tools in main_async: %s", [tool.name for tool in tools])
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
        logger.error("Error listing tools in main_async: %s", e)

    # Run stdio always; optionally run HTTP transport based on config flag
    host = config.server.get("host", "0.0.0.0")
    port = int(config.server.get("port", 3000))
    http_cfg = config.server.get("http", {})
    http_enabled_raw = http_cfg.get("enabled", False)
    if isinstance(http_enabled_raw, str):
        http_enabled = http_enabled_raw.strip().lower() in {"1", "true", "yes", "on"}
    else:
        http_enabled = bool(http_enabled_raw)

    # Get transport type (http is now default/recommended, sse for backward compatibility)
    http_transport = http_cfg.get("transport", "http").lower()
    if http_transport not in {"http", "sse"}:
        logger.warning("Invalid HTTP transport '%s', defaulting to 'http'", http_transport)
        http_transport = "http"

    # Get optional path for HTTP transport
    http_path = http_cfg.get("path", "/mcp")

    # Only the main container process (PID 1) should bind the HTTP port.
    is_main_container_process = os.getpid() == 1
    if http_enabled and not is_main_container_process:
        logger.info(
            "HTTP transport enabled in config but skipped in exec session (PID %s != 1)",
            os.getpid()
        )
        http_enabled = False

    async def run_stdio():
        logger.info("Starting FastMCP stdio server ...")
        await server.run_stdio_async()

    tasks = [run_stdio()]
    if http_enabled:
        async def run_http_transport():
            try:
                if http_transport == "sse":
                    logger.info(
                        "Starting FastMCP HTTP SSE server on %s:%s (legacy mode) ...",
                        host, port
                    )
                    logger.warning(
                        "SSE transport is legacy - consider migrating to HTTP transport "
                        "for new deployments"
                    )
                    # MCP SDK >= 1.10 (pinned to 1.13.1): configure host/port via settings
                    server.settings.host = host
                    server.settings.port = port
                    await server.run_sse_async()
                    logger.info(
                        "HTTP SSE started via run_sse_async() using server.settings host/port."
                    )
                else:  # http_transport == "http"
                    logger.info(
                        "Starting FastMCP HTTP server on %s:%s%s (streamable HTTP) ...",
                        host, port, http_path
                    )
                    # Configure server settings for HTTP transport
                    server.settings.host = host
                    server.settings.port = port
                    await server.run_streamable_http_async()
                    logger.info(
                        "HTTP server started via run_streamable_http_async() "
                        "using streamable HTTP transport."
                    )
            except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as http_e:
                transport_name = "SSE" if http_transport == "sse" else "HTTP"
                logger.error("HTTP %s server failed to start: %s", transport_name, http_e)
                logger.error(traceback.format_exc())
        tasks.append(run_http_transport())

    try:
        await asyncio.gather(*tasks)
        logger.info("FastMCP servers exited.")
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
        logger.error("Error running FastMCP servers from main_async: %s", e)
        logger.error(traceback.format_exc())
        raise

def main():
    """Synchronous entry point."""
    # ---- VERY EARLY LOG TEST ----
    try:
        logger.critical("SYNCHRONOUS main() FUNCTION ENTERED - TEST MESSAGE")
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
        print(f"Logging in main() failed: {e}", file=sys.stderr)  # Fallback
    # ---- END VERY EARLY LOG TEST ----

    logger.debug("Starting main()")  # This uses the logger from bootstrap via global scope
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Server stopped by user (KeyboardInterrupt).")
    except (RequestError, ResponseError, ConnectionError, ValueError, TypeError) as e:
        logger.exception("Unhandled exception during server run (from asyncio.run): %s", e)
    finally:
        logger.info("Server process exiting.")

# Ensure other modules can `import src.main` even when this file is executed as __main__
# --- This block might not be strictly necessary depending on imports, but harmless ---
if "src.main" not in sys.modules:
    sys.modules["src.main"] = sys.modules[__name__]
# --- End potentially unnecessary block ---

if __name__ == "__main__":
    main()
