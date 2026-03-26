# Guardrail Log Format

## Log File Location

Default: `.claude/guardrail.log`

Configurable via `log_file` in guardrail.yml:
```yaml
log_file: /path/to/custom.log
```

## Log Entry Format

Each log entry follows this structure:

```
[TIMESTAMP] EVENT:TOOL | TARGET | DECISION | REASON
```

### Fields

**TIMESTAMP**: ISO 8601 format with local timezone
- Format: `YYYY-MM-DD HH:MM:SS`
- Example: `2026-03-26 10:30:45`

**EVENT**: Hook event name
- `PreToolUse` - Before tool execution
- `PostToolUse` - After tool execution

**TOOL**: Tool name being guarded
- `Bash` - Shell commands
- `Write` - File creation
- `Edit` - File modification
- `WebFetch` - HTTP requests

**TARGET**: The actual command, file path, or URL
- Bash: Full command string
- Write/Edit: File path
- WebFetch: URL

**DECISION**: Guardrail decision
- `deny` - Blocked immediately
- `allow` - Auto-approved
- `ask` - User confirmation required
- `pass` - No rule matched, deferred to Layer 2

**REASON**: Why this decision was made
- `matched deny rule` - Deny pattern matched
- `matched allow rule` - Allow pattern matched
- `matched ask rule` - Ask pattern matched
- `no matching rule, deferred to Layer 2` - Passed to LLM
- `Layer 2 allowed` - LLM classified as safe
- `Layer 2 denied` - LLM classified as dangerous
- `Layer 2 asked` - LLM requested confirmation

## Example Log Entries

### Deny Decision

```
[2026-03-26 10:31:12] PreToolUse:Bash | rm -rf / | deny | matched deny rule
```

Command `rm -rf /` blocked by deny rule.

### Allow Decision

```
[2026-03-26 10:30:45] PreToolUse:Bash | git status | allow | matched allow rule
```

Command `git status` auto-approved by allow rule.

### Ask Decision

```
[2026-03-26 10:32:05] PreToolUse:Bash | python3 script.py | ask | matched ask rule
```

Command `python3 script.py` requires user confirmation.

### Pass to Layer 2

```
[2026-03-26 10:33:10] PreToolUse:Bash | docker run ubuntu | pass | no matching rule, deferred to Layer 2
[2026-03-26 10:33:12] PostToolUse:Bash | docker run ubuntu | allow | Layer 2 allowed
```

Command passed Layer 1, then LLM classified as safe.

### File Operations

```
[2026-03-26 10:35:20] PreToolUse:Write | /tmp/test.txt | allow | matched allow rule
[2026-03-26 10:36:45] PreToolUse:Edit | .env | deny | matched deny rule
```

File write allowed, .env edit blocked.

### WebFetch

```
[2026-03-26 10:40:15] PreToolUse:WebFetch | https://api.example.com/data | pass | no matching rule, deferred to Layer 2
[2026-03-26 10:40:17] PostToolUse:WebFetch | https://api.example.com/data | allow | Layer 2 allowed
```

URL passed Layer 1, LLM approved.

## Reading Logs

### View Recent Decisions

```bash
tail -n 20 .claude/guardrail.log
```

Shows last 20 decisions.

### Filter by Decision Type

```bash
grep "| deny |" .claude/guardrail.log
```

Shows all denied actions.

```bash
grep "| allow |" .claude/guardrail.log
```

Shows all allowed actions.

### Filter by Tool

```bash
grep "PreToolUse:Bash" .claude/guardrail.log
```

Shows all Bash command decisions.

### Filter by Time Range

```bash
grep "2026-03-26 10:" .claude/guardrail.log
```

Shows decisions from 10:00-10:59 on March 26.

### Search for Specific Command

```bash
grep "git push" .claude/guardrail.log
```

Shows all decisions involving `git push`.

## Log Analysis

### Count Decisions by Type

```bash
grep -c "| deny |" .claude/guardrail.log
grep -c "| allow |" .claude/guardrail.log
grep -c "| ask |" .claude/guardrail.log
grep -c "| pass |" .claude/guardrail.log
```

### Most Common Blocked Commands

```bash
grep "| deny |" .claude/guardrail.log | awk -F'|' '{print $2}' | sort | uniq -c | sort -rn | head -10
```

### Layer 2 Usage

```bash
grep "Layer 2" .claude/guardrail.log | wc -l
```

Count how many times LLM was invoked.

### Decisions Over Time

```bash
grep "PreToolUse" .claude/guardrail.log | awk '{print $1}' | uniq -c
```

Shows decision count per day.

## Log Rotation

Guardrail does not automatically rotate logs. To prevent unbounded growth:

### Manual Rotation

```bash
mv .claude/guardrail.log .claude/guardrail.log.old
touch .claude/guardrail.log
```

### Automated Rotation with logrotate

Create `/etc/logrotate.d/guardrail`:

```
/home/user/.claude/guardrail.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
```

### Size-Based Cleanup

```bash
# Keep only last 1000 lines
tail -n 1000 .claude/guardrail.log > .claude/guardrail.log.tmp
mv .claude/guardrail.log.tmp .claude/guardrail.log
```

## Privacy Considerations

**What's logged**:
- Timestamps
- Tool names
- Commands, file paths, URLs
- Decisions and reasons

**What's NOT logged**:
- File contents
- Command output
- API responses
- Secrets (redacted before Layer 2)

**Security**:
- Logs stored locally only
- No network transmission
- User controls retention
- Readable only by user

## Troubleshooting with Logs

### No Log Entries

**Cause**: Hook not firing or log file misconfigured

**Solution**:
- Check hook installation
- Verify log_file path in config
- Check file permissions

### Unexpected Decisions

**Cause**: Rule matching not as expected

**Solution**:
- Review matched rule in log
- Test pattern manually
- Check rule priority (deny > allow > ask)

### Layer 2 Not Appearing

**Cause**: Layer 2 disabled or all commands match Layer 1 rules

**Solution**:
- Check Layer 2 configuration
- Test command that should pass Layer 1
- Verify API key set

### Duplicate Entries

**Cause**: Multiple hooks registered or hook called twice

**Solution**:
- Check settings.json for duplicate hooks
- Verify only one guardrail hook per event
