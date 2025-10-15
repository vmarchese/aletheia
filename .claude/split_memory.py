import re
import hashlib
import time
from pathlib import Path

def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def main():
    mem = Path('.claude/memory.md')
    text = mem.read_text(encoding='utf-8')
    # Split on lines that are only dashes (>= 20)
    # Print all lines that look like separator lines (20+ dashes)
    print("DEBUG: Printing all lines that look like separator lines (20+ dashes):")
    for i, line in enumerate(text.splitlines()):
        if re.fullmatch(r'-{20,}', line.strip()):
            print(f"Line {i+1}: {repr(line)}")
    parts = re.split(r'\n-{20}\n', text)
    print(f"DEBUG: Detected {len(parts)} session chunks.")
    for idx, chunk in enumerate(parts):
        first = chunk.strip().split('\n', 1)[0] if chunk.strip() else ''
        print(f"Chunk {idx+1}: {first[:80]}")
    created = []
    for i, part in enumerate(parts):
        s = part.strip()
        if not s or len(s) < 10:
            continue
        name = None
        # 1) Completed: TODO Step X - Title
        m = re.search(r'^#+\s*Completed:\s*TODO\s*Step\s*([0-9][0-9\.-]*)\s*-\s*(.+)$', s, re.MULTILINE)
        if m:
            tid = m.group(1).strip()
            title = m.group(2).strip()
            base = f"{tid}-{slug(title)}"
            name = base
        # 2) Session Update - date (Title)
        if not name:
            m = re.search(r'^##\s*Session\s*Update\s*-\s*[^\n(]+\(([^\)]+)\)', s, re.MULTILINE)
            if m:
                base = slug(m.group(1).strip())
                name = base
        # 3) Worktree/Branch feature name
        if not name:
            m = re.search(r'^\*\*Worktree\*\*:\s*`?worktrees/feat/([^`\n]+)`?', s, re.MULTILINE)
            if not m:
                m = re.search(r'^\*\*Branch\*\*:\s*`?feat/([^`\n]+)`?', s, re.MULTILINE)
            if m:
                name = slug(m.group(1).strip())
        # 4) Session Start - date
        if not name:
            m = re.search(r'^##\s*Session\s*Start\s*-\s*([0-9-: ]+)', s, re.MULTILINE)
            if m:
                name = f"session-start-{slug(m.group(1))}"
        # 5) Key Points Summary (Session YYYY-MM-DD)
        if not name:
            m = re.search(r'^##\s*Key\s*Points\s*Summary.*?(\d{4}-\d{2}-\d{2})', s, re.MULTILINE)
            if m:
                name = f"key-points-{m.group(1)}"
        # 6) Updated TODO.md
        if not name:
            if re.search(r'^###\s*Updated\s*TODO\.md', s, re.MULTILINE):
                m = re.search(r'^##\s*Session\s*Update\s*-\s*([0-9\-: ]+)', s, re.MULTILINE)
                dt = slug(m.group(1)) if m else str(int(time.time()))
                name = f"todo-updates-{dt}"
        # 7) Fallback using first heading
        if not name:
            m = re.search(r'^##\s*([^\n]+)', s, re.MULTILINE)
            if m:
                name = slug(m.group(1))
        # 8) Always add index for uniqueness
        if not name:
            name = hashlib.sha1(s.encode('utf-8')).hexdigest()[:12]
        filename = f".claude/{name}-{i+1}.md"
        p = Path(filename)
        if not p.exists():
            p.write_text(s, encoding='utf-8')
            created.append(p.name)
    print(f"Created {len(created)} files:\n" + "\n".join(created))

if __name__ == '__main__':
    main()
