# app/api/routers/auth.py

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from starlette import status
import sqlite3
from app.api.dependencies import get_db_conn, get_current_user_optional
import app.services.user_service as user_service 
from app.core.security import create_access_token
from app.models.schemas import UserLogin
from app.core.config import settings

router = APIRouter(tags=["Auth"])


#
# ZOBRAZENÍ PŘIHLAŠOVACÍ STRÁNKY
#
@router.get("/login")
async def login_page(
    request: Request,
    payload: Optional[Dict[str, any]] = Depends(get_current_user_optional)
):
    tpl = request.app.state.templates
    
    if payload:
        # Přesměrování přihlášeného uživatele na správný dashboard
        is_super_admin = payload.get('is_super_admin', 0)
        is_admin = payload.get('is_admin', 0)
        
        if is_super_admin == 1:
            return RedirectResponse(url="/super_admin", status_code=status.HTTP_302_FOUND)
        elif is_admin == 1:
            return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
        else:
            return RedirectResponse(url="/employee/profile", status_code=status.HTTP_302_FOUND)
            
    return tpl.TemplateResponse("login.html", {"request": request, "error": None})


#
# ZPRACOVÁNÍ PŘIHLAŠOVACÍHO FORMULÁŘE
#
@router.post("/login")
async def login_submit(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db_conn),
    email: str = Form(..., alias="username"),
    password: str = Form(...),
):
    user_data = user_service.authenticate_user(
        conn, 
        UserLogin(email=email, password=password) 
    )

    if user_data is None:
        tpl = request.app.state.templates
        return tpl.TemplateResponse(
            "login.html",
            {"request": request, "error": "Neplatný e-mail nebo heslo."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    
    # Získání dat pro token
    user_id = user_data['id']
    is_super_admin = int(user_data.get('is_super_admin', 0))
    is_admin = int(user_data['is_admin'])
    
    # Vytvoření tokenu
    access_token = create_access_token(
        sub=user_data['email'],
        user_id=user_id,
        roles=["admin"] if is_admin == 1 else ["employee"], 
        is_admin=is_admin, 
        is_super_admin=is_super_admin
    )
    
    # Určení cílové URL po přihlášení
    if is_super_admin == 1:
        redirect_url = "/super_admin"
    elif is_admin == 1:
        redirect_url = "/admin"
    else:
        redirect_url = "/employee/profile"
        
    resp = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    
    # Nastavení cookie
    max_age_int = int(settings.ACCESS_TOKEN_EXPIRE_MINUTES) * 60
    
    resp.set_cookie(
        "access_token", 
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=request.app.state.ENV == "production",
        max_age=max_age_int,
        path="/",
    )
    return resp


#
# ODHLÁŠENÍ UŽIVATELE
#
@router.get("/logout")
async def logout(request: Request):
    resp = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie("access_token", path="/")
    return resp