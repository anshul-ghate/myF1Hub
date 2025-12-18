-- ============================================================
-- SCHEMA V3: Optimized F1 Analytics Database
-- ============================================================
-- Run in Supabase SQL Editor after dropping all existing tables
-- 
-- OPTIMIZATION FEATURES:
-- - Composite indexes for common query patterns
-- - Milliseconds for lap times (faster math)
-- - CASCADE deletes for data integrity
-- - ingestion_status enum instead of boolean
-- - updated_at timestamps on mutable tables
-- ============================================================

-- ============================================================
-- DROP EXISTING TABLES (Run this first to reset)
-- ============================================================
-- Uncomment and run this section to drop all existing tables:
/*
DROP TABLE IF EXISTS app_logs CASCADE;
DROP TABLE IF EXISTS predictions CASCADE;
DROP TABLE IF EXISTS simulation_results CASCADE;
DROP TABLE IF EXISTS lap_predictions CASCADE;
DROP TABLE IF EXISTS telemetry_stats CASCADE;
DROP TABLE IF EXISTS weather CASCADE;
DROP TABLE IF EXISTS pit_stops CASCADE;
DROP TABLE IF EXISTS laps CASCADE;
DROP TABLE IF EXISTS race_results CASCADE;
DROP TABLE IF EXISTS races CASCADE;
DROP TABLE IF EXISTS drivers CASCADE;
DROP TABLE IF EXISTS circuits CASCADE;
DROP TABLE IF EXISTS seasons CASCADE;
DROP TABLE IF EXISTS elo_ratings CASCADE;
*/

-- ============================================================
-- 1. SEASONS (Dimension Table)
-- ============================================================
CREATE TABLE IF NOT EXISTS seasons (
    year INTEGER PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. CIRCUITS (Dimension Table)
-- ============================================================
CREATE TABLE IF NOT EXISTS circuits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    location VARCHAR(100),
    country VARCHAR(50),
    lat NUMERIC(9,6),
    lng NUMERIC(9,6),
    ergast_circuit_id VARCHAR(50) UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 3. DRIVERS (Dimension Table)
-- Denormalized with current_team for fast lookups
-- ============================================================
CREATE TABLE IF NOT EXISTS drivers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(3) NOT NULL,
    given_name VARCHAR(50) NOT NULL,
    family_name VARCHAR(50) NOT NULL,
    nationality VARCHAR(50),
    current_team VARCHAR(50),
    ergast_driver_id VARCHAR(50) UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_drivers_code ON drivers(code);

-- ============================================================
-- 4. RACES (Fact Table - Core entity)
-- ============================================================
CREATE TABLE IF NOT EXISTS races (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    season_year INTEGER NOT NULL REFERENCES seasons(year),
    round INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    circuit_id UUID REFERENCES circuits(id),
    race_date DATE NOT NULL,
    race_time TIME,
    ergast_race_id VARCHAR(100) UNIQUE,
    ingestion_status VARCHAR(20) DEFAULT 'PENDING', -- PENDING, QUALI, COMPLETE
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(season_year, round)
);
CREATE INDEX IF NOT EXISTS idx_races_season ON races(season_year);
CREATE INDEX IF NOT EXISTS idx_races_status ON races(ingestion_status);

-- ============================================================
-- 5. RACE_RESULTS (Fact Table - Final standings)
-- ============================================================
CREATE TABLE IF NOT EXISTS race_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    race_id UUID NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    driver_id UUID NOT NULL REFERENCES drivers(id),
    position INTEGER,
    grid INTEGER,
    points NUMERIC(4,1) DEFAULT 0,
    laps_completed INTEGER,
    status VARCHAR(50) DEFAULT 'Finished',
    gap_to_leader NUMERIC(10,3), -- Seconds behind winner
    fastest_lap_rank INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(race_id, driver_id)
);
CREATE INDEX IF NOT EXISTS idx_results_race ON race_results(race_id);
CREATE INDEX IF NOT EXISTS idx_results_driver ON race_results(driver_id);
CREATE INDEX IF NOT EXISTS idx_results_position ON race_results(race_id, position);

