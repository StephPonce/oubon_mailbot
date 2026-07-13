"""
Google Ads Automation
"""
from typing import Dict, List, Optional
import os
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException


class GoogleAdsManager:
    """Manage Google Ads campaigns"""

    def __init__(self):
        self.client = GoogleAdsClient.load_from_env()
        self.customer_id = os.getenv('GOOGLE_ADS_CUSTOMER_ID')

        if not self.customer_id:
            raise ValueError("GOOGLE_ADS_CUSTOMER_ID not set")

    async def create_product_campaign(
        self,
        product_name: str,
        product_url: str,
        keywords: List[str],
        ad_copy: str,
        daily_budget: float = 15.0
    ) -> Dict:
        """
        Create Google Search Ads campaign

        Args:
            product_name: Product name
            product_url: Landing page URL
            keywords: Search keywords to target
            ad_copy: Ad description
            daily_budget: Daily budget in dollars

        Returns:
            Campaign info dict
        """
        try:
            print(f"[SEARCH] Creating Google Ads campaign for: {product_name}")

            campaign_service = self.client.get_service("CampaignService")
            ad_group_service = self.client.get_service("AdGroupService")
            ad_service = self.client.get_service("AdGroupAdService")

            # Create Campaign
            campaign_operation = self._build_campaign_operation(
                name=f"Product: {product_name}",
                daily_budget=daily_budget
            )

            campaign_response = campaign_service.mutate_campaigns(
                customer_id=self.customer_id,
                operations=[campaign_operation]
            )

            campaign_resource_name = campaign_response.results[0].resource_name

            # Create Ad Group
            ad_group_operation = self._build_ad_group_operation(
                campaign_resource_name=campaign_resource_name,
                name=f"{product_name} - Ad Group"
            )

            ad_group_response = ad_group_service.mutate_ad_groups(
                customer_id=self.customer_id,
                operations=[ad_group_operation]
            )

            ad_group_resource_name = ad_group_response.results[0].resource_name

            # Create Responsive Search Ad
            ad_operation = self._build_ad_operation(
                ad_group_resource_name=ad_group_resource_name,
                product_name=product_name,
                ad_copy=ad_copy,
                final_url=product_url
            )

            ad_response = ad_service.mutate_ad_group_ads(
                customer_id=self.customer_id,
                operations=[ad_operation]
            )

            # Add Keywords
            await self._add_keywords(ad_group_resource_name, keywords)

            print(f"[SUCCESS] Google Ads campaign created")

            return {
                'success': True,
                'campaign_id': campaign_resource_name,
                'ad_group_id': ad_group_resource_name,
                'platform': 'google',
                'daily_budget': daily_budget
            }

        except GoogleAdsException as e:
            print(f"[ERROR] Google Ads failed: {e}")
            return {'success': False, 'error': str(e)}

    def _build_campaign_operation(self, name: str, daily_budget: float):
        """Build campaign creation operation"""
        campaign_operation = self.client.get_type("CampaignOperation")
        campaign = campaign_operation.create

        campaign.name = name
        campaign.advertising_channel_type = self.client.enums.AdvertisingChannelTypeEnum.SEARCH
        campaign.status = self.client.enums.CampaignStatusEnum.PAUSED

        # Budget
        campaign.campaign_budget = self._create_budget(daily_budget)

        # Bidding strategy
        campaign.manual_cpc.enhanced_cpc_enabled = True

        return campaign_operation

    def _create_budget(self, daily_budget: float) -> str:
        """Create campaign budget"""
        budget_service = self.client.get_service("CampaignBudgetService")
        budget_operation = self.client.get_type("CampaignBudgetOperation")
        budget = budget_operation.create

        budget.name = f"Budget {daily_budget}"
        budget.amount_micros = int(daily_budget * 1_000_000)
        budget.delivery_method = self.client.enums.BudgetDeliveryMethodEnum.STANDARD

        response = budget_service.mutate_campaign_budgets(
            customer_id=self.customer_id,
            operations=[budget_operation]
        )

        return response.results[0].resource_name

    def _build_ad_group_operation(self, campaign_resource_name: str, name: str):
        """Build ad group operation"""
        operation = self.client.get_type("AdGroupOperation")
        ad_group = operation.create

        ad_group.name = name
        ad_group.campaign = campaign_resource_name
        # T25: create PAUSED, matching Meta (AdSet paused) and TikTok (adgroup
        # DISABLE). ENABLED here meant one accidental campaign-activation put
        # the whole tree live instantly.
        ad_group.status = self.client.enums.AdGroupStatusEnum.PAUSED
        ad_group.type_ = self.client.enums.AdGroupTypeEnum.SEARCH_STANDARD
        ad_group.cpc_bid_micros = 1_000_000  # $1 max CPC

        return operation

    def _build_ad_operation(
        self,
        ad_group_resource_name: str,
        product_name: str,
        ad_copy: str,
        final_url: str
    ):
        """Build responsive search ad operation"""
        operation = self.client.get_type("AdGroupAdOperation")
        ad_group_ad = operation.create

        ad_group_ad.ad_group = ad_group_resource_name
        # T25: create PAUSED (see _build_ad_group_operation).
        ad_group_ad.status = self.client.enums.AdGroupAdStatusEnum.PAUSED

        # Responsive Search Ad
        rsa = ad_group_ad.ad.responsive_search_ad

        # Headlines (3-15 required)
        headlines = [
            f"Buy {product_name}",
            f"Best {product_name}",
            f"{product_name} On Sale"
        ]

        for headline in headlines:
            headline_asset = self.client.get_type("AdTextAsset")
            headline_asset.text = headline[:30]  # Max 30 chars
            rsa.headlines.append(headline_asset)

        # Descriptions (2-4 required)
        descriptions = [
            ad_copy[:90],  # Max 90 chars
            "Shop now with free shipping!"
        ]

        for desc in descriptions:
            desc_asset = self.client.get_type("AdTextAsset")
            desc_asset.text = desc
            rsa.descriptions.append(desc_asset)

        # Final URLs
        ad_group_ad.ad.final_urls.append(final_url)

        return operation

    async def _add_keywords(self, ad_group_resource_name: str, keywords: List[str]):
        """Add keywords to ad group"""
        keyword_service = self.client.get_service("AdGroupCriterionService")
        operations = []

        for keyword in keywords:
            operation = self.client.get_type("AdGroupCriterionOperation")
            criterion = operation.create

            criterion.ad_group = ad_group_resource_name
            criterion.status = self.client.enums.AdGroupCriterionStatusEnum.ENABLED
            criterion.keyword.text = keyword
            criterion.keyword.match_type = self.client.enums.KeywordMatchTypeEnum.BROAD

            operations.append(operation)

        keyword_service.mutate_ad_group_criteria(
            customer_id=self.customer_id,
            operations=operations
        )

    async def get_campaign_metrics(self, campaign_id: str) -> Dict:
        """Get campaign performance metrics"""
        try:
            query = f"""
                SELECT
                    campaign.id,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.ctr,
                    metrics.average_cpc
                FROM campaign
                WHERE campaign.resource_name = '{campaign_id}'
            """

            ga_service = self.client.get_service("GoogleAdsService")
            response = ga_service.search(customer_id=self.customer_id, query=query)

            for row in response:
                return {
                    'impressions': row.metrics.impressions,
                    'clicks': row.metrics.clicks,
                    'spend': row.metrics.cost_micros / 1_000_000,
                    'ctr': row.metrics.ctr,
                    'cpc': row.metrics.average_cpc / 1_000_000
                }

            return {}
        except Exception as e:
            print(f"Error fetching metrics: {e}")
            return {}

    async def update_campaign_budget(self, campaign_id: str, daily_budget: float) -> bool:
        """Set the daily budget for a campaign (T22).

        Google keeps the budget on a separate CampaignBudget resource, so this
        looks it up via GAQL and mutates it. The caller (AdScheduler) must cap
        ``daily_budget`` BEFORE it reaches here.
        """
        try:
            ga_service = self.client.get_service("GoogleAdsService")
            query = f"""
                SELECT campaign.campaign_budget
                FROM campaign
                WHERE campaign.resource_name = '{campaign_id}'
            """
            response = ga_service.search(customer_id=self.customer_id, query=query)

            budget_resource_name = None
            for row in response:
                budget_resource_name = row.campaign.campaign_budget
                break

            if not budget_resource_name:
                print(f"Error updating budget: no budget resource for {campaign_id}")
                return False

            budget_service = self.client.get_service("CampaignBudgetService")
            budget_operation = self.client.get_type("CampaignBudgetOperation")
            budget = budget_operation.update
            budget.resource_name = budget_resource_name
            budget.amount_micros = int(daily_budget * 1_000_000)
            budget_operation.update_mask.paths.append("amount_micros")

            budget_service.mutate_campaign_budgets(
                customer_id=self.customer_id,
                operations=[budget_operation]
            )
            return True
        except Exception as e:
            print(f"Error updating campaign budget: {e}")
            return False

    async def pause_campaign(self, campaign_id: str) -> bool:
        """Pause a campaign"""
        try:
            campaign_service = self.client.get_service("CampaignService")
            campaign_operation = self.client.get_type("CampaignOperation")

            campaign = campaign_operation.update
            campaign.resource_name = campaign_id
            campaign.status = self.client.enums.CampaignStatusEnum.PAUSED

            campaign_operation.update_mask.paths.append("status")

            campaign_service.mutate_campaigns(
                customer_id=self.customer_id,
                operations=[campaign_operation]
            )
            return True
        except Exception as e:
            print(f"Error pausing campaign: {e}")
            return False

    async def activate_campaign(self, campaign_id: str) -> bool:
        """Activate a campaign"""
        try:
            campaign_service = self.client.get_service("CampaignService")
            campaign_operation = self.client.get_type("CampaignOperation")

            campaign = campaign_operation.update
            campaign.resource_name = campaign_id
            campaign.status = self.client.enums.CampaignStatusEnum.ENABLED

            campaign_operation.update_mask.paths.append("status")

            campaign_service.mutate_campaigns(
                customer_id=self.customer_id,
                operations=[campaign_operation]
            )
            return True
        except Exception as e:
            print(f"Error activating campaign: {e}")
            return False
