# vacation_service.py

import sqlite3
import os
import smtplib
import logging
from typing import Dict, Any
from datetime import date, datetime, timedelta
from time import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader
from app.models.schemas import VacationRequest
from app.core.config import settings
import app.repositories.vacation_repo as vacation_repo
import app.repositories.user_repo as user_repo

# Logging setup
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
BASE_URL = settings.BASE_URL

template_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

def render_email(template_name, **kwargs):
    try:
        template = template_env.get_template(template_name)
        return template.render(**kwargs)
    except Exception as e:
        logger.error(f"Šablona '{template_name}' nebyla nalezena v {TEMPLATES_DIR}: {e}")
        return None

def send_email(prijemce, predmet, text_html):
    """
    Odeslá email přes SMTP.
    
    Vyžaduje tyto env proměnné v .env:
    - SMTP_EMAIL: Email odesílatele
    - SMTP_PASSWORD: Heslo (app-specific password pro Gmail)
    - SMTP_SERVER: SMTP server (default: smtp.gmail.com)
    - SMTP_PORT: Port (default: 587)
    """
    if not settings.SMTP_EMAIL or not settings.SMTP_PASSWORD:
        logger.error("SMTP credentials nejsou nastaveny v .env souboru")
        return False
    
    msg = MIMEMultipart()
    msg['From'] = settings.SMTP_EMAIL
    msg['To'] = prijemce
    msg['Subject'] = predmet
    msg.attach(MIMEText(text_html, 'html'))
    
    try:
        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_EMAIL, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(f"Email úspěšně odeslán na {prijemce}")
        return True
    except Exception as e:
        logger.error(f"Email se nepodařilo odeslat na {prijemce}: {e}")
        return False

def is_overlapping(start1: date, end1: date, start2: date, end2: date) -> bool:
    return start1 <= end2 and end1 >= start2

def validate_vacation_hours(vacation_hours: float) -> None:
    """Validace počtu hodin pro half-time zaměstnance."""
    if vacation_hours < 1 or vacation_hours > 8:
        raise ValueError("Počet hodin musí být mezi 1 a 8")
    if (vacation_hours * 2) % 1 != 0:  # Check if it's a multiple of 0.5
        raise ValueError("Počet hodin musí být násobek 0.5")

def validate_vacation_dates(start_date: date, end_date: date) -> None:
    """Validace datumů - nelze v minulosti a start <= end."""
    if start_date < date.today():
        raise ValueError("Nelze podávat žádost o dovolenou v minulosti")
    if start_date > end_date:
        raise ValueError("Datum začátku nemůže být po datu konce dovolené.")


def validate_half_day_range(start_date: date, end_date: date, vacation_type: str) -> None:
    """Půlden lze zadat pouze na jeden den."""
    if vacation_type == "half_day" and start_date != end_date:
        raise ValueError("Půl dne lze zadat pouze na jeden den.")


def calculate_working_days(start_date: date, end_date: date) -> int:
    """Počítá všechny dny (včetně víkendů) v daném období."""
    if start_date > end_date:
        return 0
    working_days = 0
    current_date = start_date
    while current_date <= end_date:
        working_days += 1
        current_date += timedelta(days=1)
    return working_days

def calculate_vacation_units(
    start_date: date, 
    end_date: date, 
    employment_type: str,
    vacation_type: str,
    vacation_hours: float = None
) -> float:
    """
    Vypočítá počet jednotek dovolené podle typu úvazku a typu dovolené.
    
    Returns:
        - full_time + 'days': počet kalendářních dní (celá čísla, včetně víkendů)
        - full_time + 'half_day': počet kalendářních dní - 0.5 (poslední den je půl dne)
        - half_time + 'hours': vrátí vacation_hours přímo (pokud zadáno) nebo počet kalendářních dní × 4
    """
    if start_date > end_date:
        return 0
    
    # Pro half-time s konkretnidm počtem hodin
    if employment_type == "half_time" and vacation_type == "hours" and vacation_hours is not None:
        # Vrátit přímo zadaný počet hodin
        return float(vacation_hours)
    
    working_days = calculate_working_days(start_date, end_date)
    
    if employment_type == "half_time" and vacation_type == "hours":
        # Fallback: 1 pracovní den = 4 hodiny
        return working_days * 4
    elif employment_type == "full_time" and vacation_type == "half_day":
        # Plný úvazek s půl denní dovolenou: platí pouze pro právě jeden den.
        return 0.5 if working_days > 0 else 0
    else:
        # Standardní: "days" nebo "full_time" s "days"
        return float(working_days)

