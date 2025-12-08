# Quick Setup Guide

This guide will help you get the F1 Prediction Platform up and running quickly.

## Prerequisites

- Python 3.9+
- Git
- Supabase account

## Quick Start (Recommended)

We have created an automated script that handles prerequisites, environment setup, database connection, and launching the app.

**Windows (PowerShell):**
```powershell
.\start_here.ps1
```

---

## Manual Step-by-Step Setup

If you prefer to set up manually or are on a non-Windows system:

### 1. Clone and Navigate


```bash
git clone <your-repo-url>
cd F1Proj
```

### 2. Create Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials:
   ```env
   SUPABASE_URL=your_actual_url
   SUPABASE_KEY=your_actual_key
   GOOGLE_API_KEY=your_actual_key  # Optional
   ```

### 5. Database Setup

#### Option A: Using Supabase Dashboard
1. Go to your Supabase project
2. Navigate to SQL Editor
3. Create the required tables (see Database Schema below)

#### Option B: Using Migration Script (if available)
```bash
python scripts/setup_database.py
```

### 6. Run the Application

```bash
streamlit run app/main.py
```

The app will open at `http://localhost:8501`

## Database Schema (Basic)

```sql
-- Races table
CREATE TABLE races (
    id BIGSERIAL PRIMARY KEY,
    season_year INTEGER,
    round INTEGER,
    name TEXT,
    circuit_name TEXT,
    date DATE
);

-- Drivers table
CREATE TABLE drivers (
    id BIGSERIAL PRIMARY KEY,
    code TEXT,
    full_name TEXT,
    number INTEGER
);

-- Results table
CREATE TABLE results (
    id BIGSERIAL PRIMARY KEY,
    race_id BIGINT REFERENCES races(id),
    driver_id BIGINT REFERENCES drivers(id),
    position INTEGER,
    grid INTEGER,
    points NUMERIC
);

-- (Additional tables: laps, pit_stops, qualifying)
```

## Troubleshooting

### FastF1 Cache Issues
If you get cache errors:
```bash
# Clear the cache
rm -rf cache/
# Or on Windows
rmdir /s cache
```

### Module Not Found
```bash
# Ensure virtual environment is activated
# Reinstall requirements
pip install -r requirements.txt
```

### Supabase Connection Error
- Verify your `.env` file has correct credentials
- Check that your Supabase project is active
- Ensure service_role key is used (not anon key)

## Next Steps

1. **Load Initial Data**: Run the data pipeline to fetch race data
   ```bash
   python run_pipeline.py
   ```

2. **Explore the App**: Navigate through the different pages:
   - Home: Project overview
   - Analytics: Historical race analysis
   - Predictions: Race outcome predictions
   - Live Monitor: Real-time tracking

3. **Customize**: Edit configuration files to customize predictions and visualizations

## Getting Help

- Check the main README.md for detailed documentation
- Review code comments for implementation details
- Open an issue on GitHub for bugs or questions

---

**Happy Racing! 🏁**
