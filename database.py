import sqlite3
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import threading

# Thread-safe database connection
thread_local = threading.local()

def get_connection():
    """Get thread-local database connection"""
    if not hasattr(thread_local, 'connection'):
        thread_local.connection = sqlite3.connect('Bot_premium.db', check_same_thread=False)
        thread_local.connection.row_factory = sqlite3.Row
    return thread_local.connection


def generate_referral_code(length=8):
    """Generate unique referral code"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def init_database():
    """Initialize database with all required tables"""
    conn = get_connection()
    cursor = conn.cursor()

    # Users table with referral system
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY,
        nome TEXT,
        username TEXT,
        credits INTEGER DEFAULT 0,
        free_searches INTEGER DEFAULT 1,
        total_searches INTEGER DEFAULT 0,
        referral_code TEXT UNIQUE,
        referred_by INTEGER,
        total_referral_earnings INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_search TIMESTAMP,
        is_premium BOOLEAN DEFAULT 0,
        is_banned BOOLEAN DEFAULT 0
    )
    """)

    # Payments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        payment_id TEXT UNIQUE,
        invoice_id TEXT,
        invoice_url TEXT,
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

    # Referral commissions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS referral_commissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER,
        payment_id TEXT,
        credits_deposited INTEGER,
        commission_earned INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (referrer_id) REFERENCES usuarios (id),
        FOREIGN KEY (referred_id) REFERENCES usuarios (id)
    )
    """)

    # Coupons table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        type TEXT NOT NULL CHECK (type IN ('credits', 'free_searches')),
        value INTEGER NOT NULL,
        max_uses INTEGER DEFAULT 0,
        current_uses INTEGER DEFAULT 0,
        expires_at TIMESTAMP,
        is_active BOOLEAN DEFAULT 1,
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Coupon usage table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS coupon_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coupon_id INTEGER,
        user_id INTEGER,
        ip_address TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (coupon_id) REFERENCES coupons (id),
        FOREIGN KEY (user_id) REFERENCES usuarios (id)
    )
    """)

    # Admin logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER NOT NULL,
        action_type TEXT NOT NULL,
        target_user_id INTEGER,
        details TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Activity logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        action_type TEXT NOT NULL,
        details TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Rate limits table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rate_limits (
        user_id INTEGER PRIMARY KEY,
        last_action TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        action_count INTEGER DEFAULT 0,
        blocked_until TIMESTAMP
    )
    """)

    conn.commit()
    print("✅ Database initialized successfully (SQLite local)")


def add_user(user_id: int, nome: str, username: str, referred_by_code: str = None) -> bool:
    """Add new user to database"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM usuarios WHERE id = ?", (user_id,))
        if cursor.fetchone():
            return False

        # Generate unique referral code
        referral_code = generate_referral_code()
        while True:
            cursor.execute("SELECT id FROM usuarios WHERE referral_code = ?", (referral_code,))
            if not cursor.fetchone():
                break
            referral_code = generate_referral_code()

        # Find referrer if code provided
        referrer_id = None
        if referred_by_code:
            cursor.execute("SELECT id FROM usuarios WHERE referral_code = ?", (referred_by_code,))
            referrer = cursor.fetchone()
            if referrer:
                referrer_id = referrer['id']

        cursor.execute(
            """INSERT INTO usuarios (id, nome, username, credits, free_searches, referral_code, referred_by)
               VALUES (?, ?, ?, 0, 1, ?, ?)""",
            (user_id, nome, username, referral_code, referrer_id)
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

        user = get_user(user_id)
        log_activity(user_id, 'credits_added', f'{{"amount": {credits}, "new_balance": {user["credits"]}}}')
        return True
    except Exception as e:
        print(f"Error updating credits: {e}")
        return False


def deduct_credits(user_id: int, amount: int = 1) -> bool:
    """Deduct credits from user (for search) - returns True if used free search"""
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
            return False

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
        log_activity(user_id, 'search', f'{{"url": "{url}", "lines": {lines}, "is_free": {is_free}}}')
    except Exception as e:
        print(f"Error adding search history: {e}")


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


def add_payment(user_id: int, payment_id: str, amount: float, currency: str, credits: int, invoice_id: str = None, invoice_url: str = None):
    """Add payment record"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """INSERT INTO payments (user_id, payment_id, invoice_id, invoice_url, amount, currency, credits, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'waiting')""",
            (user_id, payment_id, invoice_id, invoice_url, amount, currency, credits)
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


def get_pending_payment(user_id: int) -> Optional[Dict]:
    """Get user's pending payment (if any)"""
    conn = get_connection()
    cursor = conn.cursor()

    one_hour_ago = datetime.now() - timedelta(hours=1)
    cursor.execute(
        """SELECT * FROM payments
           WHERE user_id = ?
           AND status = 'waiting'
           AND datetime(created_at) > datetime(?)
           ORDER BY created_at DESC
           LIMIT 1""",
        (user_id, one_hour_ago)
    )
    row = cursor.fetchone()

    if row:
        payment_dict = dict(row)
        if 'invoice_url' not in payment_dict or not payment_dict.get('invoice_url'):
            payment_dict['invoice_url'] = f"https://nowpayments.io/payment/?iid={payment_dict['payment_id']}"
        return payment_dict
    return None


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
    cursor.execute("SELECT COUNT(*) as count, SUM(amount) as total FROM payments WHERE status = 'finished'")
    row = cursor.fetchone()
    stats['total_transactions'] = row['count'] or 0
    stats['total_revenue'] = row['total'] or 0

    # Today's searches
    cursor.execute("SELECT COUNT(*) as count FROM search_history WHERE DATE(timestamp) = DATE('now')")
    stats['today_searches'] = cursor.fetchone()['count']

    return stats


# Referral system functions

def get_user_by_referral_code(code: str) -> Optional[Dict]:
    """Get user by referral code"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM usuarios WHERE referral_code = ?", (code,))
    row = cursor.fetchone()

    if row:
        return dict(row)
    return None


def update_referral_code(user_id: int, new_code: str) -> bool:
    """Update user's referral code"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Check if code is available
        cursor.execute("SELECT id FROM usuarios WHERE referral_code = ?", (new_code,))
        if cursor.fetchone():
            return False

        cursor.execute("UPDATE usuarios SET referral_code = ? WHERE id = ?", (new_code, user_id))
        conn.commit()

        log_admin_action(user_id, 'referral_code_changed', None, f'{{"new_code": "{new_code}"}}')
        return True
    except Exception as e:
        print(f"Error updating referral code: {e}")
        return False


def process_referral_commission(payment_id: str, user_id: int, credits_deposited: int):
    """Process referral commission when payment is confirmed"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get user info
        user = get_user(user_id)
        if not user or not user['referred_by']:
            return False

        # Calculate commission (10%)
        commission = int(credits_deposited * 0.1)
        if commission < 1:
            return False

        # Add credits to referrer
        referrer_id = user['referred_by']
        update_user_credits(referrer_id, commission)

        # Update referrer's total earnings
        referrer = get_user(referrer_id)
        cursor.execute(
            "UPDATE usuarios SET total_referral_earnings = ? WHERE id = ?",
            (referrer['total_referral_earnings'] + commission, referrer_id)
        )

        # Record commission
        cursor.execute(
            """INSERT INTO referral_commissions (referrer_id, referred_id, payment_id, credits_deposited, commission_earned)
               VALUES (?, ?, ?, ?, ?)""",
            (referrer_id, user_id, payment_id, credits_deposited, commission)
        )
        conn.commit()

        print(f"[INFO] Referral commission processed: {commission} credits to user {referrer_id}")
        return True
    except Exception as e:
        print(f"Error processing referral commission: {e}")
        return False


def get_referral_stats(user_id: int) -> Dict:
    """Get referral statistics for user"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get total referred users
        cursor.execute("SELECT COUNT(*) as count FROM usuarios WHERE referred_by = ?", (user_id,))
        total_referred = cursor.fetchone()['count']

        # Get total commissions
        cursor.execute("SELECT SUM(commission_earned) as total FROM referral_commissions WHERE referrer_id = ?", (user_id,))
        result = cursor.fetchone()
        total_earned = result['total'] if result['total'] else 0

        # Get referred users list
        cursor.execute(
            "SELECT id, nome, username, created_at FROM usuarios WHERE referred_by = ? ORDER BY created_at DESC",
            (user_id,)
        )
        referred_users = [dict(row) for row in cursor.fetchall()]

        return {
            'total_referred': total_referred,
            'total_earned': total_earned,
            'referred_users': referred_users
        }
    except Exception as e:
        print(f"Error getting referral stats: {e}")
        return {'total_referred': 0, 'total_earned': 0, 'referred_users': []}


# Coupon system functions

def create_coupon(code: str, coupon_type: str, value: int, max_uses: int, expires_at: datetime, created_by: int) -> bool:
    """Create a new coupon"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """INSERT INTO coupons (code, type, value, max_uses, expires_at, created_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (code.upper(), coupon_type, value, max_uses, expires_at, created_by)
        )
        conn.commit()

        log_admin_action(created_by, 'coupon_created', None, f'{{"code": "{code}", "type": "{coupon_type}", "value": {value}}}')
        return True
    except Exception as e:
        print(f"Error creating coupon: {e}")
        return False


def get_coupon(code: str) -> Optional[Dict]:
    """Get coupon by code"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM coupons WHERE code = ?", (code.upper(),))
    row = cursor.fetchone()

    if row:
        return dict(row)
    return None


def use_coupon(user_id: int, code: str, ip_address: str) -> tuple[bool, str]:
    """Use a coupon - returns (success, message)"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        coupon = get_coupon(code)
        if not coupon:
            return False, "Cupom inválido"

        if not coupon['is_active']:
            return False, "Cupom desativado"

        # Check expiration
        if coupon['expires_at']:
            if datetime.fromisoformat(coupon['expires_at']) < datetime.now():
                return False, "Cupom expirado"

        # Check max uses
        if coupon['max_uses'] > 0 and coupon['current_uses'] >= coupon['max_uses']:
            return False, "Cupom esgotado"

        # Check if IP already used this coupon
        cursor.execute(
            "SELECT id FROM coupon_usage WHERE coupon_id = ? AND ip_address = ?",
            (coupon['id'], ip_address)
        )
        if cursor.fetchone():
            return False, "Este IP já usou este cupom"

        # Check if user already used this coupon
        cursor.execute(
            "SELECT id FROM coupon_usage WHERE coupon_id = ? AND user_id = ?",
            (coupon['id'], user_id)
        )
        if cursor.fetchone():
            return False, "Você já usou este cupom"

        # Apply coupon
        if coupon['type'] == 'credits':
            update_user_credits(user_id, coupon['value'])
        elif coupon['type'] == 'free_searches':
            user = get_user(user_id)
            cursor.execute(
                "UPDATE usuarios SET free_searches = ? WHERE id = ?",
                (user['free_searches'] + coupon['value'], user_id)
            )

        # Record usage
        cursor.execute(
            "INSERT INTO coupon_usage (coupon_id, user_id, ip_address) VALUES (?, ?, ?)",
            (coupon['id'], user_id, ip_address)
        )

        # Update coupon usage count
        cursor.execute(
            "UPDATE coupons SET current_uses = current_uses + 1 WHERE id = ?",
            (coupon['id'],)
        )

        conn.commit()

        log_activity(user_id, 'coupon_used', f'{{"code": "{code}", "type": "{coupon["type"]}", "value": {coupon["value"]}}}')

        return True, f"Cupom aplicado! +{coupon['value']} {'créditos' if coupon['type'] == 'credits' else 'buscas grátis'}"
    except Exception as e:
        print(f"Error using coupon: {e}")
        return False, "Erro ao aplicar cupom"


def get_all_coupons() -> List[Dict]:
    """Get all coupons (admin)"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM coupons ORDER BY created_at DESC")
    return [dict(row) for row in cursor.fetchall()]


def toggle_coupon(coupon_id: str, is_active: bool) -> bool:
    """Activate/deactivate coupon"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("UPDATE coupons SET is_active = ? WHERE id = ?", (is_active, coupon_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error toggling coupon: {e}")
        return False


