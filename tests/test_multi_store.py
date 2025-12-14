#!/usr/bin/env python3
"""
Multi-Store Backend Test Script
Comprehensive testing of all multi-store API endpoints

NOTE: This is a standalone integration test script designed to be run directly with:
      python tests/test_multi_store.py

      It is NOT a pytest test file. The functions are called programmatically from run_all_tests(),
      not by pytest. Pytest is configured to skip this file.
"""

import pytest
import requests
import json
from typing import Dict, Any, Optional
import sys

# Skip this entire module when running pytest - it's a standalone integration test
pytestmark = pytest.mark.skip(reason="Standalone integration test script, not pytest tests. Run with: python tests/test_multi_store.py")

# Configuration
BASE_URL = "http://localhost:8001"
API_BASE = f"{BASE_URL}/api/portfolio"

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}  {text}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")


def print_test(name: str):
    """Print test name"""
    print(f"{YELLOW}TEST:{RESET} {name}")
    print("-" * 70)


def print_success(text: str):
    """Print success message"""
    print(f"{GREEN}✅ {text}{RESET}")


def print_error(text: str):
    """Print error message"""
    print(f"{RED}❌ {text}{RESET}")


def print_json(data: Any):
    """Pretty print JSON data"""
    print(json.dumps(data, indent=2))


def test_health_check() -> bool:
    """Test 1: Health Check - Verify multi-store is loaded"""
    print_test("Health Check")

    try:
        response = requests.get(f"{BASE_URL}/health")

        if response.status_code != 200:
            print_error(f"Health check failed: Status {response.status_code}")
            return False

        data = response.json()

        if data.get("multi_store_loaded"):
            print_success("Multi-store is loaded")
        else:
            print_error("Multi-store is NOT loaded")
            return False

        print(f"   Service: {data.get('service')}")
        print(f"   Status: {data.get('status')}")

        return True

    except Exception as e:
        print_error(f"Health check error: {e}")
        return False


def test_portfolio_overview() -> bool:
    """Test 2: Portfolio Overview - Get aggregated metrics"""
    print_test("Portfolio Overview")

    try:
        response = requests.get(f"{API_BASE}/overview")

        if response.status_code != 200:
            print_error(f"Overview failed: Status {response.status_code}")
            print(f"Response: {response.text}")
            return False

        data = response.json()

        # Validate response structure
        required_fields = [
            "total_revenue", "monthly_revenue", "active_stores",
            "total_stores", "total_products", "platforms"
        ]

        for field in required_fields:
            if field not in data:
                print_error(f"Missing field: {field}")
                return False

        print_success("Overview endpoint working")
        print(f"\n   Stores: {data['total_stores']} ({data['active_stores']} active)")
        print(f"   Products: {data['total_products']}")
        print(f"   Revenue: ${data['total_revenue']:.2f}")
        print(f"   Platforms: {', '.join(data['platforms'].keys()) if data['platforms'] else 'None'}")

        return True

    except Exception as e:
        print_error(f"Overview error: {e}")
        return False


def test_store_rankings() -> bool:
    """Test 3: Store Rankings - Get ranked stores"""
    print_test("Store Rankings")

    try:
        response = requests.get(f"{API_BASE}/rankings")

        if response.status_code != 200:
            print_error(f"Rankings failed: Status {response.status_code}")
            return False

        data = response.json()

        if not isinstance(data, list):
            print_error("Rankings should return an array")
            return False

        print_success(f"Rankings endpoint working ({len(data)} stores)")

        for idx, store in enumerate(data, 1):
            print(f"\n   #{idx} {store['store_name']} ({store['platform']})")
            print(f"      Rank: #{store['rank_position']} {store.get('rank_change_label', '—')}")
            print(f"      Revenue: ${store['monthly_revenue']:.2f}/month")

        return True

    except Exception as e:
        print_error(f"Rankings error: {e}")
        return False


def test_get_store(store_id: int) -> Optional[Dict[str, Any]]:
    """Test 4: Get Store Details"""
    print_test(f"Get Store Details (ID: {store_id})")

    try:
        response = requests.get(f"{API_BASE}/stores/{store_id}")

        if response.status_code == 404:
            print_error(f"Store {store_id} not found")
            return None

        if response.status_code != 200:
            print_error(f"Get store failed: Status {response.status_code}")
            return None

        data = response.json()

        print_success(f"Store {store_id} retrieved")
        print(f"\n   Name: {data['store_name']}")
        print(f"   Platform: {data['platform']}")
        print(f"   URL: {data['store_url']}")
        print(f"   Rank: #{data['rank_position']}")
        print(f"   Active: {data['is_active']}")

        return data

    except Exception as e:
        print_error(f"Get store error: {e}")
        return None


