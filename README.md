# AI-Based Smart Trading Journal (Flask + SQLite + Chart.js + AI Analytics)

A modern, dark TradingView-style trading journal where you can record trades, visualize performance, and get simple AI-powered insights.

## Tech stack
- **Backend**: Python + Flask
- **Frontend**: HTML (Jinja templates) + Bootstrap + vanilla JS
- **Database**: SQLite
- **Charts**: Chart.js
- **AI/Analytics**: pandas + numpy + scikit-learn (lightweight insights)

## Features (current)
- Signup / Login / Logout (secure password hashing)
- Dashboard with KPIs + equity curve chart
- Trades CRUD (add/edit/delete), filters, CSV export
- AI Insights page (rule-based + optional ML factors when enough trades exist)
- Demo seed data

## Run locally (Windows PowerShell)
Open PowerShell in this folder.

### 1) Create & activate a virtual environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3) Initialize the database
```powershell
$env:FLASK_APP = "app.py"
flask init-db
```

### 4) Seed demo data (optional but recommended)
```powershell
flask seed
```

Demo credentials:
- **username**: `demo`
- **password**: `demo1234`

### 5) Start the server
```powershell
flask run
```

Then open: `http://127.0.0.1:5000`

## Notes
- The SQLite database file is created in this folder as `trading_journal.sqlite3`.
- For production, set a strong secret key:
  - `setx SECRET_KEY "your-long-random-secret"`

## Next steps you can extend
- Add daily notes page
- Add more charts (monthly performance, win/loss pie, strategy win rate)
- Add risk management warnings directly on the dashboard
- Add profile settings (risk preferences, session times)
