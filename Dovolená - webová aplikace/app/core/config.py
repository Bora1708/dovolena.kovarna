# app/core/config.py

class Settings:
    #
    # ZABEZPEČENÍ
    #
    SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE_ME")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    #
    # KONFIGURACE DATABÁZE A SLUŽEB
    #
    DEFAULT_VACATION_DAYS: int = 20
    DB_PATH: str = os.getenv("DB_PATH", "app/data/vacation.db")
    
settings = Settings()