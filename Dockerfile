# Base Image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies (LightGBM needs libgomp1)
RUN apt-get update && apt-get install -y \
    build-essential \
    libgomp1 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run command
CMD ["streamlit", "run", "app/main.py", "--server.address=0.0.0.0"]
