# F1 Race Prediction & Analytics Platform

A comprehensive Formula 1 race prediction and analytics application powered by machine learning, featuring real-time data ingestion, Monte Carlo simulations, and interactive visualizations.

## 🏎️ Features

- **Race Predictions**: Monte Carlo simulation-based predictions for upcoming F1 races
  - Two-stage prediction system (qualifying + race results)
  - Probabilistic outcomes with win/podium percentages
  - Driver performance modeling with historical data

- **Historical Analytics**: Deep dive into past race data
  - Lap time analysis and visualizations
  - Tire strategy insights
  - Position progression tracking

- **Live Race Monitoring**: Real-time race tracking and visualization
  - Live timing data integration
  - Dynamic position updates
  - Interactive race charts

- **Automated Data Pipeline**: Scheduled updates for race results and driver standings
  - FastF1 API integration
  - Supabase database storage
  - Incremental data ingestion

## 📋 Prerequisites

- Python 3.9 or higher
- Supabase account (for database storage)
- Google AI API key (optional, for AI-powered insights)

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/f1-prediction-platform.git
cd f1-prediction-platform
```

### 2. Set Up Virtual Environment

**Windows:**
```bash
python -m venv .venv
.\.venv\Scripts\Activate
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root (use `.env.example` as template):

```env
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_service_role_key
GOOGLE_API_KEY=your_google_ai_api_key  # Optional
```

### 5. Set Up Database

Set up your Supabase database with the required tables:
- `races`
- `drivers`
- `results`
- `laps`
- `pit_stops`
- `qualifying`

See `docs/database_schema.md` (if available) for detailed schema information.

## 💻 Usage

### Run the Web Application

```bash
streamlit run app/main.py
```

The app will be available at `http://localhost:8501`

### Run Data Pipeline

To fetch and update race data:

```bash
python run_pipeline.py
```

### Automated Updates

Set up scheduled pipeline runs using:
```bash
python scripts/auto_update.py
```

## 📁 Project Structure

```
F1Proj/
├── app/                    # Streamlit web application
│   ├── main.py            # Main app entry point
│   └── pages/             # Multi-page app pages
│       ├── 1_analytics.py
│       ├── 2_predictions.py
│       └── 3_live_monitor.py
├── models/                # ML models
│   ├── simulation.py      # Race simulator
│   └── saved/            # Trained model files
├── scripts/              # Automation scripts
│   └── auto_update.py    # Scheduled data updates
├── utils/                # Utility modules
│   ├── db.py            # Database connections
│   ├── race_utils.py    # Race data utilities
│   └── ai.py            # AI integrations
├── data/                 # Data storage (gitignored)
├── cache/               # Cache directory (gitignored)
├── requirements.txt     # Python dependencies
├── .env.example        # Environment template
└── README.md           # This file
```

## 🔧 Configuration

### Model Training

To retrain the lap time prediction model:

```python
# Coming soon: model training script
python models/train_model.py
```

### Customizing Predictions

Edit `models/simulation.py` to adjust:
- Driver performance tiers
- Tire strategy parameters
- Safety car probabilities
- Monte Carlo simulation count

## 📊 Technologies Used

- **Frontend**: Streamlit
- **Data Processing**: Pandas, NumPy
- **ML**: Scikit-learn, XGBoost
- **Visualization**: Plotly, Matplotlib, Seaborn
- **Database**: Supabase (PostgreSQL)
- **F1 Data**: FastF1 API
- **AI**: Google Generative AI (optional)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This application is for educational and entertainment purposes only. Predictions are based on historical data and statistical models and should not be used for betting or financial decisions.

## 🚀 Deployment

### Deploy to Streamlit Community Cloud (Free)

1. **Push your code to GitHub**
2. **Visit** [share.streamlit.io](https://share.streamlit.io)
3. **Connect your GitHub repository**
4. **Configure**:
   - Main file: `app/main.py`
   - Python version: 3.11
5. **Add secrets** in app settings:
   ```toml
   GOOGLE_API_KEY = "your_key_here"
   SUPABASE_URL = "your_url_here"
   SUPABASE_KEY = "your_key_here"
   ```
6. **Deploy!**

Your app will be live at: `https://your-app-name.streamlit.app`

📖 **For detailed deployment instructions**, see [DEPLOYMENT.md](DEPLOYMENT.md)

### Pre-Deployment Checklist

Run the deployment readiness check:

```bash
python check_deployment.py
```

This will verify:
- ✅ All required files are present
- ✅ Dependencies are configured
- ✅ Secrets are properly gitignored
- ✅ Configuration is production-ready

## 🙏 Acknowledgments

- [FastF1](https://github.com/theOehrly/Fast-F1) for providing F1 data API
- [Supabase](https://supabase.com/) for database infrastructure
- Formula 1 community for inspiration

## 📧 Contact

For questions or support, please open an issue on GitHub.

---

**Enjoy predicting F1 races! 🏁**
