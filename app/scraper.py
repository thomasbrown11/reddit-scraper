import os # built-in python library for environment variables
from dotenv import load_dotenv # import private info
import praw # for reddit api interaction
from datetime import datetime, timezone, timedelta
import csv # for csv file exports
import time # automate scraping
import re # for regex matching
import smtplib # for sending emails
from email.message import EmailMessage # for email message creation
from pathlib import Path # dynamic reference for data file creation 
from zoneinfo import ZoneInfo # support time zone sleep rules
import json # for config values
import traceback

from database import initialize_database, insert_deal, cleanup_old_deals #import from manually created database.py

# Go up two directories from current file and then into a 'data' folder
DATA_DIR = Path(__file__).parent.parent / "data"
# make data directory if it doesn't exist, don't crash if it exists. make parent directories as well if missing (not relevant)
DATA_DIR.mkdir(parents=True, exist_ok=True)

initialize_database() #cread db file if it doesn't exist

load_dotenv()  # Load environment variables from .env file

# praw is an api tool to interact with the reddit api. praw.Reddit() passes in dev creds for api usage
reddit = praw.Reddit(
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    username=os.getenv("USERNAME"),
    password=os.getenv("PASSWORD"),
    user_agent=os.getenv("USER_AGENT")
)

#######################################
# Seen IDs helper functions 
#######################################

# def load_seen_ids(filepath="/app/data/seen_ids.txt"):
#     try:
#         with open(filepath, "r") as f:
#             return set(line.strip() for line in f if line.strip())
#     except FileNotFoundError:
#         return set()

SEEN_IDS_FILE = DATA_DIR / "seen_ids.txt"
    
def load_seen_ids(filepath=SEEN_IDS_FILE):
    try:
        with open(filepath, "r") as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()

# def save_seen_ids(seen_ids, filepath="/app/data/seen_ids.txt"):
#     with open(filepath, "w") as f:
#         for post_id in seen_ids:
#             f.write(post_id + "\n")

def save_seen_ids(seen_ids, filepath=SEEN_IDS_FILE):
    with open(filepath, "w") as f:
        for post_id in seen_ids:
            f.write(post_id + "\n")

#######################################
# Price extraction
#######################################

def price_to_float(price_str):
    """
    Converts '$1,199.99' -> 1199.99
    Returns None if conversion fails.
    """
    try:
        return float(
            price_str.replace("$", "").replace(",", "")
        )
    except (ValueError, AttributeError):
        return None


def extract_price(title):
    prices = re.findall(r"\$\d[\d,]*(?:\.\d{1,2})?", title)

    if not prices:
        return ""

    try:
        # use largest dollar value found in title
        return max(prices, key=price_to_float)
    except Exception:
        return ""

#######################################
# Deal evaluation
#######################################

def evaluate_price(title, models_config):
    title_l = title.lower()

    price_str = extract_price(title)
    if not price_str:
        return ""

    price = price_to_float(price_str)
    if price is None:
        return ""

    best_tier = ""

    for model, meta in models_config.items():

        if model not in title_l:
            continue

        base = meta.get("base_price")

        if not isinstance(base, (int, float)):
            continue

        try:
            discount = (base - price) / base
        except ZeroDivisionError:
            continue

        if discount >= 0.25:
            return "GREAT"

        elif discount >= 0.10:
            best_tier = "GOOD"

        elif discount >= 0:
            best_tier = "OK"

    return best_tier

#######################################
# Config
#######################################

# Load config.json (must be in project root)

CONFIG_FILE = DATA_DIR.parent / "config.json"

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
#with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# hard filter for unwanted posts 
# buildapcsales uses a flair system to categorize by part type or expired.. reference with .link_flair_text
# hardwareswap uses a flair system to categorize by SELLING, BUYING, TRADING, or CLOSED
EXCLUDED_FLAIRS = config["excluded_flairs"]

# object map sorts posts to cateogry based on string match 
PART_KEYWORDS = config["part_keywords"]

KEYWORD_TO_PART = {
    kw.lower().strip(): part
    for part, keywords in PART_KEYWORDS.items()
    for kw in keywords
}

# substring matches for target models for highlight flag (and email?)
TARGET_MODELS = config["target_models"]

#######################################
# Email (summary + attachment)
#######################################

