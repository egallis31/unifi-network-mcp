#!/bin/bash

# Post-create script for UniFi Network MCP devcontainer
# This script runs after the container is created and sets up the development environment

set -e

echo "🚀 Setting up UniFi Network MCP development environment..."

# Ensure we're in the workspace directory
cd /workspace

# Create virtual environment using uv
echo "📦 Creating virtual environment with uv..."
UV_VENV_CLEAR=1 uv venv

# Activate the virtual environment
echo "🔄 Activating virtual environment..."
source .venv/bin/activate

# Install the project in editable mode with dependencies
echo "📚 Installing project dependencies with uv..."
uv pip install -e .

# Install development dependencies
echo "🛠️ Installing development dependencies..."
uv pip install \
    pytest \
    pytest-asyncio \
    black \
    flake8 \
    mypy \
    isort \
    ipython 

# Copy example environment file if it doesn't exist
if [ -f ".env.example" ] && [ ! -f ".env" ]; then
    echo "📄 Creating .env file from example..."
    cp .env.example .env
    echo "⚠️ Don't forget to update the .env file with your UniFi credentials!"
fi

# Make scripts executable
chmod +x .devcontainer/post-create.sh 2>/dev/null || true

# Create cache directories
mkdir -p /tmp/uv-cache

echo "✅ Development environment setup complete!"
echo ""
echo "🎯 Quick start commands:"
echo "  • Activate venv: source .venv/bin/activate"
echo "  • Run tests: pytest"
echo "  • Format code: black src/"
echo "  • Lint code: flake8 src/"
echo "  • Type check: mypy src/"
echo "  • Start server: unifi-network-mcp"
echo "  • Dev console: python devtools/dev_console.py"
echo ""
echo "📖 Don't forget to:"
echo "  1. Update .env with your UniFi Controller credentials"
echo "  2. Review src/config/config.yaml for additional settings"
echo ""