"""
Apify Base Connector - Infrastructure for all Apify scrapers

Apify handles anti-bot detection, rate limiting, and infrastructure for web scraping.
This base class provides a consistent interface for running Apify actors.
"""
from typing import Dict, List, Optional
import os
import logging
from apify_client import ApifyClient

logger = logging.getLogger(__name__)


class ApifyConnector:
    """Base class for Apify-based scrapers"""

    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize Apify connector.

        Args:
            api_token: Apify API token (if not provided, uses APIFY_API_TOKEN env var)
        """
        self.api_token = api_token or os.getenv('APIFY_API_TOKEN')

        if not self.api_token:
            logger.warning("APIFY_API_TOKEN not set - Apify scrapers will not work")
            self.client = None
            self.enabled = False
        else:
            self.client = ApifyClient(self.api_token)
            self.enabled = True
            logger.info("Apify connector initialized successfully")

    def is_available(self) -> bool:
        """Check if Apify is configured and available"""
        return self.enabled and self.client is not None

    async def run_actor(
        self,
        actor_id: str,
        run_input: Dict,
        timeout_secs: int = 300,
        memory_mbytes: int = 256
    ) -> List[Dict]:
        """
        Run an Apify actor and return results

        Args:
            actor_id: Apify actor ID (e.g., "apify/tiktok-scraper")
            run_input: Input configuration for the actor
            timeout_secs: Max runtime (default: 5 minutes)
            memory_mbytes: Memory allocation (default: 256MB)

        Returns:
            List of scraped items
        """
        if not self.is_available():
            logger.error("Apify not configured - cannot run actor")
            return []

        try:
            logger.info(f"🤖 Running Apify actor: {actor_id}")
            logger.debug(f"Input: {run_input}")

            # Run the actor
            run = self.client.actor(actor_id).call(
                run_input=run_input,
                timeout_secs=timeout_secs,
                memory_mbytes=memory_mbytes
            )

            # Get results from default dataset
            items = []
            dataset_id = run["defaultDatasetId"]

            for item in self.client.dataset(dataset_id).iterate_items():
                items.append(item)

            logger.info(f"✅ Scraped {len(items)} items from {actor_id}")
            return items

        except Exception as e:
            logger.error(f"❌ Apify actor {actor_id} failed: {e}")
            return []

    def get_usage_stats(self) -> Dict:
        """
        Get Apify usage statistics

        Returns:
            Dict with usage and limits information
        """
        if not self.is_available():
            return {'error': 'Apify not configured'}

        try:
            user = self.client.user().get()
            return {
                'usage': user.get('usage', {}),
                'limits': user.get('limits', {}),
                'email': user.get('email', 'N/A'),
                'tier': user.get('plan', 'N/A')
            }
        except Exception as e:
            logger.error(f"Error getting Apify stats: {e}")
            return {'error': str(e)}

    def list_available_actors(self, search: Optional[str] = None) -> List[Dict]:
        """
        List available Apify actors (optionally filtered by search term)

        Args:
            search: Search term to filter actors

        Returns:
            List of actor information dicts
        """
        if not self.is_available():
            return []

        try:
            store = self.client.store()
            actors = store.list_actors(search=search) if search else store.list_actors()

            result = []
            for actor in actors.get('items', []):
                result.append({
                    'id': actor.get('id'),
                    'name': actor.get('name'),
                    'username': actor.get('username'),
                    'description': actor.get('description', '')[:200],
                    'runs_count': actor.get('stats', {}).get('totalRuns', 0)
                })

            return result
        except Exception as e:
            logger.error(f"Error listing actors: {e}")
            return []
