"""
Auto Competitor Discovery - AI finds your competitors automatically

This module uses AI and web scraping to automatically discover competitors based on:
1. Google search for niche keywords
2. Shopify store directories
3. Products you sell (find who else sells them)
4. Social media mentions
5. Similar store analysis

Author: OspraOS
"""

import asyncio
import logging
from typing import List, Dict, Optional
import httpx
from bs4 import BeautifulSoup
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class AutoCompetitorDiscovery:
    """
    Automatically discover competitors using AI and web intelligence
    """

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
        )

    async def discover_competitors(
        self,
        niche: str,
        our_products: List[str],
        max_competitors: int = 10
    ) -> List[Dict]:
        """
        Main discovery method - finds competitors automatically

        Args:
            niche: Your niche (e.g., "smart home", "led lighting")
            our_products: List of product names you sell
            max_competitors: Maximum competitors to find

        Returns:
            List of discovered competitor stores
        """
        logger.info(f"🔍 Starting auto-discovery for niche: {niche}")

        competitors = []

        # Method 1: Google Shopping Search
        google_competitors = await self._discover_via_google(niche, our_products)
        competitors.extend(google_competitors)

        # Method 2: Shopify Store Directories
        shopify_competitors = await self._discover_via_shopify_directory(niche)
        competitors.extend(shopify_competitors)

        # Method 3: Product-based Discovery
        product_competitors = await self._discover_via_products(our_products[:5])  # Top 5 products
        competitors.extend(product_competitors)

        # Deduplicate and score
        unique_competitors = self._deduplicate_and_score(competitors)

        # Sort by relevance score
        unique_competitors.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)

        logger.info(f"✅ Discovered {len(unique_competitors)} unique competitors")

        return unique_competitors[:max_competitors]

    async def _discover_via_google(self, niche: str, products: List[str]) -> List[Dict]:
        """
        Discover competitors via Google Shopping/Search

        Searches for:
        - "[niche] online store"
        - "buy [niche] products"
        - "[product name] buy online"
        """
        competitors = []

        search_queries = [
            f"{niche} online store",
            f"buy {niche} products online",
            f"{niche} shop",
            f"best {niche} store"
        ]

        # Add product-specific searches
        for product in products[:3]:  # Top 3 products
            search_queries.append(f"buy {product} online")

        for query in search_queries:
            try:
                # Google search URL
                url = f"https://www.google.com/search?q={query.replace(' ', '+')}"

                response = await self.client.get(url)
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')

                # Extract store URLs from search results
                links = soup.find_all('a', href=True)

                for link in links:
                    href = link.get('href', '')

                    # Extract actual URL from Google redirect
                    if '/url?q=' in href:
                        actual_url = href.split('/url?q=')[1].split('&')[0]

                        # Check if it's a store (not Google, not social media)
                        if self._is_valid_store_url(actual_url):
                            competitors.append({
                                'store_url': actual_url,
                                'discovery_method': 'google_search',
                                'discovery_query': query,
                                'relevance_score': 70
                            })

                await asyncio.sleep(2)  # Rate limiting

            except Exception as e:
                logger.error(f"Error in Google discovery: {e}")
                continue

        return competitors

    async def _discover_via_shopify_directory(self, niche: str) -> List[Dict]:
        """
        Discover Shopify stores from public directories

        Sources:
        - myip.ms Shopify directory
        - Shopify Exchange marketplace
        - Public Shopify store lists
        """
        competitors = []

        try:
            # Method 1: Search myip.ms (largest Shopify directory)
            # This is a public directory of Shopify stores
            search_url = f"https://myip.ms/browse/sites/1/own/{niche.replace(' ', '_')}"

            response = await self.client.get(search_url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Extract store URLs
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    if 'myshopify.com' in href or self._is_shopify_store(href):
                        competitors.append({
                            'store_url': href,
                            'discovery_method': 'shopify_directory',
                            'relevance_score': 80,
                            'platform': 'shopify'
                        })

        except Exception as e:
            logger.error(f"Error in Shopify directory discovery: {e}")

        return competitors

    async def _discover_via_products(self, products: List[str]) -> List[Dict]:
        """
        Find competitors by searching for who else sells your products

        Strategy:
        - Google search for each product
        - Find stores selling it
        - Those are your competitors
        """
        competitors = []

        for product in products:
            try:
                # Search for product
                query = f"{product} buy online"
                url = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=shop"

                response = await self.client.get(url)
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')

                # Extract merchant links
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')

                    if self._is_valid_store_url(href):
                        competitors.append({
                            'store_url': href,
                            'discovery_method': 'product_search',
                            'product': product,
                            'relevance_score': 90  # High score - they sell your products!
                        })

                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Error in product discovery: {e}")
                continue

        return competitors

    def _is_valid_store_url(self, url: str) -> bool:
        """
        Check if URL is a valid e-commerce store

        Filters out:
        - Google/Facebook/social media
        - Marketplaces (Amazon, eBay)
        - Non-store sites
        """
        if not url or len(url) < 10:
            return False

        # Exclude list
        exclude_domains = [
            'google.com', 'facebook.com', 'instagram.com', 'tiktok.com',
            'amazon.com', 'ebay.com', 'walmart.com', 'target.com',
            'youtube.com', 'twitter.com', 'linkedin.com',
            'wikipedia.org', 'reddit.com'
        ]

        for domain in exclude_domains:
            if domain in url.lower():
                return False

        # Must have valid TLD
        if not re.search(r'\.(com|net|org|shop|store|co)', url.lower()):
            return False

        return True

    def _is_shopify_store(self, url: str) -> bool:
        """Check if URL is a Shopify store"""
        return 'myshopify.com' in url or '/products.json' in url

    def _deduplicate_and_score(self, competitors: List[Dict]) -> List[Dict]:
        """
        Remove duplicates and calculate final relevance scores
        """
        seen_urls = {}

        for comp in competitors:
            url = comp['store_url'].lower().strip('/')

            # Clean URL
            url = re.sub(r'https?://(www\.)?', '', url)
            url = url.split('?')[0]  # Remove query params

            if url not in seen_urls:
                seen_urls[url] = comp
            else:
                # Update score if found via multiple methods
                seen_urls[url]['relevance_score'] += 10

        return list(seen_urls.values())

    async def classify_competitor(self, store_url: str, our_niche: str) -> Dict:
        """
        Classify discovered competitor

        Returns:
            competitor_type: DIRECT, INDIRECT, MARKET_LEADER, EMERGING
            threat_level: HIGH, MEDIUM, LOW
            confidence: 0-100
        """
        try:
            # Quick scrape to analyze
            response = await self.client.get(store_url)
            if response.status_code != 200:
                return {
                    'competitor_type': 'UNKNOWN',
                    'threat_level': 'LOW',
                    'confidence': 0
                }

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract text content
            text = soup.get_text().lower()

            # Count niche keyword mentions
            niche_mentions = text.count(our_niche.lower())

            # Analyze
            if niche_mentions > 10:
                competitor_type = 'DIRECT'
                threat_level = 'HIGH'
                confidence = 85
            elif niche_mentions > 5:
                competitor_type = 'DIRECT'
                threat_level = 'MEDIUM'
                confidence = 70
            elif niche_mentions > 0:
                competitor_type = 'INDIRECT'
                threat_level = 'MEDIUM'
                confidence = 60
            else:
                competitor_type = 'INDIRECT'
                threat_level = 'LOW'
                confidence = 40

            return {
                'competitor_type': competitor_type,
                'threat_level': threat_level,
                'confidence': confidence,
                'niche_mentions': niche_mentions
            }

        except Exception as e:
            logger.error(f"Error classifying competitor: {e}")
            return {
                'competitor_type': 'UNKNOWN',
                'threat_level': 'LOW',
                'confidence': 0
            }

    async def get_competitor_metadata(self, store_url: str) -> Dict:
        """
        Extract metadata about competitor

        Returns:
            - Store name
            - Platform (Shopify, WooCommerce, etc.)
            - Approximate product count
            - Social profiles
        """
        try:
            response = await self.client.get(store_url)
            if response.status_code != 200:
                return {}

            soup = BeautifulSoup(response.text, 'html.parser')

            metadata = {
                'store_name': self._extract_store_name(soup, store_url),
                'platform': self._detect_platform(response.text, store_url),
                'product_count_estimate': 0,
                'social_profiles': {}
            }

            # Try to get product count for Shopify stores
            if metadata['platform'] == 'shopify':
                product_count = await self._get_shopify_product_count(store_url)
                metadata['product_count_estimate'] = product_count

            # Extract social profiles
            social_links = soup.find_all('a', href=True)
            for link in social_links:
                href = link.get('href', '')
                if 'facebook.com' in href:
                    metadata['social_profiles']['facebook'] = href
                elif 'instagram.com' in href:
                    metadata['social_profiles']['instagram'] = href
                elif 'tiktok.com' in href:
                    metadata['social_profiles']['tiktok'] = href

            return metadata

        except Exception as e:
            logger.error(f"Error getting competitor metadata: {e}")
            return {}

    def _extract_store_name(self, soup: BeautifulSoup, url: str) -> str:
        """Extract store name from page"""
        # Try title tag
        title = soup.find('title')
        if title:
            return title.get_text().split('|')[0].strip()

        # Try h1
        h1 = soup.find('h1')
        if h1:
            return h1.get_text().strip()

        # Fallback to domain
        domain = url.split('//')[1].split('/')[0]
        return domain.replace('www.', '').split('.')[0].title()

    def _detect_platform(self, html: str, url: str) -> str:
        """Detect e-commerce platform"""
        if 'myshopify.com' in url or 'Shopify.theme' in html:
            return 'shopify'
        elif 'woocommerce' in html.lower():
            return 'woocommerce'
        elif '/dp/' in url or 'amazon.com' in url:
            return 'amazon'
        else:
            return 'custom'

    async def _get_shopify_product_count(self, store_url: str) -> int:
        """Get approximate product count for Shopify store"""
        try:
            # Shopify exposes /products.json
            products_url = f"{store_url.rstrip('/')}/products.json?limit=250"
            response = await self.client.get(products_url)

            if response.status_code == 200:
                data = response.json()
                return len(data.get('products', []))

        except:
            pass

        return 0

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# ============================================================================
# API INTEGRATION
# ============================================================================

async def auto_discover_and_add_competitors(
    niche: str,
    our_products: List[str],
    db_session,
    max_competitors: int = 5
) -> List[Dict]:
    """
    High-level function: Discover competitors and add them to database

    Usage:
        competitors = await auto_discover_and_add_competitors(
            niche="smart home",
            our_products=["LED Strip", "Smart Plug", "Motion Sensor"],
            db_session=db,
            max_competitors=5
        )
    """
    from ospra_os.intelligence.competitor_engine import CompetitorIntelligenceEngine

    discovery = AutoCompetitorDiscovery()
    engine = CompetitorIntelligenceEngine(db_session)

    try:
        # Discover competitors
        discovered = await discovery.discover_competitors(
            niche=niche,
            our_products=our_products,
            max_competitors=max_competitors
        )

        added_competitors = []

        for comp in discovered:
            store_url = comp['store_url']

            # Get classification
            classification = await discovery.classify_competitor(store_url, niche)

            # Get metadata
            metadata = await discovery.get_competitor_metadata(store_url)

            # Add to database
            try:
                competitor = await engine.add_competitor(
                    url=store_url,
                    name=metadata.get('store_name'),
                    competitor_type=classification['competitor_type'],
                    threat_level=classification['threat_level'],
                    primary_niches=[niche]
                )

                added_competitors.append(competitor)
                logger.info(f"✅ Added competitor: {metadata.get('store_name')} ({store_url})")

            except Exception as e:
                logger.error(f"Error adding competitor {store_url}: {e}")
                continue

        return added_competitors

    finally:
        await discovery.close()