def submit_new_vacation_request(
    conn: sqlite3.Connection, 
    employee_id: int, 
    request_data: VacationRequest, 
    user_remaining_days: float,
    employment_type: str,
    vacation_hours: float = None
) -> Dict[str, Any]:
    """
    Podá novou žádost o dovolenou s podporou half-time úvazku a půl denní dovolené.
    
    Args:
        employment_type: 'full_time' nebo 'half_time' (určuje jednotky)
        vacation_hours: počet hodin (jen pro half-time)
    """
    # Validace datumů
    validate_vacation_dates(request_data.start_date, request_data.end_date)
    validate_half_day_range(request_data.start_date, request_data.end_date, request_data.vacation_type)
    
    # Validace hodin pro half-time
    if employment_type == "half_time" and vacation_hours:
        validate_vacation_hours(float(vacation_hours))
    
    # Výpočet jednotek podle typu úvazku a typu dovolené
    total_units = calculate_vacation_units(
        request_data.start_date, 
        request_data.end_date, 
        employment_type,
        request_data.vacation_type,
        vacation_hours=vacation_hours
    )
    
    if total_units == 0:
        raise ValueError("Vybrané období neobsahuje žádný pracovní den.")
    
    if total_units > user_remaining_days:
        unit_name = "hodin" if employment_type == "half_time" else "dní"
        raise ValueError(f"Nedostatečný zůstatek. Požadováno: {total_units} {unit_name}, Zbývá: {user_remaining_days} {unit_name}.")
    
    active_requests = vacation_repo.get_active_vacation_requests(conn, employee_id)
    for req in active_requests:
        req_start = date.fromisoformat(req['start_date'])
        req_end = date.fromisoformat(req['end_date'])
        if is_overlapping(request_data.start_date, request_data.end_date, req_start, req_end):
            raise ValueError("V daném období již existuje buď čekající, nebo schválená žádost o dovolenou.")
    
    submitted_at = str(int(time())) 
    start_date_str = request_data.start_date.isoformat()
    end_date_str = request_data.end_date.isoformat()
    
    try:
        user_updated = user_repo.update_user_remaining_days(conn, employee_id, -total_units)
        if not user_updated:
            raise ValueError("Chyba DB: Selhala aktualizace zůstatku dnů po odečtu.")
        
        new_request = vacation_repo.create_vacation_request(
            conn, employee_id, start_date_str, end_date_str, total_units, 'Pending', submitted_at, request_data.vacation_type
        )
        if not new_request:
            raise ValueError("Chyba při vytváření žádosti v databázi.")
        
        try:
            user = user_repo.get_user_by_id(conn, employee_id)
            start_cz = request_data.start_date.strftime('%d. %m. %Y')
            end_cz = request_data.end_date.strftime('%d. %m. %Y')
            unit_name = "hodin" if employment_type == "half_time" else "dní"
            vacation_type_cz = "hodin" if request_data.vacation_type == "hours" else ("půl dne" if request_data.vacation_type == "half_day" else "dní")
            
            # Pro half-time s jedním dnem zobrazit jen ten den
            if employment_type == "half_time":
                date_display = f"{start_cz}"
            else:
                date_display = f"{start_cz} až {end_cz}"
            
            telo_admin = render_email(
                "vacation_email.html",
                title="Nová žádost v systému",
                content=f"Zaměstnanec <b>{user['name']}</b> podal žádost o dovolenou.<br>"
                        f"<b>Termín:</b> {date_display}<br>"
                        f"<b>Počet:</b> {total_units} {vacation_type_cz}<br>"
                        f"<b>Zbývající dovolená:</b> {user['remaining_days']} {unit_name}.",
                link=f"{BASE_URL}/admin"
            )
            send_email("funmancz10@gmail.com", f"Nová žádost o dovolenou: {user['name']}", telo_admin)
        except:
            pass
        return new_request
    except ValueError as e:
        raise e
    except Exception as e:
        conn.rollback() 
        print(f"KRITICKÁ TRANSACNÍ CHYBA PŘI PODÁNÍ: {e}") 
        raise ValueError("Neočekávaná DB chyba při podání žádosti.")

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
        try:
            user = user_repo.get_user_by_id(conn, user_id)
            stav_cz = "SCHVÁLENA" if new_status == 'Approved' else "ZAMÍTNUTA"
            start_cz = date.fromisoformat(request_data['start_date']).strftime('%d. %m. %Y')
            end_cz = date.fromisoformat(request_data['end_date']).strftime('%d. %m. %Y')
            telo_user = render_email(
                "vacation_email.html",
                title=f"Vaše žádost byla {stav_cz}",
                content=f"Dobrý den, vaše žádost o termín <b>{start_cz} - {end_cz}</b> byla {stav_cz.lower()}.<br>"
                        f"<b>Aktuální zůstatek vaší dovolené:</b> {user['remaining_days']} dní.",
                link=f"{BASE_URL}/employee/profile"
            )
            send_email(user['email'], f"Rozhodnutí o dovolené: {stav_cz}", telo_user)
        except:
            pass
        return True
    except ValueError as e:
        conn.rollback() 
        raise e 
    except Exception:
        conn.rollback()
        raise ValueError("Neočekávaná DB chyba během transakce schválení/zamítnutí.")

