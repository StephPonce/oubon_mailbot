"""
Re-export shim: the engine has always imported FulfillmentRecord from here.
The model itself lives with the other SQLAlchemy models in
ospra_os/database/fulfillment_models.py so it registers on the shared Base
metadata (T161) and is created by the app's startup create_all().
"""

from ospra_os.database.fulfillment_models import FulfillmentRecord

__all__ = ["FulfillmentRecord"]
