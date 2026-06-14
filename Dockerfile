FROM python:3.11-slim

# ---- environment settings ----
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/app

# ---- working directory ----
WORKDIR /app

# ---- install dependencies first (better layer caching) ----
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- copy project ----
COPY . .

# ---- default command (overridden by compose anyway) ----
CMD ["python", "app/scraper.py"]