# Guardrail Security Model

## Threat Model

### Threats Guardrail Addresses

1. **Accidental Destruction**
   - User accidentally runs destructive command
   - Typo in command (e.g., `rm -rf . /` instead of `rm -rf ./`)
   - Copy-paste error from untrusted source
   - Misunderstanding command behavior

2. **Prompt Injection Attacks**
   - Malicious content in files read by Claude
   - Crafted web pages instructing dangerous actions
   - Hidden commands in documentation
   - Social engineering via context

3. **Indirect Execution**
   - Commands wrapped in `eval` or `exec`
   - Base64-encoded malicious payloads
   - Chained commands hiding dangerous operations
   - PATH manipulation to run malicious binaries

4. **Unintended Side Effects**
   - Scripts with hidden destructive behavior
   - Commands with unexpected consequences
   - Operations on wrong files/directories
   - Cascading failures

### Threats Outside Scope

1. **Determined Malicious Users**
   - Users can disable hooks entirely
   - Users can modify guardrail code
   - Users have full system access

2. **Zero-Day Exploits**
   - Novel attack vectors not in deny rules
   - Undiscovered command behaviors
   - New tools not yet guarded

3. **Non-Tool Attacks**
   - Direct file manipulation by Claude
   - Memory corruption
   - Network attacks
   - Physical access

4. **Social Engineering**
   - User approves dangerous action after prompt
   - User trusts malicious advice
   - User misconfigures guardrail

## Security Layers

### Layer 1: Deny Rules (Preventive)

**Purpose**: Block known-dangerous operations immediately

**Strength**: Fast, deterministic, no false negatives for known patterns

**Weakness**: Cannot detect novel attacks, requires maintenance

**Examples**:
- `rm -rf /` → DENY
- `:(){ :|:& };:` (fork bomb) → DENY
- `dd if=/dev/zero of=/dev/sda` → DENY
- `eval rm -rf /` → DENY (indirect execution)

**Bypass resistance**: High for listed patterns, zero for unlisted

### Layer 2: Allow Rules (Efficiency)

**Purpose**: Auto-approve known-safe operations

**Strength**: Reduces user friction, improves productivity

**Weakness**: Overly broad rules could allow dangerous variants

**Examples**:
- `git status` → ALLOW
- `ls -la` → ALLOW
- `cat file.txt` → ALLOW

**Bypass resistance**: N/A (only approves, never blocks)

### Layer 3: Ask Rules (User Judgment)

**Purpose**: Prompt for potentially dangerous but legitimate operations

**Strength**: Balances security and usability

**Weakness**: Users may approve without careful review

**Examples**:
- `python script.py` → ASK
- `git push` → ASK
- `npm install` → ASK

**Bypass resistance**: Depends on user vigilance

### Layer 4: LLM Classification (Adaptive)

**Purpose**: Detect novel attacks and context-dependent threats

**Strength**: Adapts to new patterns, considers context

**Weakness**: Slower, costs money, can be fooled

**Examples**:
- `curl -X DELETE https://api.example.com/users` → DENY (destructive API call)
- `docker run ubuntu` → ALLOW (safe container)
- `bash deploy.sh` → ASK (script execution)

**Bypass resistance**: Medium (adversarial prompts possible)

### Layer 5: User Confirmation (Final Defense)

**Purpose**: User makes final decision

**Strength**: Human judgment, context awareness

**Weakness**: User fatigue, social engineering

**Bypass resistance**: Depends entirely on user

## Attack Scenarios

### Scenario 1: Malicious Documentation

**Attack**: Web page instructs Claude to run `rm -rf /`

**Defense**:
1. Layer 1 deny rule blocks immediately
2. User never sees prompt
3. Action logged for audit

**Result**: ✓ Blocked

### Scenario 2: Obfuscated Command

**Attack**: `eval $(echo cm0gLXJmIC8K | base64 -d)` (decodes to `rm -rf /`)

**Defense**:
1. Layer 1 deny rule matches `eval` pattern
2. Blocked before execution
3. Even if eval allowed, base64 piping pattern also blocked

**Result**: ✓ Blocked

### Scenario 3: PATH Manipulation

**Attack**: `/usr/bin/rm -rf /` (trying to bypass `^rm` pattern)

**Defense**:
1. Layer 1 deny rules use `(^|.*/)rm\s+-rf\s+/` pattern
2. Matches both `rm` and `/path/to/rm`
3. Blocked immediately

**Result**: ✓ Blocked

### Scenario 4: Novel Destructive API Call

**Attack**: `curl -X POST https://api.example.com/delete-all-data`

**Defense**:
1. Layer 1 has no rule (unknown command)
2. Layer 2 LLM analyzes: "delete-all-data endpoint is destructive"
3. Returns ASK decision
4. User prompted for confirmation

