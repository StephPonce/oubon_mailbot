# Ospra Intelligence - Database Deployment Guide

## Overview

Ospra Intelligence uses **Alembic** for database migrations and **PostgreSQL** in production.

---

## Quick Reference

```bash
# Check current migration status
alembic current

# Create a new migration (auto-detect changes)
alembic revision --autogenerate -m "Add new_column to users"

# Apply migrations to database
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

---

## Pre-Deployment Checklist

Before deploying to production:

- [ ] **Run migrations locally against PostgreSQL** (not SQLite)
  ```bash
  DATABASE_URL="postgresql://..." alembic upgrade head
  ```

- [ ] **Run full test suite**
  ```bash
  pytest tests/ -v
  ```

- [ ] **Check for circular FK dependencies**
  - Self-referential FKs need `use_alter=True`
  - Cross-table circular FKs need `use_alter=True` on one side

- [ ] **Verify all models are imported in `alembic/env.py`**
  - New model files must be added to the imports

- [ ] **Test registration endpoint locally**
  ```bash
  curl -X POST http://localhost:8000/api/auth/register \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"test123","name":"Test"}'
  ```

---

## Common Issues & Solutions

### 1. "relation does not exist" Error

**Cause:** Tables weren't created in PostgreSQL.

**Solution:**
```bash
# In Render Shell
python -c "
from ospra_os.database.connection import init_database
init_database()
"
```

### 2. CircularDependencyError

**Cause:** Two tables reference each other with ForeignKeys.

**Solution:** Add `use_alter=True` to one of the FKs:
```python
# Before (broken)
parent_id = Column(Integer, ForeignKey("same_table.id"))

# After (fixed)
parent_id = Column(Integer, ForeignKey("same_table.id", use_alter=True, name="fk_parent"))
```

### 3. InvalidForeignKey Error

**Cause:** FK references a column that isn't unique/primary key.

**Solution:** Add `unique=True` to the referenced column or use `use_alter=True`.

### 4. Models Not Creating Tables

**Cause:** Model file not imported before `create_all()`.

**Solution:** Add import to `_import_all_models()` in `connection.py`.

---

## Database Architecture

```
Production (Render):
├── PostgreSQL 16
├── Connection pooling (5 + 10 overflow)
└── psycopg2 driver (synchronous)

Local Development:
└── SQLite (./data/ospra_local.db)
```

### Critical Tables

These MUST exist for the app to function:
- `users` - User accounts & authentication
- `stores` - Shopify store connections
- `products` - Product catalog
- `user_settings` - User preferences

---

## Creating New Migrations

### 1. Make Your Model Changes

```python
# ospra_os/database/user_models.py
class User(Base):
    # ... existing fields ...
    new_field = Column(String(255), nullable=True)  # NEW
```

### 2. Generate Migration

```bash
alembic revision --autogenerate -m "Add new_field to users"
```

### 3. Review the Migration

Check `alembic/versions/` for the new file. Verify:
- Correct table/column names
- Correct data types
- No destructive changes you didn't intend

### 4. Test Locally

```bash
# Against local SQLite
alembic upgrade head

# Against PostgreSQL (recommended)
DATABASE_URL="postgresql://..." alembic upgrade head
```

### 5. Commit & Deploy

```bash
git add alembic/versions/
git commit -m "migration: Add new_field to users"
git push
```

---

## Emergency Recovery

### Reset Database (Nuclear Option)

**⚠️ WARNING: This deletes ALL data!**

```bash
# In Render Shell
python -c "
from ospra_os.database.connection import get_engine
from sqlalchemy import text

engine = get_engine()
with engine.connect() as conn:
    result = conn.execute(text('''
        SELECT tablename FROM pg_tables WHERE schemaname = 'public'
    '''))
    tables = [row[0] for row in result]
    for table in tables:
        conn.execute(text(f'DROP TABLE IF EXISTS \"{table}\" CASCADE'))
    conn.commit()
print('All tables dropped')

# Now recreate
from ospra_os.database.connection import init_database
init_database()
"
```

### Stamp Current Schema

If database has tables but Alembic doesn't know about them:

```bash
alembic stamp head
```

---

## Health Check

The `/health` endpoint includes database status:

```bash
curl https://ospra-intelligence-api.onrender.com/health
```

Response:
```json
{
  "status": "ok",
  "database": "postgresql",
  "version": "2026-01-14"
}
```

---

## Contacts

- **Database Issues:** Check Render Dashboard → ospra-db → Logs
- **Migration Issues:** Review `alembic/versions/` files
- **Schema Errors:** Check model files in `ospra_os/database/`
