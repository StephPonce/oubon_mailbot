#!/usr/bin/env python3
"""
Test script for Claude AI chat endpoint
"""
import requests
import json

def test_claude_chat():
    """Test the /api/claude/chat endpoint"""

    url = "http://localhost:8000/api/claude/chat"

    # Test payload
    payload = {
        "message": "Hello! Can you help me analyze my store performance?",
        "dashboard_context": None
    }

    print("=" * 60)
    print("Testing Claude Chat Endpoint")
    print("=" * 60)
    print(f"\nURL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("\nSending request...")

    try:
        response = requests.post(url, json=payload, timeout=30)

        print(f"\nStatus Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}\n")

        if response.status_code == 200:
            data = response.json()
            print("Response JSON:")
            print(json.dumps(data, indent=2))

            if data.get('success'):
                print("\n✅ SUCCESS: Chat endpoint is working!")
                print(f"\nClaude's response:\n{data.get('message', 'No message')}")
            else:
                print(f"\n❌ FAILED: {data.get('error', 'Unknown error')}")
                if 'traceback' in data:
                    print(f"\nTraceback:\n{data['traceback']}")
        else:
            print(f"\n❌ HTTP Error {response.status_code}")
            print(f"Response: {response.text}")

    except requests.exceptions.ConnectionError:
        print("\n❌ CONNECTION ERROR: Backend not running on port 8000")
        print("Start backend with: uvicorn ospra_os.main:app --port 8000")
    except requests.exceptions.Timeout:
        print("\n❌ TIMEOUT: Request took longer than 30 seconds")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    test_claude_chat()
