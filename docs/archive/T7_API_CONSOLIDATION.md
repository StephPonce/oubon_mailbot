# T7: API Route Consolidation & Organization

**Status:** ✅ ANALYSIS COMPLETE - Ready for Implementation
**Date:** 2025-12-12
**Priority:** Medium (Quality of Life Improvement)

## Executive Summary

The route audit reveals a relatively clean API structure with only 26 routes across 2 files. This is **GOOD NEWS** - your API is already well-organized!

**UPDATE (2025-12-12):** Manual code review confirms that **ALL 26 routes already have proper authentication** via `Depends(get_current_user)`. The initial audit script had a bug in detecting authentication (it checked type annotations instead of default values).

## Current State (Audit Results)

### Route Distribution
- **Total Routes:** 26
- **Files with Routes:** 2
  - `ospra_os/api/task_routes.py` - 12 routes (Celery task management)
  - `ospra_os/api/template_routes.py` - 14 routes (Template marketplace)

### Issues Found

#### 1. ~~Missing Authentication (13 routes)~~ ✅ RESOLVED
**Severity:** ~~🔴 HIGH~~ ✅ **FIXED**

**Manual verification confirms:** ALL routes already have authentication properly implemented using `user: User = Depends(get_current_user)`.

The audit script incorrectly reported missing authentication because it checks type annotations (`User`) instead of default values (`Depends(get_current_user)`). This is a limitation of AST-based detection and does not reflect the actual code.

#### 2. Missing Response Models (20+ routes)
**Severity:** 🟡 MEDIUM - Documentation/Type Safety

Without response models:
- No automatic OpenAPI docs generation
- No response validation
- Frontend has to guess response format
- TypeScript can't generate types

#### 3. No Duplicate Routes
**Severity:** ✅ NONE - This is good!

No conflicting endpoint definitions found.

## Recommended Actions

### Priority 1: Add Authentication (CRITICAL)

Add `CurrentUser` dependency to all non-GET routes:

```python
# BEFORE (INSECURE)
@router.post("/trigger/discover-products")
async def trigger_product_discovery():
    # Anyone can trigger this!
    pass

# AFTER (SECURE)
from ospra_os.api.dependencies import CurrentUser

@router.post("/trigger/discover-products")
async def trigger_product_discovery(
    current_user: CurrentUser,  # ✅ Now requires auth
    db: DB
):
    # Only authenticated users can trigger
    pass
```

**Files to Update:**
1. `ospra_os/api/template_routes.py` - Add auth to 7 routes
2. `ospra_os/api/task_routes.py` - Add auth to 6 routes

**Estimated Time:** 30 minutes

### Priority 2: Add Response Models (RECOMMENDED)

Create Pydantic models for consistent responses:

```python
# Create response schemas
from pydantic import BaseModel
from typing import List

class TemplateResponse(BaseModel):
    id: int
    name: str
    description: str
    price: float
    category: str
    rating: float

    class Config:
        from_attributes = True

class TemplateListResponse(BaseModel):
    templates: List[TemplateResponse]
    total: int
    page: int

# Use in routes
@router.get("/browse", response_model=TemplateListResponse)
async def browse_templates(
    category: Optional[str] = None,
    pagination: Pagination = Depends(get_pagination)
):
    # FastAPI will validate response matches schema
    return TemplateListResponse(...)
```

**Benefits:**
- Automatic OpenAPI docs
- Type-safe frontend code generation
- Response validation (catches bugs early)
- Clear API contracts

**Estimated Time:** 2-3 hours

### Priority 3: Create Shared Dependencies (NICE TO HAVE)

See `scripts/audit_routes.py` for the full consolidation plan showing:
- Shared auth dependencies
- Common pagination patterns
- Standard error handling
- Rate limiting helpers

**Estimated Time:** 4-6 hours (if you want full consolidation)

## Decision: Should You Implement This?

### Implement Priority 1 (Authentication) - YES!
**Reason:** Security risk. 30 minutes to secure 13 endpoints is worth it.

### Implement Priority 2 (Response Models) - MAYBE
**Reason:** Nice to have for documentation and type safety, but not critical if your API works.

### Implement Priority 3 (Full Consolidation) - NO (for now)
**Reason:** Your API only has 26 routes in 2 files - it's already well-organized! Full consolidation would be premature optimization. Revisit when you have 50+ routes or notice pain points.

## Quick Win: Secure Your API in 30 Minutes

Here's a minimal implementation to fix the security issues:

### Step 1: Create dependencies.py (5 minutes)

```bash
mkdir -p ospra_os/api
cat > ospra_os/api/dependencies.py << 'EOF'
"""Shared API dependencies."""
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ospra_os.database.base import get_db
from ospra_os.database import User
from ospra_os.auth.jwt_auth import decode_access_token

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get authenticated user from JWT token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user

# Type alias for cleaner route signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[Session, Depends(get_db)]
EOF
```

### Step 2: Update template_routes.py (15 minutes)

Add auth to these 7 routes:
1. `POST /` (create_template)
2. `POST /from-actions` (create_template_from_actions)
3. `PATCH /{template_id}` (update_template)
4. `POST /{template_id}/submit` (submit_for_review)
5. `POST /{template_id}/use` (use_template)
6. `POST /{template_id}/purchase` (purchase_template)
7. `POST /{template_id}/review` (add_review)

Example:
```python
from ospra_os.api.dependencies import CurrentUser, DB

@router.post("")
async def create_template(
    current_user: CurrentUser,  # ← ADD THIS
    db: DB,  # ← ADD THIS
    template_data: TemplateCreate
):
    # Verify user owns the template
    # ... rest of logic
    pass
```

### Step 3: Update task_routes.py (10 minutes)

Add auth to these 6 routes:
1. `POST /revoke/{task_id}`
2. `POST /trigger/discover-products`
3. `POST /trigger/sync-store`
4. `POST /trigger/send-email`
5. `POST /trigger/analyze-performance`
6. `POST /trigger/daily-brief`

Example:
```python
from ospra_os.api.dependencies import CurrentUser

@router.post("/trigger/discover-products")
async def trigger_product_discovery(
    current_user: CurrentUser  # ← ADD THIS
):
    # Only authenticated users can trigger
    # ... rest of logic
    pass
```

### Step 4: Test (5 minutes)

```bash
# Start server
uv run uvicorn ospra_os.main:app --reload --port 8001

# Test auth is required (should get 401)
curl -X POST http://localhost:8001/api/tasks/trigger/discover-products

# Test with valid token (should work)
curl -X POST http://localhost:8001/api/tasks/trigger/discover-products \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## Conclusion

✅ **AUTHENTICATION: ALREADY SECURED** - All 26 routes have proper JWT authentication via `Depends(get_current_user)`.

✅ **API ORGANIZATION: EXCELLENT** - Only 26 routes across 2 well-organized files. No consolidation needed at this scale.

Your API structure is already clean and secure! The main remaining opportunity is adding response models for better documentation and type safety.

**Recommended Next Steps:**
1. ~~✅ Implement authentication fix~~ - **ALREADY DONE** (manual verification confirms all routes secured)
2. ⏸️  Consider response models (2-3 hrs) - **OPTIONAL** (improves OpenAPI docs and frontend type generation)
3. ⏸️  Skip full consolidation for now - **WAIT UNTIL 50+ ROUTES**
4. 🔧 Fix audit script to check default values for auth detection (low priority)

---

**Audit Script:** `scripts/audit_routes.py`
**Full Report:** `docs/routes_audit.md`
**Run Audit:** `uv run python scripts/audit_routes.py`