# Admin functions

def get_all_users() -> List[Dict]:
    """Get all users (admin only)"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM usuarios ORDER BY created_at DESC")
    return [dict(row) for row in cursor.fetchall()]


def ban_user(user_id: int, admin_id: int, reason: str = None) -> bool:
    """Ban a user"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("UPDATE usuarios SET is_banned = 1 WHERE id = ?", (user_id,))
        conn.commit()
        log_admin_action(admin_id, 'user_banned', user_id, f'{{"reason": "{reason}"}}')
        return True
    except Exception as e:
        print(f"Error banning user: {e}")
        return False


def unban_user(user_id: int, admin_id: int) -> bool:
    """Unban a user"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("UPDATE usuarios SET is_banned = 0 WHERE id = ?", (user_id,))
        conn.commit()
        log_admin_action(admin_id, 'user_unbanned', user_id, "{}")
        return True
    except Exception as e:
        print(f"Error unbanning user: {e}")
        return False


def admin_adjust_credits(user_id: int, amount: int, admin_id: int, reason: str):
    """Admin manually adjust user credits"""
    try:
        update_user_credits(user_id, amount)
        log_admin_action(admin_id, 'credits_adjusted', user_id, f'{{"amount": {amount}, "reason": "{reason}"}}')
        return True
    except Exception as e:
        print(f"Error adjusting credits: {e}")
        return False


def admin_adjust_free_searches(user_id: int, amount: int, admin_id: int, reason: str):
    """Admin manually adjust user free searches"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        user = get_user(user_id)
        new_amount = max(0, user['free_searches'] + amount)
        cursor.execute("UPDATE usuarios SET free_searches = ? WHERE id = ?", (new_amount, user_id))
        conn.commit()
        log_admin_action(admin_id, 'free_searches_adjusted', user_id, f'{{"amount": {amount}, "reason": "{reason}"}}')
        return True
    except Exception as e:
        print(f"Error adjusting free searches: {e}")
        return False


