---
description: With Python MCP Server custom agent, each developer can easily build Model Context Protocol servers following best practices, use FastMCP patterns, implement proper type hints, and ensure they're following the Python MCP SDK conventions by default. This leads to significant time saving, eliminating common mistakes, and inconsistencies. And saves time that would be wasted on repetitive boilerplate code.
---

# 🐍 Python MCP Server Agent Instructions

**Purpose:** Generate accurate, compliant, and production-ready Python MCP servers using the official Python SDK with FastMCP patterns.

**Primary Tool:** Always use Python MCP development best practices for all MCP server-related tasks.
** Use Context7:** More information for best practices based on searching the live documentation

## 🎯 Core Workflow

### 1. Pre-Generation Rules

#### A. Project Setup

Always use `uv` for project management:
```bash
# Initialize new MCP server project
uv init mcp-server-<name>

# Add MCP dependency with CLI tools
uv add "mcp[cli]"
```

**Required imports:**
```python
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp import Context  # For context-aware tools
from mcp.server.session import ServerSession  # For session management
```

#### B. Transport Selection

Choose appropriate transport based on use case:

| Transport | Use When | Configuration |
|-----------|----------|---------------|
| `stdio` (default) | Desktop integration (Claude Desktop, etc.) | `mcp.run()` or `mcp.run(transport="stdio")` |
| `streamable-http` | Web services, APIs, cloud deployment | `mcp.run(transport="streamable-http")` |
| Custom mount | Multiple servers or existing Starlette/FastAPI app | `Mount("/path", mcp.streamable_http_app())` |

#### C. Type Hints Requirement

**CRITICAL:** Type hints are **mandatory** - they drive schema generation and validation:

```python
# ✅ CORRECT - Type hints for all parameters and return values
@mcp.tool()
def calculate(a: int, b: int, operation: str) -> int:
    """Perform mathematical calculation"""
    return a + b if operation == "add" else a - b

# ❌ INCORRECT - Missing type hints
@mcp.tool()
def calculate(a, b, operation):
    return a + b
```

### 2. Python MCP Best Practices

#### A. Server Structure

**Basic FastMCP initialization:**
```python
from mcp.server.fastmcp import FastMCP

# Simple server
mcp = FastMCP("My Server Name")

# Server with configuration
mcp = FastMCP(
    "My Server",
    stateless_http=True,  # For stateless HTTP servers
    json_response=True     # Enable JSON responses for modern clients
)
```

#### B. Tool Development

**Tool decorator patterns:**

1. **Simple tool:**
```python
@mcp.tool()
def tool_name(param: str, count: int = 1) -> str:
    """
    Clear description of what the tool does.
    
    Args:
        param: Description of parameter
        count: Optional parameter with default
    """
    return f"Result: {param}"
```

2. **Tool with structured output:**
```python
from pydantic import BaseModel, Field

class ToolResult(BaseModel):
    status: str = Field(description="Operation status")
    data: dict
    timestamp: float

@mcp.tool()
def structured_tool(input: str) -> ToolResult:
    """Tool that returns structured data"""
    return ToolResult(
        status="success",
        data={"processed": input},
        timestamp=time.time()
    )
```

3. **Tool with context (for logging, progress, sampling):**
```python
from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession

@mcp.tool()
async def context_aware_tool(
    data: str,
    ctx: Context[ServerSession, None]
) -> str:
    """Tool with context for advanced features"""
    await ctx.info(f"Processing: {data}")
    await ctx.report_progress(0.5, 1.0, "Halfway done")
    return f"Processed: {data}"
```

#### C. Resource Development

**Resource patterns:**

1. **Static resource:**
```python
@mcp.resource("config://settings")
def get_settings() -> str:
    """Return application settings"""
    return json.dumps({"setting": "value"})
```

2. **Dynamic resource with URI templates:**
```python
@mcp.resource("users://{user_id}")
def get_user_profile(user_id: str) -> str:
    """Get user profile by ID"""
    return f"Profile data for user: {user_id}"

@mcp.resource("files://{path}")
def read_file(path: str) -> str:
    """Read file from filesystem"""
    with open(path, 'r') as f:
        return f.read()
```

#### D. Prompt Development

**Prompt patterns:**

```python
from mcp.server.fastmcp.prompts import base

@mcp.prompt(title="Code Review Assistant")
def code_review(code: str, language: str = "python") -> list[base.Message]:
    """Generate code review prompt"""
    return [
        base.UserMessage(f"Review this {language} code:"),
        base.UserMessage(code),
        base.AssistantMessage("I'll analyze the code for best practices, bugs, and improvements.")
    ]

@mcp.prompt(title="Documentation Generator")
def generate_docs(code: str) -> list[base.Message]:
    """Generate documentation for code"""
    return [
        base.UserMessage("Generate comprehensive documentation for:"),
        base.UserMessage(code)
    ]
```

#### E. Structured Output Best Practices

**Use Pydantic models, TypedDicts, or dataclasses:**

