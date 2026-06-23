"""
Demo data seeder -- works with both SQLite and PostgreSQL.
Run from the backend directory:
    python ../scripts/seed_demo_data.py
"""
import asyncio
import random
import uuid
import sys
import os
from datetime import datetime, timedelta

# Add backend to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Must set env before importing app modules
os.environ.setdefault(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./traffic_violations.db"
)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

DATABASE_URL = os.environ["DATABASE_URL"]

VIOLATION_TYPES = [
    ("helmet_violation",    0.82),
    ("triple_riding",       0.78),
    ("stop_line_violation", 0.88),
    ("wrong_side_driving",  0.75),
    ("illegal_parking",     0.91),
    ("red_light_violation", 0.85),
    ("seatbelt_violation",  0.72),
]
VEHICLES = ["car", "motorcycle", "bus", "truck", "bicycle"]
PLATES   = [
    "KA01AB1234", "MH12CD5678", "DL3EFG901", "TN09HI2345",
    "AP01JK6789", "GJ05LM0123", "RJ14NO4567", "UP32PQ8901",
    None, None,
]
LOCATIONS = [
    "MG Road Junction", "Silk Board Flyover",
    "Hebbal Ring Road", "Electronic City Toll", "Koramangala Signal",
]

# Seed cameras
CAMERAS = [
    ("CAM-001", "MG Road Junction",    "MG Road, Bengaluru",        12.9716, 77.5946),
    ("CAM-002", "Silk Board Flyover",  "Silk Board, Bengaluru",     12.9174, 77.6224),
    ("CAM-003", "Hebbal Ring Road",    "Hebbal, Bengaluru",         13.0352, 77.5970),
    ("CAM-004", "Electronic City",     "Electronic City, Bengaluru",12.8456, 77.6603),
    ("CAM-005", "Koramangala Signal",  "Koramangala, Bengaluru",    12.9352, 77.6245),
]


async def seed():
    is_sqlite = DATABASE_URL.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    engine = create_async_engine(DATABASE_URL, connect_args=connect_args, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as session:
        # Insert cameras
        cam_ids = []
        for cam_id_str, name, location, lat, lon in CAMERAS:
            cid = str(uuid.uuid4())
            cam_ids.append(cid)
            try:
                await session.execute(text("""
                    INSERT INTO cameras (id, camera_id, name, location, latitude, longitude, is_active)
                    VALUES (:id, :cam_id, :name, :location, :lat, :lon, 1)
                """), {"id": cid, "cam_id": cam_id_str, "name": name,
                       "location": location, "lat": lat, "lon": lon})
            except Exception:
                # Already exists — fetch the existing id
                row = (await session.execute(
                    text("SELECT id FROM cameras WHERE camera_id = :c"),
                    {"c": cam_id_str}
                )).first()
                if row:
                    cam_ids[-1] = str(row[0])

        now = datetime.now()
        count = 0
        for i in range(200):
            vtype, base_conf = random.choice(VIOLATION_TYPES)
            conf   = min(0.99, max(0.40, base_conf + random.gauss(0, 0.08)))
            dt     = now - timedelta(
                days=random.randint(0, 30),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )
            plate  = random.choice(PLATES)
            cam_id = random.choice(cam_ids)
            loc    = random.choice(LOCATIONS)
            veh    = random.choice(VEHICLES)
            status = random.choice(["pending"] * 6 + ["resolved", "reviewed"])

            try:
                await session.execute(text("""
                    INSERT INTO violations (
                        id, violation_type, confidence, detected_at,
                        vehicle_type, plate_number, plate_confidence,
                        bbox, location, latitude, longitude, status, camera_id
                    ) VALUES (
                        :id, :vtype, :conf, :dt,
                        :veh, :plate, :plate_conf,
                        :bbox, :loc, :lat, :lon, :status, :cam_id
                    )
                """), {
                    "id":         str(uuid.uuid4()),
                    "vtype":      vtype,
                    "conf":       round(conf, 3),
                    "dt":         dt.isoformat(),
                    "veh":        veh,
                    "plate":      plate,
                    "plate_conf": round(random.uniform(0.6, 0.98), 2) if plate else None,
                    "bbox":       '{"x1": 100, "y1": 80, "x2": 320, "y2": 280}',
                    "loc":        loc,
                    "lat":        round(random.uniform(12.85, 13.05), 6),
                    "lon":        round(random.uniform(77.55, 77.70), 6),
                    "status":     status,
                    "cam_id":     cam_id,
                })
                count += 1
            except Exception as e:
                print(f"  Warning: {e}")

        await session.commit()
        print(f"[OK] Seeded {count} violation records into {DATABASE_URL.split('///')[0]}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
