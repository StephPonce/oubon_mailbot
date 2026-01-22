"""
Database Migration: Update Learning Tables for Hybrid Architecture
===================================================================

This migration adds the new columns required by the Hybrid Learning Engine
to the existing learning tables.

Run with: python -m ospra_os.database.migrations.update_learning_tables

Author: Ospra Intelligence
"""

import os
import sys
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from sqlalchemy import text, inspect
from ospra_os.database.connection import engine, SessionLocal


def get_existing_columns(table_name: str) -> set:
    """Get existing columns for a table."""
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    return {col['name'] for col in columns}


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def run_migration():
    """Run the learning tables migration."""
    print("=" * 60)
    print("Hybrid Learning Tables Migration")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        # ================================================================
        # 1. GlobalLearningWeights table
        # ================================================================
        print("\n[1/3] Updating global_learning_weights table...")
        
        if not table_exists('global_learning_weights'):
            print("  Creating table from scratch...")
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS global_learning_weights (
                    id SERIAL PRIMARY KEY,
                    category VARCHAR(50),
                    weights JSON,
                    version VARCHAR(20) DEFAULT '1.0',
                    learning_cycles INTEGER DEFAULT 0,
                    scoring_weights JSON DEFAULT '{}',
                    niche_confidence JSON DEFAULT '{}',
                    price_confidence JSON DEFAULT '{}',
                    trend_velocity JSON DEFAULT '{}',
                    accuracy JSON DEFAULT '{}',
                    total_users_contributing INTEGER DEFAULT 0,
                    total_sales_analyzed INTEGER DEFAULT 0,
                    total_revenue_analyzed FLOAT DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            print("  ✅ Table created!")
        else:
            existing = get_existing_columns('global_learning_weights')
            print(f"  Existing columns: {existing}")
            
            # Add missing columns
            new_columns = {
                'learning_cycles': 'INTEGER DEFAULT 0',
                'scoring_weights': "JSON DEFAULT '{}'",
                'niche_confidence': "JSON DEFAULT '{}'",
                'price_confidence': "JSON DEFAULT '{}'",
                'trend_velocity': "JSON DEFAULT '{}'",
                'accuracy': "JSON DEFAULT '{}'",
                'total_users_contributing': 'INTEGER DEFAULT 0',
                'total_sales_analyzed': 'INTEGER DEFAULT 0',
                'total_revenue_analyzed': 'FLOAT DEFAULT 0.0',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            }
            
            for col_name, col_type in new_columns.items():
                if col_name not in existing:
                    print(f"  Adding column: {col_name}")
                    try:
                        db.execute(text(f"ALTER TABLE global_learning_weights ADD COLUMN {col_name} {col_type}"))
                    except Exception as e:
                        print(f"    Warning: {e}")
            
            # Update version column type if needed
            if 'version' in existing:
                try:
                    db.execute(text("ALTER TABLE global_learning_weights ALTER COLUMN version TYPE VARCHAR(20)"))
                except:
                    pass  # May already be correct type
            
            print("  ✅ Table updated!")
        
        # ================================================================
        # 2. AILearningEvent table
        # ================================================================
        print("\n[2/3] Updating ai_learning_events table...")
        
        if not table_exists('ai_learning_events'):
            print("  Creating table from scratch...")
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS ai_learning_events (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    outcome_id INTEGER,
                    event_type VARCHAR(50) NOT NULL,
                    product_id VARCHAR(100),
                    details JSON DEFAULT '{}',
                    context JSON,
                    lesson_type VARCHAR(50),
                    lesson_strength FLOAT DEFAULT 1.0,
                    factors_validated JSON DEFAULT '[]',
                    factors_invalidated JSON DEFAULT '[]',
                    weight_adjustments JSON DEFAULT '{}',
                    processed BOOLEAN DEFAULT FALSE,
                    processed_at TIMESTAMP,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_learning_product ON ai_learning_events (product_id)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_learning_timestamp ON ai_learning_events (timestamp)"))
            print("  ✅ Table created!")
        else:
            existing = get_existing_columns('ai_learning_events')
            print(f"  Existing columns: {existing}")
            
            # Add missing columns
            new_columns = {
                'product_id': 'VARCHAR(100)',
                'details': "JSON DEFAULT '{}'",
                'timestamp': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            }
            
            for col_name, col_type in new_columns.items():
                if col_name not in existing:
                    print(f"  Adding column: {col_name}")
                    try:
                        db.execute(text(f"ALTER TABLE ai_learning_events ADD COLUMN {col_name} {col_type}"))
                    except Exception as e:
                        print(f"    Warning: {e}")
            
            # Make user_id nullable
            try:
                db.execute(text("ALTER TABLE ai_learning_events ALTER COLUMN user_id DROP NOT NULL"))
            except:
                pass
            
            # Make context nullable
            try:
                db.execute(text("ALTER TABLE ai_learning_events ALTER COLUMN context DROP NOT NULL"))
            except:
                pass
            
            # Make lesson_type nullable
            try:
                db.execute(text("ALTER TABLE ai_learning_events ALTER COLUMN lesson_type DROP NOT NULL"))
            except:
                pass
            
            # Create indexes
            try:
                db.execute(text("CREATE INDEX IF NOT EXISTS idx_learning_product ON ai_learning_events (product_id)"))
                db.execute(text("CREATE INDEX IF NOT EXISTS idx_learning_timestamp ON ai_learning_events (timestamp)"))
            except:
                pass
            
            print("  ✅ Table updated!")
        
        # ================================================================
        # 3. PersonalLearningWeights table
        # ================================================================
        print("\n[3/3] Updating personal_learning_weights table...")
        
        if not table_exists('personal_learning_weights'):
            print("  Creating table from scratch...")
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS personal_learning_weights (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL UNIQUE,
                    category VARCHAR(50),
                    weights JSON,
                    version VARCHAR(20) DEFAULT '1.0',
                    learning_cycles INTEGER DEFAULT 0,
                    scoring_adjustments JSON DEFAULT '{}',
                    niche_adjustments JSON DEFAULT '{}',
                    price_adjustments JSON DEFAULT '{}',
                    best_performing_niches JSON DEFAULT '[]',
                    optimal_price_range JSON DEFAULT '{}',
                    peak_selling_days JSON DEFAULT '[]',
                    predictions_made INTEGER DEFAULT 0,
                    predictions_correct INTEGER DEFAULT 0,
                    accuracy_rate FLOAT DEFAULT 0.5,
                    sales_analyzed INTEGER DEFAULT 0,
                    revenue_analyzed FLOAT DEFAULT 0.0,
                    custom_weights_enabled BOOLEAN DEFAULT FALSE,
                    custom_weights JSON DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            print("  ✅ Table created!")
        else:
            existing = get_existing_columns('personal_learning_weights')
            print(f"  Existing columns: {existing}")
            
            # Add missing columns
            new_columns = {
                'learning_cycles': 'INTEGER DEFAULT 0',
                'scoring_adjustments': "JSON DEFAULT '{}'",
                'niche_adjustments': "JSON DEFAULT '{}'",
                'price_adjustments': "JSON DEFAULT '{}'",
                'best_performing_niches': "JSON DEFAULT '[]'",
                'optimal_price_range': "JSON DEFAULT '{}'",
                'peak_selling_days': "JSON DEFAULT '[]'",
                'predictions_made': 'INTEGER DEFAULT 0',
                'predictions_correct': 'INTEGER DEFAULT 0',
                'accuracy_rate': 'FLOAT DEFAULT 0.5',
                'sales_analyzed': 'INTEGER DEFAULT 0',
                'revenue_analyzed': 'FLOAT DEFAULT 0.0',
                'custom_weights_enabled': 'BOOLEAN DEFAULT FALSE',
                'custom_weights': "JSON DEFAULT '{}'",
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            }
            
            for col_name, col_type in new_columns.items():
                if col_name not in existing:
                    print(f"  Adding column: {col_name}")
                    try:
                        db.execute(text(f"ALTER TABLE personal_learning_weights ADD COLUMN {col_name} {col_type}"))
                    except Exception as e:
                        print(f"    Warning: {e}")
            
            print("  ✅ Table updated!")
        
        # ================================================================
        # 4. Initialize default global weights
        # ================================================================
        print("\n[4/4] Initializing default global weights...")
        
        result = db.execute(text("SELECT COUNT(*) FROM global_learning_weights"))
        count = result.scalar()
        
        if count == 0:
            print("  Creating initial global weights row...")
            db.execute(text("""
                INSERT INTO global_learning_weights (
                    version, learning_cycles, 
                    scoring_weights, niche_confidence, price_confidence, trend_velocity, accuracy,
                    total_users_contributing, total_sales_analyzed, total_revenue_analyzed
                ) VALUES (
                    '1.0', 0,
                    '{"google_trends_weight": 0.25, "reddit_mentions_weight": 0.15, "aliexpress_orders_weight": 0.35, "price_competitiveness_weight": 0.15, "trend_velocity_weight": 0.10}',
                    '{"smart_home": 0.5, "fitness": 0.5, "tech_accessories": 0.5, "home_office": 0.5, "beauty": 0.5, "kitchen": 0.5, "outdoor": 0.5, "pet": 0.5}',
                    '{"under_20": 0.5, "20_to_50": 0.5, "50_to_100": 0.5, "over_100": 0.5}',
                    '{"early_spike_threshold": 50, "sustained_growth_days": 7, "decay_threshold": -20}',
                    '{"predictions_made": 0, "predictions_correct": 0, "accuracy_rate": 0.5}',
                    0, 0, 0.0
                )
            """))
            print("  ✅ Initial weights created!")
        else:
            print(f"  Global weights already exist ({count} rows)")
        
        db.commit()
        
        print("\n" + "=" * 60)
        print("✅ MIGRATION COMPLETE!")
        print("=" * 60)
        print("\nThe learning tables are now ready for the Hybrid Learning Engine.")
        print("Restart the server to apply changes.")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()
    
    return True


if __name__ == "__main__":
    run_migration()
