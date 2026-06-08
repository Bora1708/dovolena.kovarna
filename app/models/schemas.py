# app/models/schemas.py

from pydantic import BaseModel, EmailStr, Field
from datetime import date
from typing import Optional


#
# AUTENTIZACE A UŽIVATELÉ
#

class UserBase(BaseModel):
    email: EmailStr
    is_admin: bool = False
    is_super_admin: bool = False
    remaining_days: Optional[float] = Field(None, ge=0)
    employment_type: str = "full_time"  # "full_time" nebo "half_time"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class EmployeeCreateByAdmin(BaseModel):
    email: EmailStr
    name: str
    remaining_days: Optional[float] = Field(None, ge=0)
    employment_type: str = "full_time"  # "full_time" nebo "half_time"


class UserInDB(UserBase):
    id: int
    hashed_password: str
    name: str
    profile_picture_path: Optional[str] = None
    is_admin: bool = False
    is_super_admin: bool = False
    remaining_days: float = Field(..., ge=0)
    employment_type: str = "full_time"
    
    class Config:
        from_attributes = True


class UserDisplay(BaseModel):
    id: int
    email: EmailStr
    is_admin: bool
    is_super_admin: bool
    remaining_days: float
    name: str
    profile_picture_path: Optional[str] = None
    employment_type: str = "full_time"
    
    class Config:
        from_attributes = True


#
# DOVOLENÁ
#

class VacationRequest(BaseModel):
    start_date: date
    end_date: date
    vacation_type: str = "days"  # "days", "hours", nebo "half_day"


class VacationDisplay(VacationRequest):
    id: int
    employee_id: int
    total_days: float
    status: str
    submitted_at: str
    vacation_type: str = "days"
    
    class Config:
        from_attributes = True

#
# KONFIGURACE OCHRANY (CSRF)
#
class CsrfSettings(BaseModel):
    secret_key: str
    token_location: str = "body"
    token_key: str = "csrf_token"
    cookie_samesite: str = "lax"
    cookie_secure: bool = False
