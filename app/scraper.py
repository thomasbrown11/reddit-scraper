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
import logging # use logging for docker logs
import traceback # detailed stack trace error handling readouts
#import from manually created database.py
from database import initialize_database, insert_deal, cleanup_old_deals, already_seen

#######################################
# logging init
#######################################

# output like 2026-06-17 10:32:04 INFO Summary email sent
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# user with logger.info()
logger = logging.getLogger(__name__)

#######################################
# Database init
#######################################

# Go up two directories from current file and then into a 'data' folder
DATA_DIR = Path(__file__).parent.parent / "data"
# make data directory if it doesn't exist, don't crash if it exists. make parent directories as well if missing (not relevant)
DATA_DIR.mkdir(parents=True, exist_ok=True)

initialize_database() #cread db file if it doesn't exist

#######################################
# env init 
#######################################

load_dotenv()  # Load environment variables from .env file

#######################################
# Reddit API Client init 
#######################################

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

# open seen_ids.txt and return set (hashset for quick lookup) of seen values  
def load_seen_ids(filepath=SEEN_IDS_FILE):
    try:
        # open in read mode
        with open(filepath, "r") as f:
            # return set of non-empty lines from file after stripping leading space/newline chars 
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        # # return empty set if no file is found
        return set() 

# def save_seen_ids(seen_ids, filepath="/app/data/seen_ids.txt"):
#     with open(filepath, "w") as f:
#         for post_id in seen_ids:
#             f.write(post_id + "\n")

# save new seen_ids set as new lines to seen_ids.txt by replacing file
def save_seen_ids(seen_ids, filepath=SEEN_IDS_FILE):
    # open in write mode
    with open(filepath, "w") as f:
        # loop seen_ids, and add newline char to each line. Overwrite file (no append)
        for post_id in seen_ids:
            f.write(post_id + "\n")

#######################################
# Price extraction
#######################################

# string to floating point integer conversion 
def price_to_float(price_str):
    try:
        return float(
            # strip $ and , chars. convert from string to float 
            price_str.replace("$", "").replace(",", "")
        )
    except (ValueError, AttributeError):
        # None rather than 0 for conversion failure testing
        return None 

# extracs largest dollar amount from title, returns as string
def extract_price(title):
    """
    Extracts largest dollar amount from title.

    Returns:
        str: price like "$1,299.99"
        "" : no price found (Python None breaks email logic in later functions)
    """
    # use regex module, findall price pattern matches and return as list
    prices = re.findall(r"\$\d[\d,]*(?:\.\d{1,2})?", title)

    # if no prices then return empty
    if not prices:
        return ""

    try:
        # use largest dollar value found in title, comparing as float
        # return largest float as original string (so returns "$120.99" vs 120.99)
        return max(prices, key=price_to_float)
    except Exception:
        return ""

#######################################
# Deal evaluation
#######################################

# return great, good, ok deal designation to insert into deal_tier per post
def evaluate_price(title, models_config):

    # convert title to all lowercase for model comparison
    title_l = title.lower()

    # get price, if no price exit and return empty string
    price_str = extract_price(title)
    if not price_str:
        return ""

    # convert price to float for comparison to base price
    # if price can't be converted return empty string
    price = price_to_float(price_str)
    if price is None:
        return ""

    best_tier = ""

    # loop through all target_models from config file
    # meta references model value which is an object containing {"base_price": INT}
    for model, meta in models_config.items():

        if model not in title_l:
            continue
        
        # extract base price 
        base = meta.get("base_price")

        # error handling for base base_price insert in config file
        # confirm int or float value only
        if not isinstance(base, (int, float)):
            continue
        
        # this returns a percentage difference as a floating point value 
        # if base 400, price 300, then returns .25
        try:
            discount = (base - price) / base
        # protect against dividing by 0 (if base_price was set to 0)
        except ZeroDivisionError:
            continue

        # categorize as great is 25% discount or greater
        if discount >= 0.25:
            return "GREAT"

        # good deal if 10-24%
        elif discount >= 0.10:
            best_tier = "GOOD"

        # ok deal is 1-95 discount
        elif discount >= 0:
            best_tier = "OK"

    return best_tier

#######################################
# Config
#######################################

# Load config.json (must be in project root)

# load project root/config.json
CONFIG_FILE = DATA_DIR.parent / "config.json"

