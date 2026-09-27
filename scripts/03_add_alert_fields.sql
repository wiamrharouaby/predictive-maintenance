-- Migration: Add created_at and updated_at fields to alerts table
-- Date: 2026-04-12

ALTER TABLE alerts ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- Update existing alerts with current timestamp if missing
UPDATE alerts SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL;
UPDATE alerts SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL;

-- Log migration completion
SELECT 'Migration completed: added created_at and updated_at to alerts table' as status;