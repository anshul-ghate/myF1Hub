-- 1. Laps Table (CRITICAL for Lap-by-Lap Analytics)
-- Links to the existing 'races' and 'drivers' tables via UUIDs.
CREATE TABLE IF NOT EXISTS public.laps (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    race_id uuid NOT NULL,
    driver_id uuid NOT NULL,
    lap_number integer NOT NULL,
    lap_time interval,             -- Storing as interval is better for time calculations
    sector_1_time interval,
    sector_2_time interval,
    sector_3_time interval,
    compound character varying,    -- Tyre compound (Soft, Medium, Hard, etc.)
    tyre_life integer,             -- Laps on current set
    fresh_tyre boolean,
    track_status character varying,-- '1' (Green), '2' (Yellow), '4' (SC), etc.
    is_accurate boolean,           -- Data validation flag
    created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT laps_pkey PRIMARY KEY (id),
    CONSTRAINT laps_race_id_fkey FOREIGN KEY (race_id) REFERENCES public.races(id),
    CONSTRAINT laps_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.drivers(id),
    UNIQUE(race_id, driver_id, lap_number) -- Prevent duplicate laps
);

-- 2. Weather Table (CRITICAL for ML Models)
-- Stores weather conditions throughout the race.
CREATE TABLE IF NOT EXISTS public.weather (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    race_id uuid NOT NULL,
    timestamp timestamp with time zone NOT NULL,
    air_temp numeric,
    track_temp numeric,
    humidity numeric,
    pressure numeric,
    rainfall boolean,
    wind_speed numeric,
    wind_direction integer,
    created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT weather_pkey PRIMARY KEY (id),
    CONSTRAINT weather_race_id_fkey FOREIGN KEY (race_id) REFERENCES public.races(id)
);

-- 3. Lap Predictions Table (For Regression Model)
-- The existing 'predictions' table seems designed for Race Position. 
-- We need a separate table for per-lap time predictions.
CREATE TABLE IF NOT EXISTS public.lap_predictions (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    race_id uuid NOT NULL,
    driver_id uuid NOT NULL,
    lap_number integer NOT NULL,
    predicted_lap_time interval,
    predicted_sector_1 interval,
    predicted_sector_2 interval,
    predicted_sector_3 interval,
    model_version character varying,
    created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT lap_predictions_pkey PRIMARY KEY (id),
    CONSTRAINT lap_predictions_race_id_fkey FOREIGN KEY (race_id) REFERENCES public.races(id),
    CONSTRAINT lap_predictions_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.drivers(id)
);

-- 4. Application Logs Table (Requested)
-- Centralized logging for the application backend and ML jobs.
CREATE TABLE IF NOT EXISTS public.app_logs (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    level character varying NOT NULL, -- INFO, WARN, ERROR
    component character varying,      -- e.g., 'Ingestion', 'ML_Training', 'API'
    message text NOT NULL,
    metadata jsonb,                   -- Flexible field for extra details (e.g., race_id, error stack)
    created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT app_logs_pkey PRIMARY KEY (id)
);

-- 5. Simulation Results (For Monte Carlo)
-- Stores the summary of thousands of simulation runs.
CREATE TABLE IF NOT EXISTS public.simulation_results (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    race_id uuid NOT NULL,
    driver_id uuid NOT NULL,
    win_probability numeric,
    podium_probability numeric,
    top_10_probability numeric,
    avg_finish_position numeric,
    dnf_probability numeric,
    simulation_count integer DEFAULT 1000,
    created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT simulation_results_pkey PRIMARY KEY (id),
    CONSTRAINT simulation_results_race_id_fkey FOREIGN KEY (race_id) REFERENCES public.races(id),
    CONSTRAINT simulation_results_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.drivers(id)
);
