"""Analyze Python scripts for read-only safety."""

import ast
import os
import re
from pathlib import Path

# Dangerous system directories to block
DANGEROUS_DIRECTORIES = {
    "/bin", "/sbin", "/usr/bin", "/usr/sbin", "/usr/local/bin",
    "/etc", "/boot", "/sys", "/proc", "/dev",
    "/lib", "/lib64", "/usr/lib", "/usr/lib64",
    "/root", "/var/log", "/var/lib", "/var/run",
}

# Modules that are safe for data processing
SAFE_MODULES = {
    # Data processing
    "pandas", "numpy", "matplotlib", "seaborn", "transformers", "datasets",
    "sklearn", "scipy", "torch", "tensorflow", "keras",
    # Serialization (read-only usage is safe)
    "json", "yaml", "csv", "pickle", "xml",
    # Built-in harmless modules
    "collections", "itertools", "functools", "operator", "math", "statistics",
    "datetime", "time", "re", "string", "textwrap", "difflib",
    "heapq", "bisect", "array", "copy", "pprint", "enum", "dataclasses",
    "typing", "types", "abc", "contextlib", "warnings",
}

# Dangerous operations
DANGEROUS_PATTERNS = [
    r'\bos\.remove\b', r'\bos\.unlink\b', r'\bos\.rmdir\b', r'\bos\.removedirs\b',
    r'\bos\.mkdir\b', r'\bos\.makedirs\b', r'\bshutil\.rmtree\b',
    r'\bsubprocess\.',
    r'\bopen\s*\([^)]*["\']w["\']', r'\bopen\s*\([^)]*["\']a["\']',
    r'\.save\s*\(', r'\.to_json\s*\(', r'\.to_csv\s*\(', r'\.to_pickle\s*\(',
    r'\.to_parquet\s*\(', r'\.to_hdf\s*\(', r'\.to_sql\s*\(',
]


def is_safe_directory(directory: str) -> bool:
    """Check if a directory is safe to navigate into.

    Returns False if directory is a system directory.
    """
    try:
        # Resolve to absolute path
        abs_path = os.path.abspath(directory)

        # Check if it's a dangerous system directory
        for dangerous in DANGEROUS_DIRECTORIES:
            if abs_path == dangerous or abs_path.startswith(dangerous + "/"):
                return False

        return True
    except Exception:
        return False


def is_safe_python_script(script_path: str, working_dir: str | None = None) -> bool:
    """Check if a Python script is safe (read-only data processing).

    Parameters
    ----------
    script_path : str
        Path to the Python script (may be relative)
    working_dir : str, optional
        Working directory to resolve relative paths (default: current dir)

    Returns True if the script only:
    - Imports safe modules
    - Does not write files or modify filesystem
    - Does not use subprocess
    """
    try:
        # Check if working directory is safe
        if working_dir and not is_safe_directory(working_dir):
            return False

        # Resolve path relative to working directory
        if working_dir:
            path = Path(working_dir) / script_path
        else:
            path = Path(script_path)

        if not path.exists() or not path.is_file():
            return False

        content = path.read_text()

        # Check for dangerous patterns in source
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, content):
                return False

        # Parse AST to check imports
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return False

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split('.')[0]
                    if module not in SAFE_MODULES:
                        return False
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module = node.module.split('.')[0]
                    if module not in SAFE_MODULES:
                        return False

        return True
    except Exception:
        return False
