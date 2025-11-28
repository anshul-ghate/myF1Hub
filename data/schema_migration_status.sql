-- Add ingestion_complete column to races table
ALTER TABLE public.races 
ADD COLUMN IF NOT EXISTS ingestion_complete BOOLEAN DEFAULT FALSE;

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_races_ingestion_complete ON public.races(ingestion_complete);
