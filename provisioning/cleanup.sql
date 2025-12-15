-- Database Cleanup Script
-- Runs daily to prevent database from growing indefinitely

-- Delete sensor readings older than 7 days
DELETE FROM sensor_readings WHERE recorded_at < NOW() - INTERVAL '7 days';

-- Delete alert actions older than 30 days
DELETE FROM alert_actions WHERE created_at < NOW() - INTERVAL '30 days';

-- Show cleanup results
SELECT 
    'sensor_readings' as table_name,
    COUNT(*) as remaining_rows,
    MIN(recorded_at) as oldest_record,
    MAX(recorded_at) as newest_record
FROM sensor_readings
UNION ALL
SELECT 
    'alert_actions' as table_name,
    COUNT(*) as remaining_rows,
    MIN(created_at) as oldest_record,
    MAX(created_at) as newest_record
FROM alert_actions;
