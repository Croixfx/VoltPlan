# VoltPlan FastAPI Backend

FastAPI backend service for **VoltPlan** — AI-assisted architectural floor plan analysis, deterministic electrical engineering calculations under **RS IEC 60364**, and dynamic Bill of Quantities (BOQ) generation in Rwandan Francs (RWF).

---

## Architecture Overview

```text
Architectural Plan (PDF / PNG / JPG)
        │
        ▼
Document Extraction (pypdfium2 / Pillow)
        │
        ▼
Vision AI Service (Gemini / OpenAI / Deterministic Mock)
        │
        ▼
Structured Building Observations (Rooms, Areas, Features)
        │
        ▼
Deterministic Electrical Engineering Engine (RS IEC 60364)
        │
        ▼
Circuit Schedule & Balancing Engine (Phase allocation, MCBs)
        │
        ▼
Dynamic BOQ & Rwandan Cost Engine (Materials, Labor 28%, Contingency 12%)
        │
        ▼
FastAPI REST Endpoints → Flutter Application
```

---

## Quickstart

### 1. Local Python Environment (SQLite)

```bash
cd backend
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env

# Run FastAPI server:
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive API documentation available at:
`http://localhost:8000/docs`

### 2. Docker Compose (PostgreSQL)

```bash
cd backend
docker compose up -d --build
```

---

## Testing

Run the automated test suite:

```bash
pytest -v
```

---

## API Endpoints

- `GET /api/health` — Service health and active AI provider
- `POST /api/projects` — Create project
- `GET /api/projects` — List projects (with search filter)
- `GET /api/projects/{id}` — Get project by ID
- `POST /api/projects/{id}/plan` — Upload architectural plan (PDF/PNG/JPG up to 25 MB)
- `GET /api/projects/{id}/plan/file` — Stream rendered display plan
- `POST /api/projects/{id}/analyze` — Run end-to-end vision and engineering pipeline
- `GET /api/projects/{id}/analysis` — Get latest structured analysis results
- `GET /api/projects/{id}/boq` — Get dynamic bill of quantities
- `GET /api/projects/{id}/cost-estimate` — Get cost estimate in RWF
