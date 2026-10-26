# Food Donation and Request Management System

A simple Software Engineering PBL application with two modules:
1. Food Donation Management
2. Donation Discovery and Request Management

## Technology
- Frontend: HTML, CSS, vanilla JavaScript
- Backend: Python Flask
- Database: SQLite
- Tests: Python `unittest`

## Requirements
- Python 3.10 or later recommended

## Run on Windows
Open a terminal in this project folder:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

If PowerShell blocks activation, use Command Prompt and run:
```bat
.venv\Scripts\activate.bat
```

Then open http://127.0.0.1:5000

## Run on Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

## Run tests
With the virtual environment activated:
```bash
python -m unittest discover -s tests -v
```

The test suite uses a temporary SQLite database so it does not alter the normal application database.

## Database
The application creates `instance/food_donation.db` on first startup. To reset the demonstration data, stop the server and delete that database file. It will be recreated on the next startup.

## Important demo limitation
This is a college lab prototype. It does not include login, role-based authorization, real notifications, or production security hardening. Use sample contact details for demonstration. Do not expose the development server publicly.
