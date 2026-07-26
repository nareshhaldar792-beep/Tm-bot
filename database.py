"""
Database Layer for Telegram Store Bot
SQLite - Production Ready
"""

import sqlite3
import os
import json
from datetime import datetime
from contextlib import contextmanager

from config import DATABASE_PATH

os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)


@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        c = conn.cursor()

        # ----- CATEGORIES -----
        c.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                emoji TEXT DEFAULT '📦',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ----- PRODUCTS -----
        c.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                image_path TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            )
        ''')

        # ----- PLANS -----
        c.execute('''
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                duration TEXT DEFAULT '',
                description TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        ''')

        # ----- STOCK KEYS -----
        c.execute('''
            CREATE TABLE IF NOT EXISTS stock_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                plan_id INTEGER,
                price REAL DEFAULT 0,
                key_value TEXT NOT NULL UNIQUE,
                status TEXT DEFAULT 'available',
                order_id INTEGER,
                user_id INTEGER,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (plan_id) REFERENCES plans(id)
            )
        ''')

        # ---- Migration: add price + user_id columns if missing ----
        try:
            c.execute("ALTER TABLE stock_keys ADD COLUMN price REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # column already exists
        try:
            c.execute("ALTER TABLE stock_keys ADD COLUMN user_id INTEGER")
        except sqlite3.OperationalError:
            pass  # column already exists

        # ---- Migration: add product_pid column for reseller API ----
        try:
            c.execute("ALTER TABLE products ADD COLUMN product_pid INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # column already exists

        # ---- Migration: add reseller_response column to orders ----
        try:
            c.execute("ALTER TABLE orders ADD COLUMN reseller_response TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # column already exists

        # ---- Migration: populate product_pid from hardcoded mapping ----
        c.execute("SELECT COUNT(*) FROM products WHERE product_pid > 0")
        if c.fetchone()[0] == 0:
            # Map product name → reseller PID
            pid_map = {
                # 📱 iPhone
                "Fluorite iOS FF": 58,
                "Fluorite iOS MLBB": 84,
                "iOS Cloud CODM": 87,
                "iOS Fluorite 8 Ball Pool": 86,
                "iPhone All GBox Certificate": 85,
                "Miguli iPhone iOS FF": 69,
                # 🤖 Android
                "APK MC Panel FF Root Android": 124,
                "BR MOD FF Root Android": 67,
                "DripClient FF Root Android": 63,
                "DripClient Proxy FF NonRoot Android": 91,
                "HAXX-CKER PRO FF Root Android": 64,
                "HG Cheats Android Proxy FF NonRoot": 123,
                "HG Cheats FF APKMOD (Root+NonRoot)": 65,
                "Hikari Mod FF Root Android": 72,
                "KOS FF Root Android": 74,
                "Neo Strike FF Root Android": 70,
                "Pato Team FF All Android": 54,
                "Prime Hook FF NonRoot Android": 48,
                "Rapid Core FF Root Android": 130,
                "Reaper X Pro FF Root Android": 81,
                "Silent Cheat FF NonRoot APKMOD": 127,
                "Silent Cheat FF Root Android": 128,
                "XYZ Cheats FF Root Android": 66,
                # Other
                "BR MOD FF PC Version": 49,
                "DripClient FF PC AimKill": 44,
                "DripClient 8BP NonRoot Android": 59,
                "KOS 8 Ball Pool": 76,
                "KOS Carrom Pool": 75,
                "Snake 8 Ball Pool": 79,
                "Snake Carrom Pool": 77,
                "Snake Soccer Stars": 78,
                "Unlimited Credit For 1 Season": 129,
            }
            for name, pid_val in pid_map.items():
                c.execute("UPDATE products SET product_pid=? WHERE name=? AND product_pid=0", (pid_val, name))

        # ----- ORDERS -----
        c.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                username TEXT DEFAULT '',
                product_id INTEGER NOT NULL,
                plan_id INTEGER,
                product_name TEXT DEFAULT '',
                plan_name TEXT DEFAULT '',
                amount REAL NOT NULL,
                payment_method TEXT DEFAULT '',
                payment_status TEXT DEFAULT 'pending',
                utr_number TEXT DEFAULT '',
                order_status TEXT DEFAULT 'pending',
                binance_prepay_id TEXT DEFAULT '',
                delivered_key TEXT DEFAULT '',
                admin_note TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (plan_id) REFERENCES plans(id)
            )
        ''')

        # ----- USERS -----
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                last_name TEXT DEFAULT '',
                is_banned INTEGER DEFAULT 0,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ----- BOT CONFIG -----
        c.execute('''
            CREATE TABLE IF NOT EXISTS bot_config (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT ''
            )
        ''')

        # ----- SETTINGS (Support, Channel, Reseller) -----
        c.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT ''
            )
        ''')
        # Insert defaults if settings table is empty
        c.execute("SELECT COUNT(*) FROM settings")
        if c.fetchone()[0] == 0:
            defaults = [
                ('support_enabled', 'true'),
                ('support_username', 'nannu_key_store'),
                ('support_link', 'https://t.me/nannu_key_store'),
                ('support_button_text', '📞 Support'),
                ('channel_enabled', 'true'),
                ('channel_username', 'Nannu_Key_Store'),
                ('channel_link', 'https://t.me/Nannu_Key_Store'),
                ('channel_button_text', '📢 Official Channel'),
                ('reseller_enabled', 'false'),
                ('reseller_username', ''),
                ('reseller_link', ''),
                ('reseller_button_text', '🤝 Reseller'),
            ]
            c.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", defaults)

        # ----- LOGS -----
        c.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT DEFAULT 'info',
                user_id INTEGER,
                message TEXT DEFAULT '',
                details TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ----- ADMIN ROLES (Multi-Admin Access Control) -----
        c.execute('''
            CREATE TABLE IF NOT EXISTS admin_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                role TEXT DEFAULT 'admin',
                permissions TEXT DEFAULT '',
                added_by INTEGER,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Seed super_admin from config ADMIN_IDS
        from config import ADMIN_IDS
        for aid in ADMIN_IDS:
            c.execute("INSERT OR IGNORE INTO admin_roles (user_id, role, permissions, is_active) VALUES (?, 'super_admin', 'all', 1)", (aid,))

        # Insert default categories if empty
        c.execute("SELECT COUNT(*) FROM categories")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO categories (name, emoji) VALUES (?, ?)", ("📱 Android", "🤖"))
            c.execute("INSERT INTO categories (name, emoji) VALUES (?, ?)", ("🍎 iPhone", "🍎"))

        # Insert sample products if empty
        c.execute("SELECT COUNT(*) FROM products")
        if c.fetchone()[0] == 0:
            android_id = c.execute("SELECT id FROM categories WHERE name=?", ("📱 Android",)).fetchone()["id"]
            iphone_id = c.execute("SELECT id FROM categories WHERE name=?", ("🍎 iPhone",)).fetchone()["id"]

            android_products = [
                ("Netflix Premium", "Netflix Premium UHD 4K - 1 Month Subscription", android_id),
                ("YouTube Premium", "YouTube Premium ad-free + YouTube Music", android_id),
                ("Spotify Premium", "Spotify Premium Individual - 1 Month", android_id),
                ("Amazon Prime", "Amazon Prime Video + Shopping - 1 Month", android_id),
                ("Disney+ Hotstar", "Disney+ Hotstar Super - 1 Month", android_id),
                ("Zee5 Premium", "Zee5 Premium HD - 1 Month", android_id),
                ("Sony LIV Premium", "Sony LIV Premium - 1 Month", android_id),
                ("Apple Music", "Apple Music Individual - 1 Month (Android)", android_id),
                ("Crunchyroll", "Crunchyroll Mega Fan - 1 Month", android_id),
                ("Tidal HiFi", "Tidal HiFi Plus - 1 Month", android_id),
            ]
            for name, desc, cat_id in android_products:
                c.execute("INSERT INTO products (category_id, name, description) VALUES (?, ?, ?)",
                          (cat_id, name, desc))

            iphone_products = [
                ("Apple One", "Apple One Individual - Music, TV+, Arcade, iCloud+", iphone_id),
                ("iCloud+ 200GB", "iCloud+ 200GB Storage - 1 Month", iphone_id),
            ]
            for name, desc, cat_id in iphone_products:
                c.execute("INSERT INTO products (category_id, name, description) VALUES (?, ?, ?)",
                          (cat_id, name, desc))

            # Add sample plans
            for name, desc, cat_id in android_products:
                prod = c.execute("SELECT id FROM products WHERE name=?", (name,)).fetchone()
                if prod:
                    c.execute("INSERT INTO plans (product_id, name, price, duration) VALUES (?, ?, ?, ?)",
                              (prod["id"], "1 Month", 149.00, "30 Days"))
                    c.execute("INSERT INTO plans (product_id, name, price, duration) VALUES (?, ?, ?, ?)",
                              (prod["id"], "3 Months", 399.00, "90 Days"))
                    c.execute("INSERT INTO plans (product_id, name, price, duration) VALUES (?, ?, ?, ?)",
                              (prod["id"], "12 Months", 1199.00, "365 Days"))

            for name, desc, cat_id in iphone_products:
                prod = c.execute("SELECT id FROM products WHERE name=?", (name,)).fetchone()
                if prod:
                    c.execute("INSERT INTO plans (product_id, name, price, duration) VALUES (?, ?, ?, ?)",
                              (prod["id"], "1 Month", 199.00, "30 Days"))


