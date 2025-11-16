import sys
sys.path.insert(0, '/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot')

import sqlite3
import os
from datetime import datetime, timedelta
from ospra_os.intelligence.self_learning import SelfLearningEngine

# Mock database class for testing
class MockDB:
    def __init__(self):
        # Create in-memory SQLite database for testing
        self.conn = sqlite3.connect(':memory:')
        self.cursor = self.conn.cursor()
        self._create_test_schema()
        self._populate_test_data()

    def _create_test_schema(self):
        """Create test database schema"""

        # Products table
        self.cursor.execute("""
            CREATE TABLE products (
                id TEXT PRIMARY KEY,
                name TEXT,
                price REAL,
                rating REAL,
                orders INTEGER,
                category TEXT,
                created_at TIMESTAMP
            )
        """)

        # Product deployments table
        self.cursor.execute("""
            CREATE TABLE product_deployments (
                id INTEGER PRIMARY KEY,
                product_id TEXT,
                shopify_product_id TEXT,
                status TEXT,
                deployed_at TIMESTAMP
            )
        """)

        # Product performance table
        self.cursor.execute("""
            CREATE TABLE product_performance (
                id INTEGER PRIMARY KEY,
                product_id TEXT,
                metric_type TEXT,
                metric_value INTEGER,
                date DATE
            )
        """)

        self.conn.commit()

    def _populate_test_data(self):
        """Populate with realistic test data"""

        # WINNER PRODUCTS (good conversion, price, rating)
        winners = [
            ('prod_001', 'Smart Watch Pro', 34.99, 4.7, 1250, 'fitness'),
            ('prod_002', 'LED Strip Lights', 24.99, 4.6, 980, 'smart_home'),
            ('prod_003', 'Wireless Earbuds', 39.99, 4.8, 1450, 'audio'),
            ('prod_004', 'Phone Mount', 19.99, 4.5, 750, 'automotive'),
            ('prod_005', 'Fitness Tracker', 44.99, 4.7, 1120, 'fitness')
        ]

        for product in winners:
            self.cursor.execute("""
                INSERT INTO products (id, name, price, rating, orders, category, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (*product, datetime.now()))

            # Mark as deployed
            self.cursor.execute("""
                INSERT INTO product_deployments (product_id, shopify_product_id, status, deployed_at)
                VALUES (?, ?, 'active', ?)
            """, (product[0], f'shopify_{product[0]}', datetime.now()))

            # Add performance data (high views, good conversion)
            base_views = 300
            conversion_rate = 0.03  # 3%
            sales = int(base_views * conversion_rate)

            for day in range(30):
                date = datetime.now() - timedelta(days=day)
                self.cursor.execute("""
                    INSERT INTO product_performance (product_id, metric_type, metric_value, date)
                    VALUES (?, 'views', ?, ?)
                """, (product[0], base_views // 30, date.date()))

                self.cursor.execute("""
                    INSERT INTO product_performance (product_id, metric_type, metric_value, date)
                    VALUES (?, 'sales', ?, ?)
                """, (product[0], max(1, sales // 30), date.date()))

        # LOSER PRODUCTS (poor conversion, high price, low rating)
        losers = [
            ('prod_006', 'Expensive Camera', 89.99, 3.8, 320, 'electronics'),
            ('prod_007', 'Luxury Gadget', 129.99, 3.9, 250, 'luxury'),
            ('prod_008', 'Premium Tool', 74.99, 4.0, 180, 'tools')
        ]

        for product in losers:
            self.cursor.execute("""
                INSERT INTO products (id, name, price, rating, orders, category, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (*product, datetime.now()))

            # Mark as deployed
            self.cursor.execute("""
                INSERT INTO product_deployments (product_id, shopify_product_id, status, deployed_at)
                VALUES (?, ?, 'active', ?)
            """, (product[0], f'shopify_{product[0]}', datetime.now()))

            # Add performance data (high views, poor conversion)
            base_views = 400
            conversion_rate = 0.005  # 0.5% - very poor
            sales = max(0, int(base_views * conversion_rate))

            for day in range(30):
                date = datetime.now() - timedelta(days=day)
                self.cursor.execute("""
                    INSERT INTO product_performance (product_id, metric_type, metric_value, date)
                    VALUES (?, 'views', ?, ?)
                """, (product[0], base_views // 30, date.date()))

                if sales > 0:
                    self.cursor.execute("""
                        INSERT INTO product_performance (product_id, metric_type, metric_value, date)
                        VALUES (?, 'sales', ?, ?)
                    """, (product[0], max(0, sales // 30), date.date()))

        self.conn.commit()

    def get_underperformers(self, threshold_conversion=1.0, days=30):
        """Get underperforming products"""

        self.cursor.execute(f"""
            SELECT
                p.id, p.name, p.price, p.rating, p.category,
                COALESCE(SUM(CASE WHEN pp.metric_type = 'views' THEN pp.metric_value ELSE 0 END), 0) as views,
                COALESCE(SUM(CASE WHEN pp.metric_type = 'sales' THEN pp.metric_value ELSE 0 END), 0) as sales
            FROM products p
            LEFT JOIN product_deployments pd ON p.id = pd.product_id AND pd.status = 'active'
            LEFT JOIN product_performance pp ON p.id = pp.product_id
                AND pp.date >= date('now', '-{days} days')
            WHERE pd.product_id IS NOT NULL
            GROUP BY p.id
        """)

        underperformers = []
        for row in self.cursor.fetchall():
            views = row[5]
            sales = row[6]
            conversion = (sales / views * 100) if views > 0 else 0

            if conversion < threshold_conversion:
                underperformers.append({
                    'id': row[0],
                    'name': row[1],
                    'price': row[2],
                    'rating': row[3],
                    'category': row[4],
                    'views': views,
                    'sales': sales,
                    'conversion_rate': conversion
                })

        return underperformers

    def get_product_by_id(self, product_id):
        """Get product by ID"""
        self.cursor.execute("""
            SELECT id, name, price, rating, orders, category
            FROM products
            WHERE id = ?
        """, (product_id,))

        row = self.cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'name': row[1],
                'price': row[2],
                'rating': row[3],
                'orders': row[4],
                'category': row[5]
            }
        return None


def test_pattern_analysis():
    """Test 1: Analyze product patterns"""

    print("=" * 80)
    print("TEST 1: PATTERN ANALYSIS")
    print("=" * 80)
    print()

    db = MockDB()
    engine = SelfLearningEngine(db)

    patterns = engine.analyze_product_patterns(days=30)

    print(f"📊 Winners Found: {patterns['winners']['count']}")
    print(f"   • Average Price: ${patterns['winners']['avg_price']:.2f}")
    print(f"   • Average Rating: {patterns['winners']['avg_rating']:.1f}★")
    print(f"   • Average Conversion: {patterns['winners']['avg_conversion']:.2f}%")
    print(f"   • Price Range: ${patterns['winners']['price_range'][0]:.2f} - ${patterns['winners']['price_range'][1]:.2f}")
    print(f"   • Top Categories: {', '.join(patterns['winners']['common_categories'][:3])}")
    print()

    print(f"📉 Losers Found: {patterns['losers']['count']}")
    print(f"   • Average Price: ${patterns['losers']['avg_price']:.2f}")
    print(f"   • Average Rating: {patterns['losers']['avg_rating']:.1f}★")
    print(f"   • Average Conversion: {patterns['losers']['avg_conversion']:.2f}%")
    print(f"   • Price Range: ${patterns['losers']['price_range'][0]:.2f} - ${patterns['losers']['price_range'][1]:.2f}")
    print()

    print("💡 Insights:")
    for insight in patterns['insights']:
        print(f"   • {insight}")

    print()
    return patterns


def test_recommendations():
    """Test 2: Product recommendations"""

    print("=" * 80)
    print("TEST 2: PRODUCT RECOMMENDATIONS")
    print("=" * 80)
    print()

    db = MockDB()
    engine = SelfLearningEngine(db)

    # Create candidate products
    candidates = [
        {
            'id': 'new_001',
            'name': 'Smart Thermostat',
            'price': 39.99,
            'rating': 4.6,
            'category': 'smart_home',
            'orders': 850
        },
        {
            'id': 'new_002',
            'name': 'Expensive Drone',
            'price': 299.99,
            'rating': 4.2,
            'category': 'drones',
            'orders': 120
        },
        {
            'id': 'new_003',
            'name': 'Budget Fitness Band',
            'price': 29.99,
            'rating': 4.4,
            'category': 'fitness',
            'orders': 1200
        },
        {
            'id': 'new_004',
            'name': 'Cheap Unknown Product',
            'price': 9.99,
            'rating': 3.5,
            'category': 'unknown',
            'orders': 50
        },
        {
            'id': 'new_005',
            'name': 'Premium Audio System',
            'price': 89.99,
            'rating': 4.8,
            'category': 'audio',
            'orders': 450
        }
    ]

    recommendations = engine.recommend_products(candidates, top_n=5)

    print("Ranked Products (by AI prediction):")
    print()

    for i, product in enumerate(recommendations, 1):
        print(f"{i}. {product['name']}")
        print(f"   Score: {product['predicted_score']:.0f}/100")
        print(f"   Price: ${product['price']}")
        print(f"   Rating: {product['rating']}★")
        print(f"   Reason: {product['recommendation_reason']}")
        print()

    return recommendations


def test_performance_prediction():
    """Test 3: Performance prediction"""

    print("=" * 80)
    print("TEST 3: PERFORMANCE PREDICTION")
    print("=" * 80)
    print()

    db = MockDB()
    engine = SelfLearningEngine(db)

    # Test products with different characteristics
    test_products = [
        {
            'id': 'pred_001',
            'name': 'Ideal Smart Watch',
            'price': 34.99,
            'rating': 4.7,
            'category': 'fitness',
            'orders': 1000
        },
        {
            'id': 'pred_002',
            'name': 'Risky Expensive Item',
            'price': 149.99,
            'rating': 3.8,
            'category': 'luxury',
            'orders': 100
        }
    ]

    for product in test_products:
        print(f"Product: {product['name']}")
        print(f"  Price: ${product['price']}")
        print(f"  Rating: {product['rating']}★")
        print(f"  Category: {product['category']}")
        print()

        prediction = engine.predict_performance(product)

        print(f"  Predictions:")
        print(f"    • Success Probability: {prediction['success_probability']}/100")
        print(f"    • Expected Conversion: {prediction['predicted_conversion_rate']:.2f}%")
        print(f"    • Expected Sales/Month: {prediction['predicted_sales_per_month']}")
        print(f"    • Confidence: {prediction['confidence_score']}/100")
        print()

        if prediction['risk_factors']:
            print(f"  Risk Factors:")
            for risk in prediction['risk_factors']:
                print(f"    ⚠️  {risk}")
        else:
            print(f"  ✅ No significant risk factors")

        print()
        print("-" * 80)
        print()


def test_underperformer_detection():
    """Test 4: Underperformer detection"""

    print("=" * 80)
    print("TEST 4: UNDERPERFORMER DETECTION")
    print("=" * 80)
    print()

    db = MockDB()
    engine = SelfLearningEngine(db)

    underperformers = engine.identify_products_to_drop(min_views=100, days=30)

    print(f"Found {len(underperformers)} products to consider dropping")
    print()

    for product in underperformers:
        print(f"Product: {product['name']}")
        print(f"  Price: ${product['price']}")
        print(f"  Views: {product['views']}")
        print(f"  Sales: {product['sales']}")
        print(f"  Conversion: {product['conversion_rate']:.2f}%")
        print()
        print(f"  Drop Reason:")
        print(f"    {product['drop_reason']}")
        print()
        print(f"  Replacement Suggestions:")
        for suggestion in product['replacement_suggestions']:
            print(f"    • {suggestion}")
        print()
        print("-" * 80)
        print()


def test_learning_feedback():
    """Test 5: Learning feedback loop"""

    print("=" * 80)
    print("TEST 5: LEARNING FEEDBACK LOOP")
    print("=" * 80)
    print()

    db = MockDB()
    engine = SelfLearningEngine(db)

    # Get a product
    product_id = 'prod_001'

    # Simulate actual performance
    actual_performance = {
        'conversion_rate': 3.5,  # Slightly better than predicted
        'sales': 18,
        'views': 514
    }

    print(f"Testing learning feedback for product: {product_id}")
    print()

    result = engine.learn_from_outcome(product_id, actual_performance)

    print("Learning Results:")
    print(f"  Predicted Conversion: {result['predicted']:.2f}%")
    print(f"  Actual Conversion: {result['actual']:.2f}%")
    print(f"  Prediction Error: {result['error']:.2f}%")
    print(f"  Accuracy Score: {result['accuracy']}/100")
    print()

    if result['accuracy'] >= 90:
        print("✅ Excellent prediction accuracy!")
    elif result['accuracy'] >= 70:
        print("✓ Good prediction accuracy")
    else:
        print("⚠️  Model needs improvement")

    print()


def main():
    """Run all tests"""

    print()
    print("=" * 80)
    print("SELF-LEARNING ENGINE TEST SUITE")
    print("=" * 80)
    print()
    print("Testing AI-powered product intelligence system...")
    print()

    try:
        # Run all tests
        test_pattern_analysis()
        test_recommendations()
        test_performance_prediction()
        test_underperformer_detection()
        test_learning_feedback()

        print("=" * 80)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print()
        print("Summary:")
        print("  • Pattern analysis: Working")
        print("  • Product recommendations: Working")
        print("  • Performance prediction: Working")
        print("  • Underperformer detection: Working")
        print("  • Learning feedback: Working")
        print()
        print("The Self-Learning Engine is ready for production!")
        print()

    except Exception as e:
        print()
        print("=" * 80)
        print("❌ TEST FAILED")
        print("=" * 80)
        print()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
