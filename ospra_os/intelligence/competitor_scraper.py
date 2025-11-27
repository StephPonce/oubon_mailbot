"""
Competitor Scraper - Web scraping for competitor stores

Supports:
- Shopify stores (via /products.json API)
- Amazon storefronts
- WooCommerce stores
- Custom e-commerce sites

Author: OspraOS
Date: November 2025
"""

import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
import json

logger = logging.getLogger(__name__)


class CompetitorScraper:
    """Scrapes competitor websites for product and pricing data"""

    def __init__(self):
        self.timeout = httpx.Timeout(30.0)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    async def detect_platform(self, url: str) -> str:
        """
        Detect what e-commerce platform a competitor uses

        Args:
            url: Store URL

        Returns:
            Platform identifier: shopify, amazon, woocommerce, custom
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers, follow_redirects=True) as client:
                response = await client.get(url)
                html = response.text
                headers = dict(response.headers)

                # Check for Shopify
                if 'X-ShopId' in headers or 'shopify' in html.lower():
                    return 'shopify'

                # Check for Amazon
                if 'amazon.com' in url or 'amazon' in urlparse(url).netloc:
                    return 'amazon'

                # Check for WooCommerce
                if 'woocommerce' in html.lower() or 'wp-content/plugins/woocommerce' in html:
                    return 'woocommerce'

                # Check for other platforms
                if 'bigcommerce' in html.lower():
                    return 'bigcommerce'

                if 'magento' in html.lower():
                    return 'magento'

                return 'custom'

        except Exception as e:
            logger.error(f"Error detecting platform for {url}: {e}")
            return 'unknown'

    async def scrape_shopify_store(self, store_url: str) -> dict:
        """
        Scrape Shopify store using public /products.json endpoint

        Args:
            store_url: Base URL of Shopify store

        Returns:
            {
                'platform': 'shopify',
                'store_url': str,
                'products': list,
                'product_count': int,
                'scraped_at': datetime
            }
        """
        logger.info(f"Scraping Shopify store: {store_url}")

        # Normalize URL
        if not store_url.startswith('http'):
            store_url = f'https://{store_url}'
        store_url = store_url.rstrip('/')

        products = []
        page = 1
        max_pages = 100  # Safety limit

        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers, follow_redirects=True) as client:
                while page <= max_pages:
                    url = f"{store_url}/products.json?page={page}&limit=250"

                    try:
                        response = await client.get(url)

                        if response.status_code != 200:
                            logger.warning(f"Failed to fetch page {page}: HTTP {response.status_code}")
                            break

                        data = response.json()
                        page_products = data.get('products', [])

                        if not page_products:
                            break

                        # Parse products
                        for product in page_products:
                            parsed_product = self._parse_shopify_product(product, store_url)
                            products.append(parsed_product)

                        logger.info(f"Scraped page {page}: {len(page_products)} products")

                        # Rate limiting
                        await asyncio.sleep(1)
                        page += 1

                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON response from page {page}")
                        break
                    except Exception as e:
                        logger.error(f"Error scraping page {page}: {e}")
                        break

            result = {
                'platform': 'shopify',
                'store_url': store_url,
                'products': products,
                'product_count': len(products),
                'scraped_at': datetime.utcnow().isoformat()
            }

            logger.info(f"Successfully scraped {len(products)} products from Shopify store")
            return result

        except Exception as e:
            logger.error(f"Error scraping Shopify store {store_url}: {e}")
            return {
                'platform': 'shopify',
                'store_url': store_url,
                'products': [],
                'product_count': 0,
                'error': str(e),
                'scraped_at': datetime.utcnow().isoformat()
            }

    def _parse_shopify_product(self, product_data: dict, store_url: str) -> dict:
        """Parse Shopify product JSON into standardized format"""

        # Get first variant for pricing
        first_variant = product_data.get('variants', [{}])[0]

        # Calculate discount if compare_at_price exists
        price = float(first_variant.get('price', 0))
        compare_price = first_variant.get('compare_at_price')
        discount_percent = 0

        if compare_price:
            compare_price = float(compare_price)
            if compare_price > price:
                discount_percent = ((compare_price - price) / compare_price) * 100

        # Get images
        images = [img['src'] for img in product_data.get('images', [])]

        return {
            'shopify_product_id': str(product_data.get('id')),
            'name': product_data.get('title'),
            'handle': product_data.get('handle'),
            'url': f"{store_url}/products/{product_data.get('handle')}",
            'description': product_data.get('body_html', ''),
            'vendor': product_data.get('vendor'),
            'product_type': product_data.get('product_type'),
            'tags': product_data.get('tags', '').split(',') if product_data.get('tags') else [],
            'price': price,
            'original_price': compare_price,
            'discount_percent': round(discount_percent, 2) if discount_percent > 0 else 0,
            'currency': 'USD',  # Could be parsed from variant
            'images': images,
            'image_url': images[0] if images else None,
            'variants_count': len(product_data.get('variants', [])),
            'variants_data': product_data.get('variants', []),
            'shopify_created_at': product_data.get('created_at'),
            'shopify_updated_at': product_data.get('updated_at'),
            'available': first_variant.get('available', False),
            'inventory_quantity': first_variant.get('inventory_quantity'),
        }

    async def scrape_product_page(self, url: str) -> Optional[dict]:
        """
        Scrape individual product page (for non-Shopify or specific products)

        Args:
            url: Product page URL

        Returns:
            Product data dict or None
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers, follow_redirects=True) as client:
                response = await client.get(url)

                if response.status_code != 200:
                    logger.warning(f"Failed to fetch product page: HTTP {response.status_code}")
                    return None

                soup = BeautifulSoup(response.text, 'html.parser')

                # Try to extract basic product info
                # This is a generic approach - may need platform-specific logic

                product = {
                    'url': url,
                    'scraped_at': datetime.utcnow().isoformat()
                }

                # Title
                title_tag = (
                    soup.find('h1', class_=lambda x: x and 'product' in x.lower() if x else False) or
                    soup.find('h1') or
                    soup.find('title')
                )
                if title_tag:
                    product['name'] = title_tag.get_text(strip=True)

                # Price - try multiple selectors
                price_selectors = [
                    {'class': lambda x: x and 'price' in x.lower() if x else False},
                    {'itemprop': 'price'},
                    {'class': 'product-price'},
                ]

                for selector in price_selectors:
                    price_tag = soup.find(['span', 'div', 'p'], selector)
                    if price_tag:
                        price_text = price_tag.get_text(strip=True)
                        # Extract numeric price
                        import re
                        price_match = re.search(r'\d+\.?\d*', price_text.replace(',', ''))
                        if price_match:
                            product['price'] = float(price_match.group())
                            break

                # Image
                img_tag = soup.find('img', {'class': lambda x: x and 'product' in x.lower() if x else False})
                if img_tag and img_tag.get('src'):
                    product['image_url'] = img_tag['src']

                # Description
                desc_tag = soup.find('div', {'class': lambda x: x and 'description' in x.lower() if x else False})
                if desc_tag:
                    product['description'] = desc_tag.get_text(strip=True)

                return product

        except Exception as e:
            logger.error(f"Error scraping product page {url}: {e}")
            return None

    async def scrape_all_products(self, store_url: str) -> List[dict]:
        """
        Scrape all products from a store (platform-agnostic)

        Args:
            store_url: Store URL

        Returns:
            List of product dicts
        """
        # Detect platform
        platform = await self.detect_platform(store_url)
        logger.info(f"Detected platform: {platform}")

        # Use platform-specific scraper
        if platform == 'shopify':
            result = await self.scrape_shopify_store(store_url)
            return result.get('products', [])

        elif platform == 'amazon':
            logger.warning("Amazon scraping not yet implemented")
            return []

        elif platform == 'woocommerce':
            logger.warning("WooCommerce scraping not yet implemented")
            return []

        else:
            logger.warning(f"Scraping for platform '{platform}' not yet implemented")
            return []

    async def get_store_info(self, store_url: str) -> dict:
        """
        Get basic store information

        Args:
            store_url: Store URL

        Returns:
            Store info dict
        """
        platform = await self.detect_platform(store_url)

        info = {
            'store_url': store_url,
            'platform': platform,
            'checked_at': datetime.utcnow().isoformat()
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers, follow_redirects=True) as client:
                response = await client.get(store_url)
                soup = BeautifulSoup(response.text, 'html.parser')

                # Try to get store name
                title_tag = soup.find('title')
                if title_tag:
                    info['store_name'] = title_tag.get_text(strip=True)

                # Try to get meta description
                meta_desc = soup.find('meta', {'name': 'description'})
                if meta_desc and meta_desc.get('content'):
                    info['description'] = meta_desc['content']

                # Social links
                social_links = {}
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if 'facebook.com' in href:
                        social_links['facebook'] = href
                    elif 'instagram.com' in href:
                        social_links['instagram'] = href
                    elif 'twitter.com' in href or 'x.com' in href:
                        social_links['twitter'] = href
                    elif 'tiktok.com' in href:
                        social_links['tiktok'] = href

                if social_links:
                    info['social_links'] = social_links

        except Exception as e:
            logger.error(f"Error getting store info for {store_url}: {e}")
            info['error'] = str(e)

        return info

    async def check_product_availability(self, product_url: str) -> dict:
        """
        Check if a product is still available/in stock

        Args:
            product_url: Product page URL

        Returns:
            {'available': bool, 'in_stock': bool, 'price': float}
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers, follow_redirects=True) as client:
                response = await client.get(product_url)

                if response.status_code == 404:
                    return {'available': False, 'in_stock': False}

                if response.status_code != 200:
                    return {'available': None, 'error': f'HTTP {response.status_code}'}

                soup = BeautifulSoup(response.text, 'html.parser')

                # Check for out of stock indicators
                out_of_stock_texts = ['out of stock', 'sold out', 'unavailable', 'not available']
                page_text = soup.get_text().lower()

                in_stock = not any(text in page_text for text in out_of_stock_texts)

                # Try to get current price
                price = None
                price_tag = soup.find(['span', 'div'], {'class': lambda x: x and 'price' in x.lower() if x else False})
                if price_tag:
                    price_text = price_tag.get_text(strip=True)
                    import re
                    price_match = re.search(r'\d+\.?\d*', price_text.replace(',', ''))
                    if price_match:
                        price = float(price_match.group())

                return {
                    'available': True,
                    'in_stock': in_stock,
                    'price': price,
                    'checked_at': datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(f"Error checking product availability: {e}")
            return {'available': None, 'error': str(e)}
