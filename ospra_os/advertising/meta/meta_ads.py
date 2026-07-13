"""
Meta (Facebook/Instagram) Ads Automation
"""
from typing import Dict, List, Optional
import os
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adcreative import AdCreative


class MetaAdsManager:
    """Manage Meta (Facebook/Instagram) ad campaigns"""

    def __init__(self):
        self.app_id = os.getenv('META_APP_ID')
        self.app_secret = os.getenv('META_APP_SECRET')
        self.access_token = os.getenv('META_ACCESS_TOKEN')
        self.ad_account_id = os.getenv('META_AD_ACCOUNT_ID')

        if not all([self.app_id, self.app_secret, self.access_token, self.ad_account_id]):
            raise ValueError("Missing Meta API credentials")

        # Initialize API
        FacebookAdsApi.init(
            app_id=self.app_id,
            app_secret=self.app_secret,
            access_token=self.access_token
        )

        self.account = AdAccount(f'act_{self.ad_account_id}')

    async def create_product_campaign(
        self,
        product_name: str,
        product_url: str,
        image_url: str,
        ad_copy: str,
        daily_budget: float = 10.0,
        target_audience: Dict = None
    ) -> Dict:
        """
        Create complete ad campaign for a product

        Args:
            product_name: Product name
            product_url: Landing page URL
            image_url: Product image URL
            ad_copy: Ad text
            daily_budget: Daily budget in dollars
            target_audience: Targeting parameters

        Returns:
            Campaign info dict
        """
        try:
            print(f"[MOBILE] Creating Meta ad campaign for: {product_name}")

            # Step 1: Create Campaign
            campaign = self._create_campaign(
                name=f"Product: {product_name}",
                objective='OUTCOME_TRAFFIC'  # Drive traffic to website
            )

            # Step 2: Create Ad Set
            ad_set = self._create_ad_set(
                campaign_id=campaign['id'],
                name=f"{product_name} - Ad Set",
                daily_budget=daily_budget,
                targeting=target_audience or self._get_default_targeting()
            )

            # Step 3: Create Ad Creative
            creative = self._create_ad_creative(
                name=f"{product_name} - Creative",
                image_url=image_url,
                body_text=ad_copy,
                link_url=product_url,
                call_to_action='SHOP_NOW'
            )

            # Step 4: Create Ad
            ad = self._create_ad(
                ad_set_id=ad_set['id'],
                creative_id=creative['id'],
                name=f"{product_name} - Ad"
            )

            print(f"[SUCCESS] Meta campaign created: {campaign['id']}")

            return {
                'success': True,
                'campaign_id': campaign['id'],
                'ad_set_id': ad_set['id'],
                'ad_id': ad['id'],
                'creative_id': creative['id'],
                'platform': 'meta',
                'daily_budget': daily_budget
            }

        except Exception as e:
            print(f"[ERROR] Meta campaign creation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _create_campaign(self, name: str, objective: str) -> Dict:
        """Create campaign"""
        campaign = Campaign(parent_id=self.account.get_id_assured())
        campaign.update({
            Campaign.Field.name: name,
            Campaign.Field.objective: objective,
            Campaign.Field.status: Campaign.Status.paused,  # Start paused
            Campaign.Field.special_ad_categories: []
        })
        campaign.remote_create()
        return campaign.export_all_data()

    def _create_ad_set(
        self,
        campaign_id: str,
        name: str,
        daily_budget: float,
        targeting: Dict
    ) -> Dict:
        """Create ad set"""
        ad_set = AdSet(parent_id=self.account.get_id_assured())
        ad_set.update({
            AdSet.Field.name: name,
            AdSet.Field.campaign_id: campaign_id,
            AdSet.Field.daily_budget: int(daily_budget * 100),  # In cents
            AdSet.Field.billing_event: AdSet.BillingEvent.impressions,
            AdSet.Field.optimization_goal: AdSet.OptimizationGoal.link_clicks,
            AdSet.Field.bid_amount: 100,  # $1 CPM
            AdSet.Field.targeting: targeting,
            AdSet.Field.status: AdSet.Status.paused
        })
        ad_set.remote_create()
        return ad_set.export_all_data()

    def _create_ad_creative(
        self,
        name: str,
        image_url: str,
        body_text: str,
        link_url: str,
        call_to_action: str
    ) -> Dict:
        """Create ad creative"""
        creative = AdCreative(parent_id=self.account.get_id_assured())
        creative.update({
            AdCreative.Field.name: name,
            AdCreative.Field.object_story_spec: {
                'page_id': os.getenv('META_PAGE_ID'),
                'link_data': {
                    'image_url': image_url,
                    'link': link_url,
                    'message': body_text,
                    'call_to_action': {
                        'type': call_to_action
                    }
                }
            }
        })
        creative.remote_create()
        return creative.export_all_data()

    def _create_ad(self, ad_set_id: str, creative_id: str, name: str) -> Dict:
        """Create ad"""
        ad = Ad(parent_id=self.account.get_id_assured())
        ad.update({
            Ad.Field.name: name,
            Ad.Field.adset_id: ad_set_id,
            Ad.Field.creative: {'creative_id': creative_id},
            Ad.Field.status: Ad.Status.paused
        })
        ad.remote_create()
        return ad.export_all_data()

    def _get_default_targeting(self) -> Dict:
        """Default targeting parameters"""
        return {
            'geo_locations': {
                'countries': ['US']
            },
            'age_min': 25,
            'age_max': 55,
            'device_platforms': ['mobile', 'desktop']
        }

    async def get_campaign_metrics(self, campaign_id: str) -> Dict:
        """Get campaign performance metrics"""
        try:
            campaign = Campaign(campaign_id)
            insights = campaign.get_insights(fields=[
                'impressions',
                'clicks',
                'spend',
                'cpc',
                'cpm',
                'ctr'
            ])

            if insights:
                return insights[0].export_all_data()
            return {}

        except Exception as e:
            print(f"Error fetching metrics: {e}")
            return {}

    async def pause_campaign(self, campaign_id: str) -> bool:
        """Pause a campaign.

        Section B audit: ``campaign.update({...})`` only mutates the local SDK
        object — without ``remote_update()`` nothing was ever sent to Meta, so
        the auto-pause protection silently no-opped and "paused" campaigns
        kept spending. remote_update() is the actual API write.
        """
        try:
            campaign = Campaign(campaign_id)
            campaign.update({Campaign.Field.status: Campaign.Status.paused})
            campaign.remote_update()
            return True
        except Exception as e:
            print(f"Error pausing campaign: {e}")
            return False

    async def activate_campaign(self, campaign_id: str) -> bool:
        """Activate a campaign (see pause_campaign re: remote_update)."""
        try:
            campaign = Campaign(campaign_id)
            campaign.update({Campaign.Field.status: Campaign.Status.active})
            campaign.remote_update()
            return True
        except Exception as e:
            print(f"Error activating campaign: {e}")
            return False

    async def update_campaign_budget(self, campaign_id: str, daily_budget: float) -> bool:
        """Set the daily budget for a campaign (T22).

        Meta keeps daily budget on the AdSet, not the Campaign, so this looks
        up the campaign's ad sets and updates each. The caller (AdScheduler)
        is responsible for capping ``daily_budget`` BEFORE it reaches here.
        """
        try:
            campaign = Campaign(campaign_id)
            ad_sets = campaign.get_ad_sets(fields=[AdSet.Field.id])
            if not ad_sets:
                print(f"Error updating budget: no ad sets for campaign {campaign_id}")
                return False
            for ad_set in ad_sets:
                ad_set.update({AdSet.Field.daily_budget: int(daily_budget * 100)})  # cents
                ad_set.remote_update()
            return True
        except Exception as e:
            print(f"Error updating campaign budget: {e}")
            return False
