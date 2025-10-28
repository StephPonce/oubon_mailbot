"""Multi-niche parallel product discovery."""

from typing import List, Dict, Optional
import asyncio
from datetime import datetime
from ospra_os.product_research.pipeline import ProductDiscoveryPipeline
from ospra_os.core.settings import get_settings


class MultiNicheDiscovery:
    """
    Discover products across multiple niches in parallel.

    This class searches 10+ profitable niches simultaneously to find
    winning products across different categories.
    """

    # Define profitable niches with their relevant subreddits
    NICHES = {
        "smart_lighting": {
            "keywords": ["LED lights", "smart bulbs", "RGB lights", "strip lights", "color changing lights"],
            "subreddits": ["smarthome", "homeautomation", "Hue", "led"],
            "category": "Home & Garden"
        },
        "home_security": {
            "keywords": ["security camera", "doorbell camera", "smart lock", "motion sensor", "alarm system"],
            "subreddits": ["homesecurity", "smarthome", "homedefense"],
            "category": "Security"
        },
        "cleaning_gadgets": {
            "keywords": ["robot vacuum", "cordless vacuum", "steam mop", "carpet cleaner", "air purifier"],
            "subreddits": ["VacuumCleaners", "homeautomation", "CleaningTips"],
            "category": "Home Appliances"
        },
        "kitchen_tech": {
            "keywords": ["air fryer", "instant pot", "coffee maker", "blender", "smart scale"],
            "subreddits": ["Cooking", "MealPrepSunday", "Coffee"],
            "category": "Kitchen & Dining"
        },
        "fitness_gadgets": {
            "keywords": ["resistance bands", "yoga mat", "foam roller", "jump rope", "smart watch"],
            "subreddits": ["homegym", "bodyweightfitness", "fitness"],
            "category": "Sports & Outdoors"
        },
        "phone_accessories": {
            "keywords": ["phone case", "screen protector", "charging cable", "wireless charger", "car mount"],
            "subreddits": ["android", "iPhone", "GooglePixel"],
            "category": "Electronics"
        },
        "car_accessories": {
            "keywords": ["dash cam", "phone mount", "car charger", "seat organizer", "air freshener"],
            "subreddits": ["Dashcam", "cars", "AutoDetailing"],
            "category": "Automotive"
        },
        "pet_products": {
            "keywords": ["automatic feeder", "pet camera", "water fountain", "laser toy", "pet bed"],
            "subreddits": ["pets", "dogs", "cats"],
            "category": "Pet Supplies"
        },
        "gaming_accessories": {
            "keywords": ["gaming mouse", "mouse pad", "headset stand", "controller grip", "cable management"],
            "subreddits": ["pcmasterrace", "gaming", "battlestations"],
            "category": "Video Games"
        },
        "outdoor_gear": {
            "keywords": ["camping light", "water bottle", "portable charger", "hiking backpack", "hammock"],
            "subreddits": ["CampingGear", "hiking", "Ultralight"],
            "category": "Sports & Outdoors"
        }
    }

    def __init__(
        self,
        reddit_client_id: Optional[str] = None,
        reddit_secret: Optional[str] = None,
        aliexpress_api_key: Optional[str] = None,
        aliexpress_app_secret: Optional[str] = None
    ):
        """Initialize with API credentials."""
        self.pipeline = ProductDiscoveryPipeline(
            reddit_client_id=reddit_client_id,
            reddit_secret=reddit_secret,
            aliexpress_api_key=aliexpress_api_key,
            aliexpress_app_secret=aliexpress_app_secret
        )

    async def discover_all_niches(
        self,
        min_score: float = 7.0,
        max_per_niche: int = 5
    ) -> Dict[str, List[Dict]]:
        """
        Discover products across ALL niches in parallel.

        This runs 10+ product discoveries simultaneously for maximum efficiency.

        Args:
            min_score: Minimum product score (0-10)
            max_per_niche: Maximum products to return per niche

        Returns:
            {
                "smart_lighting": [product1, product2, ...],
                "home_security": [product1, product2, ...],
                ...
            }
        """
        print(f"\n{'='*70}")
        print(f"🔥 MULTI-NICHE DISCOVERY STARTING")
        print(f"{'='*70}")
        print(f"Niches: {len(self.NICHES)}")
        print(f"Min Score: {min_score}/10")
        print(f"Max Per Niche: {max_per_niche}")
        print(f"{'='*70}\n")

        start_time = datetime.now()

        # Run all niche discoveries in parallel
        tasks = []
        for niche_name, niche_data in self.NICHES.items():
            task = self._discover_niche(
                niche_name=niche_name,
                subreddits=niche_data["subreddits"],
                keywords=niche_data["keywords"],
                category=niche_data["category"],
                min_score=min_score,
                max_results=max_per_niche
            )
            tasks.append(task)

        print(f"⚡ Running {len(tasks)} parallel discoveries...")

        # Wait for all discoveries to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Organize results by niche
        niche_products = {}
        total_products = 0
        successful_niches = 0

        for niche_name, products in zip(self.NICHES.keys(), results):
            if isinstance(products, Exception):
                print(f"   ❌ {niche_name}: Failed - {products}")
                niche_products[niche_name] = []
            else:
                niche_products[niche_name] = products
                total_products += len(products)
                if len(products) > 0:
                    successful_niches += 1

                # Color-coded output based on results
                if len(products) >= 3:
                    print(f"   🔥 {niche_name}: {len(products)} HIGH PRIORITY products")
                elif len(products) > 0:
                    print(f"   ✅ {niche_name}: {len(products)} products")
                else:
                    print(f"   ⚠️  {niche_name}: No products above threshold")

        elapsed = (datetime.now() - start_time).total_seconds()

        print(f"\n{'='*70}")
        print(f"✅ MULTI-NICHE DISCOVERY COMPLETE")
        print(f"{'='*70}")
        print(f"Total Products: {total_products}")
        print(f"Successful Niches: {successful_niches}/{len(self.NICHES)}")
        print(f"Time Elapsed: {elapsed:.1f}s")
        print(f"{'='*70}\n")

        return niche_products

    async def _discover_niche(
        self,
        niche_name: str,
        subreddits: List[str],
        keywords: List[str],
        category: str,
        min_score: float,
        max_results: int
    ) -> List[Dict]:
        """Discover products for a single niche."""
        try:
            # Use pipeline's discover_niche_winners method
            products = await self.pipeline.discover_niche_winners(
                subreddits=subreddits,
                max_results=max_results
            )

            # Filter by minimum score
            filtered = [p for p in products if p["score"] >= min_score][:max_results]

            # Add niche metadata to each product
            for product in filtered:
                product["niche"] = niche_name
                product["keywords"] = keywords
                product["category"] = category

            return filtered

        except Exception as e:
            print(f"   ❌ Error discovering {niche_name}: {e}")
            return []

    def get_top_products_overall(
        self,
        niche_products: Dict[str, List[Dict]],
        limit: int = 20
    ) -> List[Dict]:
        """
        Get top N products across ALL niches sorted by score.

        Args:
            niche_products: Products organized by niche
            limit: Maximum products to return

        Returns:
            List of top products sorted by score (highest first)
        """
        all_products = []
        for niche_name, products in niche_products.items():
            all_products.extend(products)

        # Sort by score (highest first)
        all_products.sort(key=lambda x: x["score"], reverse=True)

        return all_products[:limit]

    def get_stats(self, niche_products: Dict[str, List[Dict]]) -> Dict:
        """Get discovery statistics."""
        total_products = sum(len(products) for products in niche_products.values())
        niches_with_products = sum(1 for products in niche_products.values() if len(products) > 0)

        # Count by priority
        high_priority = 0
        medium_priority = 0
        low_priority = 0

        for products in niche_products.values():
            for product in products:
                priority = product.get("priority", "LOW")
                if priority == "HIGH":
                    high_priority += 1
                elif priority == "MEDIUM":
                    medium_priority += 1
                else:
                    low_priority += 1

        return {
            "total_products": total_products,
            "niches_searched": len(self.NICHES),
            "niches_with_products": niches_with_products,
            "high_priority": high_priority,
            "medium_priority": medium_priority,
            "low_priority": low_priority,
        }
