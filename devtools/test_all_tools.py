#!/usr/bin/env python3
"""
Comprehensive test script for all UniFi Network MCP tools.

This script tests all 59 tools to identify which ones are broken.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Tuple
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.runtime import server, connection_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Track results
test_results: List[Dict[str, Any]] = []


async def test_tool(tool_name: str, args: Dict[str, Any] = None) -> Tuple[bool, str, Any]:
    """
    Test a single tool by calling it.

    Returns:
        Tuple of (success: bool, error_message: str, result: Any)
    """
    try:
        # Get the list of available tools
        tools = await server.list_tools()
        tool = next((t for t in tools if t.name == tool_name), None)

        if not tool:
            return False, f"Tool '{tool_name}' not registered", None

        # Call the tool
        if args is None:
            args = {}

        logger.info(f"Testing {tool_name} with args: {args}")
        result = await server.call_tool(tool_name, args)

        # Check if result indicates success
        if isinstance(result, dict):
            if result.get("success") == False:
                return False, result.get("error", "Unknown error"), result
            return True, "", result
        elif isinstance(result, list) and len(result) > 0:
            first = result[0]
            if hasattr(first, 'text'):
                try:
                    data = json.loads(first.text)
                    if data.get("success") == False:
                        return False, data.get("error", "Unknown error"), data
                    return True, "", data
                except json.JSONDecodeError:
                    return True, "", first.text

        return True, "", result

    except Exception as e:
        logger.error(f"Exception testing {tool_name}: {e}", exc_info=True)
        return False, str(e), None


async def run_all_tests():
    """Run tests for all 59 tools."""

    logger.info("=" * 80)
    logger.info("Starting comprehensive tool validation")
    logger.info("=" * 80)

    # Initialize connection
    logger.info("Initializing UniFi connection...")
    if not await connection_manager.initialize():
        logger.error("Failed to initialize connection. Tests cannot proceed.")
        return

    logger.info("Connection initialized successfully")

    # List all registered tools first
    tools = await server.list_tools()
    logger.info(f"Found {len(tools)} registered tools")
    for tool in tools:
        logger.info(f"  - {tool.name}")

    logger.info("\n" + "=" * 80)
    logger.info("Starting tool tests...")
    logger.info("=" * 80 + "\n")

    # Define all tools to test
    # Format: (tool_name, test_args, description)
    tools_to_test = [
        # CLIENT TOOLS (9)
        ("unifi_list_clients", {}, "List all clients"),
        ("unifi_list_clients", {"filter_type": "wireless"}, "List wireless clients"),
        ("unifi_list_clients", {"include_offline": True}, "List clients including offline"),
        ("unifi_get_client_details", {"mac_address": "00:00:00:00:00:00"}, "Get client details (fake MAC)"),
        ("unifi_list_blocked_clients", {}, "List blocked clients"),
        ("unifi_block_client", {"mac_address": "00:00:00:00:00:00", "confirm": False}, "Block client (no confirm)"),
        ("unifi_unblock_client", {"mac_address": "00:00:00:00:00:00", "confirm": False}, "Unblock client (no confirm)"),
        ("unifi_rename_client", {"mac_address": "00:00:00:00:00:00", "name": "Test", "confirm": False}, "Rename client (no confirm)"),
        ("unifi_force_reconnect_client", {"mac_address": "00:00:00:00:00:00", "confirm": False}, "Force reconnect client (no confirm)"),
        ("unifi_authorize_guest", {"mac_address": "00:00:00:00:00:00", "confirm": False}, "Authorize guest (no confirm)"),
        ("unifi_unauthorize_guest", {"mac_address": "00:00:00:00:00:00", "confirm": False}, "Unauthorize guest (no confirm)"),

        # DEVICE TOOLS (1)
        ("unifi_list_devices", {}, "List all devices"),
        ("unifi_list_devices", {"device_type": "ap"}, "List AP devices"),
        ("unifi_list_devices", {"include_details": True}, "List devices with details"),

        # FIREWALL TOOLS (8)
        ("unifi_list_firewall_policies", {}, "List firewall policies"),
        ("unifi_list_firewall_policies", {"include_predefined": True}, "List firewall policies including predefined"),
        ("unifi_get_firewall_policy_details", {"policy_id": "fake_id"}, "Get firewall policy details (fake ID)"),
        ("unifi_toggle_firewall_policy", {"policy_id": "fake_id", "confirm": False}, "Toggle firewall policy (no confirm)"),
        ("unifi_create_firewall_policy", {"policy_data": {"name": "test"}}, "Create firewall policy (incomplete data)"),
        ("unifi_update_firewall_policy", {"policy_id": "fake_id", "update_data": {}, "confirm": False}, "Update firewall policy (no confirm)"),
        ("unifi_create_simple_firewall_policy", {"policy": {"name": "test"}, "confirm": False}, "Create simple firewall policy (preview)"),
        ("unifi_list_firewall_zones", {}, "List firewall zones"),
        ("unifi_list_ip_groups", {}, "List IP groups"),

        # NETWORK TOOLS (9)
        ("unifi_list_networks", {}, "List networks"),
        ("unifi_get_network_details", {"network_id": "fake_id"}, "Get network details (fake ID)"),
        ("unifi_update_network", {"network_id": "fake_id", "update_data": {}, "confirm": False}, "Update network (no confirm)"),
        ("unifi_create_network", {"network_data": {"name": "test"}}, "Create network (incomplete data)"),
        ("unifi_list_wlans", {}, "List WLANs"),
        ("unifi_get_wlan_details", {"wlan_id": "fake_id"}, "Get WLAN details (fake ID)"),
        ("unifi_update_wlan", {"wlan_id": "fake_id", "update_data": {}, "confirm": False}, "Update WLAN (no confirm)"),
        ("unifi_create_wlan", {"wlan_data": {"name": "test"}}, "Create WLAN (incomplete data)"),

        # PORT FORWARD TOOLS (6)
        ("unifi_list_port_forwards", {}, "List port forwards"),
        ("unifi_get_port_forward", {"port_forward_id": "fake_id"}, "Get port forward (fake ID)"),
        ("unifi_toggle_port_forward", {"port_forward_id": "fake_id", "confirm": False}, "Toggle port forward (no confirm)"),
        ("unifi_create_port_forward", {"port_forward_data": {"name": "test"}}, "Create port forward (incomplete data)"),
        ("unifi_update_port_forward", {"port_forward_id": "fake_id", "update_data": {}, "confirm": False}, "Update port forward (no confirm)"),
        ("unifi_create_simple_port_forward", {"rule": {"name": "test"}, "confirm": False}, "Create simple port forward (preview)"),

        # QOS TOOLS (6)
        ("unifi_list_qos_rules", {}, "List QoS rules"),
        ("unifi_get_qos_rule_details", {"rule_id": "fake_id"}, "Get QoS rule details (fake ID)"),
        ("unifi_toggle_qos_rule_enabled", {"rule_id": "fake_id", "confirm": False}, "Toggle QoS rule (no confirm)"),
        ("unifi_create_qos_rule", {"qos_data": {"name": "test"}}, "Create QoS rule (incomplete data)"),
        ("unifi_update_qos_rule", {"rule_id": "fake_id", "update_data": {}, "confirm": False}, "Update QoS rule (no confirm)"),
        ("unifi_create_simple_qos_rule", {"rule": {"name": "test"}, "confirm": False}, "Create simple QoS rule (preview)"),

        # STATS TOOLS (6)
        ("unifi_get_network_stats", {}, "Get network stats"),
        ("unifi_get_network_stats", {"duration": "daily"}, "Get network stats (daily)"),
        ("unifi_get_client_stats", {"client_id": "fake_id"}, "Get client stats (fake ID)"),
        ("unifi_get_device_stats", {"device_id": "fake_id"}, "Get device stats (fake ID)"),
        ("unifi_get_top_clients", {}, "Get top clients"),
        ("unifi_get_dpi_stats", {}, "Get DPI stats"),
        ("unifi_get_alerts", {}, "Get alerts"),

        # SYSTEM TOOLS (3)
        ("unifi_get_system_info", {}, "Get system info"),
        ("unifi_get_network_health", {}, "Get network health"),
        ("unifi_get_site_settings", {}, "Get site settings"),

        # TRAFFIC ROUTE TOOLS (6)
        ("unifi_list_traffic_routes", {}, "List traffic routes"),
        ("unifi_get_traffic_route_details", {"route_id": "fake_id"}, "Get traffic route details (fake ID)"),
        ("unifi_toggle_traffic_route", {"route_id": "fake_id", "confirm": False}, "Toggle traffic route (no confirm)"),
        ("unifi_update_traffic_route", {"route_id": "fake_id", "update_data": {}, "confirm": False}, "Update traffic route (no confirm)"),
        ("unifi_create_traffic_route", {"route_data": {"name": "test"}}, "Create traffic route (incomplete data)"),
        ("unifi_create_simple_traffic_route", {"route": {"name": "test"}, "confirm": False}, "Create simple traffic route (preview)"),

        # VPN TOOLS (6)
        ("unifi_list_vpn_clients", {}, "List VPN clients"),
        ("unifi_get_vpn_client_details", {"client_id": "fake_id"}, "Get VPN client details (fake ID)"),
        ("unifi_update_vpn_client_state", {"client_id": "fake_id", "enabled": True}, "Update VPN client state"),
        ("unifi_list_vpn_servers", {}, "List VPN servers"),
        ("unifi_get_vpn_server_details", {"server_id": "fake_id"}, "Get VPN server details (fake ID)"),
        ("unifi_update_vpn_server_state", {"server_id": "fake_id", "enabled": True}, "Update VPN server state"),
    ]

    # Run tests
    passed = 0
    failed = 0

    for tool_name, args, description in tools_to_test:
        success, error, result = await test_tool(tool_name, args)

        status = "✓ PASS" if success else "✗ FAIL"
        test_results.append({
            "tool": tool_name,
            "description": description,
            "success": success,
            "error": error,
            "result": result
        })

        if success:
            passed += 1
            logger.info(f"{status} - {tool_name}: {description}")
        else:
            failed += 1
            logger.error(f"{status} - {tool_name}: {description}")
            logger.error(f"         Error: {error}")

    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total tests: {len(tools_to_test)}")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Success rate: {(passed/len(tools_to_test)*100):.1f}%")

    # List all failures
    if failed > 0:
        logger.info("\n" + "=" * 80)
        logger.info("FAILED TESTS")
        logger.info("=" * 80)
        for result in test_results:
            if not result["success"]:
                logger.info(f"\n{result['tool']} - {result['description']}")
                logger.info(f"  Error: {result['error']}")

    # Save detailed results to file
    output_file = "/home/user/unifi-network-mcp/devtools/test_results.json"
    with open(output_file, 'w') as f:
        json.dump(test_results, f, indent=2, default=str)
    logger.info(f"\nDetailed results saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
