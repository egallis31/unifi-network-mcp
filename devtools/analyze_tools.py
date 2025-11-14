#!/usr/bin/env python3
"""
Static analysis script to identify potential issues in UniFi MCP tools.
"""

import ast
import os
import sys
from typing import List, Dict, Any, Set
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class ToolAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.tools = []
        self.issues = []
        self.current_tool = None
        self.manager_calls = set()

    def visit_FunctionDef(self, node):
        # Check if this function has @server.tool decorator
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    if decorator.func.attr == 'tool':
                        # Found a tool
                        tool_name = None
                        for keyword in decorator.keywords:
                            if keyword.arg == 'name':
                                if isinstance(keyword.value, ast.Constant):
                                    tool_name = keyword.value.value

                        if tool_name:
                            self.current_tool = {
                                'name': tool_name,
                                'function': node.name,
                                'line': node.lineno,
                                'issues': []
                            }
                            self.tools.append(self.current_tool)

        self.generic_visit(node)
        self.current_tool = None

    def visit_Call(self, node):
        # Track manager method calls
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id.endswith('_manager'):
                    manager_name = node.func.value.id
                    method_name = node.func.attr
                    self.manager_calls.add((manager_name, method_name))

        self.generic_visit(node)


def analyze_tool_file(file_path: Path) -> Dict[str, Any]:
    """Analyze a single tool file."""
    with open(file_path, 'r') as f:
        source = f.read()

    try:
        tree = ast.parse(source)
        analyzer = ToolAnalyzer()
        analyzer.visit(tree)

        return {
            'file': str(file_path),
            'tools': analyzer.tools,
            'manager_calls': list(analyzer.manager_calls)
        }
    except SyntaxError as e:
        return {
            'file': str(file_path),
            'error': f"Syntax error: {e}"
        }


def check_manager_implementations():
    """Check if manager methods are implemented."""
    issues = []

    # Read manager files to see what methods exist
    manager_files = [
        'src/managers/client_manager.py',
        'src/managers/device_manager.py',
        'src/managers/firewall_manager.py',
        'src/managers/network_manager.py',
        'src/managers/qos_manager.py',
        'src/managers/stats_manager.py',
        'src/managers/system_manager.py',
        'src/managers/vpn_manager.py',
    ]

    project_root = Path('/home/user/unifi-network-mcp')

    for manager_file in manager_files:
        manager_path = project_root / manager_file
        if not manager_path.exists():
            continue

        with open(manager_path, 'r') as f:
            content = f.read()

        try:
            tree = ast.parse(content)

            # Find all method definitions in classes
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    manager_name = manager_file.split('/')[-1].replace('.py', '')

                    print(f"\n{manager_name}:")
                    print(f"  Methods: {', '.join(methods)}")

        except SyntaxError as e:
            issues.append(f"Syntax error in {manager_file}: {e}")

    return issues


def main():
    """Main analysis function."""
    project_root = Path('/home/user/unifi-network-mcp')
    tools_dir = project_root / 'src' / 'tools'

    print("=" * 80)
    print("UniFi MCP Tools - Static Analysis")
    print("=" * 80)

    all_tools = []
    all_manager_calls = set()

    # Analyze each tool file
    for tool_file in tools_dir.glob('*.py'):
        if tool_file.name.startswith('__'):
            continue

        print(f"\nAnalyzing {tool_file.name}...")
        result = analyze_tool_file(tool_file)

        if 'error' in result:
            print(f"  ERROR: {result['error']}")
            continue

        print(f"  Found {len(result['tools'])} tools:")
        for tool in result['tools']:
            print(f"    - {tool['name']} (line {tool['line']})")
            all_tools.append(tool)

        for manager_call in result['manager_calls']:
            all_manager_calls.add(manager_call)

    print("\n" + "=" * 80)
    print(f"Total tools found: {len(all_tools)}")
    print("=" * 80)

    # Print summary by category
    categories = {}
    for tool in all_tools:
        name = tool['name']
        # Extract category from tool name (e.g., unifi_list_clients -> clients)
        parts = name.split('_')
        if len(parts) >= 3:
            category = '_'.join(parts[2:-1]) if len(parts) > 3 else parts[-1]
            if category not in categories:
                categories[category] = []
            categories[category].append(name)

    print("\nTools by category:")
    for category, tools in sorted(categories.items()):
        print(f"\n{category.upper()} ({len(tools)} tools):")
        for tool in sorted(tools):
            print(f"  - {tool}")

    # Print manager method calls
    print("\n" + "=" * 80)
    print("Manager method calls:")
    print("=" * 80)
    for manager, method in sorted(all_manager_calls):
        print(f"  {manager}.{method}()")

    # Check manager implementations
    print("\n" + "=" * 80)
    print("Checking manager implementations...")
    print("=" * 80)
    issues = check_manager_implementations()

    if issues:
        print("\nIssues found:")
        for issue in issues:
            print(f"  - {issue}")


if __name__ == "__main__":
    main()
