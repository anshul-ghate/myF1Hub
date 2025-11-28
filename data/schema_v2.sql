-- Schema V2: Advanced Analytics & Telemetry

-- 1. Pit Stops Table
CREATE TABLE IF NOT EXISTS public.pit_stops (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    race_id uuid NOT NULL,
    driver_id uuid NOT NULL,
    lap_number integer NOT NULL,
    duration numeric,              -- Pit stop duration in seconds
    local_timestamp timestamp with time zone,
    created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT pit_stops_pkey PRIMARY KEY (id),
    CONSTRAINT pit_stops_race_id_fkey FOREIGN KEY (race_id) REFERENCES public.races(id),
    CONSTRAINT pit_stops_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.drivers(id)
);

-- 2. Telemetry Stats Table (Aggregated per lap)
CREATE TABLE IF NOT EXISTS public.telemetry_stats (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    race_id uuid NOT NULL,
    driver_id uuid NOT NULL,
    lap_number integer NOT NULL,
    speed_max numeric,
    speed_avg numeric,
    throttle_avg numeric,          -- Percentage 0-100
    brake_avg numeric,             -- Percentage 0-100 or binary usage avg
    gear_shifts integer,
    created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT telemetry_stats_pkey PRIMARY KEY (id),
    CONSTRAINT telemetry_stats_race_id_fkey FOREIGN KEY (race_id) REFERENCES public.races(id),
    CONSTRAINT telemetry_stats_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.drivers(id),
    UNIQUE(race_id, driver_id, lap_number)
);

-- 3. Add columns to Laps table (if they don't exist)
-- Note: User might need to run these ALTER commands manually if the table exists
ALTER TABLE public.laps ADD COLUMN IF NOT EXISTS fuel_load numeric;
ALTER TABLE public.laps ADD COLUMN IF NOT EXISTS gap_to_leader numeric;
ALTER TABLE public.laps ADD COLUMN IF NOT EXISTS position integer;
