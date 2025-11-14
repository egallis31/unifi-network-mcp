# Known Issues with UniFi Network MCP Tools

**Last Updated:** 2025-11-14

This document tracks known runtime issues with MCP tools that need fixing.

---

## Critical Issues

### 1. `unifi_get_alerts` - Event vs Alarm Confusion

**Status:** 🔴 Broken

**Problem:**
The tool queries `/stat/event` endpoint but should likely query `/stat/alarm` for actual alerts/alarms.

**Current Implementation:**
```python
# stats_manager.py line 304
api_request = ApiRequest(
    method="get",
    path=f"/stat/event?start={start_time}&end={end_time}"
)
```

**UniFi API Documentation:**
- `/stat/event` - Returns ALL events (connections, disconnections, etc.)
- `/stat/alarm` - Returns actual ALARMS/ALERTS (security, connectivity issues, etc.)

**Fix Needed:**
```python
# Should use /stat/alarm instead
api_request = ApiRequest(
    method="get",
    path="/stat/alarm"  # Can add ?archived=false to exclude archived
)
```

**Serialization Issue:**
Events returned may not have `.raw` attribute, causing serialization to fail.

**Test Case:**
```python
# Should return alarms, not all events
alerts = await stats_manager.get_alerts(include_archived=False)
# Should be serializable to JSON
json.dumps({'alerts': alerts}, default=str)
```

---

## Medium Priority Issues

### 2. Traffic Routes - Endpoint Path Ambiguity

**Status:** ⚠️ Needs Verification

**Problem:**
Conflicting documentation about endpoint path:
- Our code uses: `/trafficroutes`
- Some docs mention: `/trafficrules`

**Location:** `src/managers/firewall_manager.py:182`

**Test Needed:**
```python
# Test 1: Try current path
try:
    routes = await firewall_manager.get_traffic_routes()
    print("✅ /trafficroutes works")
except Exception as e:
    print(f"❌ /trafficroutes failed: {e}")
    # Test 2: Try alternate path
    # ... fallback logic
```

**Fix:**
Add graceful fallback in firewall_manager.py

---

### 3. QoS Rules - Schema Not Validated

**Status:** ⚠️ Needs Validation

**Problem:**
QoS rules endpoint `/qos-rules` is likely correct, but response schema not validated against real controller.

**Location:** `src/managers/qos_manager.py`

**Test Needed:**
1. Create a QoS rule via UI
2. Fetch via API
3. Validate response matches our schema

---

## Serialization Issues

### General Pattern

Many tools return aiounifi objects that may not serialize properly to JSON.

**Common Issue:**
```python
# Object has no .raw attribute
result = some_manager_call()
# Trying to access .raw fails
data = result.raw  # AttributeError
```

**Solution Pattern:**
```python
# Safe serialization
def serialize_item(item):
    if hasattr(item, 'raw'):
        return item.raw
    elif isinstance(item, dict):
        return item
    else:
        # Convert to dict manually
        return {k: v for k, v in item.__dict__.items() if not k.startswith('_')}
```

**Tools Potentially Affected:**
- ✅ `unifi_get_alerts` - Already has fix, but may not work
- ⚠️ `unifi_get_dpi_stats` - Needs verification
- ⚠️ `unifi_list_traffic_routes` - Needs verification
- ⚠️ `unifi_list_firewall_policies` - Needs verification

---

## Testing Protocol

### Prerequisites
```bash
export UNIFI_HOST="192.168.1.1"
export UNIFI_USERNAME="admin"
export UNIFI_PASSWORD="your_password"
export UNIFI_SITE="default"  # optional
```

### Run Integration Tests
```bash
python3 devtools/integration_test.py
```

### Expected Output
```
==================================================================================
UniFi Network MCP - Integration Test Suite
==================================================================================
Connecting to: 192.168.1.1
Site: default
✅ Connection established successfully

### CLIENT TOOLS ###
Testing: unifi_list_clients
  ✅ PASS
...

==================================================================================
TEST SUMMARY
==================================================================================
Total tests: 40
Passed: 38 (95.0%)
Failed: 2 (5.0%)

==================================================================================
BROKEN TOOLS
==================================================================================
❌ unifi_get_alerts
   Error: Serialization error: Object of type Event is not JSON serializable

❌ unifi_list_traffic_routes
   Error: HTTPError: 404 Not Found
```

---

## Fix Priority

### Immediate (This Week)
1. 🔴 Fix `unifi_get_alerts` - Change to `/stat/alarm`
2. 🔴 Add safe serialization wrapper for all tools

### Short Term (This Month)
1. ⚠️ Verify traffic routes endpoint path
2. ⚠️ Validate QoS rules schema
3. ⚠️ Add UDM Pro/UCG Max detection

### Long Term (This Quarter)
1. Add comprehensive error handling
2. Add rate limiting
3. Add retry logic for network errors
4. Performance optimization

---

## Workarounds for Users

### Getting Alerts
```python
# Current workaround: Query events directly
from aiounifi.models.api import ApiRequest

api_request = ApiRequest(
    method="get",
    path="/stat/alarm"  # Use alarm endpoint directly
)
response = await connection_manager.request(api_request)
```

### Traffic Routes
```python
# If /trafficroutes fails, try /trafficrules
try:
    routes = await firewall_manager.get_traffic_routes()
except Exception:
    # Manual fallback needed
    pass
```

---

## Contributing Fixes

### Steps to Fix a Tool

1. **Identify the issue**
   ```bash
   python3 devtools/integration_test.py 2>&1 | grep "FAIL"
   ```

2. **Locate the code**
   ```bash
   grep -r "tool_name" src/tools/
   ```

3. **Fix the issue**
   - Update manager method
   - Update tool wrapper
   - Add serialization logic if needed

4. **Test the fix**
   ```bash
   python3 devtools/integration_test.py
   ```

5. **Commit with descriptive message**
   ```bash
   git add src/
   git commit -m "Fix unifi_get_alerts to use /stat/alarm endpoint"
   ```

---

## References

- **UniFi API Endpoints:** See `devtools/API_REFERENCE.md`
- **Integration Tests:** See `devtools/integration_test.py`
- **Validation Results:** See `devtools/FINDINGS.md`
