# Regex Pattern Testing Techniques

## Testing Methods

### Method 1: Python One-Liner

Quick test in terminal:

```bash
python3 -c "import re; print(bool(re.search(r'PATTERN', 'STRING')))"
```

**Example**:
```bash
python3 -c "import re; print(bool(re.search(r'^git\\s+status', 'git status')))"
# Output: True
```

### Method 2: Python Script

For multiple tests:

```python
import re

pattern = r"^git\s+status"
test_strings = [
    "git status",
    "git status -v",
    "legit status",
]

for s in test_strings:
    match = re.search(pattern, s)
    print(f"{s:30} -> {bool(match)}")
```

**Output**:
```
git status                     -> True
git status -v                  -> True
legit status                   -> False
```

### Method 3: Interactive Python

```python
python3
>>> import re
>>> pattern = r"^git\s+status"
>>> re.search(pattern, "git status")
<re.Match object; span=(0, 10), match='git status'>
>>> re.search(pattern, "legit status")
None
```

### Method 4: Test Against Guardrail

Test pattern in actual guardrail context:

```bash
# Create test config
cat > /tmp/test-guardrail.yml <<EOF
deny_rules:
  bash:
    - "YOUR_PATTERN"
EOF

# Test command
GUARDRAIL_CONFIG=/tmp/test-guardrail.yml \
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"YOUR_COMMAND"}}' | python -m guardrail.cli
```

## Common Pattern Tests

### Anchors

**Start anchor `^`**:
```bash
python3 -c "import re; print(bool(re.search(r'^git', 'git status')))"  # True
python3 -c "import re; print(bool(re.search(r'^git', 'legit status')))"  # False
```

**End anchor `$`**:
```bash
python3 -c "import re; print(bool(re.search(r'status$', 'git status')))"  # True
python3 -c "import re; print(bool(re.search(r'status$', 'git status -v')))"  # False
```

**Both anchors**:
```bash
python3 -c "import re; print(bool(re.search(r'^git status$', 'git status')))"  # True
python3 -c "import re; print(bool(re.search(r'^git status$', 'git status -v')))"  # False
```

### Whitespace

**`\s` matches any whitespace**:
```bash
python3 -c "import re; print(bool(re.search(r'git\\s+status', 'git status')))"  # True
python3 -c "import re; print(bool(re.search(r'git\\s+status', 'git  status')))"  # True (multiple spaces)
python3 -c "import re; print(bool(re.search(r'git\\s+status', 'gitstatus')))"  # False
```

**Literal space**:
```bash
python3 -c "import re; print(bool(re.search(r'git status', 'git status')))"  # True
python3 -c "import re; print(bool(re.search(r'git status', 'git  status')))"  # False (two spaces)
```

### Escaping

**Dot (any character vs literal)**:
```bash
python3 -c "import re; print(bool(re.search(r'script.py', 'scriptXpy')))"  # True (. matches any)
python3 -c "import re; print(bool(re.search(r'script\\.py', 'scriptXpy')))"  # False (\\. is literal)
python3 -c "import re; print(bool(re.search(r'script\\.py', 'script.py')))"  # True
```

**Special characters**:
```bash
# Parentheses
python3 -c "import re; print(bool(re.search(r'\\(test\\)', '(test)')))"  # True

# Brackets
python3 -c "import re; print(bool(re.search(r'\\[1\\]', '[1]')))"  # True

# Dollar sign
python3 -c "import re; print(bool(re.search(r'\\$var', '\$var')))"  # True
```

### Quantifiers

**`*` (0 or more)**:
```bash
python3 -c "import re; print(bool(re.search(r'git\\s*status', 'gitstatus')))"  # True
python3 -c "import re; print(bool(re.search(r'git\\s*status', 'git status')))"  # True
```

**`+` (1 or more)**:
```bash
python3 -c "import re; print(bool(re.search(r'git\\s+status', 'gitstatus')))"  # False
python3 -c "import re; print(bool(re.search(r'git\\s+status', 'git status')))"  # True
```

**`?` (0 or 1)**:
```bash
python3 -c "import re; print(bool(re.search(r'colou?r', 'color')))"  # True
python3 -c "import re; print(bool(re.search(r'colou?r', 'colour')))"  # True
```

