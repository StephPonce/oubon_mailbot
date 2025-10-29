"""
Rotating proxy system for avoiding rate limits and blocks
"""

import os
import requests
from typing import Optional, Dict, List
import random
import time
import asyncio
import logging

logger = logging.getLogger(__name__)


class ProxyManager:
    """
    Manages rotating proxies for web scraping
    Handles rate limiting, retries, and IP rotation
    """

    def __init__(self):
        # ScraperAPI - $49/mo for 100k requests
        # Handles proxies, CAPTCHA, JavaScript rendering
        self.scraper_api_key = os.getenv('SCRAPERAPI_KEY')

        # Backup: Free proxy list
        self.free_proxies = []
        self.current_proxy_index = 0

        # Rate limiting
        self.requests_made = 0
        self.last_request_time = time.time()
        self.requests_per_second = 5

        # User agent rotation
        self.user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0'
        ]

    async def get_with_proxy(self, url: str, use_premium: bool = True) -> bytes:
        """
        Fetch URL with rotating proxy
        Returns raw bytes (for images and HTML)
        """
        # Rate limiting
        await self._rate_limit()

        if use_premium and self.scraper_api_key:
            return await self._scraper_api_request(url)
        else:
            return await self._free_proxy_request(url)

    async def _scraper_api_request(self, url: str) -> bytes:
        """
        Use ScraperAPI (premium, reliable)
        Handles: Proxies, CAPTCHA, JS rendering, retries
        """
        try:
            # ScraperAPI endpoint
            scraper_url = f"http://api.scraperapi.com?api_key={self.scraper_api_key}&url={url}&render=true&country_code=us&premium=true"

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: requests.get(scraper_url, timeout=30)
            )

            if response.status_code == 200:
                self.requests_made += 1
                logger.info(f"✅ ScraperAPI: {url[:50]}...")
                return response.content
            else:
                logger.warning(f"ScraperAPI returned {response.status_code}")
                return await self._free_proxy_request(url)

        except Exception as e:
            logger.error(f"ScraperAPI error: {e}")
            # Fallback to free proxies
            return await self._free_proxy_request(url)

    async def _free_proxy_request(self, url: str) -> bytes:
        """
        Use free rotating proxies (backup)
        """
        # Try direct connection first (fastest)
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: requests.get(
                    url,
                    timeout=10,
                    headers={'User-Agent': self._random_user_agent()}
                )
            )

            if response.status_code == 200:
                self.requests_made += 1
                logger.info(f"✅ Direct: {url[:50]}...")
                return response.content
        except Exception as e:
            logger.warning(f"Direct connection failed: {e}")

        # If direct fails, try proxies
        if not self.free_proxies:
            await self._fetch_free_proxies()

        # Try up to 3 proxies
        for attempt in range(3):
            proxy = self._get_next_proxy()

            if not proxy:
                break

            try:
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: requests.get(
                        url,
                        proxies={'http': proxy, 'https': proxy},
                        timeout=10,
                        headers={'User-Agent': self._random_user_agent()}
                    )
                )

                if response.status_code == 200:
                    self.requests_made += 1
                    logger.info(f"✅ Proxy: {url[:50]}...")
                    return response.content

            except Exception as e:
                logger.warning(f"Proxy {proxy} failed: {e}")
                continue

        # All methods failed
        raise Exception(f"Failed to fetch {url} after multiple attempts")

    async def _fetch_free_proxies(self):
        """
        Get list of free proxies
        """
        logger.info("Fetching free proxy list...")

        # Free proxy providers
        sources = [
            'https://www.proxy-list.download/api/v1/get?type=http',
            'https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all'
        ]

        for source in sources:
            try:
                response = requests.get(source, timeout=5)
                proxies = response.text.strip().split('\n')
                self.free_proxies.extend(proxies)
                logger.info(f"✅ Fetched {len(proxies)} proxies from {source[:30]}...")
            except Exception as e:
                logger.warning(f"Failed to fetch proxies from {source}: {e}")
                continue

        # Remove duplicates
        self.free_proxies = list(set(self.free_proxies))
        logger.info(f"Total free proxies available: {len(self.free_proxies)}")

    def _get_next_proxy(self) -> Optional[str]:
        """Rotate to next proxy"""
        if not self.free_proxies:
            return None

        proxy = self.free_proxies[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.free_proxies)
        return f"http://{proxy}"

    async def _rate_limit(self):
        """Rate limiting to avoid detection"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < (1.0 / self.requests_per_second):
            delay = (1.0 / self.requests_per_second) - time_since_last
            await asyncio.sleep(delay)

        self.last_request_time = time.time()

    def _random_user_agent(self) -> str:
        """Random user agent to avoid detection"""
        return random.choice(self.user_agents)

    def get_stats(self) -> Dict:
        """Get proxy manager statistics"""
        return {
            'requests_made': self.requests_made,
            'has_premium': bool(self.scraper_api_key),
            'free_proxies_available': len(self.free_proxies),
            'requests_per_second': self.requests_per_second
        }


# Singleton instance
proxy_manager = ProxyManager()
