# Common Regex Patterns for Guardrail Rules

## Basic Patterns

### Exact Command Match

```yaml
# Match exact command
- "^git status$"           # Only "git status", nothing else
- "^ls$"                   # Only "ls", no arguments
```

### Command with Arguments

```yaml
# Match command with any arguments
- "^git\\s+status"         # "git status", "git status -v"
- "^docker\\s+ps"          # "docker ps", "docker ps -a"
```

### Command Anywhere in String

```yaml
# Match command in compound statements
- "rm\\s+-rf"              # Matches "ls && rm -rf /"
- "kubectl\\s+delete"      # Matches "echo hi; kubectl delete pod"
```

## File Path Patterns

### File Extension

```yaml
# Match by extension
- "\\.env$"                # Any .env file
- "\\.key$"                # Any .key file
- "\\.(pem|key|crt)$"      # Multiple extensions
```

### Directory Path

```yaml
# Match by directory
- "^/etc/"                 # Files in /etc/
- "^/root/"                # Files in /root/
- "/secrets/"              # Files in any secrets/ directory
```

### Filename Anywhere

```yaml
# Match filename in any location
- "(^|/)config\\.yml$"     # config.yml at root or in subdirectory
- "(^|/)\\.env$"           # .env at root or in subdirectory
```

## Command Patterns

### Command with Specific Flags

```yaml
# Match specific flag combinations
- "rm\\s+-rf\\s+/"         # rm -rf /
- "git\\s+push\\s+--force" # git push --force
- "docker\\s+run.*--privileged"  # docker run with --privileged
```

### Command with PATH

```yaml
# Match command with or without path
- "(^|.*/)rm\\s+-rf"       # rm or /usr/bin/rm or /bin/rm
- "(^|.*/)python[0-9.]*"   # python or /usr/bin/python3
```

### Multiple Commands

```yaml
# Match any of several commands
- "^(rm|dd|mkfs)\\s"       # rm, dd, or mkfs
- "^(terraform|kubectl)\\s+destroy"  # terraform destroy or kubectl destroy
```

## Advanced Patterns

### Negative Lookahead

```yaml
# Match command but not specific variant
- "^git\\s+push(?!\\s+--dry-run)"  # git push but not --dry-run
```

### Case Insensitive

```yaml
# Match regardless of case
- "(?i)delete.*production" # DELETE, delete, DeLeTe
- "(?i)^drop\\s+table"     # DROP TABLE, drop table
```

### Optional Parts

```yaml
# Match with optional parts
- "^python[0-9.]*\\s"      # python, python3, python3.11
- "^npm(x)?\\s+install"    # npm install or npx install
```

### Greedy vs Non-Greedy

```yaml
# Greedy (match as much as possible)
- "docker.*rm"             # Matches "docker ps && rm file"

# Non-greedy (match as little as possible)
- "docker.*?rm"            # Matches "docker rm" in "docker rm && ls"
```

## Hostname Patterns

### Exact Domain

```yaml
# Match exact domain
- "^evil\\.com$"           # Only evil.com
- "^malicious\\.org$"      # Only malicious.org
```

### Subdomain Wildcard

```yaml
# Match domain and all subdomains
- "^([^.]+\\.)*evil\\.com$"  # evil.com, sub.evil.com, a.b.evil.com
- ".*\\.internal$"           # Anything ending in .internal
```

### Block TLD

```yaml
# Block entire top-level domain
- "\\.ru$"                 # All .ru domains
- "\\.cn$"                 # All .cn domains
```

## Escaping Special Characters

### Characters That Need Escaping

In YAML, use `\\` to escape:

| Character | Escaped | Example |
|-----------|---------|---------|
| `.` | `\\.` | `script\\.py` |
| `*` | `\\*` | `file\\*\\.txt` |
| `+` | `\\+` | `g\\+\\+` |
| `?` | `\\?` | `file\\?.txt` |
| `(` `)` | `\\(` `\\)` | `\\(test\\)` |
| `[` `]` | `\\[` `\\]` | `file\\[1\\]` |
| `{` `}` | `\\{` `\\}` | `\\{1,3\\}` |
| `\|` | `\\\|` | `(a\\\|b)` |
| `^` | `\\^` | `\\^start` (literal ^) |
| `$` | `\\$` | `\\$var` (literal $) |

