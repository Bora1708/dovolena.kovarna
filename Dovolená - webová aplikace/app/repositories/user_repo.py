# app/repositories/user_repo.py

import sqlite3
from typing import Optional, Dict, Any, List
from app.models.schemas import EmployeeCreateByAdmin
from app.core.config import settings


#
# OPERACE ČTENÍ (READ)
#
def get_all_users_for_admin_management(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    query = """
    SELECT id, name, email, is_admin, is_super_admin, remaining_days 
    FROM users 
    ORDER BY email
    """
    cursor.execute(query)
    return [dict(row) for row in cursor.fetchall()]

def get_user_by_email(conn: sqlite3.Connection, email: str) -> Optional[Dict[str, Any]]:
    cursor = conn.cursor()
    query = """
    SELECT id, email, hashed_password, is_admin, is_super_admin, remaining_days, profile_picture_path, name 
    FROM users 
    WHERE email = ?
    """
    cursor.execute(query, (email,))
    user = cursor.fetchone()
    if user:
        return dict(user)
    return None

def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> Optional[Dict[str, Any]]:
    cursor = conn.cursor()
    query = """
    SELECT id, email, hashed_password, is_admin, is_super_admin, remaining_days, profile_picture_path, name 
    FROM users 
    WHERE id = ?
    """
    cursor.execute(query, (user_id,))
    user = cursor.fetchone()
    if user:
        return dict(user)
    return None

def get_all_employees(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    query = """
    SELECT id, email, remaining_days, profile_picture_path, name 
    FROM users 
    WHERE is_admin = 0 AND is_super_admin = 0 
    ORDER BY email
    """
    cursor.execute(query)
    return [dict(row) for row in cursor.fetchall()]


#
# OPERACE TVORBY (CREATE)
#
def create_user(
    conn: sqlite3.Connection, 
    user_data: EmployeeCreateByAdmin, 
    hashed_password: str, 
    is_admin: bool = False, 
    is_super_admin: bool = False
) -> Optional[Dict[str, Any]]:
    
    remaining_days = user_data.remaining_days if user_data.remaining_days is not None else settings.DEFAULT_VACATION_DAYS
    admin_flag = 1 if is_admin else 0
    super_admin_flag = 1 if is_super_admin else 0
    
    cursor = conn.cursor()
    query = """
    INSERT INTO users (email, hashed_password, is_admin, is_super_admin, remaining_days, name) 
    VALUES (?, ?, ?, ?, ?, ?)
    """ 
    cursor.execute(query, (user_data.email, hashed_password, admin_flag, super_admin_flag, remaining_days, user_data.name))
    conn.commit()
    
    last_id = cursor.lastrowid
    return get_user_by_id(conn, last_id)


#
# OPERACE AKTUALIZACE (UPDATE)
#
def update_user_remaining_days(conn: sqlite3.Connection, user_id: int, days_change: int) -> bool:
    user = get_user_by_id(conn, user_id)
    if not user:
        return False
        
    current_remaining_days = user['remaining_days']
    new_remaining_days = current_remaining_days + days_change
    if new_remaining_days < 0:
        return False 
        
    cursor = conn.cursor()
    query = "UPDATE users SET remaining_days = ? WHERE id = ?"
    cursor.execute(query, (new_remaining_days, user_id))
    conn.commit() 
    
    return cursor.rowcount == 1

def update_user_roles(conn: sqlite3.Connection, user_id: int, is_admin: bool, is_super_admin: bool) -> bool:
    if is_super_admin:
        is_admin = False
        
    admin_flag = 1 if is_admin else 0
    super_admin_flag = 1 if is_super_admin else 0
    
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET is_admin = ?, is_super_admin = ?
        WHERE id = ?
    """, (admin_flag, super_admin_flag, user_id))
    conn.commit()
    
    return cursor.rowcount > 0


#
# OPERACE MAZÁNÍ (DELETE)
#
def delete_user(conn: sqlite3.Connection, user_id: int) -> bool:
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vacations WHERE employee_id = ?", (user_id,))
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    
    return True