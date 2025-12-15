CREATE TABLE IF NOT EXISTS sensor_readings (
    id BIGSERIAL PRIMARY KEY,
    sensor_name TEXT NOT NULL,
    parameter TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit TEXT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sensor_time ON sensor_readings (sensor_name, recorded_at DESC);

-- Table to log actions taken by worker when sustained alerts occur
CREATE TABLE IF NOT EXISTS alert_actions (
    id BIGSERIAL PRIMARY KEY,
    alert_uid TEXT NOT NULL,
    alert_title TEXT NOT NULL,
    state TEXT NOT NULL,
    threshold DOUBLE PRECISION,
    current_value DOUBLE PRECISION,
    started_at TIMESTAMPTZ,
    sustained_seconds INT,
    action TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
