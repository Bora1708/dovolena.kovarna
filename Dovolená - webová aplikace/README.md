\# Systém pro Správu Dovolených

Webová aplikace pro správu žádostí o dovolenou pro zaměstnance, administrátory a super administrátory. Systém je postaven na stacku FastAPI a SQLite.


\## Klíčové Funkce

| Role | Oprávnění |

| Zaměstnanec | Podávání a úprava žádostí s kontrolou zůstatku dnů a překrývání termínů. Zobrazení vlastní historie. |

| Admin | Schvalování/zamítání žádostí (s automatickým navracením dnů). Tvorba a mazání Employee účtů. |

| Super Admin | Kompletní správa uživatelů a rolí (vytváření Adminů/Super Adminů, mazání Adminů). Kontrola proti smazání vlastního účtu. |


\# Příprava na spuštění


  ```bash

  pip install -r requirements.txt

  ```

\# Spuštění Serveru

  ```bash

  uvicorn app.main:app --reload

  ```

  Aplikace bude dostupná na adrese `http://127.0.0.1:8000/`.


\## Testovací Přihlašovací Údaje

Pro otestování funkcionality se můžete přihlásit pomocí následujících rolí:

| Role | E-mail | Heslo |

| Super Admin | `superadmin@example.com` | `test_password` |

| Admin | `admin@example.com` | `test_password` |

| Zaměstnanec | `employee@example.com` | `test_password` |

