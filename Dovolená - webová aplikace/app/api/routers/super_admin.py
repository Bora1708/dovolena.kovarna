# app/api/routers/super_admin.py

from fastapi import APIRouter, Depends, Request, Form, status, Path
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
from typing import Dict, Any, Optional
from app.api.dependencies import get_db_conn, get_current_super_admin_payload
import app.repositories.user_repo as user_repo
from pydantic import ValidationError
from app.models.schemas import EmployeeCreateByAdmin
from app.core.security import hash_password

router = APIRouter(tags=["Super Admin"])


#
# ZOBRAZENÍ SUPER ADMIN DASHBOARDU
#
@router.get("", response_class=HTMLResponse)
async def super_admin_dashboard_page(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db_conn),
    payload: Dict[str, Any] = Depends(get_current_super_admin_payload)
):
    admin_email = payload['sub']
    admin_data = user_repo.get_user_by_email(conn, admin_email)
    admin_name = admin_data.get('name', admin_email) if admin_data else admin_email
    
    all_users = user_repo.get_all_users_for_admin_management(conn)
    
    admin_days = admin_data.get('remaining_days', 0) if admin_data else 0

    tpl = request.app.state.templates
    return tpl.TemplateResponse("super_admin_dashboard.html", {
        "request": request,
        "user_name": admin_name,
        "admin_email": admin_email,
        "remaining_days": admin_days,
        "users": all_users,
        "payload": payload,
        "error": request.query_params.get("error"),
        "success": request.query_params.get("success")
    })


#
# VYTVOŘENÍ NOVÉHO UŽIVATELE S ROLÍ
#
@router.post("/create_user_with_role", status_code=status.HTTP_303_SEE_OTHER)
async def create_new_user_with_role_submit(
    conn: sqlite3.Connection = Depends(get_db_conn),
    payload: Dict[str, Any] = Depends(get_current_super_admin_payload),
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    remaining_days: Optional[int] = Form(None),
    role_choice: int = Form(1) # 1=Employee, 2=Admin, 3=Super Admin
):
    try:
        user_data = EmployeeCreateByAdmin(
            name=name,
            email=email,
            password=password,
            remaining_days=remaining_days if remaining_days is not None else 20
        )
    except ValidationError as e:
        error_message = f"Chyba validace dat: {e}"
        return RedirectResponse(url=f"/super_admin?error={error_message.replace(' ', '_')}", status_code=status.HTTP_303_SEE_OTHER)
    
    if user_repo.get_user_by_email(conn, user_data.email):
        return RedirectResponse(url="/super_admin?error=Uživatel_s_tímto_emailem_již_existuje.", status_code=status.HTTP_303_SEE_OTHER)

    is_admin = role_choice >= 2
    is_super_admin = role_choice >= 3
    if is_super_admin:
        is_admin = False 

    hashed_password = hash_password(password)

    try:
        new_user = user_repo.create_user(
            conn, 
            user_data, 
            hashed_password, 
            is_admin=is_admin, 
            is_super_admin=is_super_admin
        )
        if new_user:
            return RedirectResponse(url="/super_admin?success=Uživatel_byl_úspěšně_vytvořen.", status_code=status.HTTP_303_SEE_OTHER)
        else:
            raise Exception("Nepodařilo se uložit uživatele do databáze.")

    except Exception:
        return RedirectResponse(url="/super_admin?error=Systémová_chyba_při_vytváření_uživatele.", status_code=status.HTTP_303_SEE_OTHER)


#
# AKTUALIZACE ÚROVNĚ ROLE
#
@router.post("/update_role/{user_id}", status_code=status.HTTP_303_SEE_OTHER)
async def update_user_role_submit(
    request: Request,
    user_id: int,
    conn: sqlite3.Connection = Depends(get_db_conn),
    payload: Dict[str, Any] = Depends(get_current_super_admin_payload),
    role_choice: int = Form(..., description="Požadovaná role: 1, 2 nebo 3") 
):
    
    is_admin = role_choice >= 2
    is_super_admin = role_choice >= 3
    
    try:
        current_user_id = payload.get('id')

        if user_id == current_user_id and not is_super_admin:
            raise ValueError("Nelze si odebrat vlastní práva Super Admina.")

        updated = user_repo.update_user_roles(conn, user_id, is_admin, is_super_admin) 
        
        if updated:
            response = RedirectResponse(url="/super_admin?success=Úroveň_role_úspěšně_aktualizována.", 
                                        status_code=status.HTTP_303_SEE_OTHER)
        else:
            response = RedirectResponse(url="/super_admin?error=Uživatel_nebyl_nalezen_nebo_role_nebyla_změněna.", 
                                        status_code=status.HTTP_303_SEE_OTHER)
            
    except ValueError as e:
        error_message = str(e).replace(" ", "_")
        response = RedirectResponse(url=f"/super_admin?error={error_message}", 
                                    status_code=status.HTTP_303_SEE_OTHER)
    except Exception:
        response = RedirectResponse(url="/super_admin?error=Systémová_chyba_při_změně_role.", 
                                    status_code=status.HTTP_303_SEE_OTHER)
        
    return response


#
# MAZÁNÍ UŽIVATELE
#
@router.post("/delete_user/{user_id}", status_code=status.HTTP_303_SEE_OTHER)
async def delete_user_by_super_admin(
    conn: sqlite3.Connection = Depends(get_db_conn),
    user_id: int = Path(..., gt=0),
    payload: Dict[str, Any] = Depends(get_current_super_admin_payload),
):
    if user_id == payload.get('id'):
        return RedirectResponse(url="/super_admin?error=Nemůžete_smazat_sám_sebe.", status_code=status.HTTP_303_SEE_OTHER)
    
    deleted = user_repo.delete_user(conn, user_id)
    if deleted:
        return RedirectResponse(url="/super_admin?success=Uživatel_byl_úspěšně_smazán.", status_code=status.HTTP_303_SEE_OTHER)
    else:
        return RedirectResponse(url="/super_admin?error=Chyba_při_mazání_uživatele.", status_code=status.HTTP_303_SEE_OTHER)