---
name: Examine Java Thread Dump
description: Gets a java thread dump from a java process in a kubernetes pod and examine it
---
Use this skill to get a java thread dump from a kubernetes pod and analyze it
1. Use `list_kubernetes_pods()` to get the list of pods in the specified namespace.
2. Get the java pid from the specified pod using `ps()`.
3. use `thread_dump()` to get the thread dump from the specified pod and java pid.
4. get the pod logs with `fetch_kubernetes_logs()` 
5. analyze the thread dump in the logs and report the findings in a bullet list in the "summary" field of the Findings section