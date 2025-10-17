"""
Single source of truth for the app entrypoint.
We now run the FastAPI app defined in oubon_os.main:app.
"""
from oubon_os.main import app  # uvicorn main:app --reload --port 8011