**Result**: ✓ Detected, user decides

### Scenario 5: Legitimate Deployment Script

**Attack**: Not an attack - `bash deploy.sh` for legitimate deployment

**Defense**:
1. Layer 1 ask rule matches `bash` pattern
2. User prompted: "bash deploy.sh"
3. User approves (legitimate use)
4. Action logged

**Result**: ✓ Allowed with confirmation

### Scenario 6: Social Engineering

**Attack**: Malicious prompt convinces user to approve dangerous action

**Defense**:
1. Layers 1-4 may detect and block
2. If reaches user, depends on user judgment
3. Audit log records decision

**Result**: ⚠ Depends on user

### Scenario 7: Adversarial LLM Prompt

**Attack**: Crafted command designed to fool Layer 2 LLM

**Defense**:
1. Sanitization removes secrets before LLM
2. LLM prompt emphasizes security
3. Falls back to user prompt if LLM passes
4. Audit log records decision

**Result**: ⚠ Partial protection

## Security Properties

### Confidentiality

**Secrets never sent to LLM**:
- API keys redacted
- Tokens redacted
- File contents excluded
- Passwords redacted

**Audit logs**:
- Stored locally only
- No network transmission
- User controls retention

### Integrity

**Config protection**:
- Default deny rules cannot be removed
- User configs additive only
- Deny rules always win

**Hook integrity**:
- Runs in user's environment
- No privilege escalation
- Fail-open on errors

### Availability

**Fail-open design**:
- Bugs never block users
- Missing config passes through
- LLM errors pass through
- Network failures pass through

**Performance**:
- Layer 1 adds <1ms latency
- Layer 2 adds 200-1000ms (optional)
- No blocking operations

## Limitations

### Known Limitations

1. **User can disable**: Hooks can be removed from settings.json
2. **Bypass via other tools**: Only guards specific tools
3. **Novel attacks**: Requires rule updates
4. **LLM fallibility**: Can be fooled by adversarial prompts
5. **User fatigue**: Too many prompts reduce vigilance

### Not a Sandbox

Guardrail is NOT a sandbox or security boundary:
- User has full system access
- Claude has full system access (when approved)
- No privilege separation
- No mandatory access control

### Appropriate Use Cases

✓ **Good for**:
- Preventing accidents
- Detecting prompt injection
- Audit trail for actions
- Reducing attack surface

✗ **Not good for**:
- Untrusted users
- Untrusted code execution
- Security boundaries
- Compliance requirements

## Best Practices

### For Users

1. **Review prompts carefully**: Don't auto-approve
2. **Keep rules updated**: Add project-specific deny rules
3. **Enable Layer 2**: LLM classification catches novel attacks
4. **Monitor logs**: Review `.claude/guardrail.log` periodically
5. **Report bypasses**: Help improve deny rules

### For Administrators

1. **Customize deny rules**: Add organization-specific patterns
2. **Disable in bypass mode**: For trusted automation
3. **Audit logs regularly**: Detect suspicious patterns
4. **Update guardrail**: Get latest security rules
5. **Train users**: Explain threat model and limitations

### For Developers

1. **Add deny rules**: For new dangerous commands
2. **Test bypasses**: Try to fool guardrail
3. **Improve LLM prompt**: Better adversarial resistance
4. **Extend sanitization**: Redact more secret patterns
5. **Document limitations**: Be transparent about scope

## Comparison to Other Security Tools

### vs. Sandboxes (Firejail, Docker)

**Guardrail**: Lightweight, fail-open, user-friendly
**Sandbox**: Heavy, fail-closed, security-focused

**Use guardrail for**: Development assistance
**Use sandbox for**: Untrusted code execution

### vs. SELinux/AppArmor

**Guardrail**: Application-level, configurable, optional
**SELinux**: Kernel-level, mandatory, complex

**Use guardrail for**: AI assistant safety
**Use SELinux for**: System-wide security policy

### vs. Antivirus

**Guardrail**: Proactive, blocks before execution
**Antivirus**: Reactive, detects after execution

**Use guardrail for**: Preventing AI-initiated actions
**Use antivirus for**: Detecting malware

### vs. Firewall

**Guardrail**: Application actions
**Firewall**: Network traffic

**Use guardrail for**: Tool execution control
**Use firewall for**: Network access control

## Conclusion

Guardrail provides defense-in-depth for AI assistant tool execution:

1. **Fast deny rules** block known threats
2. **LLM classification** adapts to novel threats
3. **User confirmation** provides final judgment
4. **Audit logging** enables detection and response

It is NOT a security boundary, but a safety net for development workflows.

Appropriate for: Preventing accidents, detecting prompt injection, reducing attack surface

Not appropriate for: Untrusted users, security boundaries, compliance requirements
