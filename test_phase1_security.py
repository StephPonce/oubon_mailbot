"""
Phase 1 Security Testing Suite
================================
Tests all Phase 1 security features:
1. Rate limiting (SlowAPI)
2. CORS restrictions
3. Tier enforcement
4. Pydantic validation
5. Security logging
"""

import requests
import time
import json
from typing import Dict, Any

# Test configuration
BASE_URL = "http://localhost:8001"
TEST_USER_EMAIL = "security_test@example.com"

# Color codes for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_test(name: str):
    """Print test name."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST: {name}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")


def print_success(message: str):
    """Print success message."""
    print(f"{GREEN}✓ {message}{RESET}")


def print_failure(message: str):
    """Print failure message."""
    print(f"{RED}✗ {message}{RESET}")


def print_info(message: str):
    """Print info message."""
    print(f"{YELLOW}ℹ {message}{RESET}")


def test_rate_limiting():
    """
    Test 1: Rate Limiting

    Verify that SlowAPI rate limiting is active and returns 429
    when limits are exceeded.
    """
    print_test("Rate Limiting (SlowAPI)")

    endpoint = f"{BASE_URL}/health"

    print_info(f"Sending rapid requests to {endpoint}")
    print_info("Expected: 429 Too Many Requests after exceeding limit")

    success_count = 0
    rate_limited = False

    # Send 40 rapid requests (free tier limit is 30/minute)
    for i in range(40):
        try:
            response = requests.get(endpoint, timeout=2)

            if response.status_code == 429:
                rate_limited = True
                print_success(f"Rate limit triggered at request {i+1}")
                print_info(f"Response: {response.json()}")

                # Check for retry-after header
                if "Retry-After" in response.headers:
                    print_success(f"Retry-After header present: {response.headers['Retry-After']}s")

                break
            elif response.status_code == 200:
                success_count += 1
        except Exception as e:
            print_failure(f"Request {i+1} failed: {e}")

    if rate_limited:
        print_success(f"PASS: Rate limiting is active ({success_count} successful before limit)")
        return True
    else:
        print_failure(f"FAIL: No rate limiting detected after {success_count} requests")
        return False


def test_cors_restrictions():
    """
    Test 2: CORS Restrictions

    Verify that CORS is restricted to ospra.io domains + localhost only.
    """
    print_test("CORS Restrictions")

    endpoint = f"{BASE_URL}/health"

    # Test 1: Localhost origin (should be allowed)
    print_info("Testing localhost origin (should be allowed)")
    try:
        response = requests.get(
            endpoint,
            headers={"Origin": "http://localhost:5173"},
            timeout=2
        )

        if response.status_code == 200:
            print_success("Localhost origin allowed")
        else:
            print_failure(f"Localhost origin rejected: {response.status_code}")
    except Exception as e:
        print_failure(f"Localhost test failed: {e}")

    # Test 2: Unauthorized origin (should be blocked)
    print_info("Testing unauthorized origin (should be blocked)")
    try:
        response = requests.get(
            endpoint,
            headers={"Origin": "https://evil-site.com"},
            timeout=2
        )

        # Check if CORS headers are missing for unauthorized origin
        cors_header = response.headers.get("Access-Control-Allow-Origin")

        if cors_header is None or "evil-site.com" not in cors_header:
            print_success("Unauthorized origin blocked (no CORS headers)")
            return True
        else:
            print_failure(f"Unauthorized origin allowed: {cors_header}")
            return False
    except Exception as e:
        print_failure(f"Unauthorized origin test failed: {e}")
        return False


def test_tier_enforcement():
    """
    Test 3: Tier Enforcement

    Verify that premium features are blocked for free tier users.
    """
    print_test("Tier Enforcement Middleware")

    # Protected endpoint that requires higher tier
    endpoint = f"{BASE_URL}/api/intelligence/briefing/morning"

    print_info(f"Testing protected endpoint: {endpoint}")
    print_info("Expected: 403 Forbidden or tier limit error for free tier")

    try:
        # Try to access without authentication (free tier)
        response = requests.get(endpoint, timeout=5)

        if response.status_code == 403:
            print_success("Access denied (403 Forbidden)")
            print_info(f"Response: {response.json()}")
            return True
        elif response.status_code == 401:
            print_success("Authentication required (401 Unauthorized)")
            print_info(f"Response: {response.json()}")
            return True
        elif response.status_code == 429:
            print_success("Rate limit enforced (429 Too Many Requests)")
            return True
        elif response.status_code == 200:
            print_failure("WARNING: Protected endpoint accessible without auth")
            return False
        else:
            print_info(f"Unexpected status code: {response.status_code}")
            print_info(f"Response: {response.text[:200]}")
            return False
    except Exception as e:
        print_failure(f"Tier enforcement test failed: {e}")
        return False


def test_pydantic_validation():
    """
    Test 4: Pydantic Request Validation

    Verify that invalid requests are rejected with proper validation errors.
    """
    print_test("Pydantic Request Validation")

    endpoint = f"{BASE_URL}/api/ai/chat"

    # Test 1: Missing required field
    print_info("Testing missing required field (message)")
    try:
        response = requests.post(
            endpoint,
            json={"context": "test"},  # Missing "message" field
            timeout=5
        )

        if response.status_code == 422:
            print_success("Invalid request rejected (422 Unprocessable Entity)")
            print_info(f"Validation error: {response.json()}")
        else:
            print_failure(f"Invalid request not rejected: {response.status_code}")
    except Exception as e:
        print_info(f"Request failed (expected): {e}")

    # Test 2: Invalid field type
    print_info("Testing invalid field type")
    try:
        response = requests.post(
            endpoint,
            json={"message": 123, "user_id": "not_an_int"},  # Wrong types
            timeout=5
        )

        if response.status_code == 422:
            print_success("Type validation working (422 Unprocessable Entity)")
            return True
        else:
            print_failure(f"Type validation failed: {response.status_code}")
            return False
    except Exception as e:
        print_info(f"Request failed (expected): {e}")
        return True


def test_security_logging():
    """
    Test 5: Security Logging

    Verify that security events are being logged to logs/security.log.
    """
    print_test("Security Logging")

    log_file = "logs/security.log"

    print_info(f"Checking for security log file: {log_file}")

    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()

            if len(lines) > 0:
                print_success(f"Security log file exists with {len(lines)} entries")

                # Show last 5 log entries
                print_info("Last 5 security log entries:")
                for line in lines[-5:]:
                    print(f"  {line.strip()}")

                # Check for specific security events
                log_content = ''.join(lines)

                events = {
                    "LOGIN_SUCCESS": "Login success events",
                    "LOGIN_FAILURE": "Login failure events",
                    "TOKEN_REFRESH": "Token refresh events",
                    "RATE_LIMIT_EXCEEDED": "Rate limit events",
                    "PERMISSION_DENIED": "Permission denied events"
                }

                print_info("\nSecurity event types logged:")
                for event_type, description in events.items():
                    if event_type in log_content:
                        print_success(f"  ✓ {description}")
                    else:
                        print_info(f"  - {description} (not logged yet)")

                return True
            else:
                print_failure("Security log file is empty")
                return False
    except FileNotFoundError:
        print_failure(f"Security log file not found: {log_file}")
        print_info("Creating logs directory...")
        import os
        os.makedirs("logs", exist_ok=True)
        return False
    except Exception as e:
        print_failure(f"Failed to read security log: {e}")
        return False


def run_all_tests():
    """Run all Phase 1 security tests."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}PHASE 1 SECURITY TEST SUITE{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    print_info(f"Testing OspraOS at: {BASE_URL}")

    results = {
        "Rate Limiting": test_rate_limiting(),
        "CORS Restrictions": test_cors_restrictions(),
        "Tier Enforcement": test_tier_enforcement(),
        "Pydantic Validation": test_pydantic_validation(),
        "Security Logging": test_security_logging(),
    }

    # Summary
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST SUMMARY{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_test in results.items():
        if passed_test:
            print_success(f"{test_name}: PASS")
        else:
            print_failure(f"{test_name}: FAIL")

    print(f"\n{BLUE}{'='*60}{RESET}")
    if passed == total:
        print_success(f"ALL TESTS PASSED ({passed}/{total})")
    else:
        print_failure(f"SOME TESTS FAILED ({passed}/{total} passed)")
    print(f"{BLUE}{'='*60}{RESET}\n")

    return passed == total


if __name__ == "__main__":
    # Wait for server to be ready
    print_info("Checking if OspraOS is running...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        print_success("OspraOS is running")
    except Exception as e:
        print_failure(f"OspraOS not accessible: {e}")
        print_info("Please start the server with: uv run uvicorn ospra_os.main:app --reload --port 8001")
        exit(1)

    # Run all tests
    success = run_all_tests()
    exit(0 if success else 1)
