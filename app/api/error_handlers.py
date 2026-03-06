# app/api/error_handlers.py

from fastapi import FastAPI, Request
from starlette.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException


def setup_error_handlers(app: FastAPI):

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        tpl: Jinja2Templates = request.app.state.templates
        
        status_code = exc.status_code
        detail = exc.detail
        
        if status_code == 404 and detail == "Not Found":
            detail = "Požadovaná stránka nebyla nalezena."
        elif status_code == 401:
            detail = "Pro přístup k této stránce se musíte přihlásit."
            
        return tpl.TemplateResponse(
            "error.html",
            {
                "request": request, 
                "status_code": status_code, 
                "detail": detail
            },
            status_code=status_code
        )