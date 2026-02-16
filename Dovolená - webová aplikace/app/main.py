# app/main.py

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.responses import RedirectResponse, HTMLResponse
from app.api.routers import auth as auth_router
from app.api.routers import employees as employees_router
from app.api.routers import admin as admin_router
from app.api.routers import super_admin as super_admin_router
from app.api.error_handlers import setup_error_handlers
import os
from app.core.security import decode_access_token
from app.utils.jinja2_filters import format_date_czech


#
# CENTRÁLNÍ OBSLUHA CHYB HTTP
#
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        return RedirectResponse(
            url="/login", 
            status_code=status.HTTP_302_FOUND
        )

    if not hasattr(request.app.state, 'templates'):
        return HTMLResponse(f"Chyba: {exc.status_code} - {exc.detail}", status_code=exc.status_code) 
        
    templates = request.app.state.templates
    
    is_admin = False
    is_super_admin = False
    
    token = request.cookies.get("access_token")
    if token:
        try:
            payload = decode_access_token(token)
            if payload.get('is_admin') == 1:
                is_admin = True
            if payload.get('is_super_admin') == 1:
                is_super_admin = True
        except:
            pass

    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": exc.status_code,
            "detail": exc.detail or "Nastala neočekávaná chyba serveru. Zkuste to prosím později.",
            "admin_url": "/admin",
            "employee_url": "/employee/profile",
            "super_admin_url": "/super_admin",
            "is_admin" : is_admin,
            "is_super_admin": is_super_admin
        },
        status_code=exc.status_code
    )


#
# TVORBA A KONFIGURACE APLIKACE
#
def create_app() -> FastAPI:
    app = FastAPI(title="Dovolená - aplikace")

    app.add_exception_handler(HTTPException, custom_http_exception_handler)
    setup_error_handlers(app)
    app.state.ENV = os.environ.get("ENV", "development")
    
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    
    app.state.templates = Jinja2Templates(directory="app/templates")
    app.state.templates.env.filters['date_cz'] = format_date_czech

    app.include_router(auth_router.router)
    app.include_router(super_admin_router.router, prefix="/super_admin")
    app.include_router(employees_router.router, prefix="/employee") 
    app.include_router(admin_router.router, prefix="/admin") 

    @app.get("/")
    async def root():
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    return app

# Start aplikace
app = create_app()