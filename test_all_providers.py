#!/usr/bin/env python3
"""
OSPRA AI PROVIDER TEST
Tests all configured AI providers (Groq, Google Gemini, xAI, OpenAI, Anthropic)
"""

import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def print_header(title: str, char: str = "="):
    """Print a formatted section header"""
    print(f"\n{char * 60}")
    print(f"{title:^60}")
    print(f"{char * 60}\n")

def mask_key(key: str) -> str:
    """Mask API key for security (show first 6 and last 4 chars)"""
    if not key or len(key) < 15:
        return "❌ NOT SET"
    return f"{key[:6]}...{key[-4:]}"

def test_groq():
    """Test Groq (FREE tier with Llama 3.1)"""
    try:
        from groq import Groq
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Say 'Groq working!' in exactly 2 words"}],
            max_tokens=10
        )

        text = response.choices[0].message.content.strip()
        tokens = response.usage.total_tokens
        return True, f"Response: '{text}' ({tokens} tokens)"
    except Exception as e:
        return False, f"Error: {str(e)[:50]}"

def test_google_gemini():
    """Test Google Gemini Flash"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

        # Try different model names (updated for Gemini 2.x)
        model_names = ['gemini-2.5-flash', 'gemini-flash-latest', 'gemini-2.5-pro', 'gemini-pro-latest']

        for model_name in model_names:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content("Say 'Gemini working!' in exactly 2 words")
                return True, f"Response: '{response.text.strip()}' (model: {model_name})"
            except:
                continue

        return False, "No compatible Gemini model found"
    except Exception as e:
        return False, f"Error: {str(e)[:50]}"

def test_xai_grok():
    """Test xAI Grok"""
    try:
        import requests

        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            return False, "XAI_API_KEY not set"

        # Try different model names
        models = ['grok-beta', 'grok-2-latest', 'grok-2-1212', 'grok-vision-beta']

        for model in models:
            response = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Say 'Grok working!' in exactly 2 words"}],
                    "max_tokens": 10
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                text = data['choices'][0]['message']['content'].strip()
                tokens = data['usage']['total_tokens']
                return True, f"Response: '{text}' ({tokens} tokens, model: {model})"

        return False, f"No compatible Grok model found. Last status: {response.status_code}"
    except Exception as e:
        return False, f"Error: {str(e)[:50]}"

def test_openai():
    """Test OpenAI GPT-4o-mini"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say 'OpenAI working!' in exactly 2 words"}],
            max_tokens=10
        )

        text = response.choices[0].message.content.strip()
        tokens = response.usage.total_tokens
        return True, f"Response: '{text}' ({tokens} tokens)"
    except Exception as e:
        return False, f"Error: {str(e)[:50]}"

def test_anthropic():
    """Test Anthropic Claude"""
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Try different Claude models (latest first, fallback to stable)
        models = [
            'claude-sonnet-4-5-20250929',    # Latest Sonnet 4.5
            'claude-3-5-sonnet-20241022',    # Sonnet 3.5 v2
            'claude-3-5-haiku-20241022',     # Haiku 3.5
            'claude-3-haiku-20240307'        # Haiku 3 (stable)
        ]

        for model in models:
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=10,
                    messages=[{"role": "user", "content": "Say 'Claude working!' in exactly 2 words"}]
                )

                text = response.content[0].text.strip()
                tokens = response.usage.input_tokens + response.usage.output_tokens
                return True, f"Response: '{text}' ({tokens} tokens, model: {model})"
            except:
                continue

        return False, "No compatible Claude model found"
    except Exception as e:
        return False, f"Error: {str(e)[:50]}"

def main():
    """Run all provider tests"""
    print_header("OSPRA AI PROVIDER TEST")

    # Print test metadata
    print(f"📅 Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 Working Dir: {os.getcwd()}")

    # Check environment variables
    print_header("ENVIRONMENT CHECK")

    env_vars = {
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
        "XAI_API_KEY": os.getenv("XAI_API_KEY"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY")
    }

    for key, value in env_vars.items():
        status = "✅" if value else "❌"
        print(f"  {status} {key}: {mask_key(value)}")

    # Run provider tests
    print_header("PROVIDER TESTS")

    tests = [
        ("Groq (FREE)", test_groq),
        ("Google Gemini", test_google_gemini),
        ("xAI Grok", test_xai_grok),
        ("OpenAI", test_openai),
        ("Anthropic Claude", test_anthropic)
    ]

    results = []
    for name, test_func in tests:
        try:
            success, message = test_func()
            status = "✅" if success else "❌"
            print(f"  {status} {name}: {message}")
            results.append(success)
        except Exception as e:
            print(f"  ❌ {name}: Unexpected error: {str(e)[:50]}")
            results.append(False)

    # Summary
    print_header("SUMMARY")

    passed = sum(results)
    total = len(results)

    print(f"  Passed: {passed}/{total}\n")

    if passed == total:
        print("  🎉 ALL PROVIDERS WORKING!")
        print("  Your multi-model AI stack is ready.\n")
    elif passed > 0:
        print("  ⚠️  SOME PROVIDERS WORKING")
        print("  Check failed providers above.\n")
    else:
        print("  ❌ NO PROVIDERS WORKING")
        print("  Check your API keys and network connection.\n")

if __name__ == "__main__":
    main()
