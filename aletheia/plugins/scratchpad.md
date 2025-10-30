The Scratchpad plugin gives access to a scratchpad file to read and write the activities you perform

- **read_scratchpad()**: Read the entire scratchpad journal to see all previous entries and context from other agents
- **write_journal_entry(description, text)**: Append a new timestamped entry to the scratchpad journal with a description and detailed text

Use the scratchpad to:
- Read previous context with `read_scratchpad()` to understand what other agents have discovered
- Document your findings with `write_journal_entry("KubernetesDataFetcher", "<description of your findings>","<your findings>")`
- Share collected logs and metadata so other agents can use your findings