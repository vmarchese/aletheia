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

### Phase 1: Add Session Awareness to Data Fetchers
- [ ] Pass `session` object to data fetcher agents
- [ ] Add `_save_to_session()` helper method to base class or utility
- [ ] Determine file naming convention (pod name, timestamp, etc.)

### Phase 2: Update KubernetesDataFetcher
- [ ] After collecting logs in `_execute_with_sk()`, save to `session.data_dir / "logs"`
- [ ] Generate filename: `{pod_name}_{timestamp}.json`
- [ ] Update scratchpad metadata to include file path
- [ ] Also update `_execute_direct()` for backward compatibility

### Phase 3: Update PrometheusDataFetcher
- [ ] After collecting metrics in `_execute_with_sk()`, save to `session.data_dir / "metrics"`
- [ ] Generate filename: `{query_hash}_{timestamp}.json`
- [ ] Update scratchpad metadata to include file path
- [ ] Also update `_execute_direct()` for backward compatibility

### Phase 4: Update Session Export/Import
- [ ] Verify exported sessions include data files
- [ ] Verify imported sessions restore data files correctly
- [ ] Test with actual log/metric files

### Phase 5: Testing
- [ ] Unit tests for `_save_to_session()` helper
- [ ] Unit tests for KubernetesDataFetcher with file persistence
- [ ] Unit tests for PrometheusDataFetcher with file persistence
- [ ] Integration tests for full session lifecycle with data files
- [ ] Test session export/import includes data files

### Phase 6: Documentation
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

---

## Next Steps
1. Implement `_save_to_session()` utility function
2. Update KubernetesDataFetcher to save logs
3. Update PrometheusDataFetcher to save metrics
4. Write comprehensive tests
5. Update documentation
