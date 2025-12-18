"""
Apify Integration - REAL API Calls for Amazon & TikTok Data
============================================================

Uses your $39/month Apify subscription for:
- Amazon Bestsellers scraping
- Amazon Product search
- TikTok trending products
- TikTok hashtag search

NO MOCK DATA. REAL API CALLS ONLY.
"""
import os
import asyncio
import httpx
from typing import Dict, List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ApifyProduct:
    """Product data from Apify scraper"""
    name: str
    price: float
    source: str
    url: str = ""
    image_url: str = ""
    rating: float = 0.0
    reviews_count: int = 0
    asin: str = ""
    bestseller_rank: int = 0
    category: str = ""
    in_stock: bool = True
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'price': self.price,
            'source': self.source,
            'url': self.url,
            'image_url': self.image_url,
            'rating': self.rating,
            'reviews_count': self.reviews_count,
            'asin': self.asin,
            'bestseller_rank': self.bestseller_rank,
            'category': self.category,
            'in_stock': self.in_stock,
        }


class ApifyClient:
    """
    Production Apify Client - REAL API calls
    
    Your subscription: $39/month
    Actors available:
    - junglee/amazon-bestsellers (Amazon bestsellers by category)
    - apify/amazon-crawler (Full Amazon product search)
    - clockworks/tiktok-scraper (TikTok videos & hashtags)
    """
    
    # Popular Apify actors for e-commerce
    ACTORS = {
        'amazon_bestsellers': 'junglee/amazon-bestsellers',
        'amazon_search': 'apify/amazon-crawler', 
        'tiktok_scraper': 'clockworks/tiktok-scraper',
        'tiktok_hashtag': 'clockworks/tiktok-hashtag-scraper',
    }
    
    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize Apify client
        
        Args:
            api_token: Apify API token. If None, reads from APIFY_API_TOKEN env var.
        """
        self.api_token = api_token or os.getenv('APIFY_API_TOKEN')
        self.base_url = "https://api.apify.com/v2"
        
        if not self.api_token:
            raise ValueError("APIFY_API_TOKEN not set. Get yours at https://console.apify.com/account/integrations")
        
        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }
        
        print(f"✅ Apify client initialized (token: {self.api_token[:10]}...)")
    
    def is_available(self) -> bool:
        """Check if Apify is configured"""
        return bool(self.api_token)
    
    async def test_connection(self) -> Dict:
        """Test API connection and get account info"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/users/me",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    data = response.json()['data']
                    return {
                        'connected': True,
                        'username': data.get('username', 'unknown'),
                        'email': data.get('email', 'unknown'),
                        'plan': data.get('plan', {}).get('id', 'unknown'),
                    }
                else:
                    return {
                        'connected': False,
                        'error': f"HTTP {response.status_code}: {response.text}"
                    }
        except Exception as e:
            return {
                'connected': False,
                'error': str(e)
            }
    
    async def run_actor(
        self,
        actor_id: str,
        run_input: Dict,
        timeout_secs: int = 300,
        memory_mbytes: int = 512
    ) -> List[Dict]:
        """
        Run an Apify actor and wait for results
        
        Args:
            actor_id: Actor ID (e.g., "junglee/amazon-bestsellers")
            run_input: Input configuration for the actor
            timeout_secs: Max seconds to wait (default 5 minutes)
            memory_mbytes: Memory allocation (higher = faster but more expensive)
        
        Returns:
            List of results from the actor
        """
        # Convert actor ID format for API
        actor_id_safe = actor_id.replace('/', '~')
        
        print(f"🚀 Starting Apify actor: {actor_id}")
        print(f"   Input: {run_input}")
        
        try:
            async with httpx.AsyncClient(timeout=timeout_secs) as client:
                # Start the actor run
                run_url = f"{self.base_url}/acts/{actor_id_safe}/runs"
                
                response = await client.post(
                    run_url,
                    headers=self.headers,
                    json={
                        **run_input,
                        "memory": memory_mbytes
                    }
                )
                
                if response.status_code not in [200, 201]:
                    print(f"❌ Failed to start actor: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return []
                
                run_data = response.json()['data']
                run_id = run_data['id']
                
                print(f"   Run ID: {run_id}")
                print(f"   Waiting for completion...")
                
                # Poll for completion
                status_url = f"{self.base_url}/actor-runs/{run_id}"
                
                poll_interval = 5
                max_polls = timeout_secs // poll_interval
                
                for attempt in range(max_polls):
                    await asyncio.sleep(poll_interval)
                    
                    status_response = await client.get(status_url, headers=self.headers)
                    status_data = status_response.json()['data']
                    status = status_data['status']
                    
                    if status == "SUCCEEDED":
                        # Get results from dataset
                        dataset_id = status_data['defaultDatasetId']
                        results_url = f"{self.base_url}/datasets/{dataset_id}/items"
                        
                        results_response = await client.get(
                            results_url,
                            headers=self.headers,
                            params={'limit': 100}
                        )
                        
                        results = results_response.json()
                        print(f"✅ Actor completed! Got {len(results)} results")
                        return results
                    
                    elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                        print(f"❌ Actor {status}: {actor_id}")
                        return []
                    
                    # Still running
                    elapsed = (attempt + 1) * poll_interval
                    if elapsed % 30 == 0:
                        print(f"   Still running... ({elapsed}s)")
                
                print(f"⏰ Timeout after {timeout_secs}s waiting for {actor_id}")
                return []
                
        except Exception as e:
            print(f"❌ Error running actor {actor_id}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def get_amazon_bestsellers(
        self,
        category: str = "Home & Kitchen",
        country: str = "US",
        max_items: int = 20
    ) -> List[ApifyProduct]:
        """
        Get Amazon bestsellers for a category
        
        Popular categories for dropshipping:
        - "Home & Kitchen"
        - "Electronics"
        - "Sports & Outdoors"
        - "Beauty & Personal Care"
        - "Toys & Games"
        - "Pet Supplies"
        """
        print(f"🏆 Fetching Amazon bestsellers: {category}")
        
        results = await self.run_actor(
            actor_id=self.ACTORS['amazon_bestsellers'],
            run_input={
                "categoryUrls": [
                    f"https://www.amazon.com/Best-Sellers-{category.replace(' ', '-').replace('&', '')}/zgbs"
                ],
                "maxItems": max_items,
                "proxy": {
                    "useApifyProxy": True,
                    "apifyProxyGroups": ["RESIDENTIAL"]
                }
            },
            timeout_secs=180
        )
        
        products = []
        for item in results:
            try:
                product = ApifyProduct(
                    name=item.get('title', item.get('name', 'Unknown')),
                    price=float(item.get('price', {}).get('value', 0) if isinstance(item.get('price'), dict) else item.get('price', 0)),
                    source='apify_amazon',
                    url=item.get('url', item.get('productUrl', '')),
                    image_url=item.get('image', item.get('imageUrl', '')),
                    rating=float(item.get('rating', 0)),
                    reviews_count=int(item.get('reviewsCount', item.get('reviews', 0))),
                    asin=item.get('asin', ''),
                    bestseller_rank=int(item.get('rank', item.get('bestsellersRank', 0))),
                    category=category,
                    in_stock=item.get('inStock', True)
                )
                products.append(product)
            except Exception as e:
                print(f"   ⚠️ Error parsing product: {e}")
                continue
        
        print(f"   Found {len(products)} bestsellers")
        return products
    
    async def search_amazon(
        self,
        keyword: str,
        max_items: int = 20,
        min_rating: float = 4.0
    ) -> List[ApifyProduct]:
        """
        Search Amazon products by keyword
        """
        print(f"🔍 Searching Amazon for: {keyword}")
        
        results = await self.run_actor(
            actor_id=self.ACTORS['amazon_search'],
            run_input={
                "searchTerms": [keyword],
                "maxItems": max_items,
                "filterByMinRating": min_rating,
                "proxy": {
                    "useApifyProxy": True
                }
            },
            timeout_secs=180
        )
        
        products = []
        for item in results:
            try:
                price_str = item.get('price', '0')
                if isinstance(price_str, str):
                    price_str = price_str.replace('$', '').replace(',', '')
                price = float(price_str) if price_str else 0
                
                product = ApifyProduct(
                    name=item.get('title', 'Unknown'),
                    price=price,
                    source='apify_amazon',
                    url=item.get('url', ''),
                    image_url=item.get('thumbnailImage', item.get('image', '')),
                    rating=float(item.get('stars', 0)),
                    reviews_count=int(item.get('reviewsCount', 0)),
                    asin=item.get('asin', ''),
                    bestseller_rank=int(item.get('bsr', 0)),
                    category=keyword,
                    in_stock=item.get('inStock', True)
                )
                products.append(product)
            except Exception as e:
                print(f"   ⚠️ Error parsing product: {e}")
                continue
        
        print(f"   Found {len(products)} products")
        return products
    
    async def get_tiktok_trending(
        self,
        hashtag: str = "tiktokmademebuyit",
        max_videos: int = 20
    ) -> List[Dict]:
        """
        Get trending TikTok videos for product discovery
        
        Popular hashtags:
        - tiktokmademebuyit
        - amazonfinds
        - musthave
        - coolgadgets
        - smarthome
        """
        print(f"📱 Fetching TikTok trends: #{hashtag}")
        
        results = await self.run_actor(
            actor_id=self.ACTORS['tiktok_hashtag'],
            run_input={
                "hashtags": [hashtag],
                "resultsPerPage": max_videos,
                "shouldDownloadVideos": False,
                "proxy": {
                    "useApifyProxy": True
                }
            },
            timeout_secs=180
        )
        
        videos = []
        for item in results:
            try:
                video = {
                    'id': item.get('id', ''),
                    'description': item.get('text', item.get('desc', '')),
                    'author': item.get('authorMeta', {}).get('name', 'unknown'),
                    'views': int(item.get('playCount', item.get('stats', {}).get('playCount', 0))),
                    'likes': int(item.get('diggCount', item.get('stats', {}).get('diggCount', 0))),
                    'comments': int(item.get('commentCount', item.get('stats', {}).get('commentCount', 0))),
                    'shares': int(item.get('shareCount', item.get('stats', {}).get('shareCount', 0))),
                    'url': item.get('webVideoUrl', f"https://tiktok.com/@{item.get('authorMeta', {}).get('name', '')}/video/{item.get('id', '')}"),
                    'hashtag': hashtag,
                    'source': 'apify_tiktok',
                }
                
                # Calculate viral score (0-100)
                engagement = video['likes'] + video['comments'] * 2 + video['shares'] * 3
                views = max(video['views'], 1)
                engagement_rate = engagement / views
                
                # Score based on views and engagement
                view_score = min(50, video['views'] / 100000 * 50)  # Max 50 from views
                engagement_score = min(50, engagement_rate * 1000)  # Max 50 from engagement
                video['viral_score'] = round(view_score + engagement_score, 1)
                
                videos.append(video)
            except Exception as e:
                print(f"   ⚠️ Error parsing video: {e}")
                continue
        
        # Sort by viral score
        videos.sort(key=lambda x: x['viral_score'], reverse=True)
        
        print(f"   Found {len(videos)} trending videos")
        return videos
    
    async def discover_products_for_ospra(
        self,
        niches: List[str] = None,
        max_products: int = 20
    ) -> List[Dict]:
        """
        Comprehensive product discovery using Apify
        
        Combines:
        1. Amazon bestsellers
        2. Amazon keyword search
        3. TikTok viral products
        """
        if not niches:
            niches = ['smart home', 'kitchen gadgets', 'fitness']
        
        all_products = []
        
        # Amazon categories mapping
        amazon_categories = {
            'smart home': 'Home & Kitchen',
            'kitchen': 'Home & Kitchen',
            'fitness': 'Sports & Outdoors',
            'beauty': 'Beauty & Personal Care',
            'pet': 'Pet Supplies',
            'tech': 'Electronics',
        }
        
        for niche in niches:
            print(f"\n🔍 Discovering products for: {niche}")
            
            # 1. Amazon bestsellers
            category = amazon_categories.get(niche.lower(), 'Home & Kitchen')
            try:
                bestsellers = await self.get_amazon_bestsellers(
                    category=category,
                    max_items=max_products // 2
                )
                for p in bestsellers:
                    product_dict = p.to_dict()
                    product_dict['niche'] = niche
                    product_dict['discovery_method'] = 'amazon_bestseller'
                    all_products.append(product_dict)
            except Exception as e:
                print(f"   ⚠️ Amazon bestsellers failed: {e}")
            
            # 2. Amazon search
            try:
                search_results = await self.search_amazon(
                    keyword=niche,
                    max_items=max_products // 2
                )
                for p in search_results:
                    product_dict = p.to_dict()
                    product_dict['niche'] = niche
                    product_dict['discovery_method'] = 'amazon_search'
                    all_products.append(product_dict)
            except Exception as e:
                print(f"   ⚠️ Amazon search failed: {e}")
        
        # 3. TikTok viral (once for all niches)
        try:
            tiktok_videos = await self.get_tiktok_trending(
                hashtag="tiktokmademebuyit",
                max_videos=max_products
            )
            for video in tiktok_videos:
                # Extract potential product mentions from description
                all_products.append({
                    'name': video['description'][:100],
                    'price': 0,  # Need to cross-reference
                    'source': 'apify_tiktok',
                    'url': video['url'],
                    'viral_score': video['viral_score'],
                    'views': video['views'],
                    'likes': video['likes'],
                    'discovery_method': 'tiktok_viral',
                    'niche': 'tiktok',
                })
        except Exception as e:
            print(f"   ⚠️ TikTok trends failed: {e}")
        
        print(f"\n✅ Total products discovered: {len(all_products)}")
        return all_products


# Factory function for Intelligence Engine
def get_apify_client(api_token: Optional[str] = None) -> ApifyClient:
    """Get configured Apify client"""
    return ApifyClient(api_token=api_token)


# Quick test
async def test_apify():
    """Test Apify connection and basic functionality"""
    print("\n" + "="*70)
    print("🧪 TESTING APIFY INTEGRATION")
    print("="*70 + "\n")
    
    try:
        client = ApifyClient()
        
        # Test connection
        print("1️⃣ Testing connection...")
        connection = await client.test_connection()
        
        if connection['connected']:
            print(f"   ✅ Connected as: {connection['username']}")
            print(f"   📧 Email: {connection['email']}")
            print(f"   💳 Plan: {connection['plan']}")
        else:
            print(f"   ❌ Connection failed: {connection['error']}")
            return
        
        # Test Amazon bestsellers (small test)
        print("\n2️⃣ Testing Amazon bestsellers...")
        bestsellers = await client.get_amazon_bestsellers(
            category="Home & Kitchen",
            max_items=5
        )
        
        for p in bestsellers[:3]:
            print(f"   📦 {p.name[:50]}...")
            print(f"      ${p.price:.2f} | ⭐{p.rating} | #{p.bestseller_rank}")
        
        print("\n✅ Apify integration working!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_apify())
