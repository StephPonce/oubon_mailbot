"""
Back-compat shim: the project has moved to 'oubon_os'.
Importers referencing 'oubonos' will keep working by forwarding to oubon_os.
"""
from oubon_os.main import app  # so 'uvicorn main:app' worked previously; now points to canonical app

# Optional fan-out re-exports so legacy code keeps running if it imported common modules
try:
    from oubon_os.forecaster import *  # noqa: F401,F403
except Exception:
    pass
try:
    from oubon_os.analytics import *  # noqa: F401,F403
except Exception:
    pass
try:
    from oubon_os.scheduler import *  # noqa: F401,F403
except Exception:
    pass
