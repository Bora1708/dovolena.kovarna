# app/utils/jinja2_filters.py

from datetime import datetime


def format_date_czech(date_str: str) -> str:
    if not date_str:
        return ""
        
    try:
        dt_obj = datetime.strptime(date_str, '%Y-%m-%d')
        
        return dt_obj.strftime('%d. %m. %Y')
        
    except ValueError:
        return date_str