**`{n,m}` (between n and m)**:
```bash
python3 -c "import re; print(bool(re.search(r'\\d{3,5}', '1234')))"  # True (4 digits)
python3 -c "import re; print(bool(re.search(r'\\d{3,5}', '12')))"  # False (2 digits)
```

### Character Classes

**`\d` (digit)**:
```bash
python3 -c "import re; print(bool(re.search(r'python\\d', 'python3')))"  # True
python3 -c "import re; print(bool(re.search(r'python\\d', 'python')))"  # False
```

**`\w` (word character)**:
```bash
python3 -c "import re; print(bool(re.search(r'\\w+', 'hello')))"  # True
python3 -c "import re; print(bool(re.search(r'\\w+', '123')))"  # True
```

**`[abc]` (any of)**:
```bash
python3 -c "import re; print(bool(re.search(r'[abc]', 'a')))"  # True
python3 -c "import re; print(bool(re.search(r'[abc]', 'd')))"  # False
```

**`[^abc]` (not any of)**:
```bash
python3 -c "import re; print(bool(re.search(r'[^abc]', 'd')))"  # True
python3 -c "import re; print(bool(re.search(r'[^abc]', 'a')))"  # False
```

### Alternation

**`|` (or)**:
```bash
python3 -c "import re; print(bool(re.search(r'(rm|dd|mkfs)', 'rm -rf')))"  # True
python3 -c "import re; print(bool(re.search(r'(rm|dd|mkfs)', 'dd if=')))"  # True
python3 -c "import re; print(bool(re.search(r'(rm|dd|mkfs)', 'ls')))"  # False
```

### Greedy vs Non-Greedy

**Greedy `.*`**:
```bash
python3 -c "import re; print(re.search(r'docker.*rm', 'docker ps && rm file').group())"
# Output: docker ps && rm
```

**Non-greedy `.*?`**:
```bash
python3 -c "import re; print(re.search(r'docker.*?rm', 'docker ps && rm file').group())"
# Output: docker ps && rm (same in this case, but stops at first match)
```

### Case Sensitivity

**Case sensitive (default)**:
```bash
python3 -c "import re; print(bool(re.search(r'DELETE', 'delete')))"  # False
```

**Case insensitive `(?i)`**:
```bash
python3 -c "import re; print(bool(re.search(r'(?i)DELETE', 'delete')))"  # True
python3 -c "import re; print(bool(re.search(r'(?i)DELETE', 'DeLeTe')))"  # True
```

## Testing Guardrail Patterns

### Test Deny Pattern

```bash
# Pattern from defaults.yml
PATTERN="(^|.*/)rm\\s+-rf\\s+/"

# Test cases
python3 -c "import re; print(bool(re.search(r'$PATTERN', 'rm -rf /')))"  # True
python3 -c "import re; print(bool(re.search(r'$PATTERN', '/usr/bin/rm -rf /')))"  # True
python3 -c "import re; print(bool(re.search(r'$PATTERN', 'rm -rf /tmp')))"  # False
```

### Test Allow Pattern

```bash
# Pattern from defaults.yml
PATTERN="^git\\s+(status|log|diff)"

# Test cases
python3 -c "import re; print(bool(re.search(r'$PATTERN', 'git status')))"  # True
python3 -c "import re; print(bool(re.search(r'$PATTERN', 'git log')))"  # True
python3 -c "import re; print(bool(re.search(r'$PATTERN', 'git push')))"  # False
```

### Test Ask Pattern

```bash
# Pattern from defaults.yml
PATTERN="^python[0-9.]*\\s"

# Test cases
python3 -c "import re; print(bool(re.search(r'$PATTERN', 'python script.py')))"  # True
python3 -c "import re; print(bool(re.search(r'$PATTERN', 'python3 script.py')))"  # True
python3 -c "import re; print(bool(re.search(r'$PATTERN', 'python3.11 script.py')))"  # True
```

## Batch Testing

### Test Multiple Patterns

```python
import re

patterns = [
    r"^git\s+status",
    r"^ls\s",
    r"^cat\s",
]

commands = [
    "git status",
    "ls -la",
    "cat file.txt",
    "rm file.txt",
]

for cmd in commands:
    matches = [p for p in patterns if re.search(p, cmd)]
    print(f"{cmd:20} -> {len(matches)} matches: {matches}")
```

