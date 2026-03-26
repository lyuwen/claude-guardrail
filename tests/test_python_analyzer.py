import tempfile
from pathlib import Path
from guardrail.python_analyzer import is_safe_python_script


class TestPythonAnalyzer:
    def test_safe_script_with_pandas(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("import pandas as pd\ndf = pd.read_csv('data.csv')\nprint(df.head())")
            f.flush()
            assert is_safe_python_script(f.name) is True
            Path(f.name).unlink()

    def test_safe_script_with_numpy(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("import numpy as np\narr = np.array([1,2,3])\nprint(arr)")
            f.flush()
            assert is_safe_python_script(f.name) is True
            Path(f.name).unlink()

    def test_unsafe_script_with_os_remove(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("import os\nos.remove('file.txt')")
            f.flush()
            assert is_safe_python_script(f.name) is False
            Path(f.name).unlink()

    def test_unsafe_script_with_subprocess(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("import subprocess\nsubprocess.run(['ls'])")
            f.flush()
            assert is_safe_python_script(f.name) is False
            Path(f.name).unlink()

    def test_unsafe_script_with_file_write(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("with open('out.txt', 'w') as f:\n    f.write('data')")
            f.flush()
            assert is_safe_python_script(f.name) is False
            Path(f.name).unlink()

    def test_unsafe_script_with_to_csv(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("import pandas as pd\ndf = pd.DataFrame()\ndf.to_csv('out.csv')")
            f.flush()
            assert is_safe_python_script(f.name) is False
            Path(f.name).unlink()

    def test_unsafe_script_with_unknown_import(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("import requests\nrequests.get('http://example.com')")
            f.flush()
            assert is_safe_python_script(f.name) is False
            Path(f.name).unlink()

    def test_nonexistent_file(self):
        assert is_safe_python_script('/nonexistent/script.py') is False

    def test_invalid_syntax(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("import pandas\nthis is not valid python")
            f.flush()
            assert is_safe_python_script(f.name) is False
            Path(f.name).unlink()
