# app/services/vacation_service.py

import sqlite3
from typing import Dict, Any
from datetime import date, timedelta
from app.models.schemas import VacationRequest
import app.repositories.vacation_repo as vacation_repo
import app.repositories.user_repo as user_repo
from time import time


#
# NÁSTROJNÉ FUNKCE (VALIDACE A VÝPOČTY)
#
def is_overlapping(start1: date, end1: date, start2: date, end2: date) -> bool:
    """Kontroluje, zda se dvě časová období překrývají."""
    return start1 <= end2 and end1 >= start2


def calculate_working_days(start_date: date, end_date: date) -> int:
    """Spočítá počet pracovních dnů v daném období."""
    if start_date > end_date:
        return 0

    working_days = 0
    current_date = start_date
    
    while current_date <= end_date:
        if current_date.weekday() < 5:
            working_days += 1
        current_date += timedelta(days=1)
        
    return working_days


#
# NOVÁ ŽÁDOST O DOVOLENOU
#
def submit_new_vacation_request(
    conn: sqlite3.Connection, 
    employee_id: int, 
    request_data: VacationRequest, 
    user_remaining_days: int
) -> Dict[str, Any]:

    if request_data.start_date > request_data.end_date:
        raise ValueError("Datum začátku nemůže být po datu konce dovolené.")

    total_days = calculate_working_days(request_data.start_date, request_data.end_date)
    
    if total_days == 0:
        raise ValueError("Vybrané období neobsahuje žádný pracovní den.")
        
    if total_days > user_remaining_days:
        raise ValueError(f"Nedostatečný zůstatek dní. Požadováno: {total_days}, Zbývá: {user_remaining_days}.")

    active_requests = vacation_repo.get_active_vacation_requests(conn, employee_id)

    for req in active_requests:
        req_start = date.fromisoformat(req['start_date'])
        req_end = date.fromisoformat(req['end_date'])
        
        if is_overlapping(
            request_data.start_date,
            request_data.end_date,
            req_start,
            req_end
        ):
            raise ValueError("V daném období již existuje buď čekající, nebo schválená žádost o dovolenou.")
    
    submitted_at = str(int(time())) 
    start_date_str = request_data.start_date.isoformat()
    end_date_str = request_data.end_date.isoformat()
    
    try:
        user_updated = user_repo.update_user_remaining_days(conn, employee_id, -total_days)
        
        if not user_updated:
            raise ValueError("Chyba DB: Selhala aktualizace zůstatku dnů po odečtu.")

        new_request = vacation_repo.create_vacation_request(
            conn, 
            employee_id, 
            start_date_str,
            end_date_str, 
            total_days,
            'Pending', 
            submitted_at
        )
        
        if not new_request:
            raise ValueError("Chyba při vytváření žádosti v databázi.")
            
        return new_request

    except ValueError as e:
        raise e 
        
    except Exception as e:
        conn.rollback() 
        print(f"KRITICKÁ TRANSACNÍ CHYBA PŘI PODÁNÍ: {e}") 
        raise ValueError("Neočekávaná DB chyba při podání žádosti.")


#
# SCHVALOVÁNÍ / ZAMÍTÁNÍ ŽÁDOSTÍ
#
def handle_vacation_approval(
    conn: sqlite3.Connection, 
    request_id: int, 
    new_status: str
) -> bool:
    request_data = vacation_repo.get_vacation_request_by_id(conn, request_id)
    
    if not request_data:
        raise ValueError("Žádost nenalezena.") 
        
    if request_data.get('status') != 'Pending':
        raise ValueError("Žádost již byla zpracována.") 
    
    user_id = request_data['employee_id']
    days_to_modify = request_data['total_days']
    
    try:
        if new_status == 'Rejected':
            user_updated = user_repo.update_user_remaining_days(conn, user_id, days_to_modify)
            
            if not user_updated:
                raise ValueError("Chyba DB: Selhala aktualizace zůstatku dnů po zamítnutí.")
        
        status_updated = vacation_repo.update_request_status(conn, request_id, new_status)
        
        if not status_updated:
            raise ValueError("Chyba DB: Selhala aktualizace statusu žádosti.")
            
        conn.commit()
        return True
    
    except ValueError as e:
        conn.rollback() 
        raise e 
        
    except Exception:
        conn.rollback()
        raise ValueError("Neočekávaná DB chyba během transakce schválení/zamítnutí.")


#
# ÚPRAVA EXISTUJÍCÍ ŽÁDOSTI
#
def edit_vacation_request(
    conn: sqlite3.Connection,
    request_id: int,
    employee_id: int,
    new_request_data: VacationRequest,
    user_remaining_days: int
) -> Dict[str, Any]:
    
    current_request = vacation_repo.get_vacation_request_by_id(conn, request_id)
    
    if not current_request:
        raise ValueError("Žádost k úpravě nenalezena.")
    if current_request['employee_id'] != employee_id:
        raise ValueError("Žádost nepatří tomuto zaměstnanci.")
    if current_request['status'] != 'Pending':
        raise ValueError(f"Žádost má status '{current_request['status']}' a nelze ji upravovat.")
        
    old_total_days = current_request['total_days']
    
    if new_request_data.start_date > new_request_data.end_date:
        raise ValueError("Datum začátku nemůže být po datu konce dovolené.")
        
    new_total_days = calculate_working_days(new_request_data.start_date, new_request_data.end_date)
    
    if new_total_days == 0:
        raise ValueError("Vybrané období neobsahuje žádný pracovní den.")
        
    days_difference = new_total_days - old_total_days
    
    if days_difference > 0 and days_difference > user_remaining_days:
        raise ValueError(f"Nedostatečný zůstatek dní. Změna vyžaduje dalších {days_difference} dní, zbývá jen {user_remaining_days}.")
        
    active_requests = vacation_repo.get_active_vacation_requests(conn, employee_id)

    for req in active_requests:
        if req['id'] == request_id:
            continue
            
        req_start = date.fromisoformat(req['start_date'])
        req_end = date.fromisoformat(req['end_date'])
        
        if is_overlapping(
            new_request_data.start_date,
            new_request_data.end_date,
            req_start,
            req_end
        ):
            raise ValueError("Upravené období se překrývá s jinou aktivní žádostí.")
    
    try:
        start_date_str = new_request_data.start_date.isoformat()
        end_date_str = new_request_data.end_date.isoformat()
        
        vacation_updated = vacation_repo.update_vacation_request(
            conn, 
            request_id,
            start_date_str,
            end_date_str,
            new_total_days
        )
        
        if not vacation_updated:
            raise ValueError("Chyba DB: Selhala aktualizace žádosti.")

        if days_difference != 0:
            days_to_change = -days_difference
            
            user_updated = user_repo.update_user_remaining_days(conn, employee_id, days_to_change)
            
            if not user_updated:
                raise ValueError("Chyba DB: Selhala aktualizace zůstatku dnů uživatele.")
        
        conn.commit()
        return vacation_repo.get_vacation_request_by_id(conn, request_id)

    except ValueError as e:
        conn.rollback() 
        raise e 
        
    except Exception:
        conn.rollback()
        raise ValueError("Neočekávaná chyba DB během editace žádosti.")