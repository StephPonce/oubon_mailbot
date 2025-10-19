"""
DEPRECATED shim: import from `ospra_os` instead.
Kept only for backward compatibility.
"""
from importlib import import_module as _imp

def __getattr__(name):
    # Allow: from oubon_os.main import app
    if name == "main":
        return _imp("ospra_os.main")
    raise AttributeError(
        "'oubon_os' is deprecated. Import from 'ospra_os' (missing: {name})."
    )
