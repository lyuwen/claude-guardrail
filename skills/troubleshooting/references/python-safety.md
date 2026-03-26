# Python Script Safety Analysis

## Overview

Guardrail analyzes Python scripts to determine if they can be auto-allowed or require user confirmation. Analysis uses AST parsing to check imports and source code patterns.

## Safety Criteria

A Python script is considered safe if ALL of these are true:

1. **All imports are whitelisted** - Only safe, read-only modules
2. **No dangerous patterns** - No file writes, subprocess, network operations
3. **File exists and is readable** - Script can be analyzed
4. **Valid Python syntax** - AST parsing succeeds

If any criterion fails, script requires "ask" decision.

## Whitelisted Modules

### Data Analysis (Safe)

```python
import pandas
import numpy
import scipy
import sklearn
import statsmodels
```

**Why safe**: Read-only data processing, no side effects

### Visualization (Safe)

```python
import matplotlib
import seaborn
import plotly
```

**Why safe**: Generate plots, no system modification

### Standard Library (Safe)

```python
import json
import yaml
import csv
import collections
import itertools
import functools
import math
import statistics
import datetime
import re
import pathlib
import typing
import dataclasses
import enum
import abc
import contextlib
import copy
import pprint
import textwrap
import string
```

**Why safe**: Read-only operations, no dangerous capabilities

### Conditional (Safe with restrictions)

```python
import random  # Safe if no seed manipulation
```

**Why safe**: Deterministic randomness acceptable for analysis

## Non-Whitelisted Modules

### File System Operations

```python
import os          # Can delete files, run commands
import shutil      # Can delete directories
import pathlib     # Can modify filesystem (some operations)
import tempfile    # Creates files
```

**Why dangerous**: File system modification

### Subprocess Execution

```python
import subprocess  # Can run arbitrary commands
import os          # os.system(), os.exec*()
```

**Why dangerous**: Command execution

### Network Operations

```python
import requests    # HTTP requests
import urllib      # URL operations
import socket      # Network sockets
import http        # HTTP client/server
import ftplib      # FTP operations
```

**Why dangerous**: External communication

### Database Operations

```python
import sqlite3     # Database modification
import psycopg2    # PostgreSQL
import pymongo     # MongoDB
```

**Why dangerous**: Data modification

## Dangerous Patterns

### File Writes

```python
# Pattern: open(..., 'w')
with open('file.txt', 'w') as f:
    f.write('data')

# Pattern: open(..., 'a')
with open('file.txt', 'a') as f:
    f.write('data')

# Pattern: .save()
df.to_csv('output.csv')
model.save('model.pkl')

# Pattern: .to_*()
df.to_excel('output.xlsx')
df.to_json('output.json')
```

**Why dangerous**: Creates or modifies files

### OS Operations

```python
# Pattern: os.remove()
os.remove('file.txt')

# Pattern: os.mkdir()
os.mkdir('directory')

# Pattern: shutil.*
shutil.rmtree('directory')
shutil.copy('src', 'dst')
```

**Why dangerous**: File system modification

### Subprocess

```python
# Pattern: subprocess.*
subprocess.run(['ls', '-la'])
subprocess.Popen(['command'])

# Pattern: os.system()
os.system('ls -la')
```

**Why dangerous**: Command execution

### Network

```python
# Pattern: requests.*
requests.get('https://api.example.com')
requests.post('https://api.example.com', data={})

# Pattern: urllib.*
urllib.request.urlopen('https://example.com')

# Pattern: socket.*
socket.socket(socket.AF_INET, socket.SOCK_STREAM)
```

**Why dangerous**: External communication

## Analysis Process

### Step 1: File Existence

```python
if not os.path.exists(script_path):
    return False, "Script file not found"
```

Script must exist and be readable.

### Step 2: Syntax Validation

```python
try:
    with open(script_path) as f:
        ast.parse(f.read())
except SyntaxError:
    return False, "Invalid Python syntax"
```

Script must be valid Python.

### Step 3: Import Analysis

```python
imports = []
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        imports.extend([alias.name for alias in node.names])
    elif isinstance(node, ast.ImportFrom):
        imports.append(node.module)

non_whitelisted = [imp for imp in imports if imp not in SAFE_MODULES]
if non_whitelisted:
    return False, f"Non-whitelisted imports: {non_whitelisted}"
```

All imports must be whitelisted.

### Step 4: Pattern Analysis

```python
source = open(script_path).read()

dangerous_patterns = [
    r"open\s*\([^)]*['\"]w['\"]",  # File write
    r"\.to_csv\s*\(",               # DataFrame save
    r"os\.remove\s*\(",             # File delete
    r"subprocess\.",                # Subprocess
    r"requests\.",                  # HTTP requests
]

for pattern in dangerous_patterns:
    if re.search(pattern, source):
        return False, f"Dangerous pattern: {pattern}"
```

