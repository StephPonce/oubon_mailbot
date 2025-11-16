# Multi-Store Testing Guide

Quick reference for testing the multi-store backend.

---

## 🚀 Quick Start

### Run the test suite:

```bash
cd /path/to/oubon_mailbot
uv run python test_multi_store.py
```

**Expected output:**
```
Multi-Store Backend Test Suite
Testing: http://localhost:8001

✅ PASS  Health Check
✅ PASS  Portfolio Overview
✅ PASS  Store Rankings
✅ PASS  Get Store Details
✅ PASS  Add Store
✅ PASS  Update Store
✅ PASS  Switch Store
✅ PASS  Delete Store

Results: 8/8 tests passed
🎉 ALL TESTS PASSED!
```

---

## 📋 Prerequisites

### 1. Backend must be running:

```bash
uv run uvicorn ospra_os.main:app --reload --host 127.0.0.1 --port 8001
```

### 2. Database must be initialized:

```bash
./multi-store --migrate --yes
```

Or the test script will fail with:
```
❌ Backend is not running!
```

---

## 🧪 What Gets Tested

### 8 Comprehensive Tests

1. **Health Check** - Verifies multi-store module is loaded
2. **Portfolio Overview** - Tests aggregated metrics endpoint
3. **Store Rankings** - Tests ranked store list endpoint
4. **Get Store Details** - Tests retrieving individual store
5. **Add Store** - Tests creating a new store (Amazon test store)
6. **Update Store** - Tests updating store name and niche
7. **Switch Store** - Tests changing active store (rank switching)
8. **Delete Store** - Tests deleting the test store (cleanup)

### All API Endpoints Covered

```
✅ GET    /health
✅ GET    /api/portfolio/overview
✅ GET    /api/portfolio/rankings
✅ GET    /api/portfolio/stores/{id}
✅ POST   /api/portfolio/stores/add
✅ PUT    /api/portfolio/stores/{id}
✅ POST   /api/portfolio/stores/{id}/switch
✅ DELETE /api/portfolio/stores/{id}
```

---

## 📊 Test Output Explained

### Color-Coded Results

- **Green (✅)** - Test passed
- **Red (❌)** - Test failed
- **Yellow** - Test name/section header
- **Blue** - Section dividers

### Sample Output

```
TEST: Add New Store
----------------------------------------------------------------------
✅ Store created (ID: 2)

   Name: Test Amazon Store
   Platform: amazon
   Rank: #2
```

This means:
- The POST request succeeded
- A new store was created with ID 2
- It was assigned rank #2 (after Oubon Shop)

---

## 🔧 Manual Testing

### Using curl

#### 1. Check Health
```bash
curl http://localhost:8001/health | python3 -m json.tool
```

#### 2. Get Portfolio Overview
```bash
curl http://localhost:8001/api/portfolio/overview | python3 -m json.tool
```

#### 3. Get Store Rankings
```bash
curl http://localhost:8001/api/portfolio/rankings | python3 -m json.tool
```

#### 4. Add a New Store
```bash
curl -X POST http://localhost:8001/api/portfolio/stores/add \
  -H "Content-Type: application/json" \
  -d '{
    "store_name": "My Amazon Store",
    "store_url": "amazon.com/sp?seller=ABC",
    "platform": "amazon",
    "credentials": {
      "seller_id": "ABC123",
      "mws_token": "amzn.mws.token",
      "marketplace_id": "ATVPDKIKX0DER"
    },
    "niche": "electronics"
  }' | python3 -m json.tool
```

#### 5. Update a Store
```bash
curl -X PUT http://localhost:8001/api/portfolio/stores/2 \
  -H "Content-Type: application/json" \
  -d '{
    "store_name": "Updated Name",
    "niche": "new_niche"
  }' | python3 -m json.tool
```

#### 6. Switch Active Store
```bash
curl -X POST http://localhost:8001/api/portfolio/stores/2/switch | python3 -m json.tool
```

#### 7. Delete a Store
```bash
curl -X DELETE http://localhost:8001/api/portfolio/stores/2
```

---

## 🌐 Using the API Documentation

### Interactive Swagger UI

Visit: **http://localhost:8001/docs**

Features:
- ✅ Try out all endpoints directly in browser
- ✅ See request/response schemas
- ✅ Test with different parameters
- ✅ View validation errors

**How to use:**
1. Click on any endpoint
2. Click "Try it out"
3. Fill in the parameters
4. Click "Execute"
5. View the response

