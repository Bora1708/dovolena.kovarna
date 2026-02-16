# app/repositories/vacation_repo.py

import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.models.schemas import VacationRequest


#
# OPERACE TVORBY (CREATE)
#
def create_vacation_request(
    conn: sqlite3.Connection, 
    employee_id: int, 
    start_date: str,
    end_date: str, 
    total_days: int,
    status: str,
    submitted_at: str
) -> Optional[Dict[str, Any]]:
    cursor = conn.cursor()
    query = """
    INSERT INTO vacations (employee_id, start_date, end_date, total_days, status, submitted_at) 
    VALUES (?, ?, ?, ?, ?, ?)
    """
    cursor.execute(query, (
        employee_id, 
        start_date,
        end_date, 
        total_days,
        status, 
        submitted_at
    ))
    conn.commit() 
    
    last_id = cursor.lastrowid
    return get_vacation_request_by_id(conn, last_id)


#
# OPERACE ČTENÍ (READ)
#
def get_vacation_request_by_id(conn: sqlite3.Connection, request_id: int) -> Optional[Dict[str, Any]]:
    cursor = conn.cursor()
    query = "SELECT * FROM vacations WHERE id = ?"
    cursor.execute(query, (request_id,))
    request = cursor.fetchone()
    if request:
        return dict(request)
    return None

def get_active_vacation_requests(conn: sqlite3.Connection, employee_id: int) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    query = """
    SELECT * FROM vacations 
    WHERE employee_id = ? AND status IN ('Pending', 'Approved')
    """
    cursor.execute(query, (employee_id,))
    return [dict(row) for row in cursor.fetchall()]

def get_employee_vacation_history(conn: sqlite3.Connection, employee_id: int) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    query = "SELECT * FROM vacations WHERE employee_id = ? ORDER BY submitted_at DESC"
    cursor.execute(query, (employee_id,))
    return [dict(row) for row in cursor.fetchall()]

def get_pending_requests(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    query = """
    SELECT v.*, u.email FROM vacations v 
    JOIN users u ON v.employee_id = u.id 
    WHERE v.status = 'Pending' 
    ORDER BY v.submitted_at ASC
    """
    cursor.execute(query)
    return [dict(row) for row in cursor.fetchall()]

def get_upcoming_approved_vacations(conn: sqlite3.Connection, limit: int = 10):
    today = datetime.now().strftime('%Y-%m-%d')
    cursor = conn.cursor()
    query = """
    SELECT v.start_date, v.end_date, u.name 
    FROM vacations v 
    JOIN users u ON v.employee_id = u.id 
    WHERE v.status = 'Approved' 
    AND v.start_date >= ? 
    ORDER BY v.start_date ASC 
    LIMIT ?
    """
    cursor.execute(query, (today, limit)) 
    return cursor.fetchall()


#
# OPERACE AKTUALIZACE (UPDATE)
#
def update_request_status(conn: sqlite3.Connection, request_id: int, new_status: str) -> bool:
    cursor = conn.cursor()
    query = "UPDATE vacations SET status = ? WHERE id = ?"
    cursor.execute(query, (new_status, request_id))
    conn.commit() 
    return cursor.rowcount == 1

def update_vacation_request(
    conn: sqlite3.Connection,
    request_id: int,
    new_start_date: str,
    new_end_date: str,
    new_total_days: int
) -> bool:
    """Aktualizuje data existující žádosti o dovolenou v DB."""
    cursor = conn.cursor()
    query = """
    UPDATE vacations 
    SET start_date = ?, end_date = ?, total_days = ?
    WHERE id = ? AND status = 'Pending'
    """
    cursor.execute(query, (
        new_start_date,
        new_end_date,
        new_total_days,
        request_id
    ))
    conn.commit()
    return cursor.rowcount == 1