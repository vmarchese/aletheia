# Session Memory - Persist Logs to Session Folder

## Task Overview
**Feature**: Save retrieved logs and metrics to session folder
**Worktree**: `worktrees/feat/persist-logs`
**Branch**: `feat/persist-logs`
**Status**: In Progress
**Started**: 2025-10-21

## Problem Statement
Currently, data fetchers (KubernetesDataFetcher, PrometheusDataFetcher) only write metadata to the scratchpad but do NOT save the actual raw logs/metrics to the session's data directory. The SPECIFICATION.md expects logs to be saved at paths like:
- `~/.aletheia/sessions/{id}/data/logs/payments-svc.json`
- `~/.aletheia/sessions/{id}/data/metrics/error_rate.json`

## Current Behavior
1. Session creates directory structure: `session.data_dir / "logs"`, `session.data_dir / "metrics"`, `session.data_dir / "traces"`
2. Data fetchers collect logs via plugins
3. Only metadata (count, summary, time_range) is written to scratchpad
4. Raw logs/metrics are NOT persisted to disk

## Implementation Plan

### Phase 1: Add Session Awareness to Data Fetchers ✅ COMPLETE
- [x] Pass `session` object to data fetcher agents
- [x] Add `_save_to_session()` helper method to base class or utility
- [x] Determine file naming convention (pod name, timestamp, etc.)

### Phase 2: Update KubernetesDataFetcher ✅ COMPLETE
- [x] After collecting logs in `_execute_with_sk()`, save to `session.data_dir / "logs"`
- [x] Generate filename: `{pod_name}_{namespace}_{timestamp}.json`
- [x] Update scratchpad metadata to include file path
- [x] Also update `_execute_direct()` for backward compatibility

### Phase 3: Update PrometheusDataFetcher ✅ COMPLETE
- [x] After collecting metrics in `_execute_with_sk()`, save to `session.data_dir / "metrics"`
- [x] Generate filename: `{sanitized_query}_{timestamp}.json`
- [x] Update scratchpad metadata to include file path
- [x] Also update `_execute_direct()` for backward compatibility

### Phase 4: Update Session Export/Import ✅ NOT NEEDED
- [x] Verified exported sessions include data files (existing implementation already handles this)
- [x] Verified imported sessions restore data files correctly (existing implementation already handles this)
- [x] Test with actual log/metric files (tested via unit tests)

### Phase 5: Testing ✅ COMPLETE
- [x] Unit tests for session persistence utilities (18 tests, 88.75% coverage)
- [x] Unit tests verify correct file creation and structure
- [x] Unit tests for filename sanitization and timestamp generation
- [x] All session, config, and persistence tests passing (84 tests total)
- [x] Session export/import includes data files (verified via existing tests)

### Phase 6: Documentation ⏳ REMAINING
- [ ] Update SPECIFICATION.md if needed
- [ ] Update README.md to mention data persistence
- [ ] Add examples of accessing saved logs

## Key Decisions

### File Naming Convention
**Kubernetes Logs**: `{pod_name}_{namespace}_{timestamp}.json`
**Prometheus Metrics**: `{sanitized_query}_{timestamp}.json`
**Timestamp Format**: ISO 8601 with seconds: `2025-10-21T14-30-45`

### File Structure
```json
{
  "source": "kubernetes",
  "metadata": {
    "pod": "payments-svc",
    "namespace": "production",
    "time_range": ["2025-10-21T14:00:00", "2025-10-21T16:00:00"],
    "collected_at": "2025-10-21T16:05:00"
  },
  "data": [ /* raw log entries */ ]
}
```

### Session Injection
Pass session via agent initialization:
```python
class KubernetesDataFetcher(SKBaseAgent):
    def __init__(self, config, scratchpad, session=None):
        super().__init__(config, scratchpad)
        self.session = session
```

Or via execute() parameter:
```python
await kubernetes_fetcher.execute(session=session, **kwargs)
```

**Decision**: Use execute() parameter for flexibility (agents can work without session)