---

## 🐛 Troubleshooting

### Backend Not Running

**Error:**
```
❌ Backend is not running!
```

**Solution:**
```bash
# Start the backend
uv run uvicorn ospra_os.main:app --reload --host 127.0.0.1 --port 8001

# Verify it's running
curl http://localhost:8001/health
```

### Multi-Store Not Loaded

**Error:**
```
{
  "multi_store_loaded": false
}
```

**Solution:**
Check backend logs for initialization errors:
```bash
tail -f logs/backend.log | grep "Multi-Store"
```

Should see:
```
✅ Multi-Store Portfolio router loaded successfully
✅ Multi-Store database initialized
```

### Database Not Initialized

**Error:**
```
sqlalchemy.exc.OperationalError: no such table: users
```

**Solution:**
```bash
# Initialize the database
./multi-store --migrate --yes

# Or manually
PYTHONPATH=. uv run python ospra_os/database/init_multi_store.py --migrate --yes
```

### Import Errors

**Error:**
```
ModuleNotFoundError: No module named 'requests'
```

**Solution:**
```bash
# Use uv to run the script
uv run python test_multi_store.py

# Or install requests
uv add requests
```

---

## 📈 Test Results Interpretation

### All Tests Passed (8/8)

```
Results: 8/8 tests passed
🎉 ALL TESTS PASSED!
```

**Meaning:**
- ✅ Backend is working correctly
- ✅ All endpoints functional
- ✅ Database operations successful
- ✅ Ready for production

### Some Tests Failed (e.g., 6/8)

```
Results: 6/8 tests passed
⚠️  Some tests failed
```

**Action:**
1. Review which tests failed
2. Check error messages
3. Verify backend logs
4. Fix issues and re-run

---

## 🔄 Running Tests Repeatedly

The test script is **idempotent** - safe to run multiple times:

```bash
# Run once
uv run python test_multi_store.py

# Run again
uv run python test_multi_store.py

# Run as many times as needed
uv run python test_multi_store.py
```

**What happens:**
- Creates test store
- Tests all operations
- Deletes test store (cleanup)
- Original data unchanged

---

## 📝 Test Script Structure

### Main Functions

```python
test_health_check()        # Verify backend is up
test_portfolio_overview()  # Test overview endpoint
test_store_rankings()      # Test rankings endpoint
test_get_store()          # Test get store details
test_add_store()          # Test creating store
test_update_store()       # Test updating store
test_switch_store()       # Test switching active store
test_delete_store()       # Test deleting store
```

### Customization

Edit `/test_multi_store.py` to:
- Add more test cases
- Change test data
- Modify assertions
- Add new endpoints

---

## ✅ Success Criteria

### All Tests Should Pass If:

- ✅ Backend running on http://localhost:8001
- ✅ Multi-store router loaded
- ✅ Database initialized with tables
- ✅ Default user exists (steph@oubonshop.com)
- ✅ At least one store exists (Oubon Shop)
- ✅ All endpoints responding correctly
- ✅ Database operations working

---

## 🎯 Next Steps After Testing

Once all tests pass:

1. **Verify Database State**
   ```bash
   ./multi-store --status
   ```

2. **View API Documentation**
   - Open http://localhost:8001/docs
   - Explore all endpoints
   - Try them out interactively

3. **Add Real Stores**
   - Use POST /api/portfolio/stores/add
   - Add your actual Shopify, Amazon, etc. stores

4. **Build Frontend**
   - Consume the API endpoints
   - Create dashboard UI
   - Show portfolio metrics

5. **Monitor Performance**
   - Check response times
   - Monitor database size
   - Set up logging

---

## 📚 Related Documentation

- **Test Results:** `/MULTI_STORE_TEST_RESULTS.md`
- **Integration Guide:** `/MULTI_STORE_INTEGRATION_COMPLETE.md`
- **API Reference:** `/ospra_os/dashboard/MULTI_STORE_API.md`
- **Database Guide:** `/ospra_os/database/README.md`
- **Migration Guide:** `/ospra_os/database/INIT_MIGRATION_GUIDE.md`

---

**Quick Commands:**

```bash
# Run tests
uv run python test_multi_store.py

# Check backend
curl http://localhost:8001/health

# View status
./multi-store --status

# View API docs
open http://localhost:8001/docs
```

---

**Built with FastAPI + SQLAlchemy + Python Requests**
**Part of OspraOS Multi-Store System**
