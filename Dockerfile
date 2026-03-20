FROM python:3.11-slim

# Prevent interactive prompts during package install
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system deps needed by matplotlib / fastf1
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# FastF1 disk cache directory (mounted as volume for persistence)
RUN mkdir -p /app/cache

EXPOSE 8501

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
