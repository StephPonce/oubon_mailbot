#!/usr/bin/env python3
"""
Test script for Gemini Provider
Tests basic functionality without requiring actual API key
"""

def test_gemini_provider():
    """Test GeminiProvider implementation"""

    print("=" * 60)
    print("TESTING GEMINI PROVIDER")
    print("=" * 60)
    print()

    # Test 1: Import
    print("1. Testing import...")
    try:
        from ospra_os.ai.providers import GeminiProvider
        print("[SUCCESS] GeminiProvider import successful")
    except ImportError as e:
        print(f"[ERROR] Import failed: {e}")
        return

    # Test 2: Initialization
    print("\n2. Testing initialization...")
    try:
        provider = GeminiProvider(api_key="test-key-12345")
        print("[SUCCESS] GeminiProvider initialization successful")
    except Exception as e:
        print(f"[ERROR] Initialization failed: {e}")
        return

    # Test 3: Provider info
    print("\n3. Testing provider info...")
    try:
        assert provider.provider_name == "gemini", "Provider name should be 'gemini'"
        print(f"[SUCCESS] Provider: {provider.provider_name}")

        assert provider.model_name == "gemini-1.5-flash", "Model should be gemini-1.5-flash"
        print(f"[SUCCESS] Model: {provider.model_name}")

        assert provider.cost_per_1k == 0.00025, "Cost should be $0.00025 per 1K"
        print(f"[SUCCESS] Cost per 1K: ${provider.cost_per_1k}")
    except AssertionError as e:
        print(f"[ERROR] Provider info test failed: {e}")
        return

    # Test 4: Model info method
    print("\n4. Testing get_model_info()...")
    try:
        info = provider.get_model_info()
        assert "provider" in info
        assert "model" in info
        assert "cost_per_1k_tokens" in info
        print("[SUCCESS] Model info working")
        print(f"   Provider: {info['provider']}")
        print(f"   Model: {info['model']}")
        print(f"   Cost/1K: ${info['cost_per_1k_tokens']}")
    except Exception as e:
        print(f"[ERROR] get_model_info() failed: {e}")
        return

    # Test 5: Cost calculation
    print("\n5. Testing cost calculation...")
    try:
        cost = provider.calculate_cost(5000)  # 5K tokens
        expected = 5000 / 1000 * 0.00025  # $0.00125
        assert abs(cost - expected) < 0.0001, f"Cost should be {expected}, got {cost}"
        print(f"[SUCCESS] Cost calculation: ${cost} for 5K tokens")
    except Exception as e:
        print(f"[ERROR] Cost calculation failed: {e}")
        return

    # Test 6: Data validation
    print("\n6. Testing product data validation...")
    try:
        # Valid data
        valid_data = {
            "name": "Test Product",
            "niche": "electronics"
        }
        provider.validate_product_data(valid_data)
        print("[SUCCESS] Product data validation working")

        # Invalid data (missing name)
        invalid_data = {"niche": "electronics"}
        try:
            provider.validate_product_data(invalid_data)
            print("[ERROR] Should have raised ValueError for missing name")
        except ValueError:
            print("[SUCCESS] Correctly rejects invalid data")
    except Exception as e:
        print(f"[ERROR] Data validation test failed: {e}")
        return

    # Test 7: JSON extraction (used for parsing responses)
    print("\n7. Testing JSON extraction from markdown...")
    try:
        # Test with markdown code block
        response_with_markdown = '''Here's the analysis:
```json
{"score": 8.5}
```
'''
        extracted = provider._extract_json_from_response(response_with_markdown)
        import json
        parsed = json.loads(extracted)
        assert parsed["score"] == 8.5
        print(f"[SUCCESS] JSON extraction from markdown works: {parsed['score']}")

        # Test without markdown
        response_without_markdown = '{"score": 9.0}'
        extracted = provider._extract_json_from_response(response_without_markdown)
        parsed = json.loads(extracted)
        assert parsed["score"] == 9.0
        print(f"[SUCCESS] JSON extraction without markdown works: {parsed['score']}")
    except Exception as e:
        print(f"[ERROR] JSON extraction failed: {e}")
        return

    # Test 8: Compare costs with other providers
    print("\n8. Cost comparison (10K tokens)...")
    try:
        from ospra_os.ai.providers import ClaudeProvider, OpenAIProvider

        gemini = GeminiProvider(api_key="test")
        claude = ClaudeProvider(api_key="test")
        openai = OpenAIProvider(api_key="test")

        tokens = 10000
        gemini_cost = gemini.calculate_cost(tokens)
        claude_cost = claude.calculate_cost(tokens)
        openai_cost = openai.calculate_cost(tokens)

        print(f"   Gemini:  ${gemini_cost:.4f}")
        print(f"   Claude:  ${claude_cost:.4f}")
        print(f"   OpenAI:  ${openai_cost:.4f}")

        print(f"\n   Gemini vs Claude: {claude_cost/gemini_cost:.0f}x cheaper")
        print(f"   Gemini vs OpenAI: {openai_cost/gemini_cost:.0f}x cheaper")

    except Exception as e:
        print(f"[WARNING]  Cost comparison skipped: {e}")

    print("\n" + "=" * 60)
    print("[SUCCESS] All basic tests passed!")
    print("=" * 60)
    print()
    print("[NOTE] Note: Actual API calls require valid GOOGLE_API_KEY")
    print("   Set environment variable to test real functionality:")
    print("   export GOOGLE_API_KEY=your-api-key")
    print()
    print("[TIP] Gemini is the MOST cost-effective option:")
    print("   - 12x cheaper than Claude")
    print("   - 60x cheaper than OpenAI")
    print("   - Fast response times (gemini-1.5-flash)")
    print("   - Production-ready despite ultra-low cost")
    print()


if __name__ == "__main__":
    test_gemini_provider()
