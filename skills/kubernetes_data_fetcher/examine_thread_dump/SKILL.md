---
name: Examine Java Thread Dump
description: Gets a java thread dump from a java process in a kubernetes pod and examine it
---
Use this skill to get a java thread dump from a kubernetes pod and analyze it
1. Use `list_kubernetes_pods()` to get the list of pods in the specified namespace.
2. Describe the specified pod with `describe_pod()`
3. Get the java pid from the specified pod using `ps()`.
4. use `sigquit()` to get the thread dump from the specified pod and java pid.
5. get the pod logs with `fetch_kubernetes_logs()` 
6. analyze the thread dump in the logs and report the findings in a bullet list in the "summary" field of the Findings section. 
7. List the number of threads by state as in the following example:
```
| State | Number |  Notes | 
| NEW | 10 | |
| RUNNABLE | 20 | | 
| BLOCKED | 1 |  The thread is blocked waiting for... | 
...
```

