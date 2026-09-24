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

# Docker build/run instructions:
#   1) Build the image:
#      docker build -t fastf1_pitwall .
#
#   2) Run the container:
#      docker run --rm -p 8501:8501 \
#        -v "$PWD/cache:/app/cache" \
#        --name fastf1-pitwall \
#        fastf1_pitwall
#
#   3) Open the app in a browser:
#      http://localhost:8501

EXPOSE 8501

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]