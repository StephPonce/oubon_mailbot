"""
Base Apify Client - ACTUALLY CALLS APIFY API
"""
import os
import asyncio
import httpx
from typing import Dict, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ApifyConnector:
    """Base connector for Apify scrapers - ACTUALLY calls Apify API"""

    def __init__(self):
        self.api_token = os.getenv('APIFY_API_TOKEN')
        self.base_url = "https://api.apify.com/v2"
        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        } if self.api_token else None

    def is_available(self) -> bool:
        """Check if Apify is configured and available"""
        return bool(self.api_token)

    async def run_actor(
        self,
        actor_id: str,
        run_input: Dict,
        timeout_secs: int = 180
    ) -> List[Dict]:
        """
        Run an Apify actor and wait for results

        Args:
            actor_id: Apify actor ID (e.g., "junglee/amazon-bestsellers")
            run_input: Input configuration for the actor
            timeout_secs: Max seconds to wait

        Returns:
            List of results from the actor
        """
        try:
            print(f"🚀 Starting Apify actor: {actor_id}")

            # Convert actor_id format: "user/actor" -> "user~actor" (Apify uses ~ separator)
            actor_id = actor_id.replace('/', '~')

            # Start the actor run
            run_url = f"{self.base_url}/acts/{actor_id}/runs"

            async with httpx.AsyncClient(timeout=timeout_secs) as client:
                # Start run
                response = await client.post(
                    run_url,
                    headers=self.headers,
                    json=run_input
                )

                if response.status_code not in [200, 201]:
                    print(f"❌ Failed to start actor: {response.status_code}")
                    print(response.text)
                    return []

                run_data = response.json()['data']
                run_id = run_data['id']

                print(f"   Run ID: {run_id}")
                print(f"   Waiting for results...")

                # Poll for completion
                status_url = f"{self.base_url}/acts/{actor_id}/runs/{run_id}"

                for attempt in range(36):  # 3 minutes max
                    await asyncio.sleep(5)

                    status_response = await client.get(status_url, headers=self.headers)
                    status_data = status_response.json()['data']
                    status = status_data['status']

                    if status == "SUCCEEDED":
                        # Get results
                        dataset_id = status_data['defaultDatasetId']
                        results_url = f"{self.base_url}/datasets/{dataset_id}/items"

                        results_response = await client.get(results_url, headers=self.headers)
                        results = results_response.json()

                        print(f"✅ Got {len(results)} results from {actor_id}")
                        return results

                    elif status == "FAILED":
                        print(f"❌ Actor failed: {actor_id}")
                        return []

                    # Still running
                    if attempt % 3 == 0 and attempt > 0:
                        print(f"   Still running... ({attempt * 5}s)")

                print(f"⏰ Timeout waiting for {actor_id}")
                return []

        except Exception as e:
            print(f"❌ Error running actor {actor_id}: {e}")
            import traceback
            traceback.print_exc()
            return []
