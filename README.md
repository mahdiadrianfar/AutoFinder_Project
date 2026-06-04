# AutoIndex

AutoIndex is a full-stack vehicle data indexing and search platform. The project collects car listings using Selenium, stores and organizes data in PostgreSQL, exposes search APIs with FastAPI, and provides a desktop client built with PySide6 for searching and exploring vehicle information.

## Project structure

```
AutoIndex/
│
├── venv/                 # Python virtual environment (local, not in git)
│
├── client/               # PySide6 desktop application
│
├── server/
│   ├── api/              # FastAPI routes and app
│   ├── database/         # PostgreSQL models and connection
│   └── scraper/          # Selenium scrapers
│
├── docs/                 # Project documentation
│
├── .env                  # Environment variables (local, not in git)
├── .env.example          # Environment template for setup
├── .gitignore
├── requirements.txt
├── README.md
└── LICENSE
```

## Setup

### 1. Virtual environment

```bash
python -m venv venv
```

**Windows (PowerShell):**

```powershell
.\venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
source venv/bin/activate
```

### 2. Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment

Copy `.env.example` to `.env` and set your PostgreSQL URL and other values:

```bash
cp .env.example .env
```

### 4. Run components

**API server:**

```bash
uvicorn server.api.main:app --reload --host 127.0.0.1 --port 8000
```

**Desktop client:**

```bash
python -m client.main
```

## License

MIT — see [LICENSE](LICENSE).
