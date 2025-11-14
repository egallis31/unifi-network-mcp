# Known Issues with UniFi Network MCP Tools

**Last Updated:** 2025-11-14

This document tracks known runtime issues with MCP tools that need fixing.

---

## Critical Issues

### 1. `unifi_get_alerts` - Event vs Alarm Confusion

**Status:** ✅ FIXED (2025-11-14)

**Problem:**
The tool queried `/stat/event` endpoint but should query `/stat/alarm` for actual alerts/alarms.

**Previous Implementation:**
```python
# stats_manager.py line 304 (OLD)
api_request = ApiRequest(
    method="get",
    path=f"/stat/event?start={start_time}&end={end_time}"
)
```

**Fixed Implementation:**
```python
# stats_manager.py line 295-306 (NEW)
alarm_path = "/stat/alarm"
if not include_archived:
    alarm_path += "?archived=false"

api_request = ApiRequest(
    method="get",
    path=alarm_path
)
```

**Fix Details:**
- ✅ Changed endpoint from `/stat/event` to `/stat/alarm`
- ✅ Properly handles `include_archived` parameter
- ✅ Updated comments to reflect correct API usage
- ✅ Added safe serialization using new utility module

**Files Modified:**
- `src/managers/stats_manager.py` - Fixed endpoint and logic
- `src/tools/stats.py` - Updated to use new serialization utility
- `src/utils/serialization.py` - Created new safe serialization module

---

## Medium Priority Issues

### 2. Traffic Routes - Endpoint Path Ambiguity

**Status:** ✅ FIXED (2025-11-14)

**Problem:**
Conflicting documentation about endpoint path:
- Primary endpoint: `/trafficroutes`
- Fallback endpoint: `/trafficrules`

**Fixed Implementation:**
```python
# src/managers/firewall_manager.py lines 181-212
try:
    # Try /trafficroutes first (primary endpoint)
    api_request = ApiRequestV2(method="get", path="/trafficroutes")
    response = await self._connection.request(api_request)
    # ... process response
except (RequestError, ResponseError) as e:
    # If 404, try alternate endpoint /trafficrules
    if "404" in str(e) or "not found" in str(e).lower():
        logger.warning("Endpoint /trafficroutes not found, trying /trafficrules as fallback")
        api_request = ApiRequestV2(method="get", path="/trafficrules")
        # ... process fallback response
```

**Fix Details:**
- ✅ Added graceful fallback from `/trafficroutes` to `/trafficrules`
- ✅ Logs warning when fallback is used
- ✅ Handles both endpoints seamlessly
- ✅ Works across different controller versions

**Files Modified:**
- `src/managers/firewall_manager.py` - Added fallback logic

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

### General Pattern - ✅ FIXED (2025-11-14)

**Problem:**
Many tools returned aiounifi objects that did not serialize properly to JSON.

**Solution Implemented:**
Created a centralized serialization utility module at `src/utils/serialization.py`:

```python
def serialize_aiounifi_object(obj: Any) -> Union[Dict, List, Any]:
    """Safely serialize an aiounifi object to JSON-compatible format."""
    if obj is None:
        return None
    if hasattr(obj, 'raw'):
        return obj.raw
    if isinstance(obj, dict):
        return {k: serialize_aiounifi_object(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serialize_aiounifi_object(item) for item in obj]
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if hasattr(obj, '__dict__'):
        return {k: serialize_aiounifi_object(v)
                for k, v in obj.__dict__.items()
                if not k.startswith('_') and not callable(v)}
    return str(obj)
```

**Tools Fixed:**
- ✅ `unifi_get_alerts` - Updated to use serialization utility
- ✅ `unifi_get_dpi_stats` - Updated to use serialization utility
- ✅ `unifi_list_traffic_routes` - Updated to use serialization utility
- ✅ `unifi_get_traffic_route_details` - Updated to use serialization utility
- ✅ ALL tools - Comprehensive cleanup of inefficient patterns (2025-11-14)

**Comprehensive Cleanup Completed (2025-11-14):**
- ✅ Eliminated 15+ `json.loads(json.dumps())` patterns across all tools
- ✅ Replaced all `.raw if hasattr()` patterns with centralized serialization
- ✅ Simplified manual serialization loops in managers
- ✅ Verified all tools compile without syntax errors
- ✅ Tools affected: clients.py, devices.py, network.py, firewall.py, port_forwards.py, qos.py, stats.py, traffic_routes.py
- ✅ Managers updated: stats_manager.py (simplified 25-line loop to 1-line call)

**Files Modified:**
- `src/utils/serialization.py` - New module with safe serialization functions
- `src/tools/stats.py` - Updated get_alerts, get_dpi_stats, and client stats
- `src/tools/traffic_routes.py` - Updated list, details, and update operations
- `src/tools/clients.py` - Updated all client listing and details tools
- `src/tools/devices.py` - Updated device listing
- `src/tools/network.py` - Updated all network and WLAN tools
- `src/tools/firewall.py` - Updated firewall policy tools
- `src/tools/port_forwards.py` - Updated all port forwarding tools
- `src/tools/qos.py` - Updated all QoS tools
- `src/managers/stats_manager.py` - Simplified manual serialization in get_top_clients

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

### Completed (2025-11-14) ✅
1. ✅ Fixed `unifi_get_alerts` - Changed to `/stat/alarm`
2. ✅ Added safe serialization wrapper for all tools
3. ✅ Added traffic routes endpoint fallback mechanism

### Short Term (This Month)
1. ⚠️ Validate QoS rules schema (integration testing needed)
2. ⚠️ Add UDM Pro/UCG Max detection
3. ⚠️ Run integration tests to verify all fixes

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