def send_summary_email(matched_posts):
    from_addr = os.getenv("EMAIL_ADDRESS")
    to_addr = os.getenv("EMAIL_ADDRESS")

    subject = "💰 PC Deals Summary"
    lines = []

    highlighted_posts = []

    def add_post_list(posts):
        for p in posts:
            lines.append(
                f"- {p.get('title', '')} {p.get('price', '')}\n"
                f"  {p.get('url', '')}"
            )

    # ---------------------------------
    # Deal sections (GREAT/GOOD/OK)
    # ---------------------------------
    for part, posts in matched_posts.items():

        great = [p for p in posts if p.get("deal_tier") == "GREAT"]
        good  = [p for p in posts if p.get("deal_tier") == "GOOD"]
        ok    = [p for p in posts if p.get("deal_tier") == "OK"]

        if great or good or ok:

            lines.append(f"\n=== {part} ===")

            if great:
                lines.append("\n🔥 GREAT DEALS")
                add_post_list(great)

            if good:
                lines.append("\n🟢 GOOD DEALS")
                add_post_list(good)

            if ok:
                lines.append("\n🟡 OK DEALS")
                add_post_list(ok)

        # collect highlighted posts that do NOT already
        # have a deal tier
        highlighted_posts.extend(
            p for p in posts
            if p.get("highlight") == "YES"
            and not p.get("deal_tier")
        )

    # ---------------------------------
    # Highlight section
    # ---------------------------------
    if highlighted_posts:

        lines.append("\n=== OTHER TARGET MODEL DEALS ===")

        for p in highlighted_posts:
            lines.append(
                f"- [{p.get('part', 'Unknown')}] "
                f"{p.get('title', '')} "
                f"{p.get('price', '')}\n"
                f"  {p.get('url', '')}"
            )

    body = "\n".join(lines).strip()

    if not body:
        body = "No deals found this run."

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    # LATEST_CSV = "/app/data/latest_deals.csv"
    LATEST_CSV = DATA_DIR / "latest_deals.csv"

    if os.path.exists(LATEST_CSV):
        with open(LATEST_CSV, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="text",
                subtype="csv",
                filename="latest_deals.csv"
            )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(from_addr, os.getenv("EMAIL_PASSWORD"))
            smtp.send_message(msg)

        print("📧 Summary email sent successfully.")

    except Exception as e:
        print("❌ Failed to send summary email:", e)

#######################################
# CSV export (HISTORY + LATEST)
#######################################