# ========== CATEGORY OPERATIONS ==========

def get_categories():
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM categories ORDER BY id").fetchall()]


def get_category(category_id):
    with get_db() as conn:
        r = conn.execute("SELECT * FROM categories WHERE id=?", (category_id,)).fetchone()
        return dict(r) if r else None


def add_category(name, emoji="📦"):
    with get_db() as conn:
        try:
            c = conn.execute("INSERT INTO categories (name, emoji) VALUES (?, ?)", (name, emoji))
            return c.lastrowid
        except sqlite3.IntegrityError:
            return None


def delete_category(category_id):
    with get_db() as conn:
        conn.execute("DELETE FROM categories WHERE id=?", (category_id,))


# ========== PRODUCT OPERATIONS ==========

def get_products(category_id=None, active_only=True):
    with get_db() as conn:
        q = "SELECT p.*, c.name as category_name, c.emoji as category_emoji FROM products p JOIN categories c ON p.category_id=c.id"
        conds = []
        params = []
        if category_id:
            conds.append("p.category_id=?")
            params.append(category_id)
        if active_only:
            conds.append("p.is_active=1")
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY p.name"
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def get_product(product_id):
    with get_db() as conn:
        r = conn.execute('''
            SELECT p.*, c.name as category_name, c.emoji as category_emoji
            FROM products p JOIN categories c ON p.category_id=c.id
            WHERE p.id=?
        ''', (product_id,)).fetchone()
        return dict(r) if r else None