### Test Pattern Against Multiple Commands

```python
import re

pattern = r"^git\s+"

commands = [
    "git status",
    "git push",
    "git log",
    "legit status",
    "ls",
]

for cmd in commands:
    match = re.search(pattern, cmd)
    print(f"{cmd:20} -> {'✓' if match else '✗'}")
```

## Common Mistakes

### Mistake 1: Single Backslash in YAML

```yaml
# Wrong
- "git\s+status"  # \s is literal in YAML

# Right
- "git\\s+status"  # \\s becomes \s in regex
```

**Test**:
```bash
# Wrong pattern
python3 -c "import re; print(bool(re.search(r'git\s+status', 'git status')))"  # False

# Right pattern
python3 -c "import re; print(bool(re.search(r'git\\s+status', 'git status')))"  # True
```

### Mistake 2: Forgetting Anchors

```yaml
# Wrong (matches "legit status")
- "git status"

# Right (only matches "git status" at start)
- "^git\\s+status"
```

**Test**:
```bash
python3 -c "import re; print(bool(re.search(r'git status', 'legit status')))"  # True (bad)
python3 -c "import re; print(bool(re.search(r'^git status', 'legit status')))"  # False (good)
```

### Mistake 3: Not Escaping Dots

```yaml
# Wrong (matches "scriptXpy")
- "script.py"

# Right (only matches "script.py")
- "script\\.py"
```

**Test**:
```bash
python3 -c "import re; print(bool(re.search(r'script.py', 'scriptXpy')))"  # True (bad)
python3 -c "import re; print(bool(re.search(r'script\\.py', 'scriptXpy')))"  # False (good)
```

### Mistake 4: Greedy Matching

```yaml
# Wrong (matches too much)
- "docker.*rm"

# Right (matches minimally)
- "docker.*?rm"
```

**Test**:
```bash
python3 -c "import re; print(re.search(r'docker.*rm', 'docker ps && rm file && ls').group())"
# Output: docker ps && rm file && ls (too much)

python3 -c "import re; print(re.search(r'docker.*?rm', 'docker ps && rm file && ls').group())"
# Output: docker ps && rm (better)
```

## Advanced Testing

### Test with re.match() vs re.search()

Guardrail uses `re.search()` (contains match), not `re.match()` (start match):

```bash
# re.match() only matches at start
python3 -c "import re; print(bool(re.match(r'status', 'git status')))"  # False

# re.search() matches anywhere
python3 -c "import re; print(bool(re.search(r'status', 'git status')))"  # True
```

### Test Compound Commands

Guardrail splits on separators (`;`, `&&`, `||`, `|`, `\n`):

```python
import re

pattern = r"rm\s+-rf"
compound = "git status && rm -rf /"

# Guardrail tests each segment
segments = re.split(r'[;&|]+|\n', compound)
for seg in segments:
    match = re.search(pattern, seg.strip())
    print(f"{seg.strip():30} -> {bool(match)}")
```

### Test PATH Manipulation

Pattern should match command with or without path:

```bash
# Pattern: (^|.*/)rm\s+-rf\s+/
python3 -c "import re; print(bool(re.search(r'(^|.*/)rm\\s+-rf\\s+/', 'rm -rf /')))"  # True
python3 -c "import re; print(bool(re.search(r'(^|.*/)rm\\s+-rf\\s+/', '/usr/bin/rm -rf /')))"  # True
python3 -c "import re; print(bool(re.search(r'(^|.*/)rm\\s+-rf\\s+/', '/bin/rm -rf /')))"  # True
```

## Quick Reference

| Test | Command |
|------|---------|
| Basic match | `python3 -c "import re; print(bool(re.search(r'PATTERN', 'STRING')))"` |
| Show match | `python3 -c "import re; m=re.search(r'PATTERN', 'STRING'); print(m.group() if m else None)"` |
| Multiple tests | Create Python script with loop |
| Against guardrail | `echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"CMD"}}' \| python -m guardrail.cli` |
| Validate YAML | `python3 -c "import yaml; yaml.safe_load(open('file.yml'))"` |
