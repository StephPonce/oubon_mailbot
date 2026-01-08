#!/usr/bin/env python3
"""
AI Image Generation Test Script
================================
Tests the complete AI image pipeline:
1. Check API key configuration
2. Test single image generation
3. Test batch enhancement via discovery endpoint
4. Verify frontend integration

Run: python scripts/test_ai_images.py
"""

import asyncio
import os
import sys
import aiohttp

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_BASE = "http://localhost:8000"


def print_header(text):
    print(f"\n{'='*60}")
    print(f" {text}")
    print('='*60)


def print_result(name, success, message=""):
    status = "[SUCCESS]" if success else "[FAILED]"
    print(f"  {status} {name}: {message}")


async def test_image_status():
    """Test 1: Check image service status"""
    print_header("TEST 1: IMAGE SERVICE STATUS")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE}/api/images/status") as response:
                data = await response.json()
                
                available = data.get("available", False)
                openai = data.get("openai_configured", False)
                gemini = data.get("gemini_configured", False)
                stability = data.get("stability_configured", False)
                cached = data.get("cached_images", 0)
                
                print_result("Image Service", available, data.get("message", ""))
                print_result("OpenAI DALL-E", openai, "OPENAI_API_KEY set" if openai else "Not configured")
                print_result("Gemini Imagen", gemini, "GEMINI_API_KEY set" if gemini else "Not configured")
                print_result("Stability AI", stability, "STABILITY_API_KEY set" if stability else "Not configured")
                print(f"  [INFO] Cached images: {cached}")
                
                return openai or gemini or stability
                
    except Exception as e:
        print_result("Connection", False, str(e))
        return False


async def test_single_generation():
    """Test 2: Generate a single AI image"""
    print_header("TEST 2: SINGLE IMAGE GENERATION")
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "product_title": "Smart LED Strip Lights WiFi RGB",
                "niche": "smart_home",
                "original_image_url": "https://example.com/placeholder.jpg",
                "tags": ["smart_home", "led", "wifi"],
                "force_regenerate": False
            }
            
            print(f"  [INFO] Generating image for: {payload['product_title'][:40]}...")
            
            async with session.post(
                f"{API_BASE}/api/images/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                data = await response.json()
                
                success = data.get("success", False)
                ai_url = data.get("ai_image_url")
                source = data.get("source", "unknown")
                
                print_result("Generation", success, f"Source: {source}")
                
                if ai_url:
                    print(f"  [INFO] AI Image URL: {ai_url[:80]}...")
                    return True
                else:
                    print(f"  [ERROR] {data.get('error', 'No URL returned')}")
                    return False
                    
    except Exception as e:
        print_result("Generation", False, str(e))
        return False


async def test_batch_enhancement():
    """Test 3: Enhance products with AI images via discovery endpoint"""
    print_header("TEST 3: BATCH IMAGE ENHANCEMENT")
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "products": [
                    {"title": "Smart WiFi Plug", "niche": "smart_home", "image_url": None},
                    {"title": "LED Night Light Sensor", "niche": "lighting", "image_url": None},
                    {"title": "Kitchen Timer Digital", "niche": "kitchen", "image_url": None},
                ],
                "max_images": 2  # Only enhance top 2 to save costs
            }
            
            print(f"  [INFO] Enhancing {len(payload['products'])} products (max {payload['max_images']} images)...")
            
            async with session.post(
                f"{API_BASE}/api/discovery/enhance-images",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=180)
            ) as response:
                data = await response.json()
                
                success = data.get("success", False)
                products = data.get("products", [])
                generated = data.get("generated", 0)
                cost = data.get("estimated_cost", 0)
                
                print_result("Batch Enhancement", success, f"{generated}/{len(products)} images generated")
                print(f"  [INFO] Estimated cost: ${cost:.2f}")
                
                for p in products:
                    has_ai = bool(p.get("ai_image_url"))
                    source = p.get("image_source", "none")
                    title = p.get("title", "Unknown")[:30]
                    print(f"    - {title}: {'[SUCCESS]' if has_ai else '[SKIP]'} ({source})")
                
                return success
                    
    except Exception as e:
        print_result("Batch Enhancement", False, str(e))
        return False


async def test_discovery_with_images():
    """Test 4: Full discovery flow with AI images enabled"""
    print_header("TEST 4: DISCOVERY WITH AI IMAGES")
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{API_BASE}/api/discovery/quick/smart_home?count=3&include_ai_images=true"
            
            print(f"  [INFO] Running discovery with AI images enabled...")
            
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=180)
            ) as response:
                data = await response.json()
                
                success = data.get("success", False)
                products = data.get("products", [])
                ai_generated = data.get("ai_images_generated", False)
                
                print_result("Discovery", success, f"Found {len(products)} products")
                print(f"  [INFO] AI images requested: {ai_generated}")
                
                enhanced_count = 0
                for p in products:
                    has_ai = bool(p.get("ai_image_url"))
                    if has_ai:
                        enhanced_count += 1
                    title = p.get("title", "Unknown")[:40]
                    source = p.get("image_source", p.get("source", "supplier"))
                    score = p.get("oi_score", 0)
                    print(f"    - [{score}] {title}")
                    print(f"      Image: {'AI (' + source + ')' if has_ai else 'Original'}")
                
                print(f"\n  [SUMMARY] {enhanced_count}/{len(products)} products have AI images")
                return success
                    
    except Exception as e:
        print_result("Discovery", False, str(e))
        return False


async def main():
    print("\n" + "="*60)
    print(" OSPRA INTELLIGENCE - AI IMAGE GENERATION TEST")
    print("="*60)
    
    # Check server is running
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE}/health") as response:
                health = await response.json()
                print(f"\n[INFO] Server: {health.get('status', 'unknown')}")
    except:
        print("\n[ERROR] Backend server not running!")
        print("Start with: uvicorn main:app --host 0.0.0.0 --port 8000")
        return
    
    results = []
    
    # Run tests
    results.append(("Image Service Status", await test_image_status()))
    results.append(("Single Image Generation", await test_single_generation()))
    results.append(("Batch Enhancement", await test_batch_enhancement()))
    results.append(("Discovery with Images", await test_discovery_with_images()))
    
    # Summary
    print_header("TEST SUMMARY")
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        print_result(name, result)
    
    print(f"\n  Score: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n  [SUCCESS] AI Image Generation fully operational!")
    elif passed > 0:
        print("\n  [WARNING] Some tests failed - check configuration")
    else:
        print("\n  [ERROR] AI Image Generation not working")
        print("\n  Required: Set at least one of these environment variables:")
        print("    - OPENAI_API_KEY (for DALL-E 3)")
        print("    - GEMINI_API_KEY (for Imagen 3)")
        print("    - STABILITY_API_KEY (for Stable Diffusion)")


if __name__ == "__main__":
    asyncio.run(main())