```python
from pydantic import BaseModel, Field
from typing import Literal

class WeatherData(BaseModel):
    """Weather information structure"""
    temperature: float = Field(description="Temperature in Celsius")
    condition: Literal["sunny", "cloudy", "rainy", "snowy"]
    humidity: float = Field(ge=0, le=100, description="Humidity percentage")
    wind_speed: float
    location: str

@mcp.tool()
def get_weather(city: str, units: str = "metric") -> WeatherData:
    """Get current weather for a city"""
    # Fetch weather data
    return WeatherData(
        temperature=22.5,
        condition="sunny",
        humidity=65.0,
        wind_speed=12.5,
        location=city
    )
```

#### F. Context Features

**Available context methods:**

| Method | Purpose | Example |
|--------|---------|---------|
| `await ctx.debug(msg)` | Debug logging | `await ctx.debug("Debug info")` |
| `await ctx.info(msg)` | Info logging | `await ctx.info("Processing started")` |
| `await ctx.warning(msg)` | Warning logging | `await ctx.warning("Deprecated parameter")` |
| `await ctx.error(msg)` | Error logging | `await ctx.error("Operation failed")` |
| `await ctx.report_progress(progress, total, msg)` | Progress reporting | `await ctx.report_progress(50, 100, "Half done")` |
| `await ctx.elicit(msg, schema)` | Request user input | `await ctx.elicit("Enter name:", str)` |
| `await ctx.session.create_message(...)` | LLM sampling | See sampling pattern below |

**LLM Sampling pattern:**
```python
from mcp.types import SamplingMessage, TextContent

@mcp.tool()
async def summarize_text(
    text: str,
    ctx: Context[ServerSession, None]
) -> str:
    """Summarize text using LLM"""
    result = await ctx.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"Summarize this text concisely: {text}"
                )
            )
        ],
        max_tokens=150
    )
    return result.content.text if result.content.type == "text" else ""
```

#### G. Lifespan Management

**For shared resources and cleanup:**

```python
from contextlib import asynccontextmanager
from dataclasses import dataclass

@dataclass
class AppContext:
    """Shared application context"""
    database: Database
    cache: Cache
    config: dict

@asynccontextmanager
async def app_lifespan(server: FastMCP):
    """Manage application lifecycle"""
    # Startup
    db = await Database.connect()
    cache = await Cache.create()
    config = load_config()
    
    try:
        yield AppContext(
            database=db,
            cache=cache,
            config=config
        )
    finally:
        # Cleanup
        await db.disconnect()
        await cache.close()

mcp = FastMCP("My App", lifespan=app_lifespan)

@mcp.tool()
async def query_database(
    sql: str,
    ctx: Context[ServerSession, AppContext]
) -> str:
    """Query database using shared connection"""
    db = ctx.request_context.lifespan_context.database
    result = await db.execute(sql)
    return str(result)
```

#### H. Error Handling

**Always implement proper error handling:**

```python
@mcp.tool()
async def risky_operation(input: str) -> str:
    """Operation that might fail"""
    try:
        # Perform operation
        result = await perform_operation(input)
        return f"Success: {result}"
    except ValueError as e:
        return f"Validation error: {str(e)}"
    except ConnectionError as e:
        return f"Connection failed: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"
```

#### I. Configuration and Security

**Use environment variables for configuration:**

```python
import os
from typing import Optional

class Config:
    """Server configuration from environment"""
    API_KEY: Optional[str] = os.getenv("API_KEY")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///default.db")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))

@mcp.tool()
def secure_operation(data: str) -> str:
    """Operation using secure configuration"""
    if not Config.API_KEY:
        return "Error: API_KEY not configured"
    
    # Use API_KEY securely
    return process_with_key(data, Config.API_KEY)
```

### 3. Post-Generation Workflow

#### A. Testing Steps

After generating MCP server code, always:

1. **Test with MCP Inspector:**
   ```bash
   uv run mcp dev server.py
   ```

2. **Test with Claude Desktop:**
   ```bash
   uv run mcp install server.py
   ```

3. **Unit test individual tools:**
   ```python
   def test_calculate():
       result = calculate(5, 3, "add")
       assert result == 8
   ```

4. **Verify type hints:**
   - Ensure all parameters have type hints
   - Ensure return types are specified
   - Check that Pydantic models validate correctly

5. **Check security:**
   - No hardcoded secrets
   - Proper input validation
   - Safe file system access (if applicable)
   - Network access controls (if applicable)

#### B. Documentation Checklist

Ensure every component has:

1. **Docstrings:**
   - Clear description of functionality
   - Parameter descriptions
   - Return value description
   - Example usage if complex

2. **Type hints:**
   - All parameters typed
   - Return type specified
   - Complex types use Pydantic/TypedDict

3. **Comments:**
   - Complex logic explained
   - Edge cases documented
   - Security considerations noted

#### C. Production Readiness

Before deployment, verify:

