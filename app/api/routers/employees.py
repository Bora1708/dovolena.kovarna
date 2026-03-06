# app/api/routers/employees.py

from fastapi import APIRouter, Depends, Request, Form, HTTPException, status, Path
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
from typing import Dict, Any, Optional
from app.api.dependencies import get_db_conn, get_current_employee_payload
import app.repositories.user_repo as user_repo
import app.services.vacation_service as vacation_service
import app.repositories.vacation_repo as vacation_repo
from app.models.schemas import VacationRequest
from pydantic import ValidationError

router = APIRouter(tags=["Employee"])


#
# ZOBRAZENÍ PROFILU ZAMĚSTNANCE A HISTORIE
#
@router.get("/profile", response_class=HTMLResponse)
async def employee_profile_page(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db_conn),
    payload: Dict[str, Any] = Depends(get_current_employee_payload)
):
    user_email = payload['sub']
    user_data = user_repo.get_user_by_email(conn, user_email)

    if not user_data:
        return RedirectResponse(url="/logout", status_code=status.HTTP_302_FOUND)

    user_id = user_data['id']
    history = vacation_repo.get_employee_vacation_history(conn, user_id)

    tpl = request.app.state.templates
    return tpl.TemplateResponse("profile.html", {
        "request": request,
        "user": user_data,
        "history": history,
        "error": request.query_params.get('error'),
        "success": request.query_params.get('success'),
    })


#
# PODÁNÍ NOVÉ ŽÁDOSTI O DOVOLENOU (POST)
#
@router.post("/request_vacation", response_class=RedirectResponse)
async def submit_vacation_request(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db_conn),
    payload: Dict[str, Any] = Depends(get_current_employee_payload), 
    start_date: str = Form(...),
    end_date: str = Form(...)
):
    user_email = payload['sub']
    user_data = user_repo.get_user_by_email(conn, user_email)

    if not user_data:
        return RedirectResponse(url="/logout", status_code=status.HTTP_302_FOUND)

    user_id = user_data['id']
    remaining_days = user_data['remaining_days']

    try:
        request_data = VacationRequest(start_date=start_date, end_date=end_date)
        
        vacation_service.submit_new_vacation_request(
            conn,
            user_id,
            request_data,
            remaining_days
        )

        return RedirectResponse(
            url="/employee/profile?success=Žádost_byla_úspěšně_podána_a_čeká_na_schválení.",
            status_code=status.HTTP_303_SEE_OTHER
        )

    except ValidationError:
        return RedirectResponse(url="/employee/profile?error=Neplatný_formát_datumu_zadaný_v_žádosti.", status_code=status.HTTP_303_SEE_OTHER)

    except (HTTPException, ValueError) as e:
        error_message = str(getattr(e, 'detail', e)).replace(" ", "_")
        return RedirectResponse(url=f"/employee/profile?error={error_message}", status_code=status.HTTP_303_SEE_OTHER)

    except Exception:
        return RedirectResponse(url="/employee/profile?error=Neočekávaná_chyba_serveru_při_ukládání_žádosti.", status_code=status.HTTP_303_SEE_OTHER)


#
# ZOBRAZENÍ FORMULÁŘE PRO ÚPRAVU ŽÁDOSTI (GET)
#
@router.get("/edit/{request_id}", response_class=HTMLResponse)
async def edit_vacation_form(
    request: Request,
    request_id: int,
    conn: sqlite3.Connection = Depends(get_db_conn),
    payload: Dict[str, Any] = Depends(get_current_employee_payload)
):
    user_email = payload['sub']
    user_data = user_repo.get_user_by_email(conn, user_email)

    if not user_data:
        return RedirectResponse(url="/logout", status_code=status.HTTP_302_FOUND)

    user_id = user_data['id']

    req_data = vacation_repo.get_vacation_request_by_id(conn, request_id)

    if not req_data or req_data['employee_id'] != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Žádost nenalezena nebo nepatří tomuto uživateli.")

    if req_data['status'] != 'Pending':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Lze upravovat pouze čekající žádosti.")

    tpl = request.app.state.templates
    return tpl.TemplateResponse("edit_vacation.html", {
        "request": request,
        "request_id": request_id,
        "request_data": req_data,
        "error": request.query_params.get('error'),
        "remaining_days": user_data['remaining_days']
    })


#
# ZPRACOVÁNÍ ÚPRAV ŽÁDOSTI (POST)
#
@router.post("/edit/{request_id}", response_class=RedirectResponse)
async def edit_vacation_request_submit(
    request_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db_conn),
    payload: Dict[str, Any] = Depends(get_current_employee_payload),
    start_date: str = Form(...),
    end_date: str = Form(...)
):
    user_email = payload['sub']
    user_data = user_repo.get_user_by_email(conn, user_email)

    if not user_data:
        return RedirectResponse(url="/logout", status_code=status.HTTP_302_FOUND)

    user_id = user_data['id']
    remaining_days = user_data['remaining_days']

    try:
        new_request_data = VacationRequest(start_date=start_date, end_date=end_date)

        vacation_service.edit_vacation_request(
            conn,
            request_id,
            user_id,
            new_request_data,
            remaining_days
        )
        return RedirectResponse(
            url="/employee/profile?success=Žádost_byla_úspěšně_upravena.",
            status_code=status.HTTP_303_SEE_OTHER
        )

    except ValidationError:
        return RedirectResponse(url="/employee/profile?error=Neplatný_formát_datumu_zadaný_v_žádosti.", status_code=status.HTTP_303_SEE_OTHER)

    except ValueError as e:
        error_message = str(e).replace(" ", "_")
        return RedirectResponse(url=f"/employee/profile?error={error_message}", status_code=status.HTTP_303_SEE_OTHER)

    except Exception:
        return RedirectResponse(url="/employee/profile?error=Neočekávaná_chyba_serveru_při_úpravě_žádosti.", status_code=status.HTTP_303_SEE_OTHER)