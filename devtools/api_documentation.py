#!/usr/bin/env python3
"""
Extract and document all UniFi Controller API endpoints used by the MCP server.
"""

import re
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict


def extract_api_endpoints(file_path: Path) -> List[Dict]:
    """Extract API endpoints from a manager file."""
    with open(file_path, 'r') as f:
        content = f.read()

    endpoints = []

    # Pattern 1: ApiRequest with path (V1 API)
    # ApiRequest(method="...", path="...")
    pattern1 = r'ApiRequest\(\s*method=["\'](\w+)["\'],\s*path=["\']([^"\']+)["\']'
    for match in re.finditer(pattern1, content, re.MULTILINE):
        method, path = match.groups()
        endpoints.append({
            'method': method.upper(),
            'path': path,
            'type': 'V1 API',
            'api_version': 'v1'
        })

    # Pattern 2: ApiRequestV2 with path (V2 API)
    # ApiRequestV2(method="...", path="...")
    pattern2 = r'ApiRequestV2\(\s*method=["\'](\w+)["\'],\s*path=["\']([^"\']+)["\']'
    for match in re.finditer(pattern2, content, re.MULTILINE):
        method, path = match.groups()
        endpoints.append({
            'method': method.upper(),
            'path': path,
            'type': 'V2 API',
            'api_version': 'v2'
        })

    return endpoints


def categorize_endpoints(endpoints: List[Dict]) -> Dict[str, List[Dict]]:
    """Categorize endpoints by their base path."""
    categories = defaultdict(list)

    for endpoint in endpoints:
        path = endpoint['path']
        # Extract category from path
        if path.startswith('/api/s/'):
            # Site-specific endpoint
            parts = path.split('/')
            if len(parts) >= 5:
                category = parts[4]  # e.g., /api/s/default/rest/... -> rest
            else:
                category = 'site'
        elif path.startswith('/rest/'):
            category = path.split('/')[2] if len(path.split('/')) > 2 else 'rest'
        elif path.startswith('/stat/'):
            category = 'statistics'
        elif path.startswith('/cmd/'):
            category = 'commands'
        elif path.startswith('/v2/api/'):
            category = 'v2_api'
        else:
            category = 'other'

        categories[category].append(endpoint)

    return dict(categories)


def main():
    """Main documentation function."""
    project_root = Path('/home/user/unifi-network-mcp')
    managers_dir = project_root / 'src' / 'managers'

    print("=" * 80)
    print("UniFi Controller API Endpoints Documentation")
    print("=" * 80)
    print()
    print("This document lists all UniFi Controller API endpoints")
    print("used by the UniFi Network MCP server.")
    print("=" * 80)

    all_endpoints = []
    manager_endpoints = {}

    # Extract from all manager files
    for manager_file in sorted(managers_dir.glob('*.py')):
        if manager_file.name.startswith('__'):
            continue

        endpoints = extract_api_endpoints(manager_file)
        if endpoints:
            manager_endpoints[manager_file.stem] = endpoints
            all_endpoints.extend(endpoints)

    # Print by manager
    print("\n## Endpoints by Manager\n")
    for manager_name, endpoints in sorted(manager_endpoints.items()):
        print(f"\n### {manager_name}\n")
        unique_endpoints = []
        seen = set()
        for e in endpoints:
            key = (e['method'], e['path'])
            if key not in seen:
                seen.add(key)
                unique_endpoints.append(e)

        for endpoint in sorted(unique_endpoints, key=lambda x: x['path']):
            api_ver = endpoint.get('api_version', 'v1')
            print(f"  {endpoint['method']:7} {endpoint['path']:40} [{api_ver.upper()}]")

    # Print by category
    print("\n" + "=" * 80)
    print("## Endpoints by Category\n")
    categories = categorize_endpoints(all_endpoints)

    for category, endpoints in sorted(categories.items()):
        print(f"\n### {category.upper()}\n")
        unique_endpoints = []
        seen = set()
        for e in endpoints:
            key = (e['method'], e['path'])
            if key not in seen:
                seen.add(key)
                unique_endpoints.append(e)

        for endpoint in sorted(unique_endpoints, key=lambda x: x['path']):
            api_ver = endpoint.get('api_version', 'v1')
            print(f"  {endpoint['method']:7} {endpoint['path']:40} [{api_ver.upper()}]")

    # Summary statistics
    print("\n" + "=" * 80)
    print("## Summary\n")
    unique_paths = set((e['method'], e['path']) for e in all_endpoints)
    print(f"Total unique API endpoints: {len(unique_paths)}")
    print(f"Total managers using APIs: {len(manager_endpoints)}")
    print(f"API categories: {len(categories)}")

    methods = defaultdict(int)
    for endpoint in all_endpoints:
        methods[endpoint['method']] += 1

    print(f"\nHTTP Methods:")
    for method, count in sorted(methods.items()):
        print(f"  {method}: {count}")

    # Save to markdown file
    output_file = project_root / 'devtools' / 'API_ENDPOINTS.md'
    with open(output_file, 'w') as f:
        f.write("# UniFi Controller API Endpoints\n\n")
        f.write("This document lists all UniFi Controller API endpoints used by the UniFi Network MCP server.\n\n")

        f.write("## Endpoints by Manager\n\n")
        for manager_name, endpoints in sorted(manager_endpoints.items()):
            f.write(f"\n### {manager_name}\n\n")
            unique_endpoints = []
            seen = set()
            for e in endpoints:
                key = (e['method'], e['path'])
                if key not in seen:
                    seen.add(key)
                    unique_endpoints.append(e)

            for endpoint in sorted(unique_endpoints, key=lambda x: x['path']):
                f.write(f"- `{endpoint['method']}` `{endpoint['path']}`\n")

        f.write("\n## Endpoints by Category\n\n")
        for category, endpoints in sorted(categories.items()):
            f.write(f"\n### {category.upper()}\n\n")
            unique_endpoints = []
            seen = set()
            for e in endpoints:
                key = (e['method'], e['path'])
                if key not in seen:
                    seen.add(key)
                    unique_endpoints.append(e)

            for endpoint in sorted(unique_endpoints, key=lambda x: x['path']):
                f.write(f"- `{endpoint['method']}` `{endpoint['path']}`\n")

        f.write("\n## Summary\n\n")
        f.write(f"- Total unique API endpoints: {len(unique_paths)}\n")
        f.write(f"- Total managers using APIs: {len(manager_endpoints)}\n")
        f.write(f"- API categories: {len(categories)}\n\n")
        f.write("### HTTP Methods\n\n")
        for method, count in sorted(methods.items()):
            f.write(f"- {method}: {count}\n")

    print(f"\n✅ Documentation saved to: {output_file}")


if __name__ == "__main__":
    main()
