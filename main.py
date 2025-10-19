"""
Single source of truth for the app entrypoint.
We now run the FastAPI app defined in ospra_os.main:app.
"""
from ospra_os.main import app  # uvicorn main:app --reload --port 8011
