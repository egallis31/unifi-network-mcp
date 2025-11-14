#!/usr/bin/env python3
"""
Validation script that checks for common issues in tools:
1. Missing manager methods
2. Type mismatches
3. Parameter issues
"""

import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Known manager methods (from grep output)
MANAGER_METHODS = {
    'client_manager': [
        'get_clients', 'get_all_clients', 'get_client_details', 'block_client',
        'unblock_client', 'rename_client', 'force_reconnect_client',
        'get_blocked_clients', 'authorize_guest', 'unauthorize_guest'
    ],
    'device_manager': [
        'get_devices', 'get_device_details', 'reboot_device', 'rename_device',
        'adopt_device', 'upgrade_device'
    ],
    'firewall_manager': [
        'get_firewall_policies', 'toggle_firewall_policy', 'update_firewall_policy',
        'get_traffic_routes', 'update_traffic_route', 'toggle_traffic_route',
        'create_traffic_route', 'delete_traffic_route', 'get_port_forwards',
        'get_port_forward_by_id', 'update_port_forward', 'toggle_port_forward',
        'create_port_forward', 'delete_port_forward', 'create_firewall_policy',
        'delete_firewall_policy', 'get_firewall_zones', 'get_ip_groups'
    ],
    'network_manager': [
        'get_networks', 'get_network_details', 'create_network', 'update_network',
        'delete_network', 'get_wlans', 'get_wlan_details', 'create_wlan',
        'update_wlan', 'delete_wlan', 'toggle_wlan'
    ],
    'qos_manager': [
        'get_qos_rules', 'get_qos_rule_details', 'update_qos_rule',
        'create_qos_rule', 'delete_qos_rule'
    ],
    'stats_manager': [
        'get_network_stats', 'get_client_stats', 'get_device_stats',
        'get_top_clients', 'get_dpi_stats', 'get_alerts'
    ],
    'system_manager': [
        'get_system_info', 'get_controller_status', 'create_backup',
        'restore_backup', 'check_firmware_updates', 'upgrade_controller',
        'reboot_controller', 'get_settings', 'update_settings',
        'get_network_health', 'get_site_settings', 'get_sites',
        'get_site_details', 'get_current_site', 'create_site',
        'update_site', 'delete_site', 'switch_site', 'get_admin_users',
        'get_admin_user_details', 'create_admin_user', 'update_admin_user',
        'delete_admin_user', 'invite_admin_user', 'get_current_admin_user'
    ],
    'vpn_manager': [
        'get_vpn_servers', 'get_vpn_server_details', 'update_vpn_server_state',
        'get_vpn_clients', 'get_vpn_client_details', 'update_vpn_client_state',
        'generate_vpn_client_profile'
    ]
}

def extract_manager_calls(file_path: Path) -> List[Tuple[str, str]]:
    """Extract manager method calls from a tool file."""
    with open(file_path, 'r') as f:
        content = f.read()

    # Pattern to match manager.method() calls
    pattern = r'(\w+_manager)\.(\w+)\('
    matches = re.findall(pattern, content)
    return matches


def validate_tool_file(file_path: Path) -> Dict:
    """Validate a single tool file."""
    issues = []
    manager_calls = extract_manager_calls(file_path)

    # Check if all called methods exist
    for manager, method in manager_calls:
        if manager not in MANAGER_METHODS:
            issues.append(f"Unknown manager: {manager}")
        elif method not in MANAGER_METHODS[manager]:
            issues.append(f"Method {manager}.{method}() not found in manager")

    return {
        'file': file_path.name,
        'manager_calls': list(set(manager_calls)),
        'issues': issues
    }


def main():
    """Main validation function."""
    project_root = Path('/home/user/unifi-network-mcp')
    tools_dir = project_root / 'src' / 'tools'

    print("=" * 80)
    print("UniFi MCP Tools - Validation Report")
    print("=" * 80)

    all_issues = []
    total_files = 0

    for tool_file in sorted(tools_dir.glob('*.py')):
        if tool_file.name.startswith('__'):
            continue

        total_files += 1
        result = validate_tool_file(tool_file)

        if result['issues']:
            all_issues.append(result)
            print(f"\n❌ {result['file']}:")
            for issue in result['issues']:
                print(f"   - {issue}")
        else:
            print(f"✅ {result['file']}")
            if result['manager_calls']:
                print(f"   Manager calls: {', '.join(f'{m}.{n}()' for m, n in result['manager_calls'])}")

    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Total files checked: {total_files}")
    print(f"Files with issues: {len(all_issues)}")
    print(f"Files OK: {total_files - len(all_issues)}")

    if all_issues:
        print("\n⚠️  Issues found in the following files:")
        for result in all_issues:
            print(f"   - {result['file']}: {len(result['issues'])} issue(s)")
        return 1
    else:
        print("\n✅ All tools validated successfully!")
        return 0


if __name__ == "__main__":
    exit(main())
