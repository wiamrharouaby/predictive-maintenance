-- ============================================================
-- PFE MAINTENANCE PRÃƒâ€°DICTIVE - SCHÃƒâ€°MA DE BASE DE DONNÃƒâ€°ES
-- ONEE - Centrale Thermique
-- ============================================================

-- CrÃƒÂ©er l'extension UUID si elle n'existe pas
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- TABLE: USERS (Authentification et gestion des utilisateurs)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'viewer', -- admin, engineer, viewer
    department VARCHAR(100),
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    archived_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

-- Index pour accÃƒÂ¨s rapide
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- ============================================================
-- TABLE: EQUIPMENT_TYPES (Types d'ÃƒÂ©quipements)
-- ============================================================
CREATE TABLE IF NOT EXISTS equipment_types (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- InsÃƒÂ©rer les types d'ÃƒÂ©quipements
INSERT INTO equipment_types (name, description) VALUES
('Turbine', 'Turbine vapeur haute pression'),
('ChaudiÃƒÂ¨re', 'ChaudiÃƒÂ¨re de rÃƒÂ©cupÃƒÂ©ration de chaleur'),
('Alternateur', 'Alternateur synchrone de puissance'),
('Compresseur', 'Compresseur ÃƒÂ  air'),
('Pompe', 'Pompe de circulation d''eau'),
('Ãƒâ€°changeur', 'Ãƒâ€°changeur thermique');

-- ============================================================
-- TABLE: EQUIPMENT (Ãƒâ€°quipements monitoriÃƒÂ©s)
-- ============================================================
CREATE TABLE IF NOT EXISTS equipment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    equipment_type_id UUID NOT NULL REFERENCES equipment_types(id),
    equipment_code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    location VARCHAR(255),
    manufacturer VARCHAR(100),
    model VARCHAR(100),
    installation_date DATE,
    nominal_power VARCHAR(50),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_equipment_type ON equipment(equipment_type_id);
CREATE INDEX idx_equipment_code ON equipment(equipment_code);
CREATE INDEX idx_equipment_active ON equipment(is_active);

-- ============================================================
-- TABLE: SENSOR_TYPES (Types de capteurs)
-- ============================================================
CREATE TABLE IF NOT EXISTS sensor_types (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    unit VARCHAR(50),
    min_value DECIMAL(10, 2),
    max_value DECIMAL(10, 2),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- InsÃƒÂ©rer les types de capteurs
INSERT INTO sensor_types (name, unit, min_value, max_value, description) VALUES
('TempÃƒÂ©rature', 'Ã‚Â°C', -50, 150, 'Capteur de tempÃƒÂ©rature'),
('Pression', 'bar', 0, 500, 'Capteur de pression'),
('Vibration', 'mm/s', 0, 50, 'Capteur de vibration'),
('Courant', 'A', 0, 5000, 'Capteur de courant ÃƒÂ©lectrique'),
('DÃƒÂ©bit', 'mÃ‚Â³/h', 0, 10000, 'Capteur de dÃƒÂ©bit liquide'),
('Vitesse', 'rpm', 0, 10000, 'Capteur de vitesse de rotation'),
('HumiditÃƒÂ©', '%', 0, 100, 'Capteur d''humiditÃƒÂ© relative'),
('Puissance', 'MW', 0, 500, 'Capteur de puissance ÃƒÂ©lectrique');

-- ============================================================
-- TABLE: SENSORS (Capteurs installÃƒÂ©s)
-- ============================================================
CREATE TABLE IF NOT EXISTS sensors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    equipment_id UUID NOT NULL REFERENCES equipment(id),
    sensor_type_id UUID NOT NULL REFERENCES sensor_types(id),
    sensor_code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    location_on_equipment VARCHAR(255),
    installation_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    last_calibration DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sensors_equipment ON sensors(equipment_id);
CREATE INDEX idx_sensors_type ON sensors(sensor_type_id);
CREATE INDEX idx_sensors_code ON sensors(sensor_code);
CREATE INDEX idx_sensors_active ON sensors(is_active);

-- ============================================================
-- TABLE: SENSOR_READINGS (Lectures des capteurs - DonnÃƒÂ©es temps rÃƒÂ©el)
-- ============================================================
CREATE TABLE IF NOT EXISTS sensor_readings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sensor_id UUID NOT NULL REFERENCES sensors(id),
    value DECIMAL(15, 4) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(20) DEFAULT 'normal', -- normal, warning, critical, anomaly
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index pour requÃƒÂªtes rapides sur le temps
CREATE INDEX idx_readings_sensor_timestamp ON sensor_readings(sensor_id, timestamp DESC);
CREATE INDEX idx_readings_timestamp ON sensor_readings(timestamp DESC);
CREATE INDEX idx_readings_status ON sensor_readings(status);

-- Partitioning par mois (optionnel pour grosse volumÃƒÂ©trie)
-- ALTER TABLE sensor_readings ADD CONSTRAINT readings_timestamp_check CHECK (timestamp >= '2024-01-01');

-- ============================================================
-- TABLE: ANOMALIES (DÃƒÂ©tections d'anomalies)
-- ============================================================
CREATE TABLE IF NOT EXISTS anomalies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sensor_id UUID NOT NULL REFERENCES sensors(id),
    anomaly_type VARCHAR(50) NOT NULL, -- univariate, multivariate, temporal
    anomaly_score DECIMAL(5, 4),
    detection_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    threshold_value DECIMAL(15, 4),
    actual_value DECIMAL(15, 4),
    severity VARCHAR(20), -- low, medium, high, critical
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by UUID REFERENCES users(id),
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_anomalies_sensor ON anomalies(sensor_id);
CREATE INDEX idx_anomalies_detection ON anomalies(detection_timestamp DESC);
CREATE INDEX idx_anomalies_severity ON anomalies(severity);
CREATE INDEX idx_anomalies_acknowledged ON anomalies(is_acknowledged);

-- ============================================================
-- TABLE: RUL_PREDICTIONS (Remaining Useful Life - DurÃƒÂ©e de vie utile restante)
-- ============================================================
CREATE TABLE IF NOT EXISTS rul_predictions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    equipment_id UUID NOT NULL REFERENCES equipment(id),
    predicted_rul_hours INTEGER,
    confidence_score DECIMAL(5, 4),
    prediction_date TIMESTAMP WITH TIME ZONE NOT NULL,
    model_version VARCHAR(50),
    prediction_window_days INTEGER,
    last_maintenance_date DATE,
    status VARCHAR(50) DEFAULT 'active', -- active, archived
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rul_equipment ON rul_predictions(equipment_id);
CREATE INDEX idx_rul_prediction_date ON rul_predictions(prediction_date DESC);
CREATE INDEX idx_rul_status ON rul_predictions(status);

-- ============================================================
-- TABLE: MAINTENANCE_ORDERS (Ordres de maintenance)
-- ============================================================
CREATE TABLE IF NOT EXISTS maintenance_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    equipment_id UUID NOT NULL REFERENCES equipment(id),
    anomaly_id UUID REFERENCES anomalies(id),
    rul_prediction_id UUID REFERENCES rul_predictions(id),
    order_number VARCHAR(50) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    priority VARCHAR(20), -- low, medium, high, urgent
    status VARCHAR(50) DEFAULT 'open', -- open, scheduled, in_progress, completed, cancelled
    assigned_to UUID REFERENCES users(id),
    scheduled_date DATE,
    completed_date DATE,
    estimated_hours DECIMAL(10, 2),
    actual_hours DECIMAL(10, 2),
    notes TEXT,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_maintenance_equipment ON maintenance_orders(equipment_id);
CREATE INDEX idx_maintenance_status ON maintenance_orders(status);
CREATE INDEX idx_maintenance_priority ON maintenance_orders(priority);
CREATE INDEX idx_maintenance_assigned ON maintenance_orders(assigned_to);

-- ============================================================
-- TABLE: ALERTS (Alertes et notifications)
-- ============================================================
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    equipment_id UUID NOT NULL REFERENCES equipment(id),
    anomaly_id UUID REFERENCES anomalies(id),
    title VARCHAR(255) NOT NULL,
    message TEXT,
    alert_type VARCHAR(50), -- anomaly, threshold, maintenance, system
    severity VARCHAR(20), -- low, medium, high, critical
    status VARCHAR(50) DEFAULT 'active', -- active, acknowledged, resolved
    acknowledged_by UUID REFERENCES users(id),
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_alerts_equipment ON alerts(equipment_id);
CREATE INDEX idx_alerts_severity ON alerts(severity);
CREATE INDEX idx_alerts_status ON alerts(status);
CREATE INDEX idx_alerts_created ON alerts(created_at DESC);

-- ============================================================
-- TABLE: ML_MODELS (Tracking des modÃƒÂ¨les ML)
-- ============================================================
CREATE TABLE IF NOT EXISTS ml_models (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_name VARCHAR(100) NOT NULL,
    model_type VARCHAR(50), -- anomaly_detection, rul_prediction, classification
    version VARCHAR(50),
    framework VARCHAR(50), -- sklearn, xgboost, tensorflow, etc
    training_date TIMESTAMP WITH TIME ZONE,
    accuracy DECIMAL(5, 4),
    precision DECIMAL(5, 4),
    recall DECIMAL(5, 4),
    f1_score DECIMAL(5, 4),
    model_path VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE: KNOWLEDGE_BASE (Pour RAG Chatbot)
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_base (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_title VARCHAR(255) NOT NULL,
    document_type VARCHAR(50), -- manual, procedure, faq, troubleshooting, specification
    content TEXT NOT NULL,
    equipment_type_id UUID REFERENCES equipment_types(id),
    tags VARCHAR(500), -- comma-separated tags
    author VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_kb_type ON knowledge_base(document_type);
CREATE INDEX idx_kb_equipment ON knowledge_base(equipment_type_id);

-- ============================================================
-- TABLE: CHAT_HISTORY (Historique des conversations avec le chatbot)
-- ============================================================
CREATE TABLE IF NOT EXISTS chat_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    message TEXT NOT NULL,
    response TEXT,
    equipment_id UUID REFERENCES equipment(id),
    is_user_message BOOLEAN,
    embedding_vector BYTEA, -- Pour recherche sÃƒÂ©mantique future
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chat_user ON chat_history(user_id);
CREATE INDEX idx_chat_equipment ON chat_history(equipment_id);
CREATE INDEX idx_chat_created ON chat_history(created_at DESC);

-- ============================================================
-- FONCTION: Update timestamp automatically
-- ============================================================
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Appliquer le trigger sur les tables avec updated_at
CREATE TRIGGER trigger_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trigger_equipment_updated_at
BEFORE UPDATE ON equipment
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trigger_sensors_updated_at
BEFORE UPDATE ON sensors
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trigger_maintenance_updated_at
BEFORE UPDATE ON maintenance_orders
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trigger_alerts_updated_at
BEFORE UPDATE ON alerts
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trigger_kb_updated_at
BEFORE UPDATE ON knowledge_base
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- ============================================================
-- VUES UTILES
-- ============================================================

-- Vue: Ãƒâ€°tat actuel de tous les ÃƒÂ©quipements avec derniÃƒÂ¨res lectures
CREATE OR REPLACE VIEW v_equipment_status AS
SELECT 
    e.id,
    e.equipment_code,
    e.name,
    et.name as equipment_type,
    COUNT(DISTINCT s.id) as sensor_count,
    COUNT(DISTINCT sr.id) as reading_count,
    MAX(sr.timestamp) as last_reading_time,
    COUNT(CASE WHEN a.is_acknowledged = FALSE THEN 1 END) as unacknowledged_anomalies,
    COUNT(CASE WHEN al.status = 'active' THEN 1 END) as active_alerts
FROM equipment e
LEFT JOIN equipment_types et ON e.equipment_type_id = et.id
LEFT JOIN sensors s ON e.id = s.equipment_id AND s.is_active = TRUE
LEFT JOIN sensor_readings sr ON s.id = sr.sensor_id
LEFT JOIN anomalies a ON s.id = a.sensor_id
LEFT JOIN alerts al ON e.id = al.equipment_id
WHERE e.is_active = TRUE
GROUP BY e.id, e.equipment_code, e.name, et.name;

-- Vue: Maintenance orders ÃƒÂ  faire
CREATE OR REPLACE VIEW v_pending_maintenance AS
SELECT 
    mo.id,
    mo.order_number,
    mo.title,
    e.name as equipment_name,
    mo.priority,
    mo.status,
    mo.assigned_to,
    u.full_name as assigned_to_name,
    mo.scheduled_date,
    CURRENT_DATE - mo.scheduled_date as days_overdue
FROM maintenance_orders mo
LEFT JOIN equipment e ON mo.equipment_id = e.id
LEFT JOIN users u ON mo.assigned_to = u.id
WHERE mo.status IN ('open', 'scheduled')
ORDER BY mo.priority DESC, mo.scheduled_date ASC;

COMMIT;
