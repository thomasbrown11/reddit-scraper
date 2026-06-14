# Reddit PC Deals Tracker

A full-stack Python system that scrapes PC hardware deals from Reddit, classifies and scores them by category and value tier, persists historical data, and exposes a web dashboard, SQL query web ui, and email alerting system for high-signal deals.

---

## Overview

This project continuously monitors PC hardware deal subreddits, extracts structured deal information from unstructured posts, and transforms them into a searchable dataset with filtering, sorting, and alerting capabilities.

It is designed as a lightweight deal intelligence pipeline:

- **Ingestion:** Reddit API scraping
- **Processing:** classification, price extraction, deduplication
- **Storage:** append-only CSV history
- **Presentation:** Flask-based dashboard + email summaries

---

## Notes

- The system is designed to run headless via Docker (e.g., Raspberry Pi or server)
- All persistent state is stored in the ./data directory
- The scraper runs continuously inside a container (no manual execution needed)

---

## Features

### Data Collection

- Scrapes posts from:
	- buildapcsales
	- hardwareswap
	- techdeals
	- pcdeals

- Prevents duplicate processing via post ID tracking
- Runs continuously on a scheduled interval (default: 30 minutes)

### Deal Processing

- Extracts price data from unstructured titles
- Classifies deals into hardware categories:
	- GPU, CPU, RAM, SSD, Motherboard, Monitor, Bundle, etc.
- Applies deal tiering system:
	- GREAT / GOOD / OK
- Supports targeted model highlighting

### Storage

- Primary storage is SQLite (deals.db), with CSV exports for:

	- historical backups (deals_history.csv)
	- latest snapshot view (latest_deals.csv)

- SQLite is used for querying, filtering, and powering both the web dashboard and Datasette.

### Interfaces

- ### Web Dashboard (Flask)

	- Sort by price or creation date
	- Filter by category, tier, and keyword search
	- Color-coded deal tiers for quick scanning

- ### Email Alerts

	- Sends periodic summaries of matched/high-signal deals
	- Includes direct links to listings

---

## Tech Stack

- Python 3.7+
- Flask (web dashboard)
- Pandas (data processing & filtering)
- PRAW (Reddit API client)
- python-dotenv (environment config)
- Docker & Docker Compose
- SQLite (primary datastore)
- Datasette (SQL UI)

---

## Configuration

This project uses two configuration files:

### 1. Environment Variables (.env)

Used for authentication and external services.

Create a .env file in the project root:

```env
CLIENT_ID=your_reddit_client_id
CLIENT_SECRET=your_reddit_client_secret
USERNAME=your_reddit_username
PASSWORD=your_reddit_password
USER_AGENT=your_user_agent_string

EMAIL_ADDRESS=your_gmail_address@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
```
**Gmail requires an App Password for SMTP authentication.**

**NOTE:** These values are secrets and should never be committed to version control.

### 2. Scraper Configuration (config.json)

This file controls all scraping logic and classification behavior.

It defines:

- Which posts to exclude
- How posts are categorized into hardware parts
- Which models are considered “target deals”
- Thresholds used for highlighting deals in email alerts

Example:

```json
{
  "excluded_flairs": ["closed", "trading", "buying", "expired"],
  "part_keywords": {
    "GPU": ["gpu", "4070", "4080"],
    "CPU": ["cpu", "7800x3d"]
  },
  "target_models": {
    "7800x3d": { "base_price": 380 },
    "9070 xt": { "base_price": 650 }
  }
}
```
### Important Notes

- **"part_keywords"** is fully manual:
	- Controls how posts are categorized into parts (GPU, CPU, SSD, etc.)
	- Adding new hardware detection requires updating this list
- **"target_models"** is fully manual
	- Defines which products are tracked for “deal highlighting”
	- base_price is used as a threshold reference for email highlighting logic
- This file acts as the core rule engine for deal detection

---

## Why this structure exists

Separating .env and config.json allows:

- .env: environment-specific secrets
- config.json: tunable scraping + classification logic without code changes

---

## Local Installation for debugging

```bash
git clone https://github.com/thomasbrown11/reddit-scraper.git
cd reddit-scraper

python -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

pip install -r requirements.txt
```
---

## Running the System Locally

### Scraper + Pipeline

Running: 

```bash
python scraper.py
```
Runs continuously, collecting and processing deals every 30 minutes.

### Web Dashboard
Run: 

```bash
python app.py
```

Then visit:

```text
http://localhost:5000
```
---

## Docker Installation

This project is fully containerized using Docker Compose.

### 1. Clone the repo

```bash
git clone https://github.com/thomasbrown11/reddit-scraper.git
cd reddit-scraper
```

### 2. Create environment file

See Configuration section above

### 3. Run entire stack

```bash
docker compose up -d --build
```

---

## Docker commands: 

Start all services:

```bash
docker compose up -d --build
```

Stop all services:

```bash 
docker compose down
```

View logs:

See docker container status: 

```bash
docker compose ps 
```

See individual container logs: 

```bash
docker compose logs -f scraper
docker compose logs -f web
docker compose logs -f datasette
```

---

## Docker Architecture

The system runs as three Docker services:

- scraper: continuously scrapes Reddit and writes structured deal data
- web: Flask dashboard for browsing and filtering deals
- Datasette: SQLite web interface for direct SQL querying

All services share a persistent volume:

./data (host) is mounted to /app/data (containers)

This contains:
- deals.db (SQLite primary datastore)
- deals_history.csv (historical export)
- latest_deals.csv (latest snapshot)
- seen_ids.txt (deduplication state)

---

## Web UI interface

A flask dashboard is available for easy browsing of the database: 

http://localhost:5000 (or https://your-server:5000)

---

## Datasette Interface

A SQL-based exploration layer is available via Datasette:

http://localhost:8001 (or https://your-server:8001)

This allows direct querying of the underlying SQLite database for debugging, analysis, and ad-hoc inspection.

---

## Data Schema

Each deal is stored with:

- **highlight** – whether it matches target models
- **part** – hardware category (GPU, CPU, etc.)
- **deal_tier** – GREAT / GOOD / OK
- **created_utc** – UTC timestamp
- **price** – extracted price (if available)
- **title** – original post title
- **url** – direct link
- **subreddit** – source subreddit
- **flair** – Reddit flair

---

## Requirements
```txt
praw
python-dotenv
pandas
flask
```
---

## Future Improvements

- Improved deal scoring model (replacing static tiers)
- Reduced email frequency via event-based alerting
- Optional real-time notifications (Discord / push)

Docker-based production hardening:
- Add healthchecks for scraper, web, and datasette
- Add restart safety for scraper scheduling
- Prevent concurrent scraper runs (lock file or DB flag)
- Structured logging instead of print statements
