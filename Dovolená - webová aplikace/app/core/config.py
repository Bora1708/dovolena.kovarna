# app/core/config.py

class Settings:
    #
    # ZABEZPEČENÍ
    #
    SECRET_KEY: str = "CHANGE_ME"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    #
    # KONFIGURACE DATABÁZE A SLUŽEB
    #
    DEFAULT_VACATION_DAYS: int = 20
    DB_PATH: str = "app/data/vacation.db"
    
settings = Settings()