-- Indexes for the most frequent dashboard/API filters and ordering paths.
-- Safe to run multiple times on PostgreSQL.

CREATE INDEX IF NOT EXISTS idx_equipment_active_type
    ON equipment (is_active, equipment_type_id);

CREATE INDEX IF NOT EXISTS idx_sensors_equipment_active
    ON sensors (equipment_id, is_active);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_timestamp
    ON sensor_readings (sensor_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_alerts_status_created
    ON alerts (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_alerts_equipment_status
    ON alerts (equipment_id, status);

CREATE INDEX IF NOT EXISTS idx_anomalies_ack_timestamp
    ON anomalies (acknowledged_by, detection_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_maintenance_orders_created
    ON maintenance_orders (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_rul_predictions_equipment_date
    ON rul_predictions (equipment_id, prediction_date DESC);
