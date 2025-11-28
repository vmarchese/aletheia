You can run scripts in a docker container with parameter passing support:

- **sandbox_run(folder, script, args=None, data=None)**: executes the python script folder/script in a docker container

## Parameters

- **folder** (required): Path to the skill folder containing the script
- **script** (required): Name of the script file to execute (must be in folder/scripts/)
- **args** (optional): Dictionary of simple arguments (str, int, float, bool) passed as UPPER_CASE environment variables
- **data** (optional): Dictionary of complex data structures (lists, nested dicts) written to /scripts/data.json

## Examples

### Simple arguments via environment variables
```python
sandbox_run(
    "/path/to/skill",
    "check_ip.py",
    args={"ip_address": "10.0.0.1", "profile": "production", "timeout": 30}
)
```

Script accesses via:
```python
import os
ip = os.environ.get('IP_ADDRESS')
profile = os.environ.get('PROFILE', 'default')
timeout = int(os.environ.get('TIMEOUT', '30'))
```

### Complex data via JSON file
```python
sandbox_run(
    "/path/to/skill",
    "analyze_resources.py",
    data={"security_groups": [...], "instances": [...]}
)
```

Script accesses via:
```python
import json
from pathlib import Path

data_file = Path('/scripts/data.json')
if data_file.exists():
    with open(data_file, 'r') as f:
        data = json.load(f)
    security_groups = data.get('security_groups', [])
```

### Both simple and complex arguments
```python
sandbox_run(
    "/path/to/skill",
    "process_logs.py",
    args={"namespace": "production", "hours": 24},
    data={"pod_filters": [...], "log_patterns": [...]}
)
``` 