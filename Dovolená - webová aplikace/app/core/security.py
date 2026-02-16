# app/core/security.py

import time
import bcrypt
from jose import jwt, JWTError
from app.core.config import settings


#
# HASHOVÁNÍ A OVĚŘOVÁNÍ HESEL (BCRYPT)
#
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


#
# TVORBA A DEKÓDOVÁNÍ JWT TOKENU
#
def create_access_token(sub: str, user_id: int, roles: list[str], is_admin: int, is_super_admin: int) -> str:
    exp = int(time.time()) + 60 * settings.ACCESS_TOKEN_EXPIRE_MINUTES
    
    payload = {
        "sub": sub, 
        "id": user_id, 
        "roles": roles, 
        "exp": exp, 
        "is_admin": is_admin, 
        "is_super_admin": is_super_admin
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM) 
    return token

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError: 
        raise ValueError("Neplatný nebo vypršelý token")