# create file object f, use json modele to load json object as python object
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
#with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# hard filter for unwanted posts 
# buildapcsales uses a flair system to categorize by part type or expired.. reference with .link_flair_text
# hardwareswap uses a flair system to categorize by SELLING, BUYING, TRADING, or CLOSED
EXCLUDED_FLAIRS = config["excluded_flairs"]

# object map sorts posts to cateogry based on string match 
PART_KEYWORDS = config["part_keywords"]

# convert {category: [keywords]} to {normalized keyword: category} lookup table
# ie {'GPU' : ['4080', '4090', 9070xt']} becomes: {'4080': 'GPU', '4090: 'GPU', '9070xt' : 'GPU'}
KEYWORD_TO_PART = {
    # Dictionary comprehension syntax
    # return inner keyword: category for each inner keyword
    # to lowercase and strip whitespace for each part
    kw.lower().strip(): part
    # first iter: part = GPU, keywords ["4080", ...]
    for part, keywords in PART_KEYWORDS.items()
    # for each value in keywords, do expression above
    for kw in keywords
}

# substring matches for target models for highlight flag (and email?)
TARGET_MODELS = config["target_models"]

#######################################
# Email (summary + attachment)
#######################################

def send_summary_email(matched_posts):

    # from and to both as app user email address
    from_addr = os.getenv("EMAIL_ADDRESS")
    to_addr = os.getenv("EMAIL_ADDRESS")

    # email subject line
    subject = "💰 PC Deals Summary"

    # init list that represents lines of the email body 
    lines = []

    # init list collection of target model posts with no deals
    highlighted_posts = []

    # helper. loop through built post list and append lines to email body like 
    # each append is a single string, but with a newline so ends up appending lines like: 
    # - 7800X3D $299 $299\n https://reddit.com/post2
    # displays like:
    # - 7800X3D $299 $299
    # https://reddit.com/post2
    # this allows each string to be seen as a single element despite having 2 lines
    # allows for things like: body = "\n".join(lines) which inserts linebreaks between posts
    def add_post_list(posts):
        for p in posts:
            lines.append(
                # f = formatted string. like: - RTX 5070 $499 $499\n
                f"- {p.get('title', '')} {p.get('price', '')}\n"
                # like: https://reddit.com/post1"
                f"  {p.get('url', '')}"
            )

    # ---------------------------------
    # Deal sections (GREAT/GOOD/OK)
    # ---------------------------------

    # loop over MATCHED_POSTS. One iteration per category
    # if deals, create organized deals section with truncated post lines, append to email body 
    for part, posts in matched_posts.items():

        # matched_posts passsed in like: 
        # MATCHED_POSTS = {
        #     "GPU": [{"title": "4070 Super $499","deal_tier": "GREAT"},{"title": "9070 XT $599","deal_tier": "GOOD"}],
        #     "CPU": [ { "title": "7800X3D $299", ... } ]
        # }
        # part = category name ("GPU", "CPU", etc.)
        # posts = list of deal dictionaries in that category

        # list comprehensions of posts. Returns new sub list of the original post list with only deal_tier = x values
        great = [p for p in posts if p.get("deal_tier") == "GREAT"]
        good  = [p for p in posts if p.get("deal_tier") == "GOOD"]
        ok    = [p for p in posts if p.get("deal_tier") == "OK"]

        # if at least one deal_tier value exists in category posts:
        if great or good or ok:
            
            # make cateogry header in email body
            lines.append(f"\n=== {part} ===")

            if great:
                # make great header
                lines.append("\n🔥 GREAT DEALS")
                # append formatted post line to body 
                add_post_list(great)

            if good:
                # make good header
                lines.append("\n🟢 GOOD DEALS")
                add_post_list(good)

            if ok:
                # make okay header
                lines.append("\n🟡 OK DEALS")
                add_post_list(ok)

        # collect highlighted posts that do NOT already have a deal tier value
        # using extend to make a single flat highlight post list to append to email vs
        # using append to get a list of lists like: [[GPU hilite posts], [CPU hilite posts], ...]
        highlighted_posts.extend(
            # list comprehension
            # include target model posts that don't have a significant discount
            p for p in posts
            if p.get("highlight") == "YES"
            and not p.get("deal_tier")
        )

    # ---------------------------------
    # Highlight section
    # ---------------------------------
    if highlighted_posts:

        # append generic header for non-deal posts that still match target models
        lines.append("\n=== OTHER TARGET MODEL DEALS ===")

        # append formatted line to email body per highlighted post item
        for p in highlighted_posts:
            lines.append(
                f"- [{p.get('part', 'Unknown')}] "
                f"{p.get('title', '')} "
                f"{p.get('price', '')}\n"
                f"  {p.get('url', '')}"
            )

    # join all appended lines with new line seperators between
    # remove whitespace from beginning and end of lines
    body = "\n".join(lines).strip()

    # handler for no posts pertaining to target models
    if not body:
        body = "No deals found this run."

    # build email message
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    # get csv file containing all pertinent new posts
    # this includes posts with part_keywords string matches meaning no target model match
    LATEST_CSV = DATA_DIR / "latest_deals.csv"

    if os.path.exists(LATEST_CSV):
        # open in Read Binary mode (raw bytes)
        # this supports emailing which also transmits in raw bytes
        with open(LATEST_CSV, "rb") as f:
            msg.add_attachment(
                # f is file object, must be read to get contents
                # attach to email message
                f.read(),
                maintype="text",
                subtype="csv",
                filename="latest_deals.csv"
            )

    try:
        # use built in smtp communication library
        # reference gmail outgoing mail server at port 465 (SMTP over ssl/tls)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            # pass email address and generated gmail app pw
            smtp.login(from_addr, os.getenv("EMAIL_PASSWORD"))
            # send message via smtp
            smtp.send_message(msg)

        # print("📧 Summary email sent successfully.")
        logger.info("Summary email sent")

    except Exception:
    # except Exception as e:
        # print("❌ Failed to send summary email:", e)
        logger.exception("❌ Failed to send summary email")