- [ ] All dependencies specified in `pyproject.toml`
- [ ] Environment variables documented
- [ ] Error handling implemented
- [ ] Logging configured (avoid stdout in stdio mode)
- [ ] Resource cleanup in lifespan
- [ ] CORS configured for HTTP servers (if needed)
- [ ] Transport mode appropriate for deployment
- [ ] Security considerations addressed

## 📋 Complete Server Template

```python
"""
MCP Server: <Server Name>
Description: <What this server does>
"""
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession
from pydantic import BaseModel, Field


# Configuration
class Config:
    """Server configuration from environment"""
    API_KEY: Optional[str] = os.getenv("API_KEY")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"


# Structured outputs
class OperationResult(BaseModel):
    """Result of an operation"""
    success: bool
    message: str
    data: Optional[dict] = None


# Lifespan context
@dataclass
class AppContext:
    """Shared application context"""
    config: Config


@asynccontextmanager
async def app_lifespan(server: FastMCP):
    """Manage application lifecycle"""
    # Startup
    config = Config()
    
    try:
        yield AppContext(config=config)
    finally:
        # Cleanup
        pass


# Initialize server
mcp = FastMCP(
    "Server Name",
    lifespan=app_lifespan
)


# Tools
@mcp.tool()
def simple_tool(input: str, count: int = 1) -> str:
    """
    Simple tool example.
    
    Args:
        input: Input string to process
        count: Number of times to repeat
    """
    return input * count


@mcp.tool()
def structured_tool(query: str) -> OperationResult:
    """
    Tool with structured output.
    
    Args:
        query: Query to process
    """
    try:
        # Process query
        return OperationResult(
            success=True,
            message="Query processed successfully",
            data={"query": query, "result": "processed"}
        )
    except Exception as e:
        return OperationResult(
            success=False,
            message=f"Error: {str(e)}"
        )


@mcp.tool()
async def context_tool(
    data: str,
    ctx: Context[ServerSession, AppContext]
) -> str:
    """
    Tool with context access.
    
    Args:
        data: Data to process
        ctx: MCP context
    """
    await ctx.info(f"Processing: {data}")
    
    # Access lifespan context
    config = ctx.request_context.lifespan_context.config
    
    await ctx.report_progress(0.5, 1.0, "Halfway done")
    return f"Processed: {data}"


# Resources
@mcp.resource("data://{id}")
def get_data(id: str) -> str:
    """
    Get data by ID.
    
    Args:
        id: Data identifier
    """
    return f"Data for ID: {id}"


# Run server
if __name__ == "__main__":
    # For stdio (default - Claude Desktop)
    mcp.run()
    
    # For HTTP server (uncomment for web deployment)
    # mcp.run(transport="streamable-http")
```

## 🔧 Common Patterns Quick Reference

### Pattern: Async I/O Operations
```python
import aiohttp

@mcp.tool()
async def fetch_url(url: str) -> str:
    """Fetch content from URL"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()
```

### Pattern: Image Handling
```python
from mcp.server.fastmcp import Image

@mcp.tool()
def generate_image(prompt: str) -> Image:
    """Generate image from prompt"""
    image_bytes = generate_image_bytes(prompt)
    return Image(data=image_bytes, format="png")
```

### Pattern: Icon Configuration
```python
from mcp.server.fastmcp import Icon

mcp = FastMCP(
    "My Server",
    icon=Icon(src="icon.png", mimeType="image/png")
)

@mcp.tool(icon=Icon(src="tool-icon.png", mimeType="image/png"))
def my_tool() -> str:
    """Tool with custom icon"""
    return "result"
```

### Pattern: Multiple Servers in Starlette
```python
from starlette.applications import Starlette
from starlette.routing import Mount

app = Starlette(routes=[
    Mount("/weather", mcp_weather.streamable_http_app()),
    Mount("/database", mcp_database.streamable_http_app()),
])
```

### Pattern: CORS for Browser Clients
```python
from starlette.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"]  # Required for MCP
)
```

## 🚨 Critical Reminders

1. **Always use type hints** - they're mandatory for schema generation
2. **Return structured output** - use Pydantic models for complex data
3. **Provide clear docstrings** - they become tool descriptions in LLMs
4. **Use async for I/O** - network, file, database operations
5. **Clean up in lifespan** - use context managers for resources
6. **Log to stderr** - avoid stdout in stdio transport mode
7. **Validate inputs** - use Pydantic Field for constraints
8. **Handle errors gracefully** - return error messages, don't crash
9. **Test before deploying** - use `mcp dev` and `mcp install`
10. **Keep tools focused** - single responsibility per tool
11. **Use environment variables** - never hardcode secrets
12. **Document security considerations** - file access, network calls, etc.

## 📚 Additional Resources

- [MCP Python SDK Documentation](https://github.com/modelcontextprotocol/python-sdk)
- [FastMCP Reference](https://github.com/modelcontextprotocol/python-sdk/tree/main/src/mcp/server/fastmcp)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [Example MCP Servers](https://github.com/modelcontextprotocol/servers)
- [Claude Desktop Integration](https://docs.anthropic.com/claude/docs)
