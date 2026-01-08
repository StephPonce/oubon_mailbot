import requests
import json

print("=== TESTING ADVANCED SCRAPING STACK ===\n")

print("1. Testing AliExpress Advanced Scraper + Google Trends...\n")

try:
    response = requests.get(
        "http://localhost:8001/api/dashboard/v2/products",
        params={"niche": "smart_home", "per_page": 10}
    )
    
    data = response.json()
    products = data.get("products", [])
    data_source = data.get("data_source", "Unknown")
    
    print(f"[SUCCESS] Data Source: {data_source}")
    print(f"[SUCCESS] Found {len(products)} products\n")
    
    if products:
        print("Top 5 Products with Velocity Scores:")
        print("-" * 80)
        for i, product in enumerate(products[:5], 1):
            velocity = product.get("velocity_score", 0)
            name = product.get("name", "Unknown")[:50]
            price = product.get("price", 0)
            source = product.get("source", "unknown")
            
            print(f"{i}. {name}")
            print(f"   Price: ${price:.2f} | Velocity: {velocity}/100 | Source: {source}")
            print()
        
        # Check if velocity scoring is working
        velocities = [p.get("velocity_score", 0) for p in products]
        avg_velocity = sum(velocities) / len(velocities) if velocities else 0
        
        print(f"[STATS] Average Velocity Score: {avg_velocity:.1f}/100")
        
        if data_source == "ADVANCED_SCRAPING":
            print("\n[SUCCESS] ADVANCED PLAYWRIGHT SCRAPER IS ACTIVE!")
        elif data_source == "REAL_TIME_API":
            print("\n[SUCCESS] REAL-TIME API IS ACTIVE (TikTok/AliExpress)")
        else:
            print(f"\n[WARNING]  Using fallback data source: {data_source}")
            
    else:
        print("[ERROR] No products returned")
        
except Exception as e:
    print(f"[ERROR] Test failed: {e}")