-- ============================================================
-- 6. LAPS (Fact Table - High-volume, per-lap data)
-- Times stored in milliseconds for precision & fast math
-- ============================================================
CREATE TABLE IF NOT EXISTS laps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    race_id UUID NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    driver_id UUID NOT NULL REFERENCES drivers(id),
    lap_number INTEGER NOT NULL,
    lap_time_ms INTEGER, -- Milliseconds for precision
    sector_1_ms INTEGER,
    sector_2_ms INTEGER,
    sector_3_ms INTEGER,
    compound VARCHAR(15), -- SOFT, MEDIUM, HARD, INTERMEDIATE, WET
    tyre_life INTEGER,
    fresh_tyre BOOLEAN,
    position INTEGER,
    gap_to_leader_ms INTEGER,
    track_status VARCHAR(10),
    is_accurate BOOLEAN DEFAULT TRUE,
    fuel_load NUMERIC(5,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(race_id, driver_id, lap_number)
);
CREATE INDEX IF NOT EXISTS idx_laps_race ON laps(race_id);
CREATE INDEX IF NOT EXISTS idx_laps_driver ON laps(driver_id);
CREATE INDEX IF NOT EXISTS idx_laps_race_lap ON laps(race_id, lap_number);

-- ============================================================
-- 7. PIT_STOPS (Fact Table)
-- ============================================================
CREATE TABLE IF NOT EXISTS pit_stops (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    race_id UUID NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    driver_id UUID NOT NULL REFERENCES drivers(id),
    lap_number INTEGER NOT NULL,
    duration_ms INTEGER, -- Milliseconds
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pits_race ON pit_stops(race_id);

-- ============================================================
-- 8. WEATHER (Fact Table - Time series)
-- ============================================================
CREATE TABLE IF NOT EXISTS weather (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    race_id UUID NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ,
    air_temp NUMERIC(4,1),
    track_temp NUMERIC(4,1),
    humidity NUMERIC(4,1),
    pressure NUMERIC(6,1),
    rainfall BOOLEAN DEFAULT FALSE,
    wind_speed NUMERIC(5,2),
    wind_direction INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_weather_race ON weather(race_id);

-- ============================================================
-- 9. TELEMETRY_STATS (Fact Table - Aggregated per lap)
-- ============================================================
CREATE TABLE IF NOT EXISTS telemetry_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    race_id UUID NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    driver_id UUID NOT NULL REFERENCES drivers(id),
    lap_number INTEGER NOT NULL,
    speed_max NUMERIC(5,1),
    speed_avg NUMERIC(5,1),
    throttle_avg NUMERIC(4,1),
    brake_avg NUMERIC(4,1),
    gear_shifts INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(race_id, driver_id, lap_number)
);
CREATE INDEX IF NOT EXISTS idx_telemetry_race ON telemetry_stats(race_id);

-- ============================================================
-- 10. PREDICTIONS (Fact Table - Store prediction outputs)
-- ============================================================
CREATE TABLE IF NOT EXISTS predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    race_id UUID NOT NULL REFERENCES races(id),
    driver_id UUID NOT NULL REFERENCES drivers(id),
    win_probability NUMERIC(5,2),
    podium_probability NUMERIC(5,2),
    top10_probability NUMERIC(5,2),
    avg_position NUMERIC(4,2),
    dnf_probability NUMERIC(5,2),
    model_version VARCHAR(50),
    simulation_count INTEGER DEFAULT 5000,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(race_id, driver_id, model_version)
);
CREATE INDEX IF NOT EXISTS idx_pred_race ON predictions(race_id);

-- ============================================================
-- 11. APP_LOGS (Operational Table)
-- ============================================================
CREATE TABLE IF NOT EXISTS app_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    level VARCHAR(10) NOT NULL,
    component VARCHAR(50),
    message TEXT NOT NULL,
    correlation_id VARCHAR(20),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_logs_level ON app_logs(level);
CREATE INDEX IF NOT EXISTS idx_logs_component ON app_logs(component);
CREATE INDEX IF NOT EXISTS idx_logs_created ON app_logs(created_at DESC);

-- ============================================================
-- 12. ELO_RATINGS (Dimension Table - Track Elo over time)
-- ============================================================
CREATE TABLE IF NOT EXISTS elo_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(10) NOT NULL, -- 'driver' or 'team'
    entity_name VARCHAR(50) NOT NULL,
    rating NUMERIC(6,1) DEFAULT 1500,
    race_id UUID REFERENCES races(id), -- Rating after this race
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_elo_entity ON elo_ratings(entity_type, entity_name);

-- ============================================================
-- ENABLE ROW LEVEL SECURITY (Optional - for production)
-- ============================================================
-- ALTER TABLE races ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE drivers ENABLE ROW LEVEL SECURITY;
-- etc.

-- ============================================================
-- END OF SCHEMA V3
-- ============================================================
