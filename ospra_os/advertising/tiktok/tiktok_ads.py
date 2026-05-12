"""
TikTok Ads Automation
"""
from typing import Dict, List, Optional
import asyncio
import os
import requests


class TikTokAdsManager:
    """Manage TikTok ad campaigns"""

    BASE_URL = "https://business-api.tiktok.com/open_api/v1.3"

    def __init__(self):
        self.app_id = os.getenv('TIKTOK_APP_ID')
        self.secret = os.getenv('TIKTOK_SECRET')
        self.access_token = os.getenv('TIKTOK_ACCESS_TOKEN')
        self.advertiser_id = os.getenv('TIKTOK_ADVERTISER_ID')

        if not all([self.app_id, self.secret, self.access_token, self.advertiser_id]):
            raise ValueError("Missing TikTok API credentials")

        self.headers = {
            'Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }

    async def create_product_campaign(
        self,
        product_name: str,
        product_url: str,
        video_id: str,
        ad_text: str,
        daily_budget: float = 10.0,
        target_audience: Dict = None
    ) -> Dict:
        """
        Create complete ad campaign for a product

        Args:
            product_name: Product name
            product_url: Landing page URL
            video_id: TikTok video ID to use as creative
            ad_text: Ad text/caption
            daily_budget: Daily budget in dollars
            target_audience: Targeting parameters

        Returns:
            Campaign info dict
        """
        try:
            print(f" Creating TikTok ad campaign for: {product_name}")

            # Step 1: Create Campaign
            campaign = await self._create_campaign(
                name=f"Product: {product_name}",
                objective='TRAFFIC'  # Drive traffic to website
            )

            # Step 2: Create Ad Group
            ad_group = await self._create_ad_group(
                campaign_id=campaign['campaign_id'],
                name=f"{product_name} - Ad Group",
                daily_budget=daily_budget,
                targeting=target_audience or self._get_default_targeting(),
                landing_page_url=product_url
            )

            # Step 3: Create Ad
            ad = await self._create_ad(
                ad_group_id=ad_group['adgroup_id'],
                name=f"{product_name} - Ad",
                video_id=video_id,
                ad_text=ad_text,
                landing_page_url=product_url
            )

            print(f"[SUCCESS] TikTok campaign created: {campaign['campaign_id']}")

            return {
                'success': True,
                'campaign_id': campaign['campaign_id'],
                'ad_group_id': ad_group['adgroup_id'],
                'ad_id': ad['ad_id'],
                'platform': 'tiktok',
                'daily_budget': daily_budget
            }

        except Exception as e:
            print(f"[ERROR] TikTok campaign creation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _create_campaign(self, name: str, objective: str) -> Dict:
        """Create campaign. Async so sync HTTP doesn't block event loop. #30"""
        url = f"{self.BASE_URL}/campaign/create/"

        payload = {
            'advertiser_id': self.advertiser_id,
            'campaign_name': name,
            'objective_type': objective,
            'budget_mode': 'BUDGET_MODE_DAY',
            'operation_status': 'DISABLE'  # Start paused
        }

        response = await asyncio.to_thread(
            requests.post, url, headers=self.headers, json=payload
        )
        data = response.json()

        if data.get('code') != 0:
            raise Exception(f"Campaign creation failed: {data.get('message')}")

        return data['data']

    async def _create_ad_group(
        self,
        campaign_id: str,
        name: str,
        daily_budget: float,
        targeting: Dict,
        landing_page_url: str
    ) -> Dict:
        """Create ad group. Async so sync HTTP doesn't block event loop. #30"""
        url = f"{self.BASE_URL}/adgroup/create/"

        payload = {
            'advertiser_id': self.advertiser_id,
            'campaign_id': campaign_id,
            'adgroup_name': name,
            'placement_type': 'PLACEMENT_TYPE_AUTOMATIC',
            'placements': ['PLACEMENT_TIKTOK'],
            'promotion_type': 'WEBSITE',
            'location_ids': targeting.get('location_ids', ['6252001']),  # US by default
            'languages': targeting.get('languages', ['en']),
            'age_groups': targeting.get('age_groups', ['AGE_25_34', 'AGE_35_44']),
            'gender': targeting.get('gender', 'GENDER_UNLIMITED'),
            'operating_systems': targeting.get('operating_systems', ['Android', 'iOS']),
            'budget_mode': 'BUDGET_MODE_DAY',
            'budget': int(daily_budget * 100),  # In cents
            'bid_type': 'BID_TYPE_MAX_CONVERSION',
            'billing_event': 'CPC',
            'optimization_goal': 'CLICK',
            'pacing': 'PACING_MODE_SMOOTH',
            'operation_status': 'DISABLE',  # Start paused
            'landing_page_url': landing_page_url
        }

        response = await asyncio.to_thread(
            requests.post, url, headers=self.headers, json=payload
        )
        data = response.json()

        if data.get('code') != 0:
            raise Exception(f"Ad group creation failed: {data.get('message')}")

        return data['data']

    async def _create_ad(
        self,
        ad_group_id: str,
        name: str,
        video_id: str,
        ad_text: str,
        landing_page_url: str
    ) -> Dict:
        """Create ad. Async so sync HTTP doesn't block event loop. #30"""
        url = f"{self.BASE_URL}/ad/create/"

        payload = {
            'advertiser_id': self.advertiser_id,
            'adgroup_id': ad_group_id,
            'ad_name': name,
            'ad_format': 'SINGLE_VIDEO',
            'ad_text': ad_text,
            'video_id': video_id,
            'call_to_action': 'SHOP_NOW',
            'landing_page_url': landing_page_url,
            'operation_status': 'DISABLE'  # Start paused
        }

        response = await asyncio.to_thread(
            requests.post, url, headers=self.headers, json=payload
        )
        data = response.json()

        if data.get('code') != 0:
            raise Exception(f"Ad creation failed: {data.get('message')}")

        return data['data']

    def _get_default_targeting(self) -> Dict:
        """Default targeting parameters"""
        return {
            'location_ids': ['6252001'],  # United States
            'languages': ['en'],
            'age_groups': ['AGE_25_34', 'AGE_35_44', 'AGE_45_54'],
            'gender': 'GENDER_UNLIMITED',
            'operating_systems': ['Android', 'iOS']
        }

    async def get_campaign_metrics(self, campaign_id: str) -> Dict:
        """Get campaign performance metrics"""
        try:
            url = f"{self.BASE_URL}/report/integrated/get/"

            payload = {
                'advertiser_id': self.advertiser_id,
                'report_type': 'BASIC',
                'data_level': 'AUCTION_CAMPAIGN',
                'dimensions': ['campaign_id'],
                'filters': [
                    {
                        'field_name': 'campaign_ids',
                        'filter_type': 'IN',
                        'filter_value': [campaign_id]
                    }
                ],
                'metrics': [
                    'spend',
                    'impressions',
                    'clicks',
                    'ctr',
                    'cpc',
                    'cpm',
                    'conversions',
                    'conversion_rate'
                ],
                'start_date': '2024-01-01',
                'end_date': '2024-12-31'
            }

            response = await asyncio.to_thread(
                requests.post, url, headers=self.headers, json=payload
            )
            data = response.json()

            if data.get('code') != 0:
                return {}

            return data.get('data', {}).get('list', [{}])[0]

        except Exception as e:
            print(f"Error fetching metrics: {e}")
            return {}

    async def pause_campaign(self, campaign_id: str) -> bool:
        """Pause a campaign"""
        try:
            url = f"{self.BASE_URL}/campaign/update/status/"

            payload = {
                'advertiser_id': self.advertiser_id,
                'campaign_ids': [campaign_id],
                'operation_status': 'DISABLE'
            }

            response = await asyncio.to_thread(
                requests.post, url, headers=self.headers, json=payload
            )
            data = response.json()

            return data.get('code') == 0

        except Exception as e:
            print(f"Error pausing campaign: {e}")
            return False

    async def activate_campaign(self, campaign_id: str) -> bool:
        """Activate a campaign"""
        try:
            url = f"{self.BASE_URL}/campaign/update/status/"

            payload = {
                'advertiser_id': self.advertiser_id,
                'campaign_ids': [campaign_id],
                'operation_status': 'ENABLE'
            }

            response = await asyncio.to_thread(
                requests.post, url, headers=self.headers, json=payload
            )
            data = response.json()

            return data.get('code') == 0

        except Exception as e:
            print(f"Error activating campaign: {e}")
            return False

    async def upload_video(self, video_file_path: str) -> Optional[str]:
        """
        Upload video to TikTok for use in ads

        Args:
            video_file_path: Local path to video file

        Returns:
            Video ID if successful, None otherwise
        """
        try:
            # Step 1: Initialize upload
            init_url = f"{self.BASE_URL}/file/video/ad/upload/"

            with open(video_file_path, 'rb') as video_file:
                files = {'video_file': video_file}
                data = {'advertiser_id': self.advertiser_id}

                # Video upload is a slow multipart POST — must not block
                # the event loop. Task #30.
                response = await asyncio.to_thread(
                    requests.post,
                    init_url,
                    headers={'Access-Token': self.access_token},
                    data=data,
                    files=files,
                )

                result = response.json()

                if result.get('code') != 0:
                    print(f"Video upload failed: {result.get('message')}")
                    return None

                video_id = result['data']['video_id']
                print(f"[SUCCESS] Video uploaded: {video_id}")
                return video_id

        except Exception as e:
            print(f"Error uploading video: {e}")
            return None
