-- Traffic Violation Detection System — Initial Schema
-- This script runs once when PostgreSQL container is first created.

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create enum types
DO $$ BEGIN
    CREATE TYPE violationstatus AS ENUM (
        'pending', 'reviewed', 'resolved', 'disputed', 'dismissed'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Cameras table
CREATE TABLE IF NOT EXISTS cameras (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id   VARCHAR(64) UNIQUE NOT NULL,
    name        VARCHAR(128) NOT NULL,
    location    VARCHAR(255),
    latitude    DOUBLE PRECISION,
    longitude   DOUBLE PRECISION,
    rtsp_url    VARCHAR(512),
    is_active   BOOLEAN DEFAULT TRUE,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ
);

-- Vehicles table
CREATE TABLE IF NOT EXISTS vehicles (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plate_number        VARCHAR(32),
    vehicle_type        VARCHAR(32),
    color               VARCHAR(32),
    make                VARCHAR(64),
    model               VARCHAR(64),
    registration_state  VARCHAR(8),
    total_violations    INTEGER DEFAULT 0,
    first_seen          TIMESTAMPTZ DEFAULT NOW(),
    last_seen           TIMESTAMPTZ,
    notes               TEXT
);

CREATE INDEX IF NOT EXISTS idx_vehicles_plate ON vehicles(plate_number);

-- Violations table
CREATE TABLE IF NOT EXISTS violations (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    violation_type      VARCHAR(64) NOT NULL,
    confidence          DOUBLE PRECISION NOT NULL,
    detected_at         TIMESTAMPTZ DEFAULT NOW(),
    vehicle_type        VARCHAR(32),
    plate_number        VARCHAR(32),
    plate_confidence    DOUBLE PRECISION,
    bbox                JSONB,
    location            VARCHAR(255),
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    original_image_path VARCHAR(512),
    evidence_image_path VARCHAR(512),
    evidence_thumbnail  TEXT,
    status              violationstatus DEFAULT 'pending',
    reviewer_notes      TEXT,
    is_false_positive   BOOLEAN DEFAULT FALSE,
    camera_id           UUID REFERENCES cameras(id) ON DELETE SET NULL,
    vehicle_id          UUID REFERENCES vehicles(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_violations_type       ON violations(violation_type);
CREATE INDEX IF NOT EXISTS idx_violations_detected   ON violations(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_violations_plate      ON violations(plate_number);
CREATE INDEX IF NOT EXISTS idx_violations_status     ON violations(status);
CREATE INDEX IF NOT EXISTS idx_violations_camera     ON violations(camera_id);

-- Seed default cameras
INSERT INTO cameras (camera_id, name, location, latitude, longitude, is_active)
VALUES
  ('CAM-001', 'MG Road Junction',        'MG Road, Bengaluru',           12.9716, 77.5946, TRUE),
  ('CAM-002', 'Silk Board Flyover',       'Silk Board, Bengaluru',        12.9174, 77.6224, TRUE),
  ('CAM-003', 'Hebbal Ring Road',         'Hebbal, Bengaluru',            13.0352, 77.5970, TRUE),
  ('CAM-004', 'Electronic City Toll',     'Electronic City, Bengaluru',   12.8456, 77.6603, TRUE),
  ('CAM-005', 'Koramangala Signal',       'Koramangala, Bengaluru',       12.9352, 77.6245, TRUE)
ON CONFLICT (camera_id) DO NOTHING;
