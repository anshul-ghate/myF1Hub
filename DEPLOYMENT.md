# F1 HUB Deployment Guide

## Overview

This guide explains how to deploy the F1 HUB application to the web using **Streamlit Community Cloud**, which offers free hosting with GitHub integration.

> [!IMPORTANT]
> **You cannot host Streamlit apps on GitHub Pages** because GitHub Pages only serves static HTML/CSS/JS files. Streamlit requires a Python server to run. Instead, we'll use Streamlit Community Cloud, which is free and integrates seamlessly with GitHub.

---

## Deployment Options

### Option 1: Streamlit Community Cloud (Recommended) ⭐

**Best for**: Free hosting, automatic deployments from GitHub, no DevOps experience needed

- ✅ **Free** forever (with resource limits)
- ✅ **Automatic deployments** when you push to GitHub
- ✅ **Built-in secrets management** for API keys
- ✅ **Custom domain support** (optional)
- ✅ **No credit card required**

**Limitations**:
- Resource limits (1 CPU, 1GB RAM per app)
- No custom backend services (but Supabase integration works)

### Option 2: GitHub Actions + External Platform

**Best for**: More control, custom infrastructure, advanced features

Platforms you can deploy to with GitHub Actions:
- **Railway** (Free tier, easy setup)
- **Render** (Free tier available)
- **Heroku** ($5-7/month minimum, but more reliable)
- **Google Cloud Run** (Pay-as-you-go, very cheap for low traffic)
- **AWS ECS/Fargate** (More complex, enterprise-grade)

---

## Quick Start: Streamlit Community Cloud Deployment

### Prerequisites

