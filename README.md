# Reddit PC Deals Tracker

A full-stack Python system that scrapes PC hardware deals from Reddit, classifies and scores them by category and value tier, persists historical data, and exposes both a web dashboard and email alerting system for high-signal deals.

---

## Overview

This project continuously monitors PC hardware deal subreddits, extracts structured deal information from unstructured posts, and transforms them into a searchable dataset with filtering, sorting, and alerting capabilities.

It is designed as a lightweight deal intelligence pipeline:

- **Ingestion:** Reddit API scraping
- **Processing:** classification, price extraction, deduplication
- **Storage:** append-only CSV history
- **Presentation:** Flask-based dashboard + email summaries

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
- Append-only CSV-based historical dataset
- Enables offline analysis and trend tracking

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

---

## Configuration

Create an .env file in the project root:
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

---

## Installation
```bash
git clone <repo-url>
cd reddit-pc-deals-tracker

python -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

pip install -r requirements.txt
```
---

## Running the System

### Scraper + Pipeline
```bash
python scraper.py
```
Runs continuously, collecting and processing deals every 30 minutes.

### Web Dashboard
```bash
python app.py
```
Then visit:
```text
http://localhost:5000
```
---

## Data Schema

Each deal is stored with:

- **highlight** – whether it matches target models
- **part** – hardware category (GPU, CPU, etc.)
- **deal_tier** – GREAT / GOOD / OK
- **created** – UTC timestamp
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
Migration from CSV → SQLite or DuckDB for query flexibility
SQL-like filtering and sorting in the web UI
Improved deal scoring model (replacing static tiers)
Reduced email frequency via event-based alerting
Optional real-time notifications (Discord / push)
