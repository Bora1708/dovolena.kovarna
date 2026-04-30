# app/api/routers/employees.py

from urllib import response

from fastapi import APIRouter, Depends, Request, Form, HTTPException, status, Path
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi_csrf_protect import CsrfProtect
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
    payload: Dict[str, Any] = Depends(get_current_employee_payload),
    csrf_protect: CsrfProtect = Depends()
):
    user_email = payload['sub']
    user_data = user_repo.get_user_by_email(conn, user_email)

    if not user_data:
        return RedirectResponse(url="/logout", status_code=status.HTTP_302_FOUND)

    user_id = user_data['id']
    history = vacation_repo.get_employee_vacation_history(conn, user_id)

    tpl = request.app.state.templates

    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
    response = tpl.TemplateResponse("profile.html", {
        "request": request,
        "user": user_data,
        "history": history,
        "error": request.query_params.get('error'),
        "success": request.query_params.get('success'),
        "csrf_token": csrf_token
    })

    csrf_protect.set_csrf_cookie(signed_token, response)
    return response


#
# PODÁNÍ NOVÉ ŽÁDOSTI O DOVOLENOU (POST)
#
@router.post("/request_vacation", response_class=RedirectResponse)
async def submit_vacation_request(
    request: Request,
    csrf_protect: CsrfProtect = Depends(),
    conn: sqlite3.Connection = Depends(get_db_conn),
    payload: Dict[str, Any] = Depends(get_current_employee_payload), 
    start_date: str = Form(...),
    end_date: str = Form(default=None),
    vacation_type: str = Form(default="days"),
    vacation_hours: str = Form(default=None)
):
    await csrf_protect.validate_csrf(request)

    user_email = payload['sub']
    user_data = user_repo.get_user_by_email(conn, user_email)

    if not user_data:
        return RedirectResponse(url="/logout", status_code=status.HTTP_302_FOUND)

    user_id = user_data['id']
    remaining_days = user_data['remaining_days']
    employment_type = user_data.get('employment_type', 'full_time')

    try:
        # Pro half_time: end_date se nastavi na start_date, vacation_hours se prejedeme do total_days
        if employment_type == 'half_time':
            actual_end_date = start_date
            request_data = VacationRequest(start_date=start_date, end_date=actual_end_date, vacation_type=vacation_type)
            # vacation_hours bude pouzit v vacation_service
            vacation_service.submit_new_vacation_request(
                conn,
                user_id,
                request_data,
                remaining_days,
                employment_type,
                vacation_hours=float(vacation_hours) if vacation_hours else 8
            )
        else:
            # Full-time: standardni logika s od-do
            request_data = VacationRequest(start_date=start_date, end_date=end_date, vacation_type=vacation_type)
            vacation_service.submit_new_vacation_request(
                conn,
                user_id,
                request_data,
                remaining_days,
                employment_type
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
    csrf_protect: CsrfProtect = Depends(),
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

    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
    tpl = request.app.state.templates
    response = tpl.TemplateResponse("edit_vacation.html", {
        "request": request,
        "request_id": request_id,
        "request_data": req_data,
        "error": request.query_params.get('error'),
        "remaining_days": user_data['remaining_days'],
        "csrf_token": csrf_token
    })

    csrf_protect.set_csrf_cookie(signed_token, response)
    return response

#
# ZPRACOVÁNÍ ÚPRAV ŽÁDOSTI (POST)
#
@router.post("/edit/{request_id}", response_class=RedirectResponse)
async def edit_vacation_request_submit(
    request_id: int,
    request: Request,
    csrf_protect: CsrfProtect = Depends(),
    conn: sqlite3.Connection = Depends(get_db_conn),
    payload: Dict[str, Any] = Depends(get_current_employee_payload),
    start_date: str = Form(...),
    end_date: str = Form(default=None),
    vacation_type: str = Form(default="days"),
    vacation_hours: str = Form(default=None)
):
    await csrf_protect.validate_csrf(request)
    user_email = payload['sub']
    user_data = user_repo.get_user_by_email(conn, user_email)

    if not user_data:
        return RedirectResponse(url="/logout", status_code=status.HTTP_302_FOUND)

    user_id = user_data['id']
    remaining_days = user_data['remaining_days']
    employment_type = user_data.get('employment_type', 'full_time')

    try:
        # Pro half_time: end_date se nastavi na start_date, vacation_hours se prejedeme
        if employment_type == 'half_time':
            actual_end_date = start_date
            new_request_data = VacationRequest(start_date=start_date, end_date=actual_end_date, vacation_type=vacation_type)
            vacation_service.edit_vacation_request(
                conn,
                request_id,
                user_id,
                new_request_data,
                remaining_days,
                employment_type,
                vacation_hours=float(vacation_hours) if vacation_hours else 8
            )
        else:
            # Full-time: standardni logika s od-do
            new_request_data = VacationRequest(start_date=start_date, end_date=end_date, vacation_type=vacation_type)
            vacation_service.edit_vacation_request(
                conn,
                request_id,
                user_id,
                new_request_data,
                remaining_days,
                employment_type
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