1. **GitHub Account** - Your code must be in a GitHub repository
2. **Streamlit Account** - Sign up at [share.streamlit.io](https://share.streamlit.io) using GitHub
3. **API Keys Ready**:
   - Google AI API Key (for Gemini)
   - Supabase URL and Key

### Step 1: Prepare Your Repository

All necessary files are already created in this guide. Ensure these files exist:

- ✅ `requirements.txt` - Python dependencies
- ✅ `.streamlit/config.toml` - Streamlit configuration
- ✅ `.streamlit/secrets.toml.example` - Secrets template (don't commit actual secrets!)
- ✅ `.gitignore` - Ensures sensitive files aren't committed
- ✅ `README.md` - Project documentation

### Step 2: Push to GitHub

```bash
# Initialize git (if not already)
git init

# Add all files
git add .

# Commit
git commit -m "Prepare F1 HUB for deployment"

# Add remote (replace with your repo URL)
git remote add origin https://github.com/YOUR_USERNAME/f1-hub.git

# Push to GitHub
git push -u origin main
```

### Step 3: Deploy on Streamlit Community Cloud

1. **Go to** [share.streamlit.io](https://share.streamlit.io)
2. **Sign in** with your GitHub account
3. **Click** "New app"
4. **Select**:
   - Repository: `YOUR_USERNAME/f1-hub`
   - Branch: `main`
   - Main file path: `app/main.py`
5. **Click** "Advanced settings" and add your secrets:
   ```toml
   GOOGLE_API_KEY = "your_google_api_key_here"
   SUPABASE_URL = "your_supabase_url_here"
   SUPABASE_KEY = "your_supabase_key_here"
   ```
6. **Click** "Deploy!"

Your app will be live at: `https://your-app-name.streamlit.app`

---

## Configuration Files

### `.streamlit/config.toml`

Production configuration for optimal performance and appearance:

```toml
[theme]
primaryColor = "#FF1801"
backgroundColor = "#0B0C10"
secondaryBackgroundColor = "#1F2833"
textColor = "#FFFFFF"
font = "sans serif"

[server]
headless = true
port = 8501
enableCORS = false
enableXsrfProtection = true

[browser]
gatherUsageStats = false
serverAddress = "0.0.0.0"
```

### `.streamlit/secrets.toml.example`

Template for secrets (actual secrets go in Streamlit Cloud UI):

```toml
# Example secrets file - DO NOT commit actual secrets!
# Copy this to secrets.toml for local development

# Google AI Configuration
GOOGLE_API_KEY = "your_google_api_key_here"

# Supabase Configuration
SUPABASE_URL = "your_supabase_project_url_here"
SUPABASE_KEY = "your_supabase_anon_key_here"
```

---

## Accessing Secrets in Code

Streamlit provides a built-in way to access secrets:

```python
import streamlit as st

# Access secrets (works both locally and in production)
google_api_key = st.secrets["GOOGLE_API_KEY"]
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_KEY"]
```

**You'll need to update your code** to use `st.secrets` instead of `os.getenv()` for production deployment.

---

## GitHub Actions for Advanced Deployment

If you want to use GitHub Actions to deploy to other platforms, here's a basic workflow:

### `.github/workflows/deploy.yml`

```yaml
name: Deploy to Railway

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to Railway
        uses: bervproject/railway-deploy@main
        with:
          railway_token: ${{ secrets.RAILWAY_TOKEN }}
          service: f1-hub
```

---

## Pre-Deployment Checklist

Before deploying, ensure:

- [ ] All secrets are in `.gitignore` (`.env`, `.streamlit/secrets.toml`)
- [ ] `requirements.txt` includes all dependencies with correct versions
- [ ] `.streamlit/config.toml` is configured for production
- [ ] Code uses `st.secrets` for environment variables (not `os.getenv()`)
- [ ] FastF1 cache directory is excluded from git (it's large)
- [ ] Database credentials are valid and accessible from external IPs
- [ ] Google API key has Gemini API enabled
- [ ] README.md has deployment instructions

---

## Troubleshooting

### Common Issues

**1. "Module not found" errors**
- Solution: Ensure all imports are in `requirements.txt` with correct versions

**2. "Secrets not found"**
- Solution: Add secrets in Streamlit Cloud settings (not in code)

**3. "Database connection failed"**
- Solution: Check if Supabase allows connections from external IPs (it should by default)

**4. "App keeps restarting"**
- Solution: Check resource usage - Streamlit Cloud has 1GB RAM limit

**5. "FastF1 taking too long to load"**
- Solution: FastF1 cache builds on first run, subsequent loads are faster

### Performance Tips

1. **Use caching**: Already implemented with `@st.cache_data`
2. **Limit data queries**: Only fetch what you need
3. **Optimize images**: Use SVG for track maps (already done)
4. **Lazy loading**: Load AI models only when needed

---

## Custom Domain (Optional)

Once deployed on Streamlit Cloud:

1. Go to your app settings
2. Click "Custom domain"
3. Add your domain (e.g., `f1hub.yourdomain.com`)
4. Configure DNS with provided CNAME records

---

## Cost Estimates

| Platform | Free Tier | Paid Tier | Best For |
|----------|-----------|-----------|----------|
| **Streamlit Cloud** | ✅ Free forever | N/A | Personal projects, demos |
| **Railway** | 500 hrs/month free | $5-20/month | Small to medium apps |
| **Render** | 750 hrs/month free | $7+/month | Production apps |
| **Heroku** | ❌ No free tier | $7+/month | Enterprise apps |
| **Google Cloud Run** | Free tier generous | ~$1-5/month | Scalable apps |

---

## Next Steps

1. ✅ Review the deployment checklist above
2. ✅ Update code to use `st.secrets` instead of `os.getenv()`
3. ✅ Push your code to GitHub
4. ✅ Deploy on Streamlit Community Cloud
5. ✅ Test the deployed app thoroughly
6. ✅ (Optional) Set up custom domain

---

## Support

- **Streamlit Docs**: https://docs.streamlit.io/streamlit-community-cloud
- **Streamlit Forum**: https://discuss.streamlit.io
- **FastF1 Docs**: https://docs.fastf1.dev

---

## Security Best Practices

> [!WARNING]
> **Never commit secrets to GitHub!**

- ✅ Always use `.gitignore` for `.env` and `secrets.toml`
- ✅ Use environment variables/secrets management
- ✅ Rotate API keys if accidentally committed
- ✅ Use read-only database keys when possible
- ✅ Enable XSRF protection in production
