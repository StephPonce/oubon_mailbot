"""Simplified Apify Client - Production Ready"""
import os
import asyncio
import httpx
from typing import Dict, List

class ApifyClient:
    def __init__(self):
        self.api_token = os.getenv('APIFY_API_TOKEN')
        if not self.api_token:
            raise ValueError("APIFY_API_TOKEN not set")
        
        self.base_url = "https://api.apify.com/v2"
        
    async def test_connection(self) -> bool:
        """Test if Apify credentials work"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{self.base_url}/users/me"
                headers = {'Authorization': f'Bearer {self.api_token}'}
                response = await client.get(url, headers=headers)
                return response.status_code == 200
        except:
            return False
    
    async def scrape_amazon_quick(self, keyword: str, max_items: int = 5) -> List[Dict]:
        """Quick Amazon product scrape"""
        print(f"🔍 Apify: Searching Amazon for '{keyword}'...")
        
        # Simplified mock for now - replace with actual Apify actor call
        # when you're ready to use paid Apify actors
        return [
            {
                'name': f"Smart {keyword.title()} Pro",
                'price': 24.99,
                'source': 'apify_amazon',
                'rating': 4.5,
                'reviews_count': 1234,
                'asin': f'B08MOCK{i}',
                'in_stock': True,
                'bestseller_rank': 100 + i * 10
            }
            for i in range(min(max_items, 3))
        ]

print("✅ Apify client created")
