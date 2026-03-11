
import sqlite3
import os
import smtplib
from typing import Dict, Any
from datetime import date, timedelta
from time import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader
from app.models.schemas import VacationRequest
import app.repositories.vacation_repo as vacation_repo
import app.repositories.user_repo as user_repo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "app", "templates")
BASE_URL = "https://dovolena.kovarna-prostejov.cz"

template_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

def render_email(template_name, **kwargs):
    try:
        template = template_env.get_template(template_name)
        return template.render(**kwargs)
    except Exception as e:
        print(f"!!! CHYBA: Šablona '{template_name}' nebyla nalezena v {TEMPLATES_DIR}!")
        return None

def send_email(prijemce, predmet, text_html):
    odesilatel = "dovolena.kovarna@gmail.com"
    heslo = "akqgszsqwxchywcq"
    msg = MIMEMultipart()
    msg['From'] = odesilatel
    msg['To'] = prijemce
    msg['Subject'] = predmet
    msg.attach(MIMEText(text_html, 'html'))
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(odesilatel, heslo)
            server.send_message(msg)
    except Exception as e:
        print(f"Email se nepodařilo odeslat: {e}")

def is_overlapping(start1: date, end1: date, start2: date, end2: date) -> bool:
    return start1 <= end2 and end1 >= start2

def calculate_working_days(start_date: date, end_date: date) -> int:
    if start_date > end_date:
        return 0
    working_days = 0
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() < 5:
            working_days += 1
        current_date += timedelta(days=1)
    return working_days

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
        if is_overlapping(request_data.start_date, request_data.end_date, req_start, req_end):
            raise ValueError("V daném období již existuje buď čekající, nebo schválená žádost o dovolenou.")
    submitted_at = str(int(time())) 
    start_date_str = request_data.start_date.isoformat()
    end_date_str = request_data.end_date.isoformat()
    try:
        user_updated = user_repo.update_user_remaining_days(conn, employee_id, -total_days)
        if not user_updated:
            raise ValueError("Chyba DB: Selhala aktualizace zůstatku dnů po odečtu.")
        new_request = vacation_repo.create_vacation_request(
            conn, employee_id, start_date_str, end_date_str, total_days, 'Pending', submitted_at
        )
        if not new_request:
            raise ValueError("Chyba při vytváření žádosti v databázi.")
        try:
            user = user_repo.get_user_by_id(conn, employee_id)
            start_cz = request_data.start_date.strftime('%d. %m. %Y')
            end_cz = request_data.end_date.strftime('%d. %m. %Y')
            telo_admin = render_email(
                "vacation_email.html",
                title="Nová žádost v systému",
                content=f"Zaměstnanec <b>{user['name']}</b> podal žádost o dovolenou.<br>"
                        f"<b>Termín:</b> {start_cz} až {end_cz}<br>"
                        f"<b>Počet dní:</b> {total_days}<br>"
                        f"<b>Zbývající dovolená:</b> {user['remaining_days']} dní.",
                link=f"{BASE_URL}/admin/requests"
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
                content=f"Dobrý den, vaše žádost o termín <b>{start_cz} - {end_cz}</b> byla zpracována.<br>"
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
        if is_overlapping(new_request_data.start_date, new_request_data.end_date, req_start, req_end):
            raise ValueError("Upravené období se překrývá s jinou aktivní žádostí.")
    try:
        start_date_str = new_request_data.start_date.isoformat()
        end_date_str = new_request_data.end_date.isoformat()
        vacation_updated = vacation_repo.update_vacation_request(
            conn, request_id, start_date_str, end_date_str, new_total_days
        )
        if not vacation_updated:
            raise ValueError("Chyba DB: Selhala aktualizace žádosti.")
        if days_difference != 0:
            user_updated = user_repo.update_user_remaining_days(conn, employee_id, -days_difference)
            if not user_updated:
                raise ValueError("Chyba DB: Selhala aktualizace zůstatku dnů uživatele.")
        conn.commit()
        try:
            user = user_repo.get_user_by_id(conn, employee_id)
            start_cz = new_request_data.start_date.strftime('%d. %m. %Y')
            end_cz = new_request_data.end_date.strftime('%d. %m. %Y')
            telo_admin = render_email(
                "vacation_email.html",
                title="Zaměstnanec upravil svou žádost",
                content=f"Zaměstnanec <b>{user['name']}</b> změnil parametry své žádosti.<br>"
                        f"<b>Nový termín:</b> {start_cz} až {end_cz}<br>"
                        f"<b>Nový počet dní:</b> {new_total_days}<br>"
                        f"<i>(Původně: {old_total_days} dní)</i><br>"
                        f"<b>Zbývající dovolená:</b> {user['remaining_days']} dní.",
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