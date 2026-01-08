"""Velocity Analyzer - Track product momentum"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ospra_os.database.multi_store_models import ProductSnapshot, ProductIntelligence

class VelocityAnalyzer:
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def save_snapshot(self, product: dict):
        """Save product snapshot for tracking"""
        snapshot = ProductSnapshot(
            asin=product.get('asin', ''),
            name=product.get('name', ''),
            price=product.get('price', 0),
            rating=product.get('rating', 0),
            reviews_count=product.get('reviews_count', 0),
            bestseller_rank=product.get('bestseller_rank', 999999),
            niche=product.get('niche', ''),
            snapshot_date=datetime.utcnow()
        )
        self.db.add(snapshot)
        self.db.commit()
    
    def calculate_velocity(self, asin: str) -> dict:
        """Calculate velocity metrics"""
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        snapshots = self.db.query(ProductSnapshot).filter(
            ProductSnapshot.asin == asin,
            ProductSnapshot.snapshot_date >= seven_days_ago
        ).order_by(ProductSnapshot.snapshot_date.asc()).all()
        
        if len(snapshots) < 2:
            return {'momentum_score': 50.0, 'is_trending': False}
        
        first = snapshots[0]
        last = snapshots[-1]
        
        # Calculate metrics
        rank_velocity = (last.bestseller_rank - first.bestseller_rank) / len(snapshots)
        review_velocity = (last.reviews_count - first.reviews_count) / len(snapshots)
        
        is_trending = rank_velocity < -50  # Rank improving
        momentum_score = min(100.0, 50.0 + (abs(rank_velocity) / 10) + (review_velocity * 2))
        
        # Save intelligence
        intel = self.db.query(ProductIntelligence).filter(
            ProductIntelligence.asin == asin
        ).first()
        
        if not intel:
            intel = ProductIntelligence(asin=asin, name=last.name)
            self.db.add(intel)
        
        intel.momentum_score = momentum_score
        intel.is_trending = is_trending
        intel.rank_velocity_7d = rank_velocity
        intel.review_velocity_7d = review_velocity
        intel.last_updated = datetime.utcnow()
        
        self.db.commit()
        
        return {
            'momentum_score': momentum_score,
            'is_trending': is_trending,
            'rank_velocity': rank_velocity,
            'review_velocity': review_velocity
        }

print("[SUCCESS] Velocity analyzer created")
