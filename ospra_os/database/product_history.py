"""
📊 PRODUCT HISTORY DATABASE
SQLite-based storage for product snapshots and change tracking
"""

import sqlite3
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class ProductHistoryDB:
    """SQLite database for tracking product history and changes"""

    def __init__(self, db_path: str = "data/product_history.db"):
        self.db_path = db_path

        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_db()
        logger.info(f"✅ Product history database initialized: {db_path}")

    def _init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Product snapshots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                price REAL,
                cost REAL,
                velocity_score INTEGER,
                orders INTEGER,
                rating REAL,
                snapshot_time TIMESTAMP,
                raw_data TEXT,
                UNIQUE(product_id, snapshot_time)
            )
        """)

        # Product changes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                change_type TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                change_timestamp TIMESTAMP,
                severity TEXT,
                notified BOOLEAN DEFAULT 0
            )
        """)

        # Products table (full product data with enrichment)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                niche TEXT,
                price REAL,
                cost REAL,
                score REAL,
                profit_margin REAL,
                estimated_profit REAL,
                rating REAL,
                orders INTEGER,
                velocity_score INTEGER,
                image_url TEXT,
                aliexpress_url TEXT,
                source TEXT,
                description TEXT,
                features TEXT,
                use_cases TEXT,
                target_market TEXT,
                last_updated TIMESTAMP,
                raw_data TEXT
            )
        """)

        # Product deployments table (track Shopify deployments)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_deployments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                shopify_product_id TEXT NOT NULL,
                shopify_handle TEXT,
                shopify_url TEXT,
                deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                last_synced_at TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)

        # Orders table (track Shopify orders and fulfillment)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shopify_order_id TEXT UNIQUE NOT NULL,
                shopify_order_number TEXT,
                customer_email TEXT,
                customer_name TEXT,
                product_id TEXT,
                product_name TEXT,
                quantity INTEGER,
                total_price REAL,
                currency TEXT DEFAULT 'USD',
                order_status TEXT DEFAULT 'pending',
                fulfillment_status TEXT DEFAULT 'unfulfilled',
                tracking_number TEXT,
                tracking_url TEXT,
                supplier_order_id TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Notifications table (track alerts and events)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT DEFAULT 'info',
                product_id TEXT,
                metadata TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Product performance table (track views, clicks, sales metrics)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                shopify_product_id TEXT,
                metric_type TEXT NOT NULL,
                metric_value INTEGER DEFAULT 0,
                date DATE DEFAULT (date('now')),
                FOREIGN KEY (product_id) REFERENCES products(id),
                UNIQUE(product_id, metric_type, date)
            )
        """)

        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_product_id
            ON product_snapshots(product_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshots_time
            ON product_snapshots(snapshot_time)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_changes_notified
            ON product_changes(notified)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_products_niche
            ON products(niche)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_products_score
            ON products(score DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deployments_product
            ON product_deployments(product_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deployments_shopify
            ON product_deployments(shopify_product_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_shopify
            ON orders(shopify_order_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_status
            ON orders(order_status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_customer
            ON orders(customer_email)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_read
            ON notifications(is_read, created_at DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_product
            ON notifications(product_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_performance_product
            ON product_performance(product_id, date)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_performance_metric
            ON product_performance(metric_type, date)
        """)

        conn.commit()
        conn.close()

    def save_snapshot(self, product: Dict):
        """Save a product snapshot"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO product_snapshots
                (product_id, product_name, price, cost, velocity_score, orders, rating, snapshot_time, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                product['id'],
                product['name'],
                product.get('price', 0),
                product.get('cost', 0),
                product.get('velocity_score', 0),
                product.get('orders', 0),
                product.get('rating', 0),
                datetime.now(),
                json.dumps(product)
            ))

            conn.commit()
            logger.debug(f"Saved snapshot for product: {product['name']}")

        except sqlite3.IntegrityError:
            logger.warning(f"Duplicate snapshot for {product['id']} at this timestamp")

        finally:
            conn.close()

    def get_latest_snapshot(self, product_id: str) -> Optional[Dict]:
        """Get the most recent snapshot for a product"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM product_snapshots
            WHERE product_id = ?
            ORDER BY snapshot_time DESC
            LIMIT 1
        """, (product_id,))

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'id': result[0],
                'product_id': result[1],
                'product_name': result[2],
                'price': result[3],
                'cost': result[4],
                'velocity_score': result[5],
                'orders': result[6],
                'rating': result[7],
                'snapshot_time': result[8],
                'raw_data': json.loads(result[9])
            }
        return None

    def get_product_history(self, product_id: str, limit: int = 30) -> List[Dict]:
        """Get historical snapshots for a product"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM product_snapshots
            WHERE product_id = ?
            ORDER BY snapshot_time DESC
            LIMIT ?
        """, (product_id, limit))

        results = cursor.fetchall()
        conn.close()

        return [
            {
                'id': row[0],
                'product_id': row[1],
                'product_name': row[2],
                'price': row[3],
                'cost': row[4],
                'velocity_score': row[5],
                'orders': row[6],
                'rating': row[7],
                'snapshot_time': row[8],
                'raw_data': json.loads(row[9])
            }
            for row in results
        ]

    def log_change(
        self,
        product_id: str,
        product_name: str,
        change_type: str,
        old_value: str,
        new_value: str,
        severity: str = "medium"
    ):
        """Log a detected change"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO product_changes
            (product_id, product_name, change_type, old_value, new_value, change_timestamp, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            product_id,
            product_name,
            change_type,
            str(old_value),
            str(new_value),
            datetime.now(),
            severity
        ))

        conn.commit()
        conn.close()

        logger.info(f"Logged change for {product_name}: {change_type} ({severity})")

    def get_unnotified_changes(self) -> List[Dict]:
        """Get all changes that haven't been notified"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM product_changes
            WHERE notified = 0
            ORDER BY change_timestamp DESC
        """)

        results = cursor.fetchall()
        conn.close()

        return [
            {
                'id': row[0],
                'product_id': row[1],
                'product_name': row[2],
                'change_type': row[3],
                'old_value': row[4],
                'new_value': row[5],
                'change_timestamp': row[6],
                'severity': row[7],
                'notified': row[8]
            }
            for row in results
        ]

    def get_recent_changes(self, limit: int = 50) -> List[Dict]:
        """Get recent changes (including notified)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM product_changes
            ORDER BY change_timestamp DESC
            LIMIT ?
        """, (limit,))

        results = cursor.fetchall()
        conn.close()

        return [
            {
                'id': row[0],
                'product_id': row[1],
                'product_name': row[2],
                'change_type': row[3],
                'old_value': row[4],
                'new_value': row[5],
                'change_timestamp': row[6],
                'severity': row[7],
                'notified': row[8]
            }
            for row in results
        ]

    def mark_change_notified(self, change_id: int):
        """Mark a change as notified"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE product_changes
            SET notified = 1
            WHERE id = ?
        """, (change_id,))

        conn.commit()
        conn.close()

    def mark_all_notified(self):
        """Mark all changes as notified"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE product_changes
            SET notified = 1
            WHERE notified = 0
        """)

        conn.commit()
        conn.close()

        logger.info("Marked all changes as notified")

    def get_tracked_products(self) -> List[str]:
        """Get list of all product IDs with snapshots"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT product_id
            FROM product_snapshots
        """)

        results = cursor.fetchall()
        conn.close()

        return [row[0] for row in results]

    def get_stats(self) -> Dict:
        """Get database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total snapshots
        cursor.execute("SELECT COUNT(*) FROM product_snapshots")
        total_snapshots = cursor.fetchone()[0]

        # Total changes
        cursor.execute("SELECT COUNT(*) FROM product_changes")
        total_changes = cursor.fetchone()[0]

        # Unnotified changes
        cursor.execute("SELECT COUNT(*) FROM product_changes WHERE notified = 0")
        unnotified_changes = cursor.fetchone()[0]

        # Tracked products
        cursor.execute("SELECT COUNT(DISTINCT product_id) FROM product_snapshots")
        tracked_products = cursor.fetchone()[0]

        conn.close()

        return {
            'total_snapshots': total_snapshots,
            'total_changes': total_changes,
            'unnotified_changes': unnotified_changes,
            'tracked_products': tracked_products
        }

    def save_products(self, products: List[Dict]):
        """Save/update products in database with full enrichment data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for product in products:
            cursor.execute("""
                INSERT OR REPLACE INTO products
                (id, name, category, niche, price, cost, score, profit_margin,
                 estimated_profit, rating, orders, velocity_score, image_url,
                 aliexpress_url, source, description, features, use_cases,
                 target_market, last_updated, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                product['id'],
                product['name'],
                product.get('category'),
                product.get('niche'),
                product['price'],
                product['cost'],
                product['score'],
                product['profit_margin'],
                product['estimated_profit'],
                product.get('rating', 4.5),
                product.get('orders', 1000),
                product['velocity_score'],
                product.get('image_url'),
                product.get('aliexpress_url'),
                product.get('source', 'fallback'),
                product.get('description'),
                json.dumps(product.get('features', [])),
                json.dumps(product.get('use_cases', [])),
                product.get('target_market'),
                datetime.now(),
                json.dumps(product)
            ))

        conn.commit()
        conn.close()
        logger.info(f"Saved {len(products)} products to database")

    def get_all_products(self, niche: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
        """Get products from database with optional niche filter"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if niche:
            query = "SELECT * FROM products WHERE niche = ? ORDER BY score DESC"
            params = (niche,)
            if limit:
                query += " LIMIT ?"
                params = (niche, limit)
            cursor.execute(query, params)
        else:
            query = "SELECT * FROM products ORDER BY score DESC"
            if limit:
                query += " LIMIT ?"
                cursor.execute(query, (limit,))
            else:
                cursor.execute(query)

        rows = cursor.fetchall()
        conn.close()

        products = []
        for row in rows:
            products.append({
                'id': row[0],
                'name': row[1],
                'category': row[2],
                'niche': row[3],
                'price': row[4],
                'cost': row[5],
                'score': row[6],
                'profit_margin': row[7],
                'estimated_profit': row[8],
                'rating': row[9],
                'orders': row[10],
                'velocity_score': row[11],
                'image_url': row[12],
                'aliexpress_url': row[13],
                'source': row[14],
                'description': row[15],
                'features': json.loads(row[16]) if row[16] else [],
                'use_cases': json.loads(row[17]) if row[17] else [],
                'target_market': row[18],
                'last_updated': row[19]
            })

        return products

    def get_product_by_id(self, product_id: str) -> Optional[Dict]:
        """Get single product with full enrichment data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'name': row[1],
                'category': row[2],
                'niche': row[3],
                'price': row[4],
                'cost': row[5],
                'score': row[6],
                'profit_margin': row[7],
                'estimated_profit': row[8],
                'rating': row[9],
                'orders': row[10],
                'velocity_score': row[11],
                'image_url': row[12],
                'aliexpress_url': row[13],
                'source': row[14],
                'description': row[15],
                'features': json.loads(row[16]) if row[16] else [],
                'use_cases': json.loads(row[17]) if row[17] else [],
                'target_market': row[18],
                'last_updated': row[19]
            }
        return None

    def save_deployment(self, product_id: str, shopify_data: Dict) -> bool:
        """Record successful Shopify deployment"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO product_deployments
                (product_id, shopify_product_id, shopify_handle, shopify_url, deployed_at, last_synced_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                product_id,
                str(shopify_data.get('id', '')),
                shopify_data.get('handle', ''),
                shopify_data.get('shopify_url', '')
            ))
            conn.commit()
            logger.info(f"✅ Recorded deployment for {product_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save deployment: {e}")
            return False
        finally:
            conn.close()

    def get_deployment(self, product_id: str) -> Optional[Dict]:
        """Check if product is already deployed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM product_deployments
            WHERE product_id = ? AND status = 'active'
            ORDER BY deployed_at DESC LIMIT 1
        """, (product_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'product_id': row[1],
                'shopify_product_id': row[2],
                'shopify_handle': row[3],
                'shopify_url': row[4],
                'deployed_at': row[5],
                'status': row[6],
                'last_synced_at': row[7]
            }
        return None

    def get_all_deployments(self) -> List[Dict]:
        """Get all active deployments with product details"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                d.*,
                p.name,
                p.price,
                p.image_url
            FROM product_deployments d
            LEFT JOIN products p ON d.product_id = p.id
            WHERE d.status = 'active'
            ORDER BY d.deployed_at DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        deployments = []
        for row in rows:
            deployments.append({
                'deployment_id': row[0],
                'product_id': row[1],
                'shopify_product_id': row[2],
                'shopify_handle': row[3],
                'shopify_url': row[4],
                'deployed_at': row[5],
                'status': row[6],
                'last_synced_at': row[7],
                'product_name': row[8],
                'price': row[9],
                'image_url': row[10]
            })

        return deployments

    def mark_deployment_removed(self, product_id: str) -> bool:
        """Mark deployment as removed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE product_deployments
                SET status = 'removed'
                WHERE product_id = ? AND status = 'active'
            """, (product_id,))
            conn.commit()
            logger.info(f"Marked deployment as removed for {product_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to mark deployment removed: {e}")
            return False
        finally:
            conn.close()

    def cleanup_old_snapshots(self, days: int = 30):
        """Delete snapshots older than specified days"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff_date = datetime.now() - timedelta(days=days)

        cursor.execute("""
            DELETE FROM product_snapshots
            WHERE snapshot_time < ?
        """, (cutoff_date,))

        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"Cleaned up {deleted_count} old snapshots")
        return deleted_count

    def create_notification(
        self,
        notification_type: str,
        title: str,
        message: str,
        severity: str = 'info',
        product_id: str = None,
        metadata: Dict = None
    ) -> bool:
        """Create a new notification"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            metadata_json = json.dumps(metadata) if metadata else None

            cursor.execute("""
                INSERT INTO notifications
                (type, title, message, severity, product_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (notification_type, title, message, severity, product_id, metadata_json))

            conn.commit()
            logger.info(f"✅ Notification created: {title}")
            return True
        except Exception as e:
            logger.error(f"Failed to create notification: {e}")
            return False
        finally:
            conn.close()

    def get_notifications(self, unread_only: bool = False, limit: int = 50) -> List[Dict]:
        """Get notifications"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            query = """
                SELECT
                    id, type, title, message, severity,
                    product_id, metadata, is_read, created_at
                FROM notifications
            """

            if unread_only:
                query += " WHERE is_read = 0"

            query += " ORDER BY created_at DESC LIMIT ?"

            cursor.execute(query, (limit,))

            notifications = []
            for row in cursor.fetchall():
                notifications.append({
                    'id': row[0],
                    'type': row[1],
                    'title': row[2],
                    'message': row[3],
                    'severity': row[4],
                    'product_id': row[5],
                    'metadata': json.loads(row[6]) if row[6] else None,
                    'is_read': bool(row[7]),
                    'created_at': row[8]
                })

            return notifications
        finally:
            conn.close()

    def mark_notification_read(self, notification_id: int) -> bool:
        """Mark notification as read"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE notifications
                SET is_read = 1
                WHERE id = ?
            """, (notification_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to mark notification read: {e}")
            return False
        finally:
            conn.close()

    def mark_all_read(self) -> bool:
        """Mark all notifications as read"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("UPDATE notifications SET is_read = 1")
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to mark all read: {e}")
            return False
        finally:
            conn.close()

    def get_unread_count(self) -> int:
        """Get count of unread notifications"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT COUNT(*) FROM notifications WHERE is_read = 0")
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def save_order(self, order_data: Dict) -> bool:
        """Save order from Shopify webhook"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO orders
                (shopify_order_id, shopify_order_number, customer_email, customer_name,
                 product_id, product_name, quantity, total_price, currency,
                 order_status, fulfillment_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_data.get('shopify_order_id'),
                order_data.get('shopify_order_number'),
                order_data.get('customer_email'),
                order_data.get('customer_name'),
                order_data.get('product_id'),
                order_data.get('product_name'),
                order_data.get('quantity', 1),
                order_data.get('total_price'),
                order_data.get('currency', 'USD'),
                'pending',
                'unfulfilled'
            ))
            conn.commit()
            logger.info(f"✅ Order saved: {order_data.get('shopify_order_number')}")
            return True
        except Exception as e:
            logger.error(f"Failed to save order: {e}")
            return False
        finally:
            conn.close()

    def get_order(self, shopify_order_id: str) -> Optional[Dict]:
        """Get order by Shopify ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM orders WHERE shopify_order_id = ?
            """, (shopify_order_id,))

            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'shopify_order_id': row[1],
                    'shopify_order_number': row[2],
                    'customer_email': row[3],
                    'customer_name': row[4],
                    'product_id': row[5],
                    'product_name': row[6],
                    'quantity': row[7],
                    'total_price': row[8],
                    'currency': row[9],
                    'order_status': row[10],
                    'fulfillment_status': row[11],
                    'tracking_number': row[12],
                    'tracking_url': row[13],
                    'supplier_order_id': row[14],
                    'notes': row[15],
                    'created_at': row[16],
                    'updated_at': row[17]
                }
            return None
        finally:
            conn.close()

    def update_order_tracking(self, shopify_order_id: str, tracking_number: str, tracking_url: str) -> bool:
        """Update order with tracking info"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE orders
                SET tracking_number = ?, tracking_url = ?,
                    fulfillment_status = 'shipped', updated_at = CURRENT_TIMESTAMP
                WHERE shopify_order_id = ?
            """, (tracking_number, tracking_url, shopify_order_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update tracking: {e}")
            return False
        finally:
            conn.close()

    def get_all_orders(self, limit: int = 50) -> List[Dict]:
        """Get all orders"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM orders
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

            orders = []
            for row in cursor.fetchall():
                orders.append({
                    'id': row[0],
                    'shopify_order_id': row[1],
                    'shopify_order_number': row[2],
                    'customer_email': row[3],
                    'customer_name': row[4],
                    'product_id': row[5],
                    'product_name': row[6],
                    'quantity': row[7],
                    'total_price': row[8],
                    'currency': row[9],
                    'order_status': row[10],
                    'fulfillment_status': row[11],
                    'tracking_number': row[12],
                    'tracking_url': row[13],
                    'supplier_order_id': row[14],
                    'notes': row[15],
                    'created_at': row[16],
                    'updated_at': row[17]
                })

            return orders
        finally:
            conn.close()

    def get_analytics(self) -> Dict:
        """Calculate analytics metrics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Total orders
            cursor.execute("SELECT COUNT(*) FROM orders")
            total_orders = cursor.fetchone()[0]

            # Total revenue
            cursor.execute("SELECT SUM(total_price) FROM orders")
            total_revenue = cursor.fetchone()[0] or 0

            # Average order value
            avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

            # Orders by status
            cursor.execute("""
                SELECT fulfillment_status, COUNT(*)
                FROM orders
                GROUP BY fulfillment_status
            """)
            orders_by_status = dict(cursor.fetchall())

            # Top products
            cursor.execute("""
                SELECT product_name, COUNT(*) as order_count, SUM(total_price) as revenue
                FROM orders
                GROUP BY product_name
                ORDER BY order_count DESC
                LIMIT 5
            """)
            top_products = [
                {
                    'name': row[0],
                    'orders': row[1],
                    'revenue': row[2]
                }
                for row in cursor.fetchall()
            ]

            # Revenue by day (last 30 days)
            cursor.execute("""
                SELECT DATE(created_at) as order_date, SUM(total_price) as daily_revenue
                FROM orders
                WHERE created_at >= datetime('now', '-30 days')
                GROUP BY DATE(created_at)
                ORDER BY order_date ASC
            """)
            revenue_by_day = [
                {
                    'date': row[0],
                    'revenue': row[1]
                }
                for row in cursor.fetchall()
            ]

            # Total deployed products
            cursor.execute("""
                SELECT COUNT(*) FROM product_deployments WHERE status = 'active'
            """)
            deployed_products = cursor.fetchone()[0]

            # Conversion rate
            conversion_rate = (total_orders / max(deployed_products, 1)) * 100 if deployed_products > 0 else 0

            return {
                'total_orders': total_orders,
                'total_revenue': round(total_revenue, 2),
                'average_order_value': round(avg_order_value, 2),
                'orders_by_status': orders_by_status,
                'top_products': top_products,
                'revenue_by_day': revenue_by_day,
                'deployed_products': deployed_products,
                'conversion_rate': round(conversion_rate, 2),
                'unfulfilled_orders': orders_by_status.get('unfulfilled', 0),
                'shipped_orders': orders_by_status.get('shipped', 0)
            }

        except Exception as e:
            logger.error(f"Failed to calculate analytics: {e}")
            return {}
        finally:
            conn.close()

    def track_performance(self, product_id: str, metric_type: str, increment: int = 1) -> bool:
        """
        Track product performance metric

        metric_type: 'views', 'clicks', 'sales', 'cart_adds'
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO product_performance (product_id, metric_type, metric_value)
                VALUES (?, ?, ?)
                ON CONFLICT(product_id, metric_type, date)
                DO UPDATE SET metric_value = metric_value + ?
            """, (product_id, metric_type, increment, increment))

            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to track performance: {e}")
            return False
        finally:
            conn.close()

    def get_product_performance(self, product_id: str, days: int = 30) -> Dict:
        """Get performance metrics for a product"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT
                    metric_type,
                    SUM(metric_value) as total,
                    date
                FROM product_performance
                WHERE product_id = ?
                AND date >= date('now', '-' || ? || ' days')
                GROUP BY metric_type
            """, (product_id, days))

            metrics = {}
            for row in cursor.fetchall():
                metrics[row[0]] = row[1]

            # Calculate conversion rate
            views = metrics.get('views', 0)
            sales = metrics.get('sales', 0)
            conversion_rate = (sales / views * 100) if views > 0 else 0

            return {
                'views': views,
                'clicks': metrics.get('clicks', 0),
                'sales': sales,
                'cart_adds': metrics.get('cart_adds', 0),
                'conversion_rate': round(conversion_rate, 2)
            }
        finally:
            conn.close()

    def get_top_performers(self, metric_type: str = 'sales', limit: int = 10, days: int = 30) -> List[Dict]:
        """Get top performing products"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT
                    pp.product_id,
                    p.name,
                    p.price,
                    p.image_url,
                    SUM(pp.metric_value) as total_metric
                FROM product_performance pp
                LEFT JOIN products p ON pp.product_id = p.id
                WHERE pp.metric_type = ?
                AND pp.date >= date('now', '-' || ? || ' days')
                GROUP BY pp.product_id
                ORDER BY total_metric DESC
                LIMIT ?
            """, (metric_type, days, limit))

            performers = []
            for row in cursor.fetchall():
                performers.append({
                    'product_id': row[0],
                    'name': row[1],
                    'price': row[2],
                    'image_url': row[3],
                    'total': row[4]
                })

            return performers
        finally:
            conn.close()

    def get_underperformers(self, threshold_conversion: float = 1.0, days: int = 30) -> List[Dict]:
        """Get underperforming products (low conversion rate)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT
                    p.id,
                    p.name,
                    p.price,
                    COALESCE(SUM(CASE WHEN pp.metric_type = 'views' THEN pp.metric_value ELSE 0 END), 0) as views,
                    COALESCE(SUM(CASE WHEN pp.metric_type = 'sales' THEN pp.metric_value ELSE 0 END), 0) as sales
                FROM products p
                LEFT JOIN product_performance pp ON p.id = pp.product_id
                    AND pp.date >= date('now', '-' || ? || ' days')
                LEFT JOIN product_deployments pd ON p.id = pd.product_id AND pd.status = 'active'
                WHERE pd.product_id IS NOT NULL
                GROUP BY p.id
                HAVING views >= 100 AND (CAST(sales AS FLOAT) / views * 100) < ?
                ORDER BY views DESC
            """, (days, threshold_conversion))

            underperformers = []
            for row in cursor.fetchall():
                views = row[3]
                sales = row[4]
                conversion = (sales / views * 100) if views > 0 else 0

                underperformers.append({
                    'product_id': row[0],
                    'name': row[1],
                    'price': row[2],
                    'views': views,
                    'sales': sales,
                    'conversion_rate': round(conversion, 2)
                })

            return underperformers
        finally:
            conn.close()


# Convenience function
def get_db() -> ProductHistoryDB:
    """Get or create database instance"""
    if not hasattr(get_db, '_instance'):
        get_db._instance = ProductHistoryDB()
    return get_db._instance
