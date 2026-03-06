# app/api/dependencies.py

import sqlite3
from typing import Iterator, Dict, Any, Optional
from app.models.db import open_conn
from app.core.security import decode_access_token
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2AuthorizationCodeBearer

#
# ZÁKLADNÍ ZÁVISLOSTI
#
def get_db_conn() -> Iterator[sqlite3.Connection]:
    with open_conn() as conn:
        conn.row_factory = sqlite3.Row
        yield conn

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


#
# ZÍSKÁNÍ PAYLOADU (Ověření tokenu a přihlášení)
#
async def get_current_user_payload(request: Request) -> Dict[str, Any]:
    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Přístup odepřen: Chybí autorizační token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        payload = decode_access_token(token)
        if 'sub' not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Neplatný token: Chybí e-mail."
            )
        return payload
        
    except ValueError as e: 
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Neplatný nebo vypršelý token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get("access_token")
    
    if not token:
        return None
    
    try:
        payload = decode_access_token(token)
        if 'sub' not in payload:
            return None 
        return payload
    
    except Exception:
        return None


#
# ZÁVISLOSTI PRO SPECIFICKÉ ROLE
#

async def get_current_employee_payload(
    payload: Dict[str, Any] = Depends(get_current_user_payload)
) -> Dict[str, Any]:
    if payload.get('is_admin') == 1 or payload.get('is_super_admin') == 1: 
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Přístup odepřen: Administrátor/Super Admin nemůže přistupovat k profilu zaměstnance."
        )
    return payload

async def get_current_admin_payload(
    payload: Dict[str, Any] = Depends(get_current_user_payload)
) -> Dict[str, Any]:
    if payload.get('is_admin') != 1 and payload.get('is_super_admin') != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Přístup odepřen: Vyžadována administrátorská práva."
        )
    return payload

async def get_current_super_admin_payload(
    payload: Dict[str, Any] = Depends(get_current_user_payload)
) -> Dict[str, Any]:
    if payload.get('is_super_admin') != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Přístup odepřen: Vyžadována práva Super Admina."
        )
    return payload