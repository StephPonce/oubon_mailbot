# OspraOS Test Suite

Comprehensive test suite for OspraOS platform covering unit, integration, and end-to-end tests.

## Quick Start

```bash
# Run all tests
./scripts/run_tests.sh all

# Run specific category
./scripts/run_tests.sh unit
./scripts/run_tests.sh integration
./scripts/run_tests.sh e2e

# Check coverage
./scripts/check_coverage.sh
```

## Test Structure

```
tests/
├── conftest.py              # Pytest fixtures and configuration
├── factories.py             # Test data factories (UserFactory, StoreFactory, etc.)
├── unit/                    # Unit tests (50+ tests)
│   ├── test_confidence_engine.py
│   └── test_action_executor.py
├── integration/             # Integration tests (30+ tests)
│   └── test_actions_api.py
└── e2e/                     # End-to-end tests (15+ tests)
    └── test_product_deployment_flow.py
```

## Test Categories

### Unit Tests
Fast, isolated tests for individual components:
- Confidence scoring engine
- Action executors
- Data validation
- Utility functions

**Run**: `./scripts/run_tests.sh unit`

### Integration Tests
Tests for API endpoints and service integration:
- REST API endpoints
- Authentication/authorization
- Database operations
- External service mocking

**Run**: `./scripts/run_tests.sh integration`

### E2E Tests
Complete workflow tests:
- Product deployment flow
- Multi-step operations
- User journeys
- Error recovery

**Run**: `./scripts/run_tests.sh e2e`

## Fixtures Available

### Database Fixtures
- `db_session` - In-memory SQLite with transaction rollback
- `app_fixture` - FastAPI test application
- `test_client` - HTTP client for API testing

### User Fixtures
- `test_user` - Standard tier user
- `test_user_premium` - Premium tier user
- `auth_headers` - JWT authentication headers
- `auth_client` - Authenticated HTTP client

### Domain Fixtures
- `test_store` - Shopify store configuration
- `test_product` - Sample product entity
- `test_action` - Sample action entity

### Mock Fixtures
- `mock_shopify_client` - Mocked Shopify API
- `mock_anthropic_client` - Mocked AI client

## Test Factories

Use factories to create test data with sensible defaults:

```python
from tests.factories import UserFactory, StoreFactory, ProductFactory

# Create test user
user = UserFactory.create(email="test@example.com")

# Create premium user
premium_user = UserFactory.create_premium()

# Create product with high confidence
product = ProductFactory.create_with_confidence(
    confidence_score=0.85,
    niche="smart_home"
)
```

## Writing Tests

### Unit Test Example

```python
import pytest
from ospra_os.intelligence.confidence_engine import ConfidenceEngine

def test_confidence_calculation():
    """Test basic confidence score calculation"""
    engine = ConfidenceEngine()

    metrics = {
        "profit_margin": 60.0,
        "velocity_score": 85,
        "saturation_score": 25,
        "trend_direction": 15
    }

    result = engine.calculate_product_confidence(metrics)

    assert result.score >= 70
    assert result.risk_level == "low"
```

### Integration Test Example

```python
import pytest

@pytest.mark.asyncio
async def test_create_action(auth_client, test_store):
    """Test creating a new action via API"""
    payload = {
        "action_type": "deploy_product",
        "store_id": test_store.id,
        "confidence": 0.85,
        "payload": {"product_id": 123}
    }

    response = auth_client.post("/api/actions", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
```

### E2E Test Example

```python
import pytest
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_deployment_workflow(auth_client, test_user, test_store):
    """Test complete deployment workflow"""
    # Create action
    action = await create_deployment_action(...)

    # Mock Shopify API
    with patch('ospra_os.services.action_executor.ShopifyClient') as mock:
        mock_client = AsyncMock()
        mock_client.create_product.return_value = {...}
        mock.return_value = mock_client

        # Approve action
        response = auth_client.post(f"/api/actions/{action.id}/approve")

    assert response.status_code == 200
```

## Test Markers

Use markers to categorize tests:

```python
@pytest.mark.unit
def test_unit_example():
    pass

@pytest.mark.integration
def test_integration_example():
    pass

@pytest.mark.e2e
@pytest.mark.slow
async def test_slow_e2e_example():
    pass
```

Available markers:
- `unit` - Unit tests
- `integration` - Integration tests
- `e2e` - End-to-end tests
- `slow` - Long-running tests
- `asyncio` - Async tests

## Configuration

### pytest.ini
- Coverage threshold: 70%
- Parallel execution: Enabled (`-n auto`)
- Coverage reports: HTML, JSON, XML, Terminal
- Test discovery: `test_*.py`, `Test*` classes, `test_*` functions

### Coverage Exclusions
- Frontend code (`node_modules/`, `frontend/`)
- Virtual environments (`.venv/`, `venv/`)
- Build artifacts (`dist/`, `build/`)

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
      - name: Run tests
        run: ./scripts/run_tests_ci.sh all
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

## Troubleshooting

### Tests failing with database errors?
```bash
# Reset test database
rm -f test_database.db
```

### Coverage below threshold?
```bash
# See detailed coverage report
./scripts/check_coverage.sh
open htmlcov/index.html
```

### Slow tests?
```bash
# Run only fast tests
./scripts/run_tests.sh unit

# Show slowest tests
./scripts/run_tests.sh all --durations=20
```

### Resource warnings?
These are non-blocking but indicate unclosed connections. Check test cleanup logic.

## Best Practices

1. **Isolation**: Each test should be independent
2. **Fast**: Keep unit tests under 100ms
3. **Clear**: Use descriptive test names
4. **Arrange-Act-Assert**: Structure tests clearly
5. **Mock External**: Always mock external APIs
6. **Clean Up**: Use fixtures for setup/teardown
7. **Coverage**: Aim for 85%+ on core logic

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Coverage.py](https://coverage.readthedocs.io/)

## Support

For issues or questions:
1. Check `TEST_SUITE_REPORT.md` for known issues
2. Review test logs: `tests/test.log`
3. Run with verbose: `./scripts/run_tests.sh all -vv`
