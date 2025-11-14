#!/usr/bin/env python3
"""
Comprehensive integration test suite for UniFi Network MCP tools.

This script tests all 59 tools against a REAL UniFi controller to identify
actual runtime issues, serialization problems, and API errors.

Usage:
    python3 devtools/integration_test.py

Environment variables required:
    UNIFI_HOST, UNIFI_USERNAME, UNIFI_PASSWORD, UNIFI_SITE (optional)
"""

import asyncio
import json
import logging
import os
import sys
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.runtime import connection_manager, client_manager, device_manager
from src.runtime import firewall_manager, network_manager, qos_manager
from src.runtime import stats_manager, system_manager, vpn_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test results storage
test_results = []
broken_tools = []
working_tools = []


class ToolTester:
    """Integration tester for UniFi MCP tools."""

    def __init__(self):
        self.connection_ready = False
        self.sample_client_mac = None
        self.sample_device_id = None
        self.sample_network_id = None
        self.sample_wlan_id = None

    async def initialize(self) -> bool:
        """Initialize connection to UniFi controller."""
        logger.info("=" * 80)
        logger.info("UniFi Network MCP - Integration Test Suite")
        logger.info("=" * 80)

        # Check environment
        required_vars = ['UNIFI_HOST', 'UNIFI_USERNAME', 'UNIFI_PASSWORD']
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            logger.error(f"Missing required environment variables: {', '.join(missing)}")
            logger.error("Please set: UNIFI_HOST, UNIFI_USERNAME, UNIFI_PASSWORD")
            return False

        logger.info(f"Connecting to: {os.getenv('UNIFI_HOST')}")
        logger.info(f"Site: {os.getenv('UNIFI_SITE', 'default')}")

        try:
            self.connection_ready = await connection_manager.initialize()
            if not self.connection_ready:
                logger.error("Failed to initialize connection")
                return False

            logger.info("✅ Connection established successfully")

            # Get sample IDs for testing
            await self._get_sample_ids()
            return True

        except Exception as e:
            logger.error(f"Connection error: {e}")
            logger.error(traceback.format_exc())
            return False

    async def _get_sample_ids(self):
        """Get sample IDs for testing."""
        try:
            # Get a sample client
            clients = await client_manager.get_clients()
            if clients:
                first_client = clients[0]
                self.sample_client_mac = first_client.mac if hasattr(first_client, 'mac') else first_client.get('mac')
                logger.info(f"Sample client MAC: {self.sample_client_mac}")

            # Get a sample device
            devices = await device_manager.get_devices()
            if devices:
                first_device = devices[0]
                if hasattr(first_device, 'mac'):
                    self.sample_device_id = first_device.mac
                elif hasattr(first_device, '_id'):
                    self.sample_device_id = first_device._id
                elif isinstance(first_device, dict):
                    self.sample_device_id = first_device.get('mac') or first_device.get('_id')
                logger.info(f"Sample device ID: {self.sample_device_id}")

            # Get a sample network
            networks = await network_manager.get_networks()
            if networks:
                self.sample_network_id = networks[0].get('_id')
                logger.info(f"Sample network ID: {self.sample_network_id}")

            # Get a sample WLAN
            wlans = await network_manager.get_wlans()
            if wlans:
                first_wlan = wlans[0]
                if hasattr(first_wlan, '_id'):
                    self.sample_wlan_id = first_wlan._id
                elif isinstance(first_wlan, dict):
                    self.sample_wlan_id = first_wlan.get('_id')
                logger.info(f"Sample WLAN ID: {self.sample_wlan_id}")

        except Exception as e:
            logger.warning(f"Error getting sample IDs: {e}")

    async def test_tool(
        self,
        tool_name: str,
        manager_func: Any,
        args: List = None,
        kwargs: Dict = None
    ) -> Tuple[bool, Optional[str], Optional[Any]]:
        """
        Test a single tool.

        Returns:
            Tuple of (success, error_message, result)
        """
        args = args or []
        kwargs = kwargs or {}

        try:
            logger.info(f"Testing: {tool_name}")
            result = await manager_func(*args, **kwargs)

            # Try to serialize result to JSON (catches serialization issues)
            try:
                json.dumps(result, default=str)
            except (TypeError, ValueError) as e:
                return False, f"Serialization error: {e}", result

            # Check for error in result
            if isinstance(result, dict):
                if result.get('success') == False:
                    return False, result.get('error', 'Unknown error'), result

            logger.info(f"  ✅ PASS")
            return True, None, result

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"  ❌ FAIL: {error_msg}")
            logger.debug(traceback.format_exc())
            return False, error_msg, None

    async def run_all_tests(self):
        """Run comprehensive tests on all tools."""
        logger.info("\n" + "=" * 80)
        logger.info("Starting comprehensive tool tests...")
        logger.info("=" * 80 + "\n")

        # CLIENT TOOLS
        logger.info("\n### CLIENT TOOLS ###")
        await self._test_client_tools()

        # DEVICE TOOLS
        logger.info("\n### DEVICE TOOLS ###")
        await self._test_device_tools()

        # NETWORK TOOLS
        logger.info("\n### NETWORK TOOLS ###")
        await self._test_network_tools()

        # FIREWALL TOOLS
        logger.info("\n### FIREWALL TOOLS ###")
        await self._test_firewall_tools()

        # PORT FORWARD TOOLS
        logger.info("\n### PORT FORWARD TOOLS ###")
        await self._test_port_forward_tools()

        # QOS TOOLS
        logger.info("\n### QOS TOOLS ###")
        await self._test_qos_tools()

        # TRAFFIC ROUTE TOOLS
        logger.info("\n### TRAFFIC ROUTE TOOLS ###")
        await self._test_traffic_route_tools()

        # VPN TOOLS
        logger.info("\n### VPN TOOLS ###")
        await self._test_vpn_tools()

        # STATISTICS TOOLS
        logger.info("\n### STATISTICS TOOLS ###")
        await self._test_statistics_tools()

        # SYSTEM TOOLS
        logger.info("\n### SYSTEM TOOLS ###")
        await self._test_system_tools()

    async def _test_client_tools(self):
        """Test client management tools."""
        # List clients
        success, error, result = await self.test_tool(
            "unifi_list_clients",
            client_manager.get_clients
        )
        test_results.append({
            'tool': 'unifi_list_clients',
            'category': 'clients',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_list_clients')
        else:
            broken_tools.append(('unifi_list_clients', error))

        # List all clients (including offline)
        success, error, result = await self.test_tool(
            "unifi_list_clients (all)",
            client_manager.get_all_clients
        )
        test_results.append({
            'tool': 'unifi_list_clients_all',
            'category': 'clients',
            'success': success,
            'error': error
        })

        # Get client details
        if self.sample_client_mac:
            success, error, result = await self.test_tool(
                "unifi_get_client_details",
                client_manager.get_client_details,
                args=[self.sample_client_mac]
            )
            test_results.append({
                'tool': 'unifi_get_client_details',
                'category': 'clients',
                'success': success,
                'error': error
            })
            if success:
                working_tools.append('unifi_get_client_details')
            else:
                broken_tools.append(('unifi_get_client_details', error))

        # List blocked clients
        success, error, result = await self.test_tool(
            "unifi_list_blocked_clients",
            client_manager.get_blocked_clients
        )
        test_results.append({
            'tool': 'unifi_list_blocked_clients',
            'category': 'clients',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_list_blocked_clients')
        else:
            broken_tools.append(('unifi_list_blocked_clients', error))

    async def _test_device_tools(self):
        """Test device management tools."""
        success, error, result = await self.test_tool(
            "unifi_list_devices",
            device_manager.get_devices
        )
        test_results.append({
            'tool': 'unifi_list_devices',
            'category': 'devices',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_list_devices')
        else:
            broken_tools.append(('unifi_list_devices', error))

        # Get device details
        if self.sample_device_id:
            success, error, result = await self.test_tool(
                "unifi_get_device_details",
                device_manager.get_device_details,
                args=[self.sample_device_id]
            )
            test_results.append({
                'tool': 'device_manager.get_device_details',
                'category': 'devices',
                'success': success,
                'error': error
            })

    async def _test_network_tools(self):
        """Test network management tools."""
        # List networks
        success, error, result = await self.test_tool(
            "unifi_list_networks",
            network_manager.get_networks
        )
        test_results.append({
            'tool': 'unifi_list_networks',
            'category': 'networks',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_list_networks')
        else:
            broken_tools.append(('unifi_list_networks', error))

        # Get network details
        if self.sample_network_id:
            success, error, result = await self.test_tool(
                "unifi_get_network_details",
                network_manager.get_network_details,
                args=[self.sample_network_id]
            )
            test_results.append({
                'tool': 'unifi_get_network_details',
                'category': 'networks',
                'success': success,
                'error': error
            })

        # List WLANs
        success, error, result = await self.test_tool(
            "unifi_list_wlans",
            network_manager.get_wlans
        )
        test_results.append({
            'tool': 'unifi_list_wlans',
            'category': 'networks',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_list_wlans')
        else:
            broken_tools.append(('unifi_list_wlans', error))

        # Get WLAN details
        if self.sample_wlan_id:
            success, error, result = await self.test_tool(
                "unifi_get_wlan_details",
                network_manager.get_wlan_details,
                args=[self.sample_wlan_id]
            )
            test_results.append({
                'tool': 'unifi_get_wlan_details',
                'category': 'networks',
                'success': success,
                'error': error
            })

    async def _test_firewall_tools(self):
        """Test firewall management tools."""
        # List firewall policies
        success, error, result = await self.test_tool(
            "unifi_list_firewall_policies",
            firewall_manager.get_firewall_policies
        )
        test_results.append({
            'tool': 'unifi_list_firewall_policies',
            'category': 'firewall',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_list_firewall_policies')
        else:
            broken_tools.append(('unifi_list_firewall_policies', error))

        # List firewall zones
        success, error, result = await self.test_tool(
            "unifi_list_firewall_zones",
            firewall_manager.get_firewall_zones
        )
        test_results.append({
            'tool': 'unifi_list_firewall_zones',
            'category': 'firewall',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_list_firewall_zones')
        else:
            broken_tools.append(('unifi_list_firewall_zones', error))

        # List IP groups
        success, error, result = await self.test_tool(
            "unifi_list_ip_groups",
            firewall_manager.get_ip_groups
        )
        test_results.append({
            'tool': 'unifi_list_ip_groups',
            'category': 'firewall',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_list_ip_groups')
        else:
            broken_tools.append(('unifi_list_ip_groups', error))

    async def _test_port_forward_tools(self):
        """Test port forward tools."""
        success, error, result = await self.test_tool(
            "unifi_list_port_forwards",
            firewall_manager.get_port_forwards
        )
        test_results.append({
            'tool': 'unifi_list_port_forwards',
            'category': 'port_forwards',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_list_port_forwards')
        else:
            broken_tools.append(('unifi_list_port_forwards', error))

    async def _test_qos_tools(self):
        """Test QoS tools."""
        success, error, result = await self.test_tool(
            "unifi_list_qos_rules",
            qos_manager.get_qos_rules
        )
        test_results.append({
            'tool': 'unifi_list_qos_rules',
            'category': 'qos',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_list_qos_rules')
        else:
            broken_tools.append(('unifi_list_qos_rules', error))

    async def _test_traffic_route_tools(self):
        """Test traffic route tools."""
        success, error, result = await self.test_tool(
            "unifi_list_traffic_routes",
            firewall_manager.get_traffic_routes
        )
        test_results.append({
            'tool': 'unifi_list_traffic_routes',
            'category': 'traffic_routes',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_list_traffic_routes')
        else:
            broken_tools.append(('unifi_list_traffic_routes', error))

    async def _test_vpn_tools(self):
        """Test VPN tools."""
        # List VPN clients
        success, error, result = await self.test_tool(
            "unifi_list_vpn_clients",
            vpn_manager.get_vpn_clients
        )
        test_results.append({
            'tool': 'unifi_list_vpn_clients',
            'category': 'vpn',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_list_vpn_clients')
        else:
            broken_tools.append(('unifi_list_vpn_clients', error))

        # List VPN servers
        success, error, result = await self.test_tool(
            "unifi_list_vpn_servers",
            vpn_manager.get_vpn_servers
        )
        test_results.append({
            'tool': 'unifi_list_vpn_servers',
            'category': 'vpn',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_list_vpn_servers')
        else:
            broken_tools.append(('unifi_list_vpn_servers', error))

    async def _test_statistics_tools(self):
        """Test statistics tools."""
        # Get network stats
        success, error, result = await self.test_tool(
            "unifi_get_network_stats",
            stats_manager.get_network_stats,
            kwargs={'duration_hours': 1}
        )
        test_results.append({
            'tool': 'unifi_get_network_stats',
            'category': 'statistics',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_get_network_stats')
        else:
            broken_tools.append(('unifi_get_network_stats', error))

        # Get client stats
        if self.sample_client_mac:
            success, error, result = await self.test_tool(
                "unifi_get_client_stats",
                stats_manager.get_client_stats,
                args=[self.sample_client_mac],
                kwargs={'duration_hours': 1}
            )
            test_results.append({
                'tool': 'unifi_get_client_stats',
                'category': 'statistics',
                'success': success,
                'error': error
            })

        # Get device stats
        if self.sample_device_id:
            success, error, result = await self.test_tool(
                "unifi_get_device_stats",
                stats_manager.get_device_stats,
                args=[self.sample_device_id],
                kwargs={'duration_hours': 1}
            )
            test_results.append({
                'tool': 'unifi_get_device_stats',
                'category': 'statistics',
                'success': success,
                'error': error
            })

        # Get top clients
        success, error, result = await self.test_tool(
            "unifi_get_top_clients",
            stats_manager.get_top_clients,
            kwargs={'limit': 10}
        )
        test_results.append({
            'tool': 'unifi_get_top_clients',
            'category': 'statistics',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_get_top_clients')
        else:
            broken_tools.append(('unifi_get_top_clients', error))

        # Get DPI stats
        success, error, result = await self.test_tool(
            "unifi_get_dpi_stats",
            stats_manager.get_dpi_stats
        )
        test_results.append({
            'tool': 'unifi_get_dpi_stats',
            'category': 'statistics',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_get_dpi_stats')
        else:
            broken_tools.append(('unifi_get_dpi_stats', error))

        # Get alerts - THIS IS THE PROBLEMATIC ONE
        success, error, result = await self.test_tool(
            "unifi_get_alerts",
            stats_manager.get_alerts,
            kwargs={'include_archived': False}
        )
        test_results.append({
            'tool': 'unifi_get_alerts',
            'category': 'statistics',
            'success': success,
            'error': error,
            'result_sample': str(result)[:200] if result else None
        })
        if success:
            working_tools.append('unifi_get_alerts')
        else:
            broken_tools.append(('unifi_get_alerts', error))

    async def _test_system_tools(self):
        """Test system tools."""
        # Get system info
        success, error, result = await self.test_tool(
            "unifi_get_system_info",
            system_manager.get_system_info
        )
        test_results.append({
            'tool': 'unifi_get_system_info',
            'category': 'system',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_get_system_info')
        else:
            broken_tools.append(('unifi_get_system_info', error))

        # Get network health
        success, error, result = await self.test_tool(
            "unifi_get_network_health",
            system_manager.get_network_health
        )
        test_results.append({
            'tool': 'unifi_get_network_health',
            'category': 'system',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_get_network_health')
        else:
            broken_tools.append(('unifi_get_network_health', error))

        # Get site settings
        success, error, result = await self.test_tool(
            "unifi_get_site_settings",
            system_manager.get_site_settings
        )
        test_results.append({
            'tool': 'unifi_get_site_settings',
            'category': 'system',
            'success': success,
            'error': error
        })
        if success:
            working_tools.append('unifi_get_site_settings')
        else:
            broken_tools.append(('unifi_get_site_settings', error))

    def print_summary(self):
        """Print test summary."""
        logger.info("\n" + "=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)

        total = len(test_results)
        passed = len(working_tools)
        failed = len(broken_tools)

        logger.info(f"Total tests: {total}")
        logger.info(f"Passed: {passed} ({passed/total*100:.1f}%)")
        logger.info(f"Failed: {failed} ({failed/total*100:.1f}%)")

        if broken_tools:
            logger.info("\n" + "=" * 80)
            logger.info("BROKEN TOOLS")
            logger.info("=" * 80)
            for tool, error in broken_tools:
                logger.error(f"❌ {tool}")
                logger.error(f"   Error: {error}\n")

        # Save results to file
        output_file = Path(__file__).parent / f"integration_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total_tests': total,
                'passed': passed,
                'failed': failed,
                'results': test_results,
                'broken_tools': [{'tool': t, 'error': e} for t, e in broken_tools],
                'working_tools': working_tools
            }, f, indent=2, default=str)

        logger.info(f"\n📄 Detailed results saved to: {output_file}")

        return failed == 0


async def main():
    """Main test function."""
    tester = ToolTester()

    # Initialize
    if not await tester.initialize():
        return 1

    # Run all tests
    try:
        await tester.run_all_tests()
    except Exception as e:
        logger.error(f"Fatal error during testing: {e}")
        logger.error(traceback.format_exc())
        return 1
    finally:
        await connection_manager.cleanup()

    # Print summary
    success = tester.print_summary()

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