Source must not contain dangerous operations.

### Step 5: Decision

```python
if all_checks_pass:
    return True, "Safe script"
else:
    return False, "Reason for failure"
```

## Examples

### Safe Script

```python
# script.py
import pandas as pd
import numpy as np

df = pd.read_csv('data.csv')
print(df.describe())
print(df.mean())
```

**Analysis**:
- ✓ Imports: pandas, numpy (whitelisted)
- ✓ No file writes
- ✓ No subprocess
- ✓ No network operations

**Decision**: ALLOW (auto-approved)

### Unsafe Script (File Write)

```python
# script.py
import pandas as pd

df = pd.read_csv('data.csv')
df.to_csv('output.csv')  # File write
```

**Analysis**:
- ✓ Imports: pandas (whitelisted)
- ✗ File write: `.to_csv()`

**Decision**: ASK (user confirmation required)

### Unsafe Script (Non-Whitelisted Import)

```python
# script.py
import os
import pandas as pd

df = pd.read_csv('data.csv')
print(df.describe())
```

**Analysis**:
- ✗ Imports: os (not whitelisted)
- ✓ No dangerous patterns in source

**Decision**: ASK (user confirmation required)

### Unsafe Script (Subprocess)

```python
# script.py
import subprocess
import pandas as pd

subprocess.run(['ls', '-la'])  # Command execution
df = pd.read_csv('data.csv')
```

**Analysis**:
- ✗ Imports: subprocess (not whitelisted)
- ✗ Dangerous pattern: `subprocess.`

**Decision**: ASK (user confirmation required)

### Unsafe Script (Network)

```python
# script.py
import requests
import pandas as pd

response = requests.get('https://api.example.com/data')  # Network
df = pd.DataFrame(response.json())
```

**Analysis**:
- ✗ Imports: requests (not whitelisted)
- ✗ Dangerous pattern: `requests.`

**Decision**: ASK (user confirmation required)

## Testing Script Safety

### Manual Test

```bash
python3 -c "
from guardrail.python_analyzer import is_safe_python_script
safe, reason = is_safe_python_script('script.py')
print(f'Safe: {safe}')
print(f'Reason: {reason}')
"
```

### Check Imports

```bash
python3 -c "
import ast
with open('script.py') as f:
    tree = ast.parse(f.read())

imports = []
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        imports.extend([alias.name for alias in node.names])
    elif isinstance(node, ast.ImportFrom):
        imports.append(node.module)

print('Imports:', imports)
"
```

### Check for Dangerous Patterns

```bash
python3 -c "
from guardrail.python_analyzer import _has_dangerous_patterns
with open('script.py') as f:
    source = f.read()
print('Has dangerous patterns:', _has_dangerous_patterns(source))
"
```

## Bypassing Analysis

### Option 1: Add to Allow Rules

If script is safe but uses non-whitelisted imports:

```yaml
# .claude/guardrail.yml
allow_rules:
  bash:
    - "^python3 /path/to/safe-script\\.py$"
```

### Option 2: Approve Once

When prompted, approve the script. Guardrail will remember for the session.

### Option 3: Remove Non-Whitelisted Imports

Refactor script to use only whitelisted modules:

```python
# Before (uses os)
import os
files = os.listdir('.')

# After (uses pathlib)
from pathlib import Path
files = [f.name for f in Path('.').iterdir()]
```

## Limitations

### False Positives

Scripts may be flagged as unsafe even if they're actually safe:

```python
# Flagged as unsafe (has 'requests' in comment)
import pandas as pd
# This script makes no requests
df = pd.read_csv('data.csv')
```

**Workaround**: Remove misleading comments or add to allow rules.

### False Negatives

Scripts may be flagged as safe even if they're dangerous:

```python
# Flagged as safe (indirect execution)
import pandas as pd
exec("import os; os.system('rm -rf /')")
```

**Mitigation**: Layer 2 LLM may catch this, or user review.

### Dynamic Imports

Dynamic imports not detected:

```python
# Not detected by AST analysis
__import__('os').system('ls')
```

**Mitigation**: Dangerous pattern detection may catch this.

## Best Practices

### For Safe Scripts

1. Use only whitelisted modules
2. Avoid file writes (use print/display instead)
3. No subprocess or network operations
4. Read-only data analysis

### For Scripts Requiring Approval

1. Document why non-whitelisted imports needed
2. Minimize dangerous operations
3. Add to allow rules if repeatedly used
4. Consider refactoring to use whitelisted modules

### For Guardrail Configuration

1. Add project-specific safe scripts to allow rules
2. Don't disable Python analysis entirely
3. Review scripts before approving
4. Monitor logs for patterns
