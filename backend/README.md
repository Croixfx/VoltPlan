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
- `PUT /api/projects/{id}/scale` — Calibrate plan scale (two points as image ratios + real distance in mm)
- `GET /api/projects/{id}/scale` / `DELETE /api/projects/{id}/scale` — Read or clear the calibration
- `POST /api/projects/{id}/points` — Place catalog equipment (validated against rooms and the catalog's room rules)
- `PATCH /api/projects/{id}/points/{point_id}` — Move a point / change quantity (marks it manual)
- `DELETE /api/projects/{id}/points/{point_id}` — Delete a point. All three regenerate circuits, BOQ and cost, and return the full analysis.
  Manual points are kept when the analysis is re-run.
- `GET /api/projects/{id}/geometry` — Detected / corrected rooms and doors with the geometry-check results
- `POST|PATCH|DELETE /api/projects/{id}/rooms[/{room_id}]` — Add, rename, reshape or delete rooms (doors stay on their wall)
- `POST|PATCH|DELETE /api/projects/{id}/doors[/{door_id}]` — Add, move (wall + position), flip or delete doors
- `POST /api/projects/{id}/regenerate` — Rebuild equipment, circuits, BOQ and cost from the stored (corrected) rooms/doors. Runs the geometry checks first and returns 422 with the issue list if any fail; the previous design is left untouched.
- `POST /api/projects/{id}/analyze?reset_geometry=true` — Re-read the plan with AI. Without the flag this returns 409 if the project has manual room/door corrections, so they are never discarded silently.
- `GET /api/projects/{id}/calculations[?method=B2&ambient_c=30&grouped_circuits=1]` — Voltage drop per circuit, cable current-carrying capacity and maximum demand (preliminary; see `docs/CALCULATION_REVIEW.md`)
- `GET /api/ai/check` — Tests the configured AI provider (key accepted? model available?) without analysing a plan; never returns the key
- `GET /api/projects` — List projects (with search filter)
- `GET /api/projects/{id}` — Get project by ID
- `POST /api/projects/{id}/plan` — Upload architectural plan (PDF/PNG/JPG up to 25 MB)
- `GET /api/projects/{id}/plan/file` — Stream rendered display plan
- `POST /api/projects/{id}/analyze` — Run end-to-end vision and engineering pipeline
- `GET /api/projects/{id}/analysis` — Get latest structured analysis results
- `GET /api/projects/{id}/boq` — Get dynamic bill of quantities
- `GET /api/projects/{id}/cost-estimate` — Get cost estimate in RWF

---

## Equipment Catalog

All placeable equipment is declared once in `app/catalog/equipment.py` (`EquipmentSpec`): symbol, mounting,
default load, cable/protection, circuit class, cable run and BOQ lines with prices. The circuit engine, BOQ
engine and `GET /api/equipment` read from it.

To add equipment:

1. `register_equipment(EquipmentSpec(...))` in `app/catalog/equipment.py`.
2. To have it proposed automatically, add a rule in `get_additional_equipment` of the engineering standard
   (`app/engineering_rules/rs_iec_60364.py`) using `catalog_point(type_id, coord, notes)`.
3. Add the type to `ElectricalPointType` in `lib/shared/models/electrical_point.dart` and a symbol in
   `floor_plan_painter.dart`.

---

## Geometry checks and real-plan evaluation

Equipment is only generated from geometry that passes `app/services/geometry_validator.py`: rooms must have a closed,
non-degenerate boundary inside the plan, must not overlap (more than 3 % of the smaller room), doors must sit on a wall of
an existing room, and sizes must be plausible (checked in metres once the scale is calibrated). Errors stop generation and
are returned to the user; warnings are shown but do not block. Nothing is repaired automatically.

To measure how well VoltPlan reads real plans against an electrician's design, see `eval_plans/README.md`
(`python -m tools.evaluate_plans`).

---

## Deployment

The container image (`Dockerfile`) needs PostgreSQL (`DATABASE_URL`), a volume at `/app/uploads` and these variables:

| Variable | Purpose |
|---|---|
| `API_KEY` | Shared key; when set every route except `/api/health` requires the header `X-API-Key`. **Set it on any internet-facing instance.** With `APP_ENV=production` and a real AI provider the server refuses to start without it. |
| `APP_ENV` / `DEBUG` | `production` / `False` for a deployment |
| `AI_PROVIDER` | `mock` (demo data), `gemini` or `openai` (+ `GEMINI_API_KEY` / `OPENAI_API_KEY`) |
| `DATABASE_URL` | `postgres://` and `postgresql://` URLs from hosting platforms are accepted |

Step-by-step (Render blueprint in `render.yaml`, building the APK): see `../docs/DEPLOY.md`.