def add_product(category_id, name, description="", image_path=""):
    with get_db() as conn:
        try:
            c = conn.execute(
                "INSERT INTO products (category_id, name, description, image_path) VALUES (?, ?, ?, ?)",
                (category_id, name, description, image_path))
            return c.lastrowid
        except sqlite3.IntegrityError:
            return None


def update_product(product_id, **kwargs):
    allowed = {"category_id", "name", "description", "image_path", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [product_id]
    with get_db() as conn:
        conn.execute(f"UPDATE products SET {set_clause} WHERE id=?", values)


def delete_product(product_id):
    with get_db() as conn:
        conn.execute("DELETE FROM products WHERE id=?", (product_id,))


# ========== PLAN OPERATIONS ==========

def get_plans(product_id=None, active_only=True):
    with get_db() as conn:
        q = "SELECT * FROM plans"
        conds = []
        params = []
        if product_id:
            conds.append("product_id=?")
            params.append(product_id)
        if active_only:
            conds.append("is_active=1")
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY price"
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def get_plan(plan_id):
    with get_db() as conn:
        r = conn.execute("SELECT * FROM plans WHERE id=?", (plan_id,)).fetchone()
        return dict(r) if r else None


def add_plan(product_id, name, price, duration="", description=""):
    with get_db() as conn:
        c = conn.execute(
            "INSERT INTO plans (product_id, name, price, duration, description) VALUES (?, ?, ?, ?, ?)",
            (product_id, name, price, duration, description))
        return c.lastrowid


def update_plan(plan_id, **kwargs):
    allowed = {"name", "price", "duration", "description", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [plan_id]
    with get_db() as conn:
        conn.execute(f"UPDATE plans SET {set_clause} WHERE id=?", values)


def delete_plan(plan_id):
    with get_db() as conn:
        conn.execute("DELETE FROM plans WHERE id=?", (plan_id,))


# ========== STOCK KEY OPERATIONS ==========

def get_stock_keys(product_id=None, plan_id=None, price=None, status=None):
    with get_db() as conn:
        q = "SELECT sk.*, p.name as product_name, pl.name as plan_name FROM stock_keys sk LEFT JOIN products p ON sk.product_id=p.id LEFT JOIN plans pl ON sk.plan_id=pl.id"
        conds = []
        params = []
        if product_id:
            conds.append("sk.product_id=?")
            params.append(product_id)
        if plan_id:
            conds.append("sk.plan_id=?")
            params.append(plan_id)
        if price is not None:
            conds.append("sk.price=?")
            params.append(price)
        if status:
            conds.append("sk.status=?")
            params.append(status)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY sk.created_at DESC"
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def get_available_key(product_id, plan_id=None, price=None):
    """Get an available key matching product_id, plan_id AND price exactly."""
    with get_db() as conn:
        conds = ["product_id=?", "status='available'"]
        params = [product_id]
        if plan_id:
            conds.append("plan_id=?")
            params.append(plan_id)
        if price is not None:
            conds.append("price=?")
            params.append(price)
        where = " AND ".join(conds)
        q = f"SELECT * FROM stock_keys WHERE {where} ORDER BY id LIMIT 1"
        r = conn.execute(q, params).fetchone()
        return dict(r) if r else None


def add_stock_key(product_id, key_value, plan_id=None, price=0):
    with get_db() as conn:
        try:
            c = conn.execute(
                "INSERT INTO stock_keys (product_id, plan_id, price, key_value) VALUES (?, ?, ?, ?)",
                (product_id, plan_id, price, key_value.strip()))
            return c.lastrowid
        except sqlite3.IntegrityError:
            return None


def import_stock_keys(product_id, keys_text, plan_id=None, price=0):
    keys = [k.strip() for k in keys_text.strip().split("\n") if k.strip()]
    added, skipped = 0, 0
    for key in keys:
        result = add_stock_key(product_id, key, plan_id, price)
        if result:
            added += 1
        else:
            skipped += 1
    return added, skipped


def mark_key_used(key_id, order_id, user_id=None):
    with get_db() as conn:
        conn.execute(
            "UPDATE stock_keys SET status='used', order_id=?, user_id=?, used_at=CURRENT_TIMESTAMP WHERE id=?",
            (order_id, user_id, key_id))


def delete_stock_key(key_id):
    with get_db() as conn:
        conn.execute("DELETE FROM stock_keys WHERE id=?", (key_id,))


def get_stock_keys_count(product_id=None, plan_id=None, price=None):
    """Get available/used/total counts for a product+plan+price."""
    with get_db() as conn:
        conds = []
        params = []
        if product_id:
            conds.append("product_id=?")
            params.append(product_id)
        if plan_id is not None:
            conds.append("plan_id=?")
            params.append(plan_id)
        if price is not None:
            conds.append("price=?")
            params.append(price)
        where = " WHERE " + " AND ".join(conds) if conds else ""
        available = conn.execute(f"SELECT COUNT(*) as c FROM stock_keys{where} AND status='available'", params).fetchone()["c"]
        used = conn.execute(f"SELECT COUNT(*) as c FROM stock_keys{where} AND status='used'", params).fetchone()["c"]
        total = conn.execute(f"SELECT COUNT(*) as c FROM stock_keys{where}", params).fetchone()["c"]
        return {"available": available, "used": used, "total": total}


def get_stock_count(product_id=None):
    with get_db() as conn:
        q = "SELECT product_id, status, COUNT(*) as cnt FROM stock_keys"
        params = []
        if product_id:
            q += " WHERE product_id=?"
            params.append(product_id)
        q += " GROUP BY product_id, status"
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def delete_keys_by_product_plan(product_id, plan_id=None, price=None):
    """Delete all keys for a product+plan+price. Returns count deleted."""
    with get_db() as conn:
        conds = ["product_id=?"]
        params = [product_id]
        if plan_id is not None:
            conds.append("plan_id=?")
            params.append(plan_id)
        if price is not None:
            conds.append("price=?")
            params.append(price)
        where = " AND ".join(conds)
        c = conn.execute(f"SELECT COUNT(*) as c FROM stock_keys WHERE {where}", params).fetchone()["c"]
        conn.execute(f"DELETE FROM stock_keys WHERE {where}", params)
        return c


def export_stock_keys_text(product_id, plan_id=None, price=None, status=None):
    """Export keys as text, one per line."""
    keys = get_stock_keys(product_id=product_id, plan_id=plan_id, price=price, status=status)
    return "\n".join(k["key_value"] for k in keys)


def delete_stock_keys_by_ids(key_ids):
    """Delete multiple keys by id list."""
    with get_db() as conn:
        placeholders = ",".join("?" for _ in key_ids)
        conn.execute(f"DELETE FROM stock_keys WHERE id IN ({placeholders})", key_ids)
        return len(key_ids)


# ========== ORDER OPERATIONS ==========

def generate_order_id():
    now = datetime.now()
    return f"ORD{now.strftime('%Y%m%d%H%M%S')}{os.urandom(3).hex().upper()}"


def create_order(user_id, username, product_id, plan_id, product_name, plan_name, amount, payment_method):
    order_id_str = generate_order_id()
    with get_db() as conn:
        conn.execute('''
            INSERT INTO orders (order_id, user_id, username, product_id, plan_id, product_name, plan_name, amount, payment_method)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (order_id_str, user_id, username, product_id, plan_id, product_name, plan_name, amount, payment_method))
        return order_id_str


def get_order(order_id):
    with get_db() as conn:
        r = conn.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
        return dict(r) if r else None


def get_orders(status=None, user_id=None, limit=50, offset=0):
    with get_db() as conn:
        q = "SELECT * FROM orders"
        conds = []
        params = []
        if status:
            conds.append("order_status=?")
            params.append(status)
        if user_id:
            conds.append("user_id=?")
            params.append(user_id)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def get_user_orders(user_id, limit=20):
    return get_orders(user_id=user_id, limit=limit)


def update_order(order_id, **kwargs):
    allowed = {"payment_status", "utr_number", "order_status", "binance_prepay_id",
               "delivered_key", "admin_note"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    updates["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [order_id]
    with get_db() as conn:
        conn.execute(f"UPDATE orders SET {set_clause} WHERE order_id=?", values)


def approve_order(order_id):
    order = get_order(order_id)
    if not order or order["order_status"] != "pending":
        return False, "Order not found or already processed"

    # Check if product has a reseller API PID
    from reseller_api import get_product_pid, is_reseller_api_configured, call_reseller_api
    product_pid = get_product_pid(order["product_id"])

    if product_pid and is_reseller_api_configured():
        # ============================================================
        # RESELLER API AUTO-DELIVERY PATH
        # ============================================================
        plan = get_plan(order["plan_id"]) if order["plan_id"] else None
        duration_text = plan["duration"] if plan else "30 Days"

        result = call_reseller_api(
            product_id=order["product_id"],
            duration_text=duration_text,
            order_id=order_id
        )

        if result["success"]:
            # API delivered successfully
            delivered_key = result["key"]
            update_order(order_id,
                        order_status="approved",
                        delivered_key=delivered_key,
                        payment_status="completed",
                        reseller_response=result["raw_response"])
            add_log("reseller_delivered", order.get("user_id"),
                    f"Reseller API delivered for order {order_id}: PID={product_pid}, key={delivered_key[:60]}")
            return True, delivered_key
        else:
            # API failed — mark order as pending with note
            error_msg = result["error"]
            update_order(order_id,
                        admin_note=f"[RESELLER FAILED] {error_msg}",
                        reseller_response=result["raw_response"])
            add_log("reseller_failed", None,
                    f"Reseller API FAILED for order {order_id}: {error_msg}")
            return False, f"Reseller API error: {error_msg}"

    # ============================================================
    # NO PID PATH — approve without key, admin adds manually later
    # ============================================================
    update_order(order_id, order_status="approved", payment_status="completed",
                 delivered_key="[MANUAL] Admin will add key",
                 admin_note="⚠️ No reseller PID — add key manually")
    add_log("manual_approve", order.get("user_id"),
            f"Order {order_id} approved manually — no reseller PID, admin must add key")
    return True, "Approved — add key manually from Stock Manager"


def reject_order(order_id, reason=""):
    order = get_order(order_id)
    if not order or order["order_status"] != "pending":
        return False, "Order not found or already processed"

    update_order(order_id, order_status="rejected", admin_note=reason)
    return True, "Order rejected"


# ========== USER OPERATIONS ==========

def get_or_create_user(user_id, username="", first_name="", last_name=""):
    with get_db() as conn:
        r = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if r:
            conn.execute(
                "UPDATE users SET username=?, first_name=?, last_name=?, last_active=CURRENT_TIMESTAMP WHERE user_id=?",
                (username, first_name, last_name, user_id))
            return dict(r)
        conn.execute(
            "INSERT OR REPLACE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, last_name))
        return dict(conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone())


def get_users(banned_only=False, limit=100, offset=0):
    with get_db() as conn:
        q = "SELECT * FROM users"
        if banned_only:
            q += " WHERE is_banned=1"
        q += " ORDER BY last_active DESC LIMIT ? OFFSET ?"
        return [dict(r) for r in conn.execute(q, (limit, offset)).fetchall()]


def get_user_count():
    with get_db() as conn:
        return conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]


def ban_user(user_id):
    with get_db() as conn:
        conn.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))


def unban_user(user_id):
    with get_db() as conn:
        conn.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))


# ========== CONFIG OPERATIONS ==========

def get_config(key, default=None):
    with get_db() as conn:
        r = conn.execute("SELECT value FROM bot_config WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default


def set_config(key, value):
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)",
            (key, str(value)))


def get_binance_extra_charge():
    """Get Binance extra charge — DB overrides env, default 20."""
    from config import BINANCE_EXTRA_CHARGE
    val = get_config("binance_extra_charge")
    if val is not None:
        try:
            return float(val)
        except ValueError:
            pass
    return BINANCE_EXTRA_CHARGE


def set_binance_extra_charge(amount):
    """Set Binance extra charge."""
    set_config("binance_extra_charge", str(amount))


def is_binance_enabled():
    """Check if Binance Pay is enabled."""
    from config import BINANCE_ENABLED
    val = get_config("binance_enabled")
    if val is not None:
        return val.lower() == "true"
    return BINANCE_ENABLED


def set_binance_enabled(enabled: bool):
    """Enable/disable Binance Pay."""
    set_config("binance_enabled", "true" if enabled else "false")


# ========== SETTINGS OPERATIONS (Support, Channel, Reseller) ==========

def get_setting(key, default=None):
    """Get a setting value from the settings table."""
    with get_db() as conn:
        r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default


def set_setting(key, value):
    """Set a setting value in the settings table."""
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, str(value)))


def is_support_enabled():
    return get_setting("support_enabled", "true") == "true"


def is_channel_enabled():
    return get_setting("channel_enabled", "true") == "true"


def is_reseller_enabled():
    return get_setting("reseller_enabled", "false") == "true"


def get_all_support_channel_settings():
    """Get all support/channel/reseller settings as a dict."""
    keys = [
        "support_enabled", "support_username", "support_link", "support_button_text",
        "channel_enabled", "channel_username", "channel_link", "channel_button_text",
        "reseller_enabled", "reseller_username", "reseller_link", "reseller_button_text",
    ]
    result = {}
    with get_db() as conn:
        for key in keys:
            r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            result[key] = r["value"] if r else ""
    return result


# ========== LOG OPERATIONS ==========

def add_log(event_type, user_id=None, message="", details=""):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO logs (event_type, user_id, message, details) VALUES (?, ?, ?, ?)",
            (event_type, user_id, message, details))


def get_logs(limit=100, event_type=None):
    with get_db() as conn:
        q = "SELECT * FROM logs"
        params = []
        if event_type:
            q += " WHERE event_type=?"
            params.append(event_type)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(q, params).fetchall()]


# ========== STATISTICS ==========

def get_stats():
    with get_db() as conn:
        c = conn.cursor()
        stats = {}
        stats["total_users"] = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        stats["total_products"] = c.execute("SELECT COUNT(*) FROM products WHERE is_active=1").fetchone()[0]
        stats["total_orders"] = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        stats["pending_orders"] = c.execute("SELECT COUNT(*) FROM orders WHERE order_status='pending'").fetchone()[0]
        stats["approved_orders"] = c.execute("SELECT COUNT(*) FROM orders WHERE order_status='approved'").fetchone()[0]
        stats["rejected_orders"] = c.execute("SELECT COUNT(*) FROM orders WHERE order_status='rejected'").fetchone()[0]
        stats["available_keys"] = c.execute("SELECT COUNT(*) FROM stock_keys WHERE status='available'").fetchone()[0]
        stats["used_keys"] = c.execute("SELECT COUNT(*) FROM stock_keys WHERE status='used'").fetchone()[0]
        revenue = c.execute("SELECT SUM(amount) FROM orders WHERE order_status='approved'").fetchone()[0]
        stats["total_revenue"] = revenue or 0.0
        return stats


# ========== BACKUP ==========

def backup_database():
    import shutil
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    from config import BACKUP_DIR
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"store_backup_{timestamp}.db")
    shutil.copy2(DATABASE_PATH, backup_path)
    return backup_path


# ========== ADMIN ROLE OPERATIONS (Multi-Admin Access Control) ==========

ADMIN_ROLES = ["super_admin", "admin", "editor"]

# Define permissions per role
ROLE_PERMISSIONS = {
    "super_admin": ["all"],  # Can do everything
    "admin": ["products", "plans", "keys", "orders", "users", "broadcast", "stats", "config", "logs", "backup", "categories"],
    "editor": ["products", "plans", "keys", "orders", "stats", "categories"],
}


def is_admin(user_id):
    """Check if user has ANY admin role and is active. Also checks config ADMIN_IDS for backward compat."""
    from config import ADMIN_IDS
    if user_id in ADMIN_IDS:
        return True
    with get_db() as conn:
        r = conn.execute("SELECT role FROM admin_roles WHERE user_id=? AND is_active=1", (user_id,)).fetchone()
        return r is not None


def is_super_admin(user_id):
    """Check if user is super_admin."""
    from config import ADMIN_IDS
    if user_id in ADMIN_IDS:
        return True
    with get_db() as conn:
        r = conn.execute("SELECT role FROM admin_roles WHERE user_id=? AND is_active=1 AND role='super_admin'", (user_id,)).fetchone()
        return r is not None


def get_admin_role(user_id):
    """Get admin's role and permissions."""
    from config import ADMIN_IDS
    if user_id in ADMIN_IDS:
        return {"role": "super_admin", "permissions": "all"}
    with get_db() as conn:
        r = conn.execute("SELECT * FROM admin_roles WHERE user_id=? AND is_active=1", (user_id,)).fetchone()
        return dict(r) if r else None


def get_admin_roles():
    """Get all admin entries."""
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM admin_roles ORDER BY role, username").fetchall()]


def has_permission(user_id, permission):
    """Check if admin has a specific permission."""
    role_info = get_admin_role(user_id)
    if not role_info:
        return False
    if role_info.get("role") == "super_admin" or role_info.get("role") == "superadmin" or "all" in (role_info.get("permissions", "") or "all"):
        return True
    perms = role_info.get("permissions", "")
    if perms == "all":
        return True
    perm_list = [p.strip() for p in perms.split(",") if p.strip()]
    if not perm_list:
        # Fallback to role-based permissions
        perm_list = ROLE_PERMISSIONS.get(role_info.get("role", "admin"), [])
    return permission in perm_list


def add_admin_role(user_id, username="", first_name="", role="admin", permissions="", added_by=None):
    """Add a new admin role."""
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO admin_roles (user_id, username, first_name, role, permissions, added_by) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, first_name, role, permissions, added_by))
            return True
        except sqlite3.IntegrityError:
            return False


def update_admin_role(user_id, **kwargs):
    """Update admin role, permissions, or status."""
    allowed = {"role", "permissions", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    updates["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [user_id]
    with get_db() as conn:
        conn.execute(f"UPDATE admin_roles SET {set_clause} WHERE user_id=?", values)


def remove_admin_role(user_id):
    """Remove an admin role entry."""
    with get_db() as conn:
        conn.execute("DELETE FROM admin_roles WHERE user_id=?", (user_id,))
