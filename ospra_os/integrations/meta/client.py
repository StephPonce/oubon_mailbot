"""
Meta Business API Client - Facebook & Instagram Ads
"""
import os
import httpx
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()


class MetaAdsClient:
    """Client for Meta (Facebook/Instagram) Ads API"""

    def __init__(self, access_token: str = None, ad_account_id: str = None):
        """
        Initialize Meta Ads client

        Args:
            access_token: Meta API access token
            ad_account_id: Ad account ID (format: act_123456789)
        """
        self.access_token = access_token or os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = ad_account_id or os.getenv('META_AD_ACCOUNT_ID')

        if not self.access_token:
            raise ValueError("Meta access token not found in environment")

        if not self.ad_account_id:
            raise ValueError("Meta ad account ID not found in environment")

        # Ensure ad account ID has 'act_' prefix
        if not self.ad_account_id.startswith('act_'):
            self.ad_account_id = f"act_{self.ad_account_id}"

        self.base_url = "https://graph.facebook.com/v18.0"
        self.default_params = {
            'access_token': self.access_token
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Dict = None,
        data: Dict = None
    ) -> Dict:
        """Make API request to Meta"""
        try:
            url = f"{self.base_url}/{endpoint}"

            # Merge params with access token
            request_params = {**self.default_params}
            if params:
                request_params.update(params)

            async with httpx.AsyncClient(timeout=30.0) as client:
                if method == 'GET':
                    response = await client.get(url, params=request_params)
                elif method == 'POST':
                    response = await client.post(
                        url,
                        params=request_params,
                        json=data
                    )
                elif method == 'DELETE':
                    response = await client.delete(url, params=request_params)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                if response.status_code not in [200, 201]:
                    print(f"[ERROR] Meta API error: {response.status_code}")
                    print(response.text)
                    return None

                result = response.json()

                # Check for API errors
                if 'error' in result:
                    error = result['error']
                    print(f"[ERROR] Meta error: {error.get('message')}")
                    return None

                return result

        except Exception as e:
            print(f"[ERROR] Request error: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def get_ad_account(self) -> Dict:
        """Get ad account information"""
        try:
            result = await self._make_request(
                'GET',
                f"{self.ad_account_id}",
                params={'fields': 'name,currency,account_status,balance,spend_cap'}
            )

            return result

        except Exception as e:
            print(f"[ERROR] Error getting ad account: {e}")
            return None

    async def create_campaign(
        self,
        name: str,
        objective: str = 'OUTCOME_SALES',
        status: str = 'PAUSED',
        special_ad_categories: List[str] = None
    ) -> Dict:
        """
        Create ad campaign

        Args:
            name: Campaign name
            objective: Campaign objective (OUTCOME_SALES, OUTCOME_TRAFFIC, etc.)
            status: ACTIVE or PAUSED
            special_ad_categories: e.g., ['HOUSING', 'EMPLOYMENT', 'CREDIT']

        Returns:
            Campaign data with campaign_id
        """
        try:
            print(f" Creating Meta campaign: {name}")

            data = {
                'name': name,
                'objective': objective,
                'status': status,
                'special_ad_categories': special_ad_categories or []
            }

            result = await self._make_request(
                'POST',
                f"{self.ad_account_id}/campaigns",
                data=data
            )

            if result:
                print(f"[SUCCESS] Campaign created! ID: {result.get('id')}")

            return result

        except Exception as e:
            print(f"[ERROR] Campaign creation error: {e}")
            return None

    async def create_ad_set(
        self,
        campaign_id: str,
        name: str,
        daily_budget: int,  # In cents (e.g., 1000 = $10)
        targeting: Dict,
        optimization_goal: str = 'OFFSITE_CONVERSIONS',
        billing_event: str = 'IMPRESSIONS',
        bid_strategy: str = 'LOWEST_COST_WITHOUT_CAP',
        status: str = 'PAUSED'
    ) -> Dict:
        """
        Create ad set (defines budget, schedule, targeting)

        Args:
            campaign_id: Parent campaign ID
            name: Ad set name
            daily_budget: Daily budget in cents
            targeting: Audience targeting specs
            optimization_goal: What to optimize for
            billing_event: When you're charged
            bid_strategy: Bidding strategy
            status: ACTIVE or PAUSED
        """
        try:
            print(f"[TARGET] Creating ad set: {name}")

            data = {
                'name': name,
                'campaign_id': campaign_id,
                'daily_budget': daily_budget,
                'billing_event': billing_event,
                'optimization_goal': optimization_goal,
                'bid_strategy': bid_strategy,
                'targeting': targeting,
                'status': status
            }

            result = await self._make_request(
                'POST',
                f"{self.ad_account_id}/adsets",
                data=data
            )

            if result:
                print(f"[SUCCESS] Ad set created! ID: {result.get('id')}")

            return result

        except Exception as e:
            print(f"[ERROR] Ad set creation error: {e}")
            return None

    async def create_ad_creative(
        self,
        name: str,
        title: str,
        body: str,
        image_url: str = None,
        video_id: str = None,
        link: str = None,
        call_to_action: str = 'SHOP_NOW'
    ) -> Dict:
        """
        Create ad creative (the actual ad content)

        Args:
            name: Creative name
            title: Ad headline
            body: Ad text/description
            image_url: Image URL (for image ads)
            video_id: Video ID (for video ads)
            link: Destination URL
            call_to_action: CTA button type
        """
        try:
            print(f" Creating ad creative: {name}")

            # Build object story spec
            object_story_spec = {
                'page_id': os.getenv('META_PAGE_ID'),
                'link_data': {
                    'link': link or os.getenv('SHOPIFY_STORE_URL'),
                    'message': body,
                    'name': title,
                    'call_to_action': {
                        'type': call_to_action
                    }
                }
            }

            # Add image or video
            if image_url:
                object_story_spec['link_data']['image_url'] = image_url
            elif video_id:
                object_story_spec['video_data'] = {
                    'video_id': video_id,
                    'message': body,
                    'title': title,
                    'call_to_action': {
                        'type': call_to_action,
                        'value': {
                            'link': link or os.getenv('SHOPIFY_STORE_URL')
                        }
                    }
                }

            data = {
                'name': name,
                'object_story_spec': object_story_spec
            }

            result = await self._make_request(
                'POST',
                f"{self.ad_account_id}/adcreatives",
                data=data
            )

            if result:
                print(f"[SUCCESS] Ad creative created! ID: {result.get('id')}")

            return result

        except Exception as e:
            print(f"[ERROR] Ad creative creation error: {e}")
            return None

    async def create_ad(
        self,
        ad_set_id: str,
        creative_id: str,
        name: str,
        status: str = 'PAUSED'
    ) -> Dict:
        """
        Create ad (links creative to ad set)

        Args:
            ad_set_id: Parent ad set ID
            creative_id: Ad creative ID
            name: Ad name
            status: ACTIVE or PAUSED
        """
        try:
            print(f"[MOBILE] Creating ad: {name}")

            data = {
                'name': name,
                'adset_id': ad_set_id,
                'creative': {'creative_id': creative_id},
                'status': status
            }

            result = await self._make_request(
                'POST',
                f"{self.ad_account_id}/ads",
                data=data
            )

            if result:
                print(f"[SUCCESS] Ad created! ID: {result.get('id')}")

            return result

        except Exception as e:
            print(f"[ERROR] Ad creation error: {e}")
            return None

    async def get_campaign_insights(
        self,
        campaign_id: str,
        date_preset: str = 'last_7d'
    ) -> Dict:
        """
        Get campaign performance metrics

        Args:
            campaign_id: Campaign ID
            date_preset: Time range (today, yesterday, last_7d, last_30d)
        """
        try:
            fields = [
                'impressions',
                'clicks',
                'spend',
                'reach',
                'cpm',
                'cpc',
                'ctr',
                'conversions',
                'cost_per_conversion'
            ]

            result = await self._make_request(
                'GET',
                f"{campaign_id}/insights",
                params={
                    'fields': ','.join(fields),
                    'date_preset': date_preset
                }
            )

            return result

        except Exception as e:
            print(f"[ERROR] Insights error: {e}")
            return None

    async def update_campaign_status(
        self,
        campaign_id: str,
        status: str
    ) -> bool:
        """
        Update campaign status (pause/activate)

        Args:
            campaign_id: Campaign ID
            status: ACTIVE or PAUSED
        """
        try:
            result = await self._make_request(
                'POST',
                campaign_id,
                data={'status': status}
            )

            if result:
                print(f"[SUCCESS] Campaign status updated to {status}")
                return True

            return False

        except Exception as e:
            print(f"[ERROR] Status update error: {e}")
            return False

    async def update_ad_set_budget(
        self,
        ad_set_id: str,
        daily_budget: int
    ) -> bool:
        """
        Update ad set daily budget

        Args:
            ad_set_id: Ad set ID
            daily_budget: New daily budget in cents
        """
        try:
            result = await self._make_request(
                'POST',
                ad_set_id,
                data={'daily_budget': daily_budget}
            )

            if result:
                print(f"[SUCCESS] Budget updated to ${daily_budget/100:.2f}/day")
                return True

            return False

        except Exception as e:
            print(f"[ERROR] Budget update error: {e}")
            return False

    async def delete_campaign(self, campaign_id: str) -> bool:
        """Delete campaign"""
        try:
            result = await self._make_request('DELETE', campaign_id)

            if result:
                print(f"[SUCCESS] Campaign deleted")
                return True

            return False

        except Exception as e:
            print(f"[ERROR] Delete error: {e}")
            return False
