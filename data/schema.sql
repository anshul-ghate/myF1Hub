-- Enable the UUID extension
create extension if not exists "uuid-ossp";

-- Races Table
create table if not exists races (
    race_id uuid primary key default uuid_generate_v4(),
    year int not null,
    round int not null,
    circuit_id text not null,
    name text not null,
    date timestamp with time zone not null,
    location text,
    unique(year, round)
);

-- Drivers Table
create table if not exists drivers (
    driver_id text primary key, -- e.g., 'VER', 'HAM'
    driver_number int,
    full_name text not null,
    team_name text,
    country text
);

-- Laps Table
create table if not exists laps (
    lap_id uuid primary key default uuid_generate_v4(),
    race_id uuid references races(race_id),
    driver_id text references drivers(driver_id),
    lap_number int not null,
    lap_time float, -- in seconds
    sector1_time float,
    sector2_time float,
    sector3_time float,
    compound text, -- SOFT, MEDIUM, HARD, INTERMEDIATE, WET
    tyre_life int,
    fresh_tyre boolean,
    track_status text, -- '1' for Green, '2' for Yellow, etc.
    is_accurate boolean -- FastF1 flag for data accuracy
);

-- Telemetry Table (Sampled, maybe not every tick to save space, or aggregated)
-- For now, let's store weather data per race/session
create table if not exists weather (
    weather_id uuid primary key default uuid_generate_v4(),
    race_id uuid references races(race_id),
    time timestamp with time zone,
    air_temp float,
    track_temp float,
    humidity float,
    pressure float,
    rainfall boolean,
    wind_speed float,
    wind_direction int
);

-- Predictions Table
create table if not exists predictions (
    prediction_id uuid primary key default uuid_generate_v4(),
    race_id uuid references races(race_id),
    driver_id text references drivers(driver_id),
    predicted_lap_time float,
    confidence_interval_lower float,
    confidence_interval_upper float,
    model_version text,
    created_at timestamp with time zone default now()
);
