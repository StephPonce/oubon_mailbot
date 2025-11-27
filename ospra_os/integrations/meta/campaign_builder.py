"""
Campaign Builder - Complete ad campaign creation
"""
from typing import Dict, List
from .client import MetaAdsClient
from .ad_generator import AdCopyGenerator


class CampaignBuilder:
    """Service for building complete ad campaigns"""

    def __init__(self):
        self.client = MetaAdsClient()
        self.ad_generator = AdCopyGenerator()

    async def create_complete_campaign(
        self,
        product: Dict,
        daily_budget: float = 10.0,  # $10/day
        target_audience: Dict = None,
        auto_activate: bool = False
    ) -> Dict:
        """
        Create complete campaign from product

        Steps:
        1. Generate AI ad copy
        2. Create campaign
        3. Create ad set with targeting & budget
        4. Create ad creatives
        5. Create ads

        Returns:
            Campaign details with all IDs
        """
        try:
            print(f"\n{'='*70}")
            print(f"🚀 BUILDING META AD CAMPAIGN")
            print(f"{'='*70}")
            print(f"Product: {product.get('name', 'Unknown')[:50]}")
            print(f"Budget: ${daily_budget:.2f}/day")
            print()

            campaign_name = f"{product.get('name', 'Product')[:30]} - {self._get_timestamp()}"

            # Step 1: Generate ad copy variations
            print("📝 Step 1: Generating AI ad copy...")
            ad_variations = await self.ad_generator.generate_ad_copy(product)

            if not ad_variations:
                return {
                    'success': False,
                    'error': 'Failed to generate ad copy'
                }

            # Step 2: Create campaign
            print("\n📢 Step 2: Creating campaign...")
            campaign = await self.client.create_campaign(
                name=campaign_name,
                objective='OUTCOME_SALES',
                status='ACTIVE' if auto_activate else 'PAUSED'
            )

            if not campaign:
                return {
                    'success': False,
                    'error': 'Campaign creation failed'
                }

            campaign_id = campaign['id']

            # Step 3: Create ad set
            print("\n🎯 Step 3: Creating ad set...")

            targeting = target_audience or self._get_default_targeting(product)

            ad_set = await self.client.create_ad_set(
                campaign_id=campaign_id,
                name=f"{campaign_name} - Ad Set",
                daily_budget=int(daily_budget * 100),  # Convert to cents
                targeting=targeting,
                optimization_goal='OFFSITE_CONVERSIONS',
                status='ACTIVE' if auto_activate else 'PAUSED'
            )

            if not ad_set:
                return {
                    'success': False,
                    'error': 'Ad set creation failed'
                }

            ad_set_id = ad_set['id']

            # Step 4 & 5: Create creatives and ads
            print("\n🎨 Step 4-5: Creating ad creatives and ads...")

            ads_created = []

            for i, variation in enumerate(ad_variations, 1):
                # Create creative
                creative = await self.client.create_ad_creative(
                    name=f"{campaign_name} - Creative {i}",
                    title=variation['headline'],
                    body=variation['body'],
                    image_url=product.get('image_url'),
                    link=product.get('shopify_url') or product.get('source_url')
                )

                if not creative:
                    print(f"⚠️  Failed to create creative {i}")
                    continue

                # Create ad
                ad = await self.client.create_ad(
                    ad_set_id=ad_set_id,
                    creative_id=creative['id'],
                    name=f"{campaign_name} - Ad {i}",
                    status='ACTIVE' if auto_activate else 'PAUSED'
                )

                if ad:
                    ads_created.append({
                        'ad_id': ad['id'],
                        'creative_id': creative['id'],
                        'headline': variation['headline'],
                        'body': variation['body'],
                        'angle': variation['angle']
                    })

            result = {
                'success': True,
                'campaign_id': campaign_id,
                'ad_set_id': ad_set_id,
                'ads': ads_created,
                'campaign_name': campaign_name,
                'daily_budget': daily_budget,
                'status': 'ACTIVE' if auto_activate else 'PAUSED',
                'ads_created': len(ads_created),
                'product_name': product.get('name')
            }

            print(f"\n{'='*70}")
            print(f"✅ CAMPAIGN BUILD COMPLETE")
            print(f"{'='*70}")
            print(f"Campaign ID: {campaign_id}")
            print(f"Ad Set ID: {ad_set_id}")
            print(f"Ads Created: {len(ads_created)}")
            print(f"Status: {result['status']}")
            print(f"{'='*70}\n")

            return result

        except Exception as e:
            print(f"❌ Campaign build error: {e}")
            import traceback
            traceback.print_exc()

            return {
                'success': False,
                'error': str(e)
            }

    def _get_default_targeting(self, product: Dict) -> Dict:
        """Get default targeting based on product"""

        # Base targeting - US, 25-55, both genders
        targeting = {
            'geo_locations': {
                'countries': ['US']
            },
            'age_min': 25,
            'age_max': 55,
            'genders': [1, 2]  # All genders
        }

        # Add interests based on niche
        niche = product.get('niche', '').lower()

        interests = []
        if 'smart_home' in niche or 'tech' in niche:
            interests.extend([
                'Smart home technology',
                'Home automation',
                'Technology early adopters'
            ])
        elif 'fitness' in niche:
            interests.extend([
                'Physical fitness',
                'Health and wellness',
                'Exercise & fitness'
            ])
        elif 'beauty' in niche:
            interests.extend([
                'Beauty',
                'Skin care',
                'Cosmetics'
            ])
        else:
            interests.extend([
                'Online shopping',
                'Shopping and fashion'
            ])

        if interests:
            targeting['flexible_spec'] = [{
                'interests': [{'name': i} for i in interests]
            }]

        return targeting

    def _get_timestamp(self) -> str:
        """Get timestamp for campaign name"""
        from datetime import datetime
        return datetime.now().strftime('%Y%m%d_%H%M')

    async def bulk_create_campaigns(
        self,
        products: List[Dict],
        daily_budget_per_product: float = 10.0
    ) -> List[Dict]:
        """Create campaigns for multiple products"""
        import asyncio

        print(f"\n🚀 Bulk creating campaigns for {len(products)} products...")

        results = []

        for product in products:
            result = await self.create_complete_campaign(
                product=product,
                daily_budget=daily_budget_per_product,
                auto_activate=False
            )

            results.append(result)

            # Rate limit
            await asyncio.sleep(3)

        successful = sum(1 for r in results if r.get('success'))
        print(f"\n✅ Created {successful}/{len(products)} campaigns successfully")

        return results
