"""
Create Actions and ActionLog tables in the database.

Run this script to initialize the actions queue database tables.
"""
from sqlalchemy import create_engine
from ospra_os.database.multi_store_models import Base
from ospra_os.database.action_models import Action, ActionLog, AIActionType, AIActionStatus
import os

# Get database URL from environment or use default SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/ospra_os.db")

print(f"📊 Creating Actions Queue tables in database: {DATABASE_URL}")
print()

# Create engine
engine = create_engine(
    DATABASE_URL.replace("postgres://", "postgresql://"),  # Handle Render's postgres:// format
    echo=True  # Print SQL statements
)

# Create all tables (only creates tables that don't exist yet)
print("🔨 Creating tables...")
Base.metadata.create_all(engine)

print()
print("✅ Database tables created successfully!")
print()
print("Tables created:")
print("  - actions: Stores AI-generated actions awaiting user approval")
print("  - action_logs: Audit trail of action status changes")
print()
print("Next steps:")
print("  1. Start the backend server: uv run uvicorn ospra_os.main:app --reload --host 127.0.0.1 --port 8001")
print("  2. Test API endpoints:")
print("     - GET  http://localhost:8001/api/actions")
print("     - GET  http://localhost:8001/api/actions/stats")
print("     - POST http://localhost:8001/api/actions (create test action)")