#######################################
# CSV export (HISTORY + LATEST)
#######################################

def export_to_csv(matched_posts):

    # comprehensive deals csv containing all collected posts
    # now redundant with database.py 
    # history_file = "/app/data/deals_history.csv"
    history_file = DATA_DIR / "deals_history.csv"

    # contains only new posts that passed part_keywords/target_model filtering on current run
    # latest_file = "/app/data/latest_deals.csv"
    latest_file = DATA_DIR / "latest_deals.csv"

    # standardized csv columns for exported deals
    # note that posts need to pass values in this order to work properly
    fieldnames = [
        "source", "source_id", "highlight", "deal_tier", "part",
        "created_utc", "price", "title", "url",
        "subreddit", "flair"
    ]

    # redundant section. deals_history is replaced by deals.db and doesn't need to exist
    # -----------------------------
    # 1. APPEND TO HISTORY
    # -----------------------------

    # history_exists = os.path.isfile(history_file)

    # history_exists = history_file.exists()

    # with open(history_file, mode='a', newline='', encoding='utf-8') as f:
    #     writer = csv.DictWriter(f, fieldnames=fieldnames)

    #     if not history_exists:
    #         writer.writeheader()

    #     for part, posts in matched_posts.items():
    #         for post in posts:
    #             row = {"part": part} # may be redundant? 
    #             row.update(post) # may be redundant? 
    #             writer.writerow(row)

    # -----------------------------
    # 2. OVERWRITE LATEST
    # -----------------------------

    # open latest_deals.csv in write mode as f
    with open(latest_file, mode='w', newline='', encoding='utf-8') as f:
        # use built in csv python module
        # pass file object to dictionary writer with fieldnames as dictionary keys in expected order
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        # write column names as first row
        writer.writeheader()

        # write one row to csv per post in matched_posts
        # _, posts on .items() is equivalent to for posts in matched_posts.values():
        # just get each category's values (post dict list) and inner loop looops over the dicts
        for _, posts in matched_posts.items():
            for post in posts:
                writer.writerow(post)

#######################################
# Scraper
#######################################