def test_add_store() -> Optional[int]:
    """Test 5: Add New Store"""
    print_test("Add New Store")

    store_data = {
        "store_name": "Test Amazon Store",
        "store_url": "test-amazon.com/seller/TEST123",
        "platform": "amazon",
        "credentials": {
            "seller_id": "TEST123",
            "mws_token": "test_mws_token",
            "marketplace_id": "ATVPDKIKX0DER"
        },
        "niche": "electronics",
        "target_market": "US",
        "currency": "USD"
    }

    try:
        response = requests.post(
            f"{API_BASE}/stores/add",
            json=store_data,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code not in [200, 201]:
            print_error(f"Add store failed: Status {response.status_code}")
            print(f"Response: {response.text}")
            return None

        data = response.json()
        store_id = data.get("id")

        print_success(f"Store created (ID: {store_id})")
        print(f"\n   Name: {data['store_name']}")
        print(f"   Platform: {data['platform']}")
        print(f"   Rank: #{data['rank_position']}")

        return store_id

    except Exception as e:
        print_error(f"Add store error: {e}")
        return None


def test_update_store(store_id: int) -> bool:
    """Test 6: Update Store"""
    print_test(f"Update Store (ID: {store_id})")

    update_data = {
        "niche": "updated_niche",
        "store_name": "Updated Test Store"
    }

    try:
        response = requests.put(
            f"{API_BASE}/stores/{store_id}",
            json=update_data,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code != 200:
            print_error(f"Update failed: Status {response.status_code}")
            return False

        data = response.json()

        print_success(f"Store {store_id} updated")
        print(f"\n   New name: {data['store_name']}")
        print(f"   New niche: {data['niche']}")

        return True

    except Exception as e:
        print_error(f"Update error: {e}")
        return False


def test_switch_store(store_id: int) -> bool:
    """Test 7: Switch Active Store"""
    print_test(f"Switch Active Store (ID: {store_id})")

    try:
        response = requests.post(f"{API_BASE}/stores/{store_id}/switch")

        if response.status_code != 200:
            print_error(f"Switch failed: Status {response.status_code}")
            return False

        data = response.json()

        print_success(f"Switched to store {store_id}")
        print(f"\n   Name: {data['store_name']}")
        print(f"   New rank: #{data['rank_position']}")

        return True

    except Exception as e:
        print_error(f"Switch error: {e}")
        return False


def test_delete_store(store_id: int) -> bool:
    """Test 8: Delete Store"""
    print_test(f"Delete Store (ID: {store_id})")

    try:
        response = requests.delete(f"{API_BASE}/stores/{store_id}")

        if response.status_code == 204:
            print_success(f"Store {store_id} deleted")
            return True
        elif response.status_code == 400:
            # Can't delete only store
            data = response.json()
            print_error(f"Cannot delete: {data.get('detail')}")
            return False
        else:
            print_error(f"Delete failed: Status {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Delete error: {e}")
        return False


def run_all_tests():
    """Run all tests in sequence"""
    print_header("MULTI-STORE BACKEND TEST SUITE")

    results = []

    # Test 1: Health Check
    print()
    results.append(("Health Check", test_health_check()))

    # Test 2: Portfolio Overview
    print()
    results.append(("Portfolio Overview", test_portfolio_overview()))

    # Test 3: Store Rankings
    print()
    results.append(("Store Rankings", test_store_rankings()))

    # Test 4: Get Store Details (assuming store ID 1 exists)
    print()
    store_data = test_get_store(1)
    results.append(("Get Store Details", store_data is not None))

    # Test 5: Add New Store
    print()
    new_store_id = test_add_store()
    results.append(("Add Store", new_store_id is not None))

    if new_store_id:
        # Test 6: Update Store
        print()
        results.append(("Update Store", test_update_store(new_store_id)))

        # Test 7: Switch Active Store
        print()
        results.append(("Switch Store", test_switch_store(new_store_id)))

        # Test 8: Delete Store (cleanup)
        print()
        results.append(("Delete Store", test_delete_store(new_store_id)))

    # Print Summary
    print_header("TEST SUMMARY")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = f"{GREEN}✅ PASS{RESET}" if result else f"{RED}❌ FAIL{RESET}"
        print(f"{status}  {test_name}")

    print(f"\n{'-'*70}")
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print(f"{GREEN}🎉 ALL TESTS PASSED!{RESET}")
        return 0
    else:
        print(f"{RED}⚠️  Some tests failed{RESET}")
        return 1


def check_backend_running() -> bool:
    """Check if backend is running"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def main():
    """Main entry point"""
    print(f"\n{BLUE}Multi-Store Backend Test Suite{RESET}")
    print(f"{BLUE}Testing: {BASE_URL}{RESET}\n")

    # Check if backend is running
    if not check_backend_running():
        print_error("Backend is not running!")
        print(f"\nPlease start the backend:")
        print(f"  cd /path/to/oubon_mailbot")
        print(f"  uv run uvicorn ospra_os.main:app --reload --host 127.0.0.1 --port 8001")
        sys.exit(1)

    # Run all tests
    exit_code = run_all_tests()

    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}Test suite complete!{RESET}")
    print(f"{BLUE}API Documentation: {BASE_URL}/docs{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
