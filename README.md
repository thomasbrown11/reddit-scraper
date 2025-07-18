# Reddit PC Deals Scraper

A Python script that scrapes recent PC hardware deals from multiple subreddits, filters and categorizes them by part type, highlights targeted models, extracts price info, and sends email alerts for important deals. It saves all deal data to a CSV file and keeps track of processed posts to avoid duplicates.

---

## Features

- Scrapes posts from subreddits: `buildapcsales`, `hardwareswap`, `techdeals`, and `pcdeals`.
- Filters posts by flair and keywords to categorize hardware parts (GPU, CPU, SSD, etc.).
- Extracts price from post titles when available.
- Highlights and emails notifications for specific targeted models.
- Saves matched deals in an append-only CSV file.
- Avoids duplicate processing by tracking seen post IDs.
- Runs continuously every 30 minutes with error handling.

---

## Requirements

- Python 3.7 or higher
- Reddit API credentials (client ID, secret, username, password, user agent... save to a local .ENV file in same directory)
    .env: 
        CLIENT_ID=your_reddit_client_id
        CLIENT_SECRET=your_reddit_client_secret
        USERNAME=your_reddit_username
        PASSWORD=your_reddit_password
        USER_AGENT=your_user_agent_string
        EMAIL_ADDRESS=your_gmail_address@gmail.com
        EMAIL_PASSWORD=your_gmail_app_password

- Gmail account with "App Password" enabled for email notifications
- Libraries:
  - `praw`
  - `python-dotenv`

---

## Installation

1. Clone the repository or copy the script files to your local machine.

2. Create and activate a Python virtual environment (optional but recommended):

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # macOS/Linux
   venv\Scripts\activate     # Windows

3. Install dependencies: 

    pip install -r requirements.txt