### YAML String Quoting

```yaml
# Single quotes (literal, no escaping needed)
- '^git\s+status'          # Works but \s is literal

# Double quotes (escaping required)
- "^git\\s+status"         # Correct, \s is whitespace

# Recommendation: Always use double quotes for regex
```

## Testing Patterns

### Python Test Script

```python
import re

pattern = r"^git\s+status"
test_strings = [
    "git status",
    "git status -v",
    "ls && git status",
]

for s in test_strings:
    match = re.search(pattern, s)
    print(f"{s:30} -> {bool(match)}")
```

### Bash One-Liner

```bash
python3 -c "import re; print(bool(re.search(r'YOUR_PATTERN', 'YOUR_STRING')))"
```

## Common Mistakes

### Mistake 1: Forgetting Anchors

❌ **Bad**: `"git status"` matches "legit status update"

✅ **Good**: `"^git\\s+status"` matches only git command

### Mistake 2: Not Escaping Dots

❌ **Bad**: `"script.py"` matches "scriptXpy"

✅ **Good**: `"script\\.py"` matches only "script.py"

### Mistake 3: Single Backslash in YAML

❌ **Bad**: `"\s"` is literal `\s` in YAML

✅ **Good**: `"\\s"` is whitespace regex

### Mistake 4: Greedy Matching

❌ **Bad**: `".*"` matches entire string

✅ **Good**: `".*?"` matches minimally

### Mistake 5: Case Sensitivity

❌ **Bad**: `"DELETE"` doesn't match "delete"

✅ **Good**: `"(?i)delete"` matches any case

## Pattern Library

### Destructive Commands

```yaml
- "(^|.*/)rm\\s+-rf\\s+/"
- "(^|.*/)dd\\s+if=/dev/(zero|random)\\s+of="
- "(^|.*/)mkfs\\."
- ":\\(\\)\\{.*:\\|:&\\};"
- ">(\\s*/dev/sd|/dev/nvme)"
```

### Indirect Execution

```yaml
- "\\beval\\b"
- "\\bexec\\b"
- "\\bbase64\\s.*\\|.*\\b(bash|sh|zsh)\\b"
- "\\bxargs\\s.*(rm|dd|mkfs)"
```

### Sensitive Files

```yaml
- "(^|/)\\.env$"
- "(^|/)id_(rsa|ed25519)$"
- "(^|/)\\.aws/credentials$"
- "(^|/)secrets\\."
- "\\.key$"
- "\\.pem$"
```

### Script Execution

```yaml
- "^python[0-9.]*\\s"
- "^node\\s"
- "^(bash|sh|zsh)\\s"
- "^\\./\\S+"
- "^(ruby|perl|php)\\s"
```

### Package Management

```yaml
- "^(pip|pip3)\\s+(install|uninstall)"
- "^npm\\s+(install|uninstall|publish)"
- "^cargo\\s+(install|build)"
- "^go\\s+(install|build)"
```

### Version Control (Destructive)

```yaml
- "^git\\s+push\\s+--force"
- "^git\\s+reset\\s+--hard"
- "^git\\s+clean\\s+-[fd]"
- "^git\\s+stash\\s+drop"
- "^git\\s+branch\\s+-D"
```

## Quick Reference

### Anchors
- `^` - Start of string
- `$` - End of string
- `\b` - Word boundary

### Character Classes
- `\s` - Whitespace
- `\d` - Digit
- `\w` - Word character (a-z, A-Z, 0-9, _)
- `.` - Any character
- `[abc]` - Any of a, b, c
- `[^abc]` - Not a, b, or c
- `[a-z]` - Range a to z

### Quantifiers
- `*` - 0 or more
- `+` - 1 or more
- `?` - 0 or 1
- `{n}` - Exactly n
- `{n,}` - n or more
- `{n,m}` - Between n and m

### Groups
- `(abc)` - Capture group
- `(?:abc)` - Non-capture group
- `(a|b)` - Alternation

### Lookahead
- `(?=abc)` - Positive lookahead
- `(?!abc)` - Negative lookahead

### Flags
- `(?i)` - Case insensitive
- `(?m)` - Multiline mode
- `(?s)` - Dot matches newline