def run_scraper():

    # counts for console stdout
    total_seen = 0
    total_skipped_old = 0
    total_skipped_flair = 0
    total_skipped_no_match = 0
    total_skipped_already_seen = 0 # new 
    total_processed = 0
    total_errors = 0

    # seen_ids = load_seen_ids() # redundant

    # used to discard stale posts.. should maybe move to 2 weeks instead
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

                    # early check for duplicate post
                    # table schema already handles uniqueness but this saves loop processing
                    # if post.id in seen_ids:
                    if already_seen("reddit", post.id):
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
                    # MATCHED_POSTS[category].append(deal)

                    # insert into deals.db deals table
                    # inserted boolean true if success
                    inserted = insert_deal(deal)

                    if inserted:
                        # Add to MATCHED_POSTS for csv exports/email
                        MATCHED_POSTS[category].append(deal)

                        total_processed += 1
                    else: 
                        total_skipped_already_seen += 1

                    # add to seen_ids only after successful post
                    # seen_ids.add(post.id) # redundant

                    # increment count if successful post
                    # total_processed += 1

                except Exception:
                # except Exception as e:
                    total_errors += 1
                    # print(
                    #     f"⚠️ Skipping post "
                    #     f"{getattr(post, 'id', 'unknown')}: {e}"
                    # )
                    # traceback.print_exc()
                    logger.exception(
                        "⚠️ Skipping post %s",
                        getattr(post, "id", "unknown")
                    )
                    continue
        except Exception:
        # except Exception as e:
            # print(f"❌ Failed to read subreddit {sub}: {e}")
            # traceback.print_exc()
            logger.exception(
                "❌ Failed to read subreddit %s",
                sub
            )
            continue

    # After your scraping logic finishes
    # export_to_csv_append(MATCHED_POSTS)
    export_to_csv(MATCHED_POSTS)

    # Save all seen_ids to file
    # save_seen_ids(seen_ids) # redundant

    # print("\n📊 SCRAPER SUMMARY")
    # print(f"Total posts seen: {total_seen}")
    # print(f"Skipped (too old): {total_skipped_old}")
    # print(f"Skipped (flair): {total_skipped_flair}")
    # print(f"Skipped (Already Seen): {total_skipped_already_seen}")
    # print(f"Skipped (no category match): {total_skipped_no_match}")
    # print(f"Processed (passed filters): {total_processed}")
    # print(f"Errors: {total_errors}\n")

    # detailed logger output for docker stdout
    logger.info("📊 SCRAPER SUMMARY")
    logger.info("Total posts seen: %s", total_seen)
    logger.info("Skipped (too old): %s", total_skipped_old)
    logger.info("Skipped (flair): %s", total_skipped_flair)
    logger.info("Skipped (Already Seen): %s", total_skipped_already_seen)
    logger.info("Skipped (no category match): %s", total_skipped_no_match)
    logger.info("Processed (new deals inserted): %s", total_processed)
    logger.info("Errors: %s", total_errors)

    ####################
    # Send email (gated)
    ####################
    try:
        now = datetime.now(ZoneInfo("America/New_York"))

        within_hours = 8 <= now.hour < 23
        has_new_deals = total_processed > 0

        if within_hours and has_new_deals:
            send_summary_email(MATCHED_POSTS)
            # print("📧 Summary email sent")
            logger.info("📧 Summary email sent")
        else:
            if not within_hours:
                # print("📭 Email skipped (outside 8am–11pm window)")
                logger.info("📭 Email skipped (outside 8am–11pm window)")
            if not has_new_deals:
                # print("📭 Email skipped (no new deals)")
                logger.info("📭 Email skipped (no new deals)")
    except Exception:
    # except Exception as e:
        # print("⚠️ Email failed:", e)
        # traceback.print_exc()
        logger.exception("⚠️ Email failed")

    ####################
    # DB cleanup
    ####################
    try:
        cleanup_old_deals()
        # print("🧹 Cleaned up old deals (>30 days)")
        logger.info("🧹 Cleaned up old deals (>30 days)")
    except Exception:
    # except Exception as e:
        logger.exception("⚠️ Cleanup failed")
        # print("⚠️ Cleanup failed:", e)
        # traceback.print_exc()

#######################################
# Main loop
#######################################

while True:

    logger.info("🔁 Running scraper")

    try:
        run_scraper()

    except Exception: 
        logger.exception("❌ Unhandled error in run_scraper")
        logger.info("Retrying in 5 minutes")
        # Retry after 5 minutes if an error occurs
        time.sleep(5 * 60)
        continue

    logger.info("✅ Done. Sleeping for 30 minutes.")

    # Sleep for 30 minutes
    time.sleep(30 * 60)