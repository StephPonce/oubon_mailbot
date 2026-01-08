# PostgreSQL Migration Testing Guide

## Overview

This guide explains how to test the PostgreSQL migration to ensure the OspraOS application has fully migrated from SQLite to PostgreSQL.

## Changes Made

### 1. Database Connection Layer (`ospra_os/database/connection.py`)
- ✅ Removed SQLite as fallback database
- ✅ Made `DATABASE_URL` environment variable required
- ✅ Added PostgreSQL URL validation
- ✅ Removed SQLite-specific imports and connection pooling
- ✅ Optimized for PostgreSQL production use (connection pooling)

### 2. Render Deployment (`render.yaml`)
- ✅ Added `ospra-db` PostgreSQL database service
- ✅ Configured `DATABASE_URL` environment variable injection
- ✅ Linked database connection to web service

## Testing Strategy

### Option 1: Quick Test (Recommended)
Deploy to Render and verify the migration works in production.

```bash
# Push changes to trigger Render deployment
git push origin main

# Monitor deployment logs at https://dashboard.render.com
# Look for:
#   [SUCCESS] PostgreSQL database initialized
#   URL: <host>:<port>/ospra_intelligence
#   Tables: <count>
```

### Option 2: Local Testing with PostgreSQL

#### Prerequisites
- Local PostgreSQL installation or Docker PostgreSQL container
- PostgreSQL database created

#### Setup Local PostgreSQL (Docker)
```bash
# Start PostgreSQL container
docker run -d \
  --name ospra-postgres \
  -e POSTGRES_USER=ospra \
  -e POSTGRES_PASSWORD=ospra_dev \
  -e POSTGRES_DB=ospra_intelligence \
  -p 5432:5432 \
  postgres:15

# Set DATABASE_URL
export DATABASE_URL="postgresql://ospra:ospra_dev@localhost:5432/ospra_intelligence"
```

#### Run Tests
```bash
# Run comprehensive test suite
uv run python scripts/test_postgresql_migration.py

# Expected output:
# ✅ PASSED: DATABASE_URL is set
# ✅ PASSED: Database connection successful
# ✅ PASSED: Using PostgreSQL dialect
# ✅ PASSED: Tables created successfully
# ✅ PASSED: Connection pooling configured
# ✅ PASSED: Basic queries work
```

### Option 3: Verify Migration Rejects SQLite

This demonstrates that the migration successfully removed SQLite support:

```bash
# Try to use SQLite (should FAIL)
export DATABASE_URL="sqlite:///./test.db"
uv run python scripts/test_postgresql_migration.py

# Expected output:
# ❌ FAILED: Not using PostgreSQL (got: sqlite://...)
```

## Test Script Details

The test script (`scripts/test_postgresql_migration.py`) performs 6 comprehensive checks:

1. **Environment Variables**: Verifies `DATABASE_URL` is set and points to PostgreSQL
2. **Database Connection**: Tests connectivity and health check
3. **Database Type**: Confirms PostgreSQL dialect is being used (not SQLite)
4. **Table Creation**: Verifies all SQLAlchemy tables can be created
5. **Connection Pooling**: Checks pool configuration (not using SQLite's StaticPool)
6. **CRUD Operations**: Tests basic database queries work correctly

## Render Deployment Testing

### 1. Pre-Deployment Checklist

- ✅ Commit PostgreSQL migration changes
- ✅ Push to GitHub main branch
- ✅ Verify `ospra-db` service is active on Render
- ✅ Ensure `DATABASE_URL` environment variable is configured in render.yaml

### 2. Monitor Deployment

Watch the deployment logs for:

```
[SUCCESS] PostgreSQL database initialized
   URL: <host>:<port>/ospra_intelligence
   Tables: <count>
```

### 3. Verify API Health

Once deployed, check the health endpoint:

```bash
curl https://your-render-app.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": {
    "status": "healthy",
    "database_type": "postgresql",
    "url_masked": "<host>:<port>/ospra_intelligence"
  }
}
```

### 4. Check Database Connection

Verify database tables were created:

```bash
# SSH into Render shell (if needed)
# Or use Render's PostgreSQL dashboard to view tables
```

## Troubleshooting

### Error: "DATABASE_URL environment variable is required"

**Cause**: `DATABASE_URL` not set

**Fix**:
```bash
export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
```

### Error: "Invalid database URL. PostgreSQL required"

**Cause**: Attempting to use SQLite or invalid URL format

**Fix**: Ensure DATABASE_URL starts with `postgresql://` or `postgres://`

### Error: "Database connection failed"

**Possible causes**:
1. PostgreSQL service not running
2. Incorrect credentials
3. Database doesn't exist
4. Network/firewall issues

**Fix**:
```bash
# Verify PostgreSQL is running
psql -U ospra -d ospra_intelligence -h localhost

# Check credentials in DATABASE_URL
echo $DATABASE_URL
```

### Error: Connection pooling issues

**Symptom**: "Too many connections" or pool timeout errors

**Fix**: Adjust pool settings in `ospra_os/database/connection.py`:
```python
{
    "pool_size": 5,        # Default 5, increase if needed
    "max_overflow": 10,    # Default 10
    "pool_recycle": 3600,  # Recycle after 1 hour
}
```

## Migration Verification Checklist

- [ ] ✅ Commit and push PostgreSQL migration changes
- [ ] ✅ Render deployment successful (no errors)
- [ ] ✅ Health endpoint shows `database_type: postgresql`
- [ ] ✅ Application starts without errors
- [ ] ✅ Database tables created (check Render dashboard)
- [ ] ✅ API endpoints working correctly
- [ ] ✅ Local test script passes (optional)

## Rollback Plan (If Needed)

If the migration fails, you can temporarily rollback:

```bash
# Revert the commits
git revert HEAD~2..HEAD

# Push the revert
git push origin main
```

However, the migration should work smoothly as:
1. PostgreSQL drivers were already installed
2. SQLAlchemy models are database-agnostic
3. Connection pooling is optimized for PostgreSQL

## Next Steps

After successful migration:

1. **Monitor Performance**: Check database query performance
2. **Setup Backups**: Configure automatic PostgreSQL backups on Render
3. **Optimize Queries**: Use PostgreSQL-specific optimizations if needed
4. **Clean Up**: Remove any remaining SQLite `.db` files locally

## Support

If you encounter issues:

1. Check Render deployment logs
2. Review `ospra_os/database/connection.py` for connection errors
3. Verify PostgreSQL service is active on Render dashboard
4. Run local test script for detailed diagnostics

---

**Migration Status**: ✅ Complete

**Deployed**: Ready to deploy to Render

**Tested**: Use test script to verify
