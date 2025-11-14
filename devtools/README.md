# UniFi Network MCP - Development Tools

This directory contains comprehensive testing, validation, and documentation tools for the UniFi Network MCP server.

---

## 📋 Available Tools

### Testing & Validation

#### `integration_test.py` - Live Integration Testing ⭐
**Purpose:** Test all 59 MCP tools against a REAL UniFi controller

**Usage:**
```bash
# Set environment variables
export UNIFI_HOST="192.168.1.1"
export UNIFI_USERNAME="admin"
export UNIFI_PASSWORD="your_password"
export UNIFI_SITE="default"  # optional, defaults to "default"

# Run tests
python3 devtools/integration_test.py
```

**Output:**
- Console output with pass/fail for each tool
- JSON report saved to `integration_test_results_YYYYMMDD_HHMMSS.json`
- List of all broken tools with error messages

**What it Tests:**
- ✅ All 59 tools across 10 categories
- ✅ API connectivity
- ✅ Data serialization
- ✅ Error handling
- ✅ Response validation

---

#### `test_all_tools.py` - Mock Testing
**Purpose:** Test tools without a real controller (mock/dry-run mode)

**Usage:**
```bash
python3 devtools/test_all_tools.py
```

**Use Case:** Quick syntax and structure validation without controller access

---

#### `validate_tools.py` - Static Code Validation ✅
**Purpose:** Validate that all manager methods exist

**Usage:**
```bash
python3 devtools/validate_tools.py
```

**Output:**
```
================================================================================
UniFi MCP Tools - Validation Report
================================================================================
✅ clients.py
   Manager calls: client_manager.get_clients(), ...
✅ devices.py
   Manager calls: device_manager.get_devices()
...
================================================================================
Summary
================================================================================
Total files checked: 10
Files with issues: 0
Files OK: 10

✅ All tools validated successfully!
```

---

#### `analyze_tools.py` - AST Code Analysis
**Purpose:** Analyze tool structure using Python AST

**Usage:**
```bash
python3 devtools/analyze_tools.py
```

**Output:** Tool inventory, manager call analysis

---

### Documentation

#### `api_documentation.py` - API Endpoint Extractor
**Purpose:** Extract and document all UniFi API endpoints used

**Usage:**
```bash
python3 devtools/api_documentation.py
```

**Output:**
- Console output showing all endpoints
- Updates `API_ENDPOINTS.md` with latest endpoint list
- Shows V1 vs V2 API usage

---

## 📚 Documentation Files

### `API_ENDPOINTS.md` - Endpoint Listing
Complete list of all 27 UniFi API endpoints used by the MCP server.
- Organized by manager
- Organized by category
- Shows V1 vs V2 API
- HTTP method for each endpoint

### `API_REFERENCE.md` - Complete API Validation ⭐
**8,000+ word** comprehensive validation document:
- Every endpoint validated against official docs
- TypedDict schemas for all data structures
- V1 vs V2 API differences
- UDM Pro/UCG Max considerations
- 90% validation rate

### `FINDINGS.md` - Research Findings ⭐
**5,000+ word** research summary:
- Executive summary
- Validation results by category
- Known issues and uncertainties
- Production recommendations
- Integration testing roadmap

### `TESTING_SUMMARY.md` - Testing Overview
High-level summary of:
- Tool inventory (59 tools)
- Validation results
- Recent fixes applied
- Status and next steps

### `KNOWN_ISSUES.md` - Issue Tracker ⭐
Active tracking of known runtime issues:
- Critical issues (get_alerts, etc.)
- Medium priority issues
- Serialization problems
- Workarounds
- Fix priorities

---

## 🚀 Quick Start - Testing Your Installation

### Step 1: Static Validation (No Controller Needed)
```bash
# Verify all code is correct
python3 devtools/validate_tools.py

# Should show: "✅ All tools validated successfully!"
```

### Step 2: Integration Testing (Requires Controller)
```bash
# Set credentials
export UNIFI_HOST="192.168.1.1"
export UNIFI_USERNAME="admin"
export UNIFI_PASSWORD="password"

# Run comprehensive tests
python3 devtools/integration_test.py

# Check results
ls -lt integration_test_results_*.json | head -1
cat $(ls -t integration_test_results_*.json | head -1) | jq '.broken_tools'
```

### Step 3: Review Issues
```bash
# Read known issues
cat devtools/KNOWN_ISSUES.md

# If integration tests found broken tools, they'll be listed with errors
```

---

## 🔧 Common Testing Scenarios

### Scenario 1: "I want to verify everything works"
```bash
# Quick static check
python3 devtools/validate_tools.py

# If you have a controller, run integration tests
export UNIFI_HOST="192.168.1.1"
export UNIFI_USERNAME="admin"
export UNIFI_PASSWORD="password"
python3 devtools/integration_test.py
```

