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
    remaining_days: Optional[int] = Field(None, ge=0)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class EmployeeCreateByAdmin(BaseModel):
    email: EmailStr
    name: str
    remaining_days: Optional[int] = Field(None, ge=0)


class UserInDB(UserBase):
    id: int
    hashed_password: str
    name: str
    profile_picture_path: Optional[str] = None
    is_admin: bool = False
    is_super_admin: bool = False
    remaining_days: int = Field(..., ge=0)
    
    class Config:
        from_attributes = True


class UserDisplay(BaseModel):
    id: int
    email: EmailStr
    is_admin: bool
    is_super_admin: bool
    remaining_days: int
    name: str
    profile_picture_path: Optional[str] = None
    
    class Config:
        from_attributes = True


#
# DOVOLENÁ
#

class VacationRequest(BaseModel):
    start_date: date
    end_date: date


class VacationDisplay(VacationRequest):
    id: int
    employee_id: int
    total_days: int
    status: str
    submitted_at: str
    
    class Config:
        from_attributes = True