# syntax=docker/dockerfile:1
# OverwatcherPI Dashboard — Streamlit
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dashboard-specific deps
COPY dashboard/requirements-dashboard.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements-dashboard.txt

# Copy entire repo so dashboard can import from core/config
COPY . .

CMD ["streamlit", "run", "dashboard/app.py", \
     "--server.address", "0.0.0.0", \
     "--server.port", "8501", \
     "--server.headless", "true"]
