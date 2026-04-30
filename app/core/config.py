# app/core/config.py
import os
from dotenv import load_dotenv

# Načti .env soubor z kořenového adresáře aplikace
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(dotenv_path=ENV_PATH)

class Settings:
    #
    # ZABEZPEČENÍ
    #
    SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE_ME")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))
    
    # CSRF Protection
    CSRF_SECRET_KEY: str = os.getenv("CSRF_SECRET_KEY", SECRET_KEY)

    #
    # KONFIGURACE DATABÁZE A SLUŽEB
    #
    DEFAULT_VACATION_DAYS: int = 20
    DB_PATH: str = os.getenv("DB_PATH", "app/data/vacation.db")
    
    #
    # EMAIL KONFIGURACE
    #
    SMTP_EMAIL: str = os.getenv("SMTP_EMAIL", "dovolena.kovarna@gmail.com")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "akqgszsqwxchywcq")
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    
    #
    # APLIKACE
    #
    ENV: str = os.getenv("ENV", "development")
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")
    
settings = Settings()