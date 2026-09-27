-- Migration: Ajouter les champs manquants à la table sensors
-- Date: 2026-04-28

-- Ajouter les colonnes manquantes si elles n'existent pas
ALTER TABLE sensors
ADD COLUMN IF NOT EXISTS unit VARCHAR(50) DEFAULT '';

ALTER TABLE sensors
ADD COLUMN IF NOT EXISTS min_value NUMERIC(15, 4) DEFAULT 0;

ALTER TABLE sensors
ADD COLUMN IF NOT EXISTS max_value NUMERIC(15, 4) DEFAULT 100;

-- Vérification
SELECT COUNT(*) as total_sensors FROM sensors;