def export_to_csv(matched_posts):

    # history_file = "/app/data/deals_history.csv"
    history_file = DATA_DIR / "deals_history.csv"

    # latest_file = "/app/data/latest_deals.csv"
    latest_file = DATA_DIR / "latest_deals.csv"

    fieldnames = [
        "source", "source_id", "highlight", "deal_tier", "part",
        "created_utc", "price", "title", "url",
        "subreddit", "flair"
    ]

    # -----------------------------
    # 1. APPEND TO HISTORY
    # -----------------------------

    # history_exists = os.path.isfile(history_file)

    history_exists = history_file.exists()

    with open(history_file, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not history_exists:
            writer.writeheader()

        for part, posts in matched_posts.items():
            for post in posts:
                row = {"part": part} # may be redundant? 
                row.update(post) # may be redundant? 
                writer.writerow(row)

    # -----------------------------
    # 2. OVERWRITE LATEST
    # -----------------------------
    with open(latest_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for part, posts in matched_posts.items():
            for post in posts:
                row = {"part": part}
                row.update(post)
                writer.writerow(row)

#######################################
# Scraper
#######################################

def run_scraper():

    total_seen = 0
    total_skipped_old = 0
    total_skipped_flair = 0
    total_skipped_no_match = 0
    total_skipped_already_seen = 0 # new 
    total_processed = 0
    total_errors = 0

    seen_ids = load_seen_ids()

    one_month_ago = (
        datetime.now(timezone.utc)
        - timedelta(days=30)
    )

    MATCHED_POSTS = {
        "Case Fan": [],
        "CPU": [],
        "CPU Cooler": [],
        "GPU": [],
        "HDD": [],
        "Monitor": [],
        "Motherboard": [],
        "RAM": [],
        "SSD": [],
        "Bundle": []
    }

    for sub in ["buildapcsales", "techdeals", "pcdeals"]:

        try:
            for post in reddit.subreddit(sub).new(limit=50):

                try:
                    total_seen += 1

                    flair = (post.link_flair_text or "").lower()
                    title = (post.title or "").lower()

                    created_time = datetime.fromtimestamp(
                        post.created_utc,
                        tz=timezone.utc
                    )

                    formatted_time = created_time.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

                    ####################
                    # Filters
                    ####################

                    if post.id in seen_ids:
                        total_skipped_already_seen += 1
                        continue

                    if created_time < one_month_ago:
                        total_skipped_old += 1
                        continue

                    if any(
                        substring in flair
                        for substring in EXCLUDED_FLAIRS
                    ):
                        total_skipped_flair += 1
                        continue

                    ####################
                    # Category detection
                    ####################

                    matched_parts = set()

                    for kw, part in KEYWORD_TO_PART.items():
                        if re.search(rf"\b{re.escape(kw)}\b", title):
                            matched_parts.add(part)

                    if not matched_parts:
                        total_skipped_no_match += 1
                        continue

                    # title_norm = re.sub(r'[^a-z0-9]+', '', title.lower())

                    # matched_parts = set()

                    # for kw, part in KEYWORD_TO_PART.items():
                    #     kw_norm = re.sub(r'[^a-z0-9]+', '', kw.lower())

                    #     if kw_norm in title_norm:
                    #         matched_parts.add(part)

                    # if not matched_parts:
                    #     total_skipped_no_match += 1
                    #     continue

                    is_bundle = len(matched_parts) > 1

                    category = (
                        "Bundle"
                        if is_bundle
                        else list(matched_parts)[0]
                    )

                    ####################
                    # Highlight logic
                    ####################

                    is_target = any(
                        target in title
                        for target in TARGET_MODELS
                    )

                    ####################
                    # Deal logic
                    ####################

                    deal_tier = evaluate_price(
                        title,
                        TARGET_MODELS
                    )

                    ####################
                    # Append
                    ####################

                    deal = {
                        "source": "reddit",
                        "source_id": post.id,

                        "part": category,
                        "title": post.title,
                        "url": post.url,
                        "subreddit": sub,
                        "flair": post.link_flair_text,
                        "created_utc": formatted_time,
                        "highlight": "YES" if is_target else "",
                        "deal_tier": deal_tier,
                        "price": extract_price(post.title)
                    }

                    # Add to MATCHED_POSTS for csv exports/email
                    MATCHED_POSTS[category].append(deal)

                    # insert into deals.db deals table
                    insert_deal(deal)

                    # add to seen_ids only after successful post
                    seen_ids.add(post.id) 

                    # increment count if successful post
                    total_processed += 1

                except Exception as e:
                    total_errors += 1
                    print(
                        f"⚠️ Skipping post "
                        f"{getattr(post, 'id', 'unknown')}: {e}"
                    )
                    traceback.print_exc()
                    continue

        except Exception as e:
            print(f"❌ Failed to read subreddit {sub}: {e}")
            traceback.print_exc()
            continue

    # After your scraping logic finishes
    # export_to_csv_append(MATCHED_POSTS)
    export_to_csv(MATCHED_POSTS)

    #Save all seen_ids to file
    save_seen_ids(seen_ids)

    print("\n📊 SCRAPER SUMMARY")
    print(f"Total posts seen: {total_seen}")
    print(f"Skipped (too old): {total_skipped_old}")
    print(f"Skipped (flair): {total_skipped_flair}")
    print(f"Skipped (Already Seen): {total_skipped_already_seen}")
    print(f"Skipped (no category match): {total_skipped_no_match}")
    print(f"Processed (passed filters): {total_processed}")
    print(f"Errors: {total_errors}\n")

    ####################
    # Send email
    ####################
    # try:
    #     send_summary_email(MATCHED_POSTS)
    #     print("📧 Summary email sent")
    # except Exception as e:
    #     print("⚠️ Email failed:", e)
    #     traceback.print_exc()

    ####################
    # Send email (gated)
    ####################
    try:
        now = datetime.now(ZoneInfo("America/New_York"))

        within_hours = 8 <= now.hour < 23
        has_new_deals = total_processed > 0

        if within_hours and has_new_deals:
            send_summary_email(MATCHED_POSTS)
            print("📧 Summary email sent")
        else:
            if not within_hours:
                print("📭 Email skipped (outside 8am–11pm window)")
            if not has_new_deals:
                print("📭 Email skipped (no new deals)")
    except Exception as e:
        print("⚠️ Email failed:", e)
        traceback.print_exc()

    ####################
    # DB cleanup
    ####################
    try:
        cleanup_old_deals()
        print("🧹 Cleaned up old deals (>30 days)")
    except Exception as e:
        print("⚠️ Cleanup failed:", e)
        traceback.print_exc()

#######################################
# Main loop
#######################################

while True:
    print("🔁 Running scraper at", datetime.now())

    try:
        run_scraper()

    except Exception as e:
        print("❌ Unhandled error in run_scraper:")
        print(e)
        time.sleep(5 * 60) # Retry after 5 minutes if an error occurs
        continue

    print("✅ Done. Sleeping for 30 minutes.\n")
    time.sleep(30 * 60) # Sleep for 30 minutes