def log_admin_action(admin_id: int, action_type: str, target_user_id: int = None, details: str = None):
    """Log admin action"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO admin_logs (admin_id, action_type, target_user_id, details) VALUES (?, ?, ?, ?)",
            (admin_id, action_type, target_user_id, details)
        )
        conn.commit()
    except Exception as e:
        print(f"Error logging admin action: {e}")


def get_admin_logs(limit: int = 50) -> List[Dict]:
    """Get admin action logs"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM admin_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
    return [dict(row) for row in cursor.fetchall()]


def log_activity(user_id: int, action_type: str, details: str = None):
    """Log user activity"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO activity_logs (user_id, action_type, details) VALUES (?, ?, ?)",
            (user_id, action_type, details)
        )
        conn.commit()
    except Exception as e:
        print(f"Error logging activity: {e}")


def get_activity_logs(user_id: int = None, limit: int = 50) -> List[Dict]:
    """Get activity logs"""
    conn = get_connection()
    cursor = conn.cursor()

    if user_id:
        cursor.execute("SELECT * FROM activity_logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?", (user_id, limit))
    else:
        cursor.execute("SELECT * FROM activity_logs ORDER BY timestamp DESC LIMIT ?", (limit,))

    return [dict(row) for row in cursor.fetchall()]


# Anti-spam / Rate limiting functions

def check_rate_limit(user_id: int) -> tuple[bool, int]:
    """Check if user is rate limited - returns (is_blocked, seconds_remaining)"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM rate_limits WHERE user_id = ?", (user_id,))
        rate_limit = cursor.fetchone()

        if not rate_limit:
            # First action, create record
            cursor.execute(
                "INSERT INTO rate_limits (user_id, action_count) VALUES (?, 1)",
                (user_id,)
            )
            conn.commit()
            return False, 0

        rate_limit = dict(rate_limit)

        # Check if currently blocked
        if rate_limit['blocked_until']:
            blocked_until = datetime.fromisoformat(rate_limit['blocked_until'])
            if blocked_until > datetime.now():
                seconds_remaining = int((blocked_until - datetime.now()).total_seconds())
                return True, seconds_remaining
            else:
                # Unblock
                cursor.execute(
                    "UPDATE rate_limits SET blocked_until = NULL, action_count = 1, last_action = ? WHERE user_id = ?",
                    (datetime.now(), user_id)
                )
                conn.commit()
                return False, 0

        # Check action count in last 10 seconds
        last_action = datetime.fromisoformat(rate_limit['last_action'])
        time_diff = (datetime.now() - last_action).total_seconds()

        if time_diff < 10:
            # Within 10 seconds window
            new_count = rate_limit['action_count'] + 1

            if new_count > 5:
                # Block for 5 minutes
                blocked_until = datetime.now() + timedelta(minutes=5)
                cursor.execute(
                    "UPDATE rate_limits SET blocked_until = ?, action_count = 0 WHERE user_id = ?",
                    (blocked_until, user_id)
                )
                conn.commit()

                log_activity(user_id, 'rate_limit_triggered', '{"reason": "too_many_actions"}')
                return True, 300  # 5 minutes

            # Update count
            cursor.execute(
                "UPDATE rate_limits SET action_count = ?, last_action = ? WHERE user_id = ?",
                (new_count, datetime.now(), user_id)
            )
            conn.commit()
        else:
            # Reset counter
            cursor.execute(
                "UPDATE rate_limits SET action_count = 1, last_action = ? WHERE user_id = ?",
                (datetime.now(), user_id)
            )
            conn.commit()

        return False, 0
    except Exception as e:
        print(f"Error checking rate limit: {e}")
        return False, 0


def get_blocked_users() -> List[Dict]:
    """Get list of currently blocked users"""
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now()
    cursor.execute("SELECT user_id, blocked_until FROM rate_limits WHERE blocked_until > ?", (now,))
    return [dict(row) for row in cursor.fetchall()]
