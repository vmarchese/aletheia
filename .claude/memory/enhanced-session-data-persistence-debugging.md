# Enhanced Session Data Persistence with Debugging

## Date: 2025-10-21 (Follow-up)

## Issue Reported
User reported that logs are still not being saved even after the initial fix.

## Investigation
The infrastructure was correctly in place:
1. ✅ Session object was being passed from orchestrator to agents
2. ✅ `save_logs_to_session()` and `save_metrics_to_session()` functions exist
3. ✅ Agents have code to call these functions

**Possible Root Cause**: The data collection might be returning empty data, or the condition checks are failing silently.

## Solution: Enhanced Debugging

Added comprehensive debug logging to help identify the exact reason logs aren't being saved:

### Changes Made

#### 1. **Kubernetes Data Fetcher** (`aletheia/agents/kubernetes_data_fetcher.py`)
- Added debug logging before save attempt:
  - Log collected data keys
  - Log data entries count
  - Log whether session is provided
- Enhanced else block logging to distinguish between:
  - No session provided
  - No data collected (empty or None)
  - Unknown reason

#### 2. **Prometheus Data Fetcher** (`aletheia/agents/prometheus_data_fetcher.py`)
- Added import for `log_warning`
- Added same debug logging as Kubernetes fetcher
- Enhanced else block logging with detailed reasons

### Debug Output Now Includes:

**SK Mode (when LLM invokes plugins):**
```
[INFO] Collected data keys: ['source', 'data', 'metadata', 'count', 'summary']
[INFO] Data entries count: 150
[INFO] Session provided: True
[INFO] Saved Kubernetes logs to /path/to/session/data/logs/kubernetes_pod-name_namespace_2025-10-21T14-30-45.json
```

**SK Mode (when data is empty):**
```
[INFO] Collected data keys: ['source', 'metadata', 'count', 'summary']
[INFO] Data entries count: 0
[INFO] Session provided: True
[WARNING] No data collected (data is empty or None), skipping log saving. Collected data: {...}
```

**SK Mode (when no session):**
```
[INFO] Collected data keys: ['source', 'data', 'metadata']
[INFO] Data entries count: 50
[INFO] Session provided: False
[WARNING] No session provided, skipping log saving to session folder
```

**Direct Mode (similar output with "Direct mode -" prefix):**
```
[INFO] Direct mode - Fetch result data count: 200
[INFO] Direct mode - Session provided: True
[INFO] Saved Kubernetes logs to /path/to/session/data/logs/...
```

## How to Use Debug Output

When running Aletheia with verbose mode (`-vv`), check the logs for:

1. **"Collected data keys"** or **"Fetch result data count"**: 
   - If count is 0, the problem is in data collection, not saving
   - If keys don't include "data", the response parsing might be failing

2. **"Session provided"**:
   - If False, the session isn't being passed (orchestrator issue)
   - If True, continue checking

3. **Warning messages**:
   - "No data collected": The data source returned no results
   - "No session provided": Session wasn't passed (shouldn't happen after our fix)
   - "Unknown reason": This shouldn't appear - if it does, it's a bug

## Next Steps for User

If logs are still not being saved, run with `-vv` flag and check output:

```bash
aletheia session open --very-verbose -vv
```

Look for the debug messages above and report:
1. What does "Data entries count" show?
2. What does "Session provided" show?
3. What warning message appears (if any)?

This will help us identify whether:
- The data collection is failing (no logs to save)
- The session is not being passed (infrastructure issue)
- The data is being collected but not saved (logic bug)

## Files Modified
- `aletheia/agents/kubernetes_data_fetcher.py`: +12 lines of debug logging
- `aletheia/agents/prometheus_data_fetcher.py`: +13 lines of debug logging + 1 import

## Testing
- All existing tests pass (6/6 session passing tests)
- Code parses correctly (no syntax errors)
- Debug logging ready for production troubleshooting