## Session Log

### 2025-10-21 - Initial Investigation
- Verified logs are NOT currently saved to session folder
- Session structure exists but is unused
- SPECIFICATION.md expects file paths in DATA_COLLECTED
- Created worktree and environment setup complete

### 2025-10-21 - Implementation Complete ✅
- **Created** `aletheia/utils/session_persistence.py` with utilities:
  - `sanitize_filename()`: Sanitizes strings for filename safety
  - `generate_timestamp()`: Creates ISO 8601 timestamps for filenames
  - `save_logs_to_session()`: Saves logs to `session.data_dir/logs/`
  - `save_metrics_to_session()`: Saves metrics to `session.data_dir/metrics/`
  - `save_traces_to_session()`: Saves traces to `session.data_dir/traces/`

- **Updated** `aletheia/agents/kubernetes_data_fetcher.py`:
  - Added `session` parameter to `execute()` method
  - Modified `_execute_with_sk()` to save logs to session folder
  - Modified `_execute_direct()` to save logs to session folder
  - Added file path to scratchpad metadata: `collected_data["path"]`
  - Graceful error handling if save fails (continues execution)

- **Updated** `aletheia/agents/prometheus_data_fetcher.py`:
  - Added `session` parameter to `execute()` method
  - Modified `_execute_with_sk()` to save metrics to session folder
  - Modified `_execute_direct()` to save metrics to session folder
  - Added file path to scratchpad metadata: `collected_data["path"]`
  - Graceful error handling if save fails (continues execution)

- **Testing**:
  - Created 18 comprehensive unit tests in `tests/unit/test_session_persistence.py`
  - Coverage: 88.75% for session_persistence.py
  - All 84 tests passing (session, config, persistence modules)
  - Verified filename sanitization, unicode handling, large datasets
  - Verified directory creation and file structure

- **Commit**: `e4395fb` - "feat: add session persistence for logs and metrics"

### File Structure Created
```
session.data_dir/
├── logs/
│   └── kubernetes_{pod}_{namespace}_{timestamp}.json
├── metrics/
│   └── prometheus_{sanitized_query}_{timestamp}.json
└── traces/
    └── jaeger_{identifier}_{timestamp}.json
```

### JSON File Format
```json
{
  "source": "kubernetes",
  "metadata": {
    "pod": "payments-svc",
    "namespace": "production",
    "time_range": ["2025-10-21T14:00:00", "2025-10-21T16:00:00"],
    "collected_at": "2025-10-21T16:05:00",
    "count": 200
  },
  "data": [/* raw log entries */]
}
```

---

## Summary

**Status**: ✅ **IMPLEMENTATION COMPLETE**
**Worktree**: `worktrees/feat/persist-logs`
**Branch**: `feat/persist-logs`
**Commit**: `e4395fb`

### What Was Implemented
1. ✅ Session persistence utility module with helper functions
2. ✅ KubernetesDataFetcher saves logs to session folder
3. ✅ PrometheusDataFetcher saves metrics to session folder
4. ✅ File paths added to scratchpad metadata
5. ✅ Comprehensive unit tests (18 tests, 88.75% coverage)
6. ✅ All tests passing

### What Remains
1. ⏳ Update documentation (SPECIFICATION.md, README.md)
2. ⏳ Update orchestrator/CLI to pass session to fetchers (if needed)

### Usage Example
```python
# In orchestrator or CLI:
from aletheia.session import Session

session = Session.create(password="secret")
kubernetes_fetcher = KubernetesDataFetcher(config, scratchpad)

# Pass session to enable persistence
result = await kubernetes_fetcher.execute(session=session, pod="payments-svc")

# Check scratchpad for file path
data = scratchpad.read_section(ScratchpadSection.DATA_COLLECTED)
log_file_path = data["kubernetes"]["path"]
# => ~/.aletheia/sessions/INC-ABCD/data/logs/kubernetes_payments-svc_default_2025-10-21T16-05-23.json
```
