# app/api/routers/admin.py

from fastapi import APIRouter, Depends, Request, Form, HTTPException, status, Path
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
from typing import Dict, Any, Optional
from app.api.dependencies import get_db_conn, get_current_admin_payload
import app.repositories.user_repo as user_repo
import app.services.vacation_service as vacation_service
import app.repositories.vacation_repo as vacation_repo
from app.models.schemas import EmployeeCreateByAdmin
import app.services.user_service as user_service

router = APIRouter(tags=["Admin"])


#
# ZOBRAZENÍ ADMIN DASHBOARDU
#
@router.get("", response_class=HTMLResponse)
async def admin_dashboard_page(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db_conn),
    payload: Dict[str, Any] = Depends(get_current_admin_payload)
):
    admin_email = payload['sub']
    admin_data = user_repo.get_user_by_email(conn, admin_email)
    admin_name = admin_data.get('name', admin_email) if admin_data else admin_email
    employees = user_repo.get_all_employees(conn)

    is_super_admin = payload.get('is_super_admin', 0)
    if is_super_admin == 1:
        return RedirectResponse(url="/super_admin", status_code=status.HTTP_302_FOUND)

    upcoming_vacations = vacation_repo.get_upcoming_approved_vacations(conn, limit=10)
    pending_requests = vacation_repo.get_pending_requests(conn)

    tpl = request.app.state.templates
    return tpl.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "user_name": admin_name,
        "user_email": admin_email,
        "employees": employees,
        "upcoming_vacations": upcoming_vacations,
        "pending_requests": pending_requests,
        "error": None
    })


#
# TVORBA ZAMĚSTNANCE
#
@router.post("/create_employee", status_code=status.HTTP_303_SEE_OTHER)
async def create_employee_submit(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db_conn),
    payload: Dict[str, Any] = Depends(get_current_admin_payload),
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    remaining_days: Optional[int] = Form(None),
):
    try:
        employee_data = EmployeeCreateByAdmin(
            email=email,
            name=name,
            remaining_days=remaining_days
        )

        user_service.create_employee_by_admin(
            conn,
            employee_data=employee_data,
            raw_password=password
        )

        return RedirectResponse(
            url="/admin?success=Zaměstnanec_byl_úspěšně_vytvořen.",
            status_code=status.HTTP_303_SEE_OTHER
        )

    except ValueError as e:
        error_message = str(e).replace(" ", "_")
        return RedirectResponse(
            url=f"/admin?error={error_message}",
            status_code=status.HTTP_303_SEE_OTHER
        )

    except Exception:
        return RedirectResponse(
            url="/admin?error=Nepodařilo_se_vytvořit_zaměstnance_kvůli_systémové_chybě.",
            status_code=status.HTTP_303_SEE_OTHER
        )


#
# MAZÁNÍ UŽIVATELE
#
@router.post("/delete_user/{user_id}", status_code=status.HTTP_303_SEE_OTHER)
async def delete_user_submit(
    conn: sqlite3.Connection = Depends(get_db_conn),
    user_id: int = Path(..., gt=0),
    payload: Dict[str, Any] = Depends(get_current_admin_payload),
):
    user_to_delete = user_repo.get_user_by_id(conn, user_id)
    
    if not user_to_delete:
        return RedirectResponse(url="/admin?error=Uživatel_nebyl_nalezen.", status_code=status.HTTP_303_SEE_OTHER)
        
    if user_to_delete['id'] == payload.get('id'):
        return RedirectResponse(url="/admin?error=Nemůžete_smazat_sám_sebe.", status_code=status.HTTP_303_SEE_OTHER)
        
    # Admin nemůže mazat jiné Adminy/Super Adminy
    if user_to_delete['is_admin'] == 1 or user_to_delete['is_super_admin'] == 1:
        return RedirectResponse(url="/admin?error=Nemáte_oprávnění_mazat_administrátory.", status_code=status.HTTP_303_SEE_OTHER)
        
    deleted = user_repo.delete_user(conn, user_id)
    
    if deleted:
        return RedirectResponse(url="/admin?success=Uživatel_byl_úspěšně_smazán.", status_code=status.HTTP_303_SEE_OTHER)
    else:
        return RedirectResponse(url="/admin?error=Chyba_při_mazání_uživatele.", status_code=status.HTTP_303_SEE_OTHER)


#
# SCHVALOVÁNÍ/ZAMÍTÁNÍ ŽÁDOSTÍ O DOVOLENOU
#
@router.post("/process_request/{request_id}")
async def process_vacation_request(
    request_id: int,
    conn: sqlite3.Connection = Depends(get_db_conn),
    payload: Dict[str, Any] = Depends(get_current_admin_payload),
    action: str = Form(..., description="Akce: 'Approve' nebo 'Reject'")
):
    
    if action == "Approve":
        new_status = "Approved"
        action_verb = "schválena"
    elif action == "Reject":
        new_status = "Rejected"
        action_verb = "zamítnuta"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Neplatná akce.")

    try:
        updated = vacation_service.handle_vacation_approval(
            conn,
            request_id,
            new_status
        )

        if not updated:
            raise ValueError("Žádost k aktualizaci nenalezena.")

        return RedirectResponse(
            url=f"/admin?success=Žádost_byla_úspěšně_{action_verb}.",
            status_code=status.HTTP_303_SEE_OTHER
        )

    except ValueError as e:
        error_message = str(e).replace(" ", "_")
        return RedirectResponse(
            url=f"/admin?error={error_message}",
            status_code=status.HTTP_303_SEE_OTHER
        )

    except HTTPException:
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)