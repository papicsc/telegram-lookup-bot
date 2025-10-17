from typing import Optional, Dict, List
from datetime import datetime
import sqlite3
from database import get_connection

def get_all_categories() -> List[Dict]:
    """Get all active bank categories"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bank_categories WHERE is_active = 1 ORDER BY `order`")
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting categories: {e}")
        return []


def get_subcategories_by_category(category_id: str) -> List[Dict]:
    """Get all subcategories for a specific category"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bank_subcategories WHERE category_id = ? AND is_active = 1 ORDER BY `order`", (category_id,))
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting subcategories: {e}")
        return []


def get_banks_by_subcategory(subcategory_id: str) -> List[Dict]:
    """Get all banks for a specific subcategory"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM banks WHERE subcategory_id = ? AND is_active = 1 ORDER BY `order`", (subcategory_id,))
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting banks: {e}")
        return []


def get_bank_by_id(bank_id: str) -> Optional[Dict]:
    """Get specific bank by ID"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM banks WHERE id = ? AND is_active = 1", (bank_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"Error getting bank: {e}")
        return None


def get_category_by_id(category_id: str) -> Optional[Dict]:
    """Get specific category by ID"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bank_categories WHERE id = ?", (category_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"Error getting category: {e}")
        return None


def get_subcategory_by_id(subcategory_id: str) -> Optional[Dict]:
    """Get specific subcategory by ID"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bank_subcategories WHERE id = ?", (subcategory_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"Error getting subcategory: {e}")
        return None


def create_bank_request(user_id: int, bank_id: str, credits_used: int, notes: str = None) -> bool:
    """Create a new bank request"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO bank_requests (user_id, bank_id, credits_used, status, notes, created_at)
               VALUES (?, ?, ?, 'pending', ?, ?)""",
            (user_id, bank_id, credits_used, notes, datetime.now().isoformat())
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error creating bank request: {e}")
        return False


def get_user_bank_requests(user_id: int, limit: int = 10) -> List[Dict]:
    """Get user's bank requests"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT br.*, b.name, b.account_type, b.price
               FROM bank_requests br
               LEFT JOIN banks b ON br.bank_id = b.id
               WHERE br.user_id = ?
               ORDER BY br.created_at DESC
               LIMIT ?""",
            (user_id, limit)
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting user requests: {e}")
        return []


def get_all_bank_requests(status: str = None, limit: int = 50) -> List[Dict]:
    """Get all bank requests (admin only)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if status:
            cursor.execute(
                """SELECT br.*, b.name, b.account_type, b.price
                   FROM bank_requests br
                   LEFT JOIN banks b ON br.bank_id = b.id
                   WHERE br.status = ?
                   ORDER BY br.created_at DESC
                   LIMIT ?""",
                (status, limit)
            )
        else:
            cursor.execute(
                """SELECT br.*, b.name, b.account_type, b.price
                   FROM bank_requests br
                   LEFT JOIN banks b ON br.bank_id = b.id
                   ORDER BY br.created_at DESC
                   LIMIT ?""",
                (limit,)
            )

        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting all requests: {e}")
        return []


def update_request_status(request_id: str, status: str, admin_notes: str = None) -> bool:
    """Update bank request status (admin only)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if admin_notes:
            cursor.execute(
                "UPDATE bank_requests SET status = ?, processed_at = ?, admin_notes = ? WHERE id = ?",
                (status, datetime.now().isoformat(), admin_notes, request_id)
            )
        else:
            cursor.execute(
                "UPDATE bank_requests SET status = ?, processed_at = ? WHERE id = ?",
                (status, datetime.now().isoformat(), request_id)
            )

        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating request status: {e}")
        return False


def add_bank(subcategory_id: str, name: str, account_type: str, price: float,
             has_physical_card: bool, has_esim: bool, description: str,
             credits_cost: int, logo_url: str = None, screenshot_url: str = None) -> Optional[str]:
    """Add new bank (admin only)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        existing_banks = get_banks_by_subcategory(subcategory_id)
        order = len(existing_banks)

        cursor.execute(
            """INSERT INTO banks (subcategory_id, name, account_type, price, has_physical_card,
                                  has_esim, description, credits_cost, logo_url, screenshot_url,
                                  `order`, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (subcategory_id, name, account_type, price, has_physical_card,
             has_esim, description, credits_cost, logo_url, screenshot_url, order)
        )
        conn.commit()
        return str(cursor.lastrowid)
    except Exception as e:
        print(f"Error adding bank: {e}")
        return None


def update_bank(bank_id: str, **kwargs) -> bool:
    """Update bank information (admin only)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        kwargs['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values()) + [bank_id]

        cursor.execute(f"UPDATE banks SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating bank: {e}")
        return False


def delete_bank(bank_id: str) -> bool:
    """Soft delete bank by setting is_active to False (admin only)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE banks SET is_active = 0 WHERE id = ?", (bank_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting bank: {e}")
        return False


def add_subcategory(category_id: str, name: str, icon: str = '📍') -> Optional[str]:
    """Add new subcategory (admin only)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        existing_subs = get_subcategories_by_category(category_id)
        order = len(existing_subs)

        cursor.execute(
            """INSERT INTO bank_subcategories (category_id, name, icon, `order`, is_active)
               VALUES (?, ?, ?, ?, 1)""",
            (category_id, name, icon, order)
        )
        conn.commit()
        return str(cursor.lastrowid)
    except Exception as e:
        print(f"Error adding subcategory: {e}")
        return None


def search_banks(query: str) -> List[Dict]:
    """Search banks by name"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT b.*, bs.name as subcategory_name, bc.name as category_name
               FROM banks b
               LEFT JOIN bank_subcategories bs ON b.subcategory_id = bs.id
               LEFT JOIN bank_categories bc ON bs.category_id = bc.id
               WHERE b.name LIKE ? AND b.is_active = 1
               LIMIT 10""",
            (f"%{query}%",)
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error searching banks: {e}")
        return []


def get_bank_stats() -> Dict:
    """Get statistics about banks (admin only)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        categories_count = len(get_all_categories())

        cursor.execute("SELECT COUNT(*) as count FROM banks WHERE is_active = 1")
        banks_count = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM bank_requests")
        requests_count = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM bank_requests WHERE status = 'pending'")
        pending_count = cursor.fetchone()['count']

        return {
            'total_categories': categories_count,
            'total_banks': banks_count,
            'total_requests': requests_count,
            'pending_requests': pending_count
        }
    except Exception as e:
        print(f"Error getting stats: {e}")
        return {
            'total_categories': 0,
            'total_banks': 0,
            'total_requests': 0,
            'pending_requests': 0
        }


def format_bank_message(bank: Dict, index: int = 0, total: int = 0) -> str:
    """Format bank information for display"""
    physical_card = "✅ Sim" if bank.get('has_physical_card') else "❌ Não"
    esim = "✅ Sim" if bank.get('has_esim') else "❌ Não"

    account_icon = "🏢" if bank.get('account_type') == 'Empresa' else "👤"

    message = f"""<b>🏦 {bank['name']}</b>

{account_icon} <b>Tipo de Conta:</b> {bank.get('account_type', 'Pessoal')}
💰 <b>Preço:</b> €{float(bank.get('price', 0)):.2f}
💳 <b>Cartão Físico:</b> {physical_card}
📱 <b>eSIM:</b> {esim}

📋 <b>Descrição:</b>
{bank.get('description', 'Sem descrição disponível')}

💎 <b>Custo:</b> {bank.get('credits_cost', 1)} crédito(s)"""

    if total > 1:
        message += f"\n\n<i>📊 Banco {index + 1} de {total}</i>"

    return message
