import sqlite3
from datetime import datetime
from typing import Optional, Dict, List
import threading

# Thread-safe database connection
thread_local = threading.local()

def get_connection():
    """Get thread-local database connection"""
    if not hasattr(thread_local, 'connection'):
        thread_local.connection = sqlite3.connect('Bot_free.db', check_same_thread=False)
        thread_local.connection.row_factory = sqlite3.Row
    return thread_local.connection

def init_database():
    """Initialize database with all required tables"""
    conn = get_connection()
    cursor = conn.cursor()

    # Users table with credits system
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY,
        nome TEXT,
        user TEXT,
        credits INTEGER DEFAULT 0,
        free_searches INTEGER DEFAULT 1,
        total_searches INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_search TIMESTAMP,
        is_premium BOOLEAN DEFAULT 0,
        is_banned BOOLEAN DEFAULT 0
    )
    """)

    # Transactions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        amount REAL,
        credits INTEGER,
        status TEXT,
        payment_id TEXT,
        currency TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES usuarios (id)
    )
    """)

    # Search history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS search_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        url TEXT,
        lines INTEGER,
        credits_used INTEGER,
        is_free BOOLEAN DEFAULT 0,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES usuarios (id)
    )
    """)

    # Payments table (NOWPayments)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        payment_id TEXT UNIQUE,
        invoice_id TEXT,
        amount REAL,
        currency TEXT,
        pay_currency TEXT,
        pay_amount REAL,
        credits INTEGER,
        status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES usuarios (id)
    )
    """)

    conn.commit()
    print("✅ Database initialized successfully")

def add_user(user_id: int, nome: str, username: str) -> bool:
    """Add new user to database"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM usuarios WHERE id = ?", (user_id,))
        if cursor.fetchone():
            return False

        cursor.execute(
            """INSERT INTO usuarios (id, nome, user, credits, free_searches)
               VALUES (?, ?, ?, 0, 1)""",
            (user_id, nome, username)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding user: {e}")
        return False

def get_user(user_id: int) -> Optional[Dict]:
    """Get user information"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM usuarios WHERE id = ?", (user_id,))
    row = cursor.fetchone()

    if row:
        return dict(row)
    return None

def update_user_credits(user_id: int, credits: int) -> bool:
    """Update user credits"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "UPDATE usuarios SET credits = credits + ? WHERE id = ?",
            (credits, user_id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating credits: {e}")
        return False

def deduct_credits(user_id: int, amount: int = 1) -> bool:
    """Deduct credits from user (for search)"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        user = get_user(user_id)
        if not user:
            return False

        # Check if user has free searches
        if user['free_searches'] > 0:
            cursor.execute(
                "UPDATE usuarios SET free_searches = free_searches - 1, total_searches = total_searches + 1, last_search = ? WHERE id = ?",
                (datetime.now(), user_id)
            )
            conn.commit()
            return True

        # Check if user has credits
        if user['credits'] >= amount:
            cursor.execute(
                "UPDATE usuarios SET credits = credits - ?, total_searches = total_searches + 1, last_search = ? WHERE id = ?",
                (amount, datetime.now(), user_id)
            )
            conn.commit()
            return True

        return False
    except Exception as e:
        print(f"Error deducting credits: {e}")
        return False

def add_search_history(user_id: int, url: str, lines: int, credits_used: int, is_free: bool = False):
    """Add search to history"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """INSERT INTO search_history (user_id, url, lines, credits_used, is_free)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, url, lines, credits_used, is_free)
        )
        conn.commit()
    except Exception as e:
        print(f"Error adding search history: {e}")

def add_transaction(user_id: int, type: str, amount: float, credits: int, payment_id: str = None, currency: str = 'USD') -> int:
    """Add transaction record"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """INSERT INTO transactions (user_id, type, amount, credits, status, payment_id, currency)
               VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
            (user_id, type, amount, credits, payment_id, currency)
        )
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"Error adding transaction: {e}")
        return 0

def update_transaction_status(payment_id: str, status: str):
    """Update transaction status"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """UPDATE transactions
               SET status = ?, completed_at = ?
               WHERE payment_id = ?""",
            (status, datetime.now(), payment_id)
        )
        conn.commit()
    except Exception as e:
        print(f"Error updating transaction: {e}")

def get_user_history(user_id: int, limit: int = 10) -> List[Dict]:
    """Get user search history"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """SELECT * FROM search_history
           WHERE user_id = ?
           ORDER BY timestamp DESC
           LIMIT ?""",
        (user_id, limit)
    )

    return [dict(row) for row in cursor.fetchall()]

def get_user_transactions(user_id: int, limit: int = 10) -> List[Dict]:
    """Get user transaction history"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """SELECT * FROM transactions
           WHERE user_id = ?
           ORDER BY created_at DESC
           LIMIT ?""",
        (user_id, limit)
    )

    return [dict(row) for row in cursor.fetchall()]

def get_all_users() -> List[Dict]:
    """Get all users (admin only)"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM usuarios ORDER BY created_at DESC")
    return [dict(row) for row in cursor.fetchall()]

def get_stats() -> Dict:
    """Get overall statistics"""
    conn = get_connection()
    cursor = conn.cursor()

    stats = {}

    # Total users
    cursor.execute("SELECT COUNT(*) as count FROM usuarios")
    stats['total_users'] = cursor.fetchone()['count']

    # Total searches
    cursor.execute("SELECT COUNT(*) as count FROM search_history")
    stats['total_searches'] = cursor.fetchone()['count']

    # Total transactions
    cursor.execute("SELECT COUNT(*) as count, SUM(amount) as total FROM transactions WHERE status = 'completed'")
    row = cursor.fetchone()
    stats['total_transactions'] = row['count'] or 0
    stats['total_revenue'] = row['total'] or 0

    # Today's searches
    cursor.execute("SELECT COUNT(*) as count FROM search_history WHERE DATE(timestamp) = DATE('now')")
    stats['today_searches'] = cursor.fetchone()['count']

    return stats

def add_payment(user_id: int, payment_id: str, amount: float, currency: str, credits: int, invoice_id: str = None):
    """Add payment record"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """INSERT INTO payments (user_id, payment_id, invoice_id, amount, currency, credits, status)
               VALUES (?, ?, ?, ?, ?, ?, 'waiting')""",
            (user_id, payment_id, invoice_id, amount, currency, credits)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding payment: {e}")
        return False

def update_payment_status(payment_id: str, status: str, pay_currency: str = None, pay_amount: float = None):
    """Update payment status"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if pay_currency and pay_amount:
            cursor.execute(
                """UPDATE payments
                   SET status = ?, pay_currency = ?, pay_amount = ?, updated_at = ?
                   WHERE payment_id = ?""",
                (status, pay_currency, pay_amount, datetime.now(), payment_id)
            )
        else:
            cursor.execute(
                """UPDATE payments
                   SET status = ?, updated_at = ?
                   WHERE payment_id = ?""",
                (status, datetime.now(), payment_id)
            )
        conn.commit()

        # If completed, add credits to user
        if status == 'finished':
            cursor.execute("SELECT user_id, credits FROM payments WHERE payment_id = ?", (payment_id,))
            row = cursor.fetchone()
            if row:
                update_user_credits(row['user_id'], row['credits'])

        return True
    except Exception as e:
        print(f"Error updating payment: {e}")
        return False

def get_payment(payment_id: str) -> Optional[Dict]:
    """Get payment information"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM payments WHERE payment_id = ?", (payment_id,))
    row = cursor.fetchone()

    if row:
        return dict(row)
    return None