### Scenario 2: "I suspect tool X is broken"
```bash
# Run integration test and grep for that tool
python3 devtools/integration_test.py 2>&1 | grep -A3 "tool_name"

# Or check the JSON results
cat integration_test_results_*.json | jq '.results[] | select(.tool == "unifi_get_alerts")'
```

### Scenario 3: "I fixed a bug and want to verify"
```bash
# Run integration test before fix
python3 devtools/integration_test.py > before.log

# Make your fix
vim src/managers/stats_manager.py

# Run integration test after fix
python3 devtools/integration_test.py > after.log

# Compare
diff before.log after.log
```

### Scenario 4: "I want to document new API endpoints"
```bash
# After adding new manager methods
python3 devtools/api_documentation.py

# Review updated documentation
cat devtools/API_ENDPOINTS.md
```

---

## 📊 Understanding Test Results

### Integration Test JSON Output
```json
{
  "timestamp": "2025-11-14T10:30:00",
  "total_tests": 40,
  "passed": 38,
  "failed": 2,
  "results": [
    {
      "tool": "unifi_get_alerts",
      "category": "statistics",
      "success": false,
      "error": "Serialization error: Object of type Event is not JSON serializable"
    }
  ],
  "broken_tools": [
    {
      "tool": "unifi_get_alerts",
      "error": "Serialization error: ..."
    }
  ],
  "working_tools": [
    "unifi_list_clients",
    "unifi_list_devices",
    ...
  ]
}
```

### Exit Codes
- `0` - All tests passed ✅
- `1` - Some tests failed or error occurred ❌

---

## 🐛 Debugging Failed Tests

### Enable Debug Logging
```python
# In integration_test.py, change:
logging.basicConfig(level=logging.DEBUG)  # Instead of INFO
```

### Check Specific Tool
```python
# Edit integration_test.py to test only one tool:
# Comment out other test calls in run_all_tests()
async def run_all_tests(self):
    # Only test the problematic tool
    await self._test_statistics_tools()  # For get_alerts
```

### Manual Testing
```python
# Create a test script
import asyncio
from src.runtime import connection_manager, stats_manager

async def test_alerts():
    await connection_manager.initialize()
    alerts = await stats_manager.get_alerts()
    print(f"Alerts: {alerts}")
    await connection_manager.cleanup()

asyncio.run(test_alerts())
```

---

## 🔍 Known Issues Being Tracked

See [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) for complete list:

1. **🔴 Critical:** `unifi_get_alerts` - Uses wrong endpoint (`/stat/event` vs `/stat/alarm`)
2. **⚠️ Medium:** Traffic routes endpoint path ambiguity
3. **⚠️ Low:** QoS rules schema needs validation

---

## 📖 Reading the Documentation

**Start here:**
1. `TESTING_SUMMARY.md` - Quick overview
2. `KNOWN_ISSUES.md` - What's broken
3. `API_REFERENCE.md` - Deep dive into APIs
4. `FINDINGS.md` - Research results

**For development:**
- `API_ENDPOINTS.md` - Quick endpoint reference
- Integration test results JSON - Latest test status

---

## 🤝 Contributing

### To Report an Issue
1. Run `integration_test.py`
2. Save the JSON output
3. Check if issue is in `KNOWN_ISSUES.md`
4. If new, create an issue with:
   - Tool name
   - Error message
   - Controller version
   - JSON test results

### To Fix an Issue
1. Check `KNOWN_ISSUES.md` for the problem
2. Make your fix in `src/managers/` or `src/tools/`
3. Run `integration_test.py` to verify
4. Update `KNOWN_ISSUES.md` to mark as fixed
5. Commit with descriptive message

---

## 📞 Support

### Environment Issues
```bash
# Verify environment
echo $UNIFI_HOST
echo $UNIFI_USERNAME
# Password check (don't echo!)

# Test connectivity
curl -k https://$UNIFI_HOST:8443
```

### Controller Compatibility
- Tested on UniFi Network Application 7.x and 8.x
- UDM Pro/UCG Max may require `/proxy/network` prefix
- Cloud Keys should work with standard paths

### SSL/TLS Issues
```python
# If you get SSL errors
export UNIFI_VERIFY_SSL=false
```

---

## 📈 Metrics

- **Total Tools:** 59
- **Static Validation:** 100% pass rate
- **API Validation:** 90% validated
- **Integration Tests:** Run against real controller
- **Documentation:** 20,000+ words across all docs

---

## 🔄 Maintenance

### Regular Tasks
- Run `integration_test.py` after any code changes
- Update `API_ENDPOINTS.md` when adding new endpoints
- Update `KNOWN_ISSUES.md` when bugs are found/fixed
- Re-validate against new controller versions

### Version Compatibility Testing
Test against:
- UniFi Network Application 7.5+
- UniFi Network Application 8.0+
- UDM Pro firmware
- UCG Max firmware