def edit_vacation_request(
    conn: sqlite3.Connection,
    request_id: int,
    employee_id: int,
    new_request_data: VacationRequest,
    user_remaining_days: float,
    employment_type: str,
    vacation_hours: float = None
) -> Dict[str, Any]:
    """
    Upraví existující žádost o dovolenou.
    """
    current_request = vacation_repo.get_vacation_request_by_id(conn, request_id)
    if not current_request:
        raise ValueError("Žádost k úpravě nenalezena.")
    if current_request['employee_id'] != employee_id:
        raise ValueError("Žádost nepatří tomuto zaměstnanci.")
    if current_request['status'] != 'Pending':
        raise ValueError(f"Žádost má status '{current_request['status']}' a nelze ji upravovat.")
    
    old_total_units = current_request['total_days']
    
    # Validace datumů
    validate_vacation_dates(new_request_data.start_date, new_request_data.end_date)
    validate_half_day_range(new_request_data.start_date, new_request_data.end_date, new_request_data.vacation_type)
    
    # Validace hodin pro half-time
    if employment_type == "half_time" and vacation_hours:
        validate_vacation_hours(float(vacation_hours))
    
    new_total_units = calculate_vacation_units(
        new_request_data.start_date, 
        new_request_data.end_date, 
        employment_type,
        new_request_data.vacation_type,
        vacation_hours=vacation_hours
    )
    
    if new_total_units == 0:
        raise ValueError("Vybrané období neobsahuje žádný pracovní den.")
    
    units_difference = new_total_units - old_total_units
    if units_difference > 0 and units_difference > user_remaining_days:
        unit_name = "hodin" if employment_type == "half_time" else "dní"
        raise ValueError(f"Nedostatečný zůstatek. Změna vyžaduje dalších {units_difference} {unit_name}, zbývá jen {user_remaining_days} {unit_name}.")
    
    active_requests = vacation_repo.get_active_vacation_requests(conn, employee_id)
    for req in active_requests:
        if req['id'] == request_id:
            continue
        req_start = date.fromisoformat(req['start_date'])
        req_end = date.fromisoformat(req['end_date'])
        if is_overlapping(new_request_data.start_date, new_request_data.end_date, req_start, req_end):
            raise ValueError("Upravené období se překrývá s jinou aktivní žádostí.")
    
    try:
        start_date_str = new_request_data.start_date.isoformat()
        end_date_str = new_request_data.end_date.isoformat()
        vacation_updated = vacation_repo.update_vacation_request(
            conn, request_id, start_date_str, end_date_str, new_total_units, new_request_data.vacation_type
        )
        if not vacation_updated:
            raise ValueError("Chyba DB: Selhala aktualizace žádosti.")
        
        if units_difference != 0:
            user_updated = user_repo.update_user_remaining_days(conn, employee_id, -units_difference)
            if not user_updated:
                raise ValueError("Chyba DB: Selhala aktualizace zůstatku dnů uživatele.")
        
        conn.commit()
        try:
            user = user_repo.get_user_by_id(conn, employee_id)
            start_cz = new_request_data.start_date.strftime('%d. %m. %Y')
            end_cz = new_request_data.end_date.strftime('%d. %m. %Y')
            unit_name = "hodin" if employment_type == "half_time" else "dní"
            vacation_type_cz = "hodin" if new_request_data.vacation_type == "hours" else ("půl dne" if new_request_data.vacation_type == "half_day" else "dní")
            
            # Pro half-time s jedním dnem zobrazit jen ten den
            if employment_type == "half_time":
                date_display = f"{start_cz}"
            else:
                date_display = f"{start_cz} až {end_cz}"
            
            telo_admin = render_email(
                "vacation_email.html",
                title="Zaměstnanec upravil svou žádost",
                content=f"Zaměstnanec <b>{user['name']}</b> změnil parametry své žádosti.<br>"
                        f"<b>Nový termín:</b> {date_display}<br>"
                        f"<b>Nový počet:</b> {new_total_units} {vacation_type_cz}<br>"
                        f"<i>(Původně: {old_total_units} {vacation_type_cz})</i><br>"
                        f"<b>Zbývající dovolená:</b> {user['remaining_days']} {unit_name}.",
                link=f"{BASE_URL}/admin/requests"
            )
            send_email("funmancz10@gmail.com", f"ÚPRAVA žádosti o dovolenou: {user['name']}", telo_admin)
        except:
            pass
        return vacation_repo.get_vacation_request_by_id(conn, request_id)
    except ValueError as e:
        conn.rollback() 
        raise e 
    except Exception:
        conn.rollback()
        raise ValueError("Neočekávaná chyba DB během editace žádosti.")