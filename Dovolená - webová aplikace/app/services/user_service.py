# app/services/user_service.py

import sqlite3
from typing import Optional, Dict, Any
from app.models.schemas import UserLogin, EmployeeCreateByAdmin
import app.repositories.user_repo as user_repo
from app.core.security import verify_password, hash_password
from fastapi import HTTPException, status
from app.core.config import settings


#
# AUTENTIZACE UŽIVATELE
#
def authenticate_user(conn: sqlite3.Connection, form_data: UserLogin) -> Optional[Dict[str, Any]]:
    user_data = user_repo.get_user_by_email(conn, form_data.email)

    if not user_data:
        return None
    
    if not verify_password(form_data.password, user_data['hashed_password']):
        return None
        
    return user_data

#
# TVORBA ZAMĚSTNANCE ADMINEM
#
def create_employee_by_admin(
    conn: sqlite3.Connection, 
    employee_data: EmployeeCreateByAdmin,
    raw_password: str
) -> Optional[Dict[str, Any]]:
    
    if user_repo.get_user_by_email(conn, employee_data.email):
        raise ValueError("Uživatel s tímto emailem již existuje.")

    hashed_password = hash_password(raw_password)

    new_user = user_repo.create_user(
        conn, 
        employee_data, 
        hashed_password, 
        is_admin=False,
    )
    return new_user

#
# RESET ROČNÍCH DNŮ DOVOLENÉ
#
def reset_annual_vacation_days(conn: sqlite3.Connection, employee_id: int) -> bool:
    user_data = user_repo.get_user_by_id(conn, employee_id)
    
    if not user_data:
        return False
        
    current_days = user_data['remaining_days']
    default_days = settings.DEFAULT_VACATION_DAYS
    days_to_add = default_days - current_days
    return user_repo.update_user_remaining_days(conn, employee_id, days_to_add)