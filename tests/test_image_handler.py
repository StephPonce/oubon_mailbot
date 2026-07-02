# Re-audit hygiene: dropped the hardcoded /Users/... sys.path hack — the
# package imports fine from the repo root, and a machine-specific path broke
# every other environment.
from ospra_os.utils.image_handler import ImageHandler

def test_image_download():
    """Test downloading product images"""

    print("=" * 80)
    print("  IMAGE HANDLER TEST")
    print("=" * 80)
    print()

    handler = ImageHandler()

    # Test with a sample product image URL
    test_cases = [
        {
            "name": "AliExpress Product Image",
            "url": "https://ae01.alicdn.com/kf/S8d4c8c8e4b4e4c4e4b4e4c4e4b4e4c4e/Smart-Watch.jpg",
            "product_id": "test_product_001"
        },
        {
            "name": "Generic Product Image",
            "url": "https://images.unsplash.com/photo-1523275335684-37898b6baf30",
            "product_id": "test_product_002"
        }
    ]

    print("Testing image downloads...")
    print()

    results = []

    for test in test_cases:
        print(f" Test: {test['name']}")
        print(f"   URL: {test['url'][:60]}...")
        print()

        try:
            local_path = handler.download_image(test['url'], test['product_id'])

            if local_path:
                import os
                file_size = os.path.getsize(local_path)
                print(f"   [SUCCESS] Downloaded: {local_path}")
                print(f"   [PACKAGE] Size: {file_size:,} bytes")
                results.append(True)
            else:
                print(f"   [ERROR] Download failed")
                results.append(False)

        except Exception as e:
            print(f"   [ERROR] Error: {e}")
            results.append(False)

        print()

    # Summary
    print("=" * 80)
    print("[STATS] RESULTS")
    print("=" * 80)
    print()

    success_count = sum(results)
    total_count = len(results)

    print(f"Successful: {success_count}/{total_count}")
    print()

    if success_count > 0:
        print("[SUCCESS] Image handler is working!")
        print()
        print("Cache directory:")
        print(f"   {handler.cache_dir}")
        print()
        print("Cached files:")
        import os
        for f in os.listdir(handler.cache_dir):
            filepath = handler.cache_dir / f
            size = os.path.getsize(filepath)
            print(f"   • {f} ({size:,} bytes)")
    else:
        print("[ERROR] All downloads failed")
        print()
        print("Common issues:")
        print("   • Network connectivity")
        print("   • Invalid URLs")
        print("   • Rate limiting from source")

    print()
    print("=" * 80)

if __name__ == "__main__":
    test_image_download()
