# 🚦 AI-Powered Traffic Violation Detection System

A production-ready, full-stack system that automatically analyzes traffic surveillance images, detects vehicles and road users, identifies violations, extracts license plates, generates annotated evidence, and provides a real-time analytics dashboard.

---

## 🏗 Architecture Overview

```
┌─────────────────┐     ┌─────────────────────────────────────────┐     ┌──────────────────┐
│                 │     │           FastAPI Backend                │     │                  │
│  React Frontend │────▶│  ┌──────────┐ ┌───────────┐ ┌───────┐  │────▶│   PostgreSQL DB   │
│  (Dashboard,    │     │  │ YOLOv8   │ │ EasyOCR   │ │Eviden-│  │     │   (Violations,    │
│   Upload,       │◀────│  │ Detector │ │ PaddleOCR │ │ce Gen │  │◀────│    Cameras,       │
│   Violations,   │     │  └──────────┘ └───────────┘ └───────┘  │     │    Vehicles)      │
│   Reports)      │     │  ┌─────────────────────────────────────┐│     │                  │
│                 │     │  │ Violation Rules Engine               ││     └──────────────────┘
└─────────────────┘     │  │ (Helmet, Triple, Stop-line, Parking)││
                        │  └─────────────────────────────────────┘│
                        └─────────────────────────────────────────┘
```

---

## ✨ Features

| Module | Capabilities |
|--------|-------------|
| **Image Enhancement** | CLAHE, auto-gamma correction, denoising, unsharp masking |
| **Vehicle Detection** | YOLOv8 — cars, motorcycles, buses, trucks, persons |
| **Violation Detection** | Helmet, triple riding, stop-line, wrong-side, parking |
| **License Plate OCR** | EasyOCR + PaddleOCR fallback, Indian plate validation |
| **Evidence Generation** | Annotated images with bboxes, timestamps, camera info |
| **Analytics Dashboard** | KPI cards, charts, trends, heatmap |
| **Export** | CSV + PDF reports |
| **Docker** | One-command deployment |

---

## 🚀 Quick Start

### Option 1 — Docker (Recommended)

```bash
# Clone and enter project directory
cd traffic-violation-system

# Start everything
docker compose -f docker/docker-compose.yml up --build

# Seed demo data (in a separate terminal)
docker exec tvds_backend python scripts/seed_demo_data.py
```

- **Dashboard**: http://localhost:3000
- **API Docs**:  http://localhost:8000/docs
- **Database**:  localhost:5432

---

### Option 2 — Local Development

#### Backend

```powershell
# 1. Create virtual environment
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up PostgreSQL (ensure it's running on localhost:5432)
#    Create database: CREATE DATABASE traffic_violations;
#    Apply schema:    psql -U postgres -d traffic_violations -f ..\scripts\init_db.sql

# 4. Copy env file
copy .env.example .env

# 5. Start the API server
uvicorn app.main:app --reload --port 8000
```

#### Frontend

```powershell
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

#### Seed Demo Data

```powershell
cd backend
python ..\scripts\seed_demo_data.py
```

---

## 📡 API Endpoints

### Upload & Detection
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/upload/image` | Process single image |
| POST | `/api/v1/upload/batch` | Process up to 20 images |

### Violations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/violations` | List with filters (type, status, plate, date) |
| GET | `/api/v1/violations/{id}` | Single violation detail |
| PUT | `/api/v1/violations/{id}` | Update status/notes |
| GET | `/api/v1/violations/search/plate` | Search by plate number |

### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/analytics/summary` | KPI cards |
| GET | `/api/v1/analytics/by-type` | Violation distribution |
| GET | `/api/v1/analytics/trends` | Daily/weekly/monthly trends |
| GET | `/api/v1/analytics/heatmap` | Geographic data |
| GET | `/api/v1/analytics/by-camera` | Per-camera counts |

### Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/reports/csv` | Download CSV |
| GET | `/api/v1/reports/pdf` | Download PDF |

---

## 🧠 AI Pipeline

```
Input Image
    │
    ▼
[1] Image Enhancement (CLAHE + Gamma + Denoise + Sharpen)
    │
    ▼
[2] YOLOv8 Detection (vehicles + persons)
    │
    ▼
[3] Violation Rules Engine
    ├── Helmet check (head-region HSV heuristic)
    ├── Triple riding (person count per motorcycle)
    ├── Stop-line crossing (configurable Y coordinate)
    ├── Wrong-side driving (requires tracking)
    └── Illegal parking (requires tracking + zone config)
    │
    ▼
[4] License Plate OCR (EasyOCR → PaddleOCR fallback)
    │
    ▼
[5] Evidence Image Generation (annotated + HUD)
    │
    ▼
[6] Database Storage → API Response
```

---

## 📁 Project Structure

```
traffic-violation-system/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app entry
│   │   ├── config.py         # All settings (env-driven)
│   │   ├── database.py       # Async SQLAlchemy
│   │   ├── models/           # ORM: violation, vehicle, camera
│   │   ├── schemas/          # Pydantic request/response types
│   │   ├── api/routes/       # upload, violations, analytics, reports
│   │   └── core/
│   │       ├── preprocessing/ # Image enhancement
│   │       ├── detection/     # YOLOv8 + violation rules
│   │       ├── ocr/           # Plate OCR
│   │       └── evidence/      # Annotated image generation
│   ├── tests/                 # Pytest async smoke tests
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── api/client.js      # Axios API client
│       ├── components/        # Sidebar, StatCard, Charts, ViolationCard
│       └── pages/             # Dashboard, Upload, Violations, Reports
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── docker-compose.yml
└── scripts/
    ├── init_db.sql            # Schema + seed cameras
    └── seed_demo_data.py      # 200 sample violations
```

---

## ⚙️ Configuration

All settings are in `backend/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | PostgreSQL | Database connection string |
| `YOLO_DEVICE` | `cpu` | `cpu` or `cuda` |
| `YOLO_MODEL_PATH` | `yolov8n.pt` | Model weights (nano/small/medium) |
| `YOLO_CONFIDENCE_THRESHOLD` | `0.45` | Detection confidence cutoff |
| `OCR_ENGINE` | `easyocr` | `easyocr` or `paddleocr` |
| `MAX_UPLOAD_SIZE_MB` | `50` | Max image upload size |

---

## 📊 Performance Metrics

The system evaluates detection quality using:
- **mAP@50** — Mean Average Precision at IoU 0.50
- **mAP@50-95** — Stricter multi-threshold mAP
- **Precision / Recall / F1**
- **OCR Accuracy** — Plate text character accuracy
- **Inference Time (ms) / FPS**

For production accuracy, fine-tune `yolov8n.pt` on a labeled Indian traffic dataset using Roboflow or a custom annotation pipeline.

---

## 🔧 Extending the System

### Add a new violation rule
1. Create a class in `backend/app/core/detection/violation_rules.py`
2. Add the rule to `ViolationEngine.analyze()`
3. Add the type constant to `app/config.py → ViolationType`
4. Add a color in `VIOLATION_COLORS`

### Switch to GPU inference
```bash
# In .env:
YOLO_DEVICE=cuda
# Install GPU PyTorch:
pip install torch==2.3.0+cu121 torchvision==0.18.0+cu121 --index-url https://download.pytorch.org/whl/cu121
```

### Use a custom license plate model
```bash
# In .env:
PLATE_MODEL_PATH=path/to/your/plate_detector.pt
```

---

## 📄 License

MIT License — free to use for research, smart city projects, and law enforcement systems.
