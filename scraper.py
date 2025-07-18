import os #built-in python library for environment variables
from dotenv import load_dotenv # import private info
import praw # for reddit api interaction
from datetime import datetime, timezone, timedelta
import csv # for csv file exports
import time # automate scraping
import re # for regex matching
import smtplib # for sending emails
from email.message import EmailMessage # for email message creation

load_dotenv()  # Load environment variables from .env file

# praw is an api tool to interact with the reddit api. praw.Reddit() passes in dev creds for api usage
reddit = praw.Reddit(
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    username=os.getenv("USERNAME"),
    password=os.getenv("PASSWORD"),
    user_agent=os.getenv("USER_AGENT")
)

# helper functions to load and save seen post IDS to deduplicate posts
#######################################

def load_seen_ids(filepath="seen_ids.txt"):
    try:
        with open(filepath, "r") as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()

def save_seen_ids(seen_ids, filepath="seen_ids.txt"):
    with open(filepath, "w") as f:
        for post_id in seen_ids:
            f.write(post_id + "\n")

#email helper function to send email notifications
#######################################

def send_email(subject, body, to_email):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("EMAIL_ADDRESS")
    msg["To"] = to_email
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(os.getenv("EMAIL_ADDRESS"), os.getenv("EMAIL_PASSWORD"))
            smtp.send_message(msg)
        print("📧 Email sent successfully.")
    except Exception as e:
        print("❌ Failed to send email:", e)

#Email helper function to send CSV file as an attachment
#######################################

def send_csv_email():
    from_addr = os.getenv("EMAIL_ADDRESS")
    to_addr = os.getenv("EMAIL_ADDRESS")
    subject = "📦 Daily PC Deals CSV"
    body = "Attached is your daily deals.csv export."

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    with open("deals.csv", "rb") as f:
        file_data = f.read()
        file_name = "deals.csv"
    
    msg.add_attachment(file_data, maintype="text", subtype="csv", filename=file_name)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(from_addr, os.getenv("EMAIL_PASSWORD"))
            smtp.send_message(msg)
        print("📧 CSV email sent successfully.")
    except Exception as e:
        print("❌ Failed to send CSV email:", e)


#######################################

# helper function to extract price from title using regex

def extract_price(title):
    # Find the first pattern like $999.99 or $999
    match = re.search(r"\$\d+(?:\.\d{1,2})?", title)
    return match.group(0) if match else ""

#######################################

# buildapcsales uses a flair system to categorize by part type or expired.. reference with .link_flair_text
# hardwareswap uses a flair system to categorize by SELLING, BUYING, TRADING, or CLOSED

EXCLUDED_FLAIRS = ["closed", "trading", "buying", "expired :table_flip:", "phone", "watch", "home"]

# substring matches for part matching/sorting
PART_KEYWORDS = {
    "GPU": ["gpu", "4070", "4080", "7800", "7900", "9070", "5080", "5070", "3080", "3090"],
    "CPU": ["cpu", "7800x3d", "7700x", "7950x3d", "7900x3d", "14700k", "14900K", "14600K"],
    "SSD": ["ssd","nvme", "sn850", "990", "980", "p5", "rocket 4"],
    "Motherboard": ["mobo", "motherboard", "mb", "am5", "x670", "b650", "b650e", "z790", "atx", "tomahawk"],
    "RAM": ["ram", "ddr5", "ddr4", "32gb", "64gb"],
    "Case Fan": ["case fan", "120mm", "140mm", "pwm"],
    "CPU Cooler": ["cooler", "cpu fan", "noctua", "liquid", "aio", "air", "peerless"],
    "HDD": ["nas", "hdd", "ironwolf", "hard drive", "wd red", "red plus", "red pro"],
    "Monitor": ["4k"]
}

KEYWORD_TO_PART = {}

for part, keywords in PART_KEYWORDS.items():
    for kw in keywords:
        KEYWORD_TO_PART[kw.lower()] = part

# convert to something like: 
# {
#   "4070": "GPU",
#   "4080": "GPU",
#   "cpu": "CPU",
#   ...
# }

# substring matches for target models for highlight flag (and email?)
TARGET_MODELS = [
    "7800x3d", "7900xt", "9070", "990 pro", "980 pro", "sn850x", "4080 super", "14600k", "peeless", "noctua", "tomahawk"
]

###########################################

# use .subreddit() to target specific subreddits
# .new() to get the newest posts limited to 30 posts (rbuildapcsales was averaging 20 per day max)

def run_scraper():

    seen_ids = load_seen_ids() #initialize seen_ids from file for depulication

    #populate matching deals
    MATCHED_POSTS = {
        "Case Fan": [],
        "CPU": [],
        "CPU Cooler": [],
        "GPU": [],
        "HDD": [],
        "Monitor": [],
        "Motherboard": [],
        "RAM": [],
        "SSD": []
    }

    try:
        for sub in ["buildapcsales", "hardwareswap", "techdeals", "pcdeals"]:
            for post in reddit.subreddit(sub).new(limit=50):

                flair = (post.link_flair_text or "").lower()
                title = (post.title or "").lower()
                # convert created_utc to a datetime object and format it
                created_time = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
                formatted_time = created_time.strftime("%Y-%m-%d %H:%M:%S UTC") 
                one_month_ago = datetime.now(timezone.utc) - timedelta(days=30)

                ################

                #filter out seen posts
                if post.id in seen_ids:
                    continue  # Skip already processed posts

                # #skip posts older than 1 month
                if created_time < one_month_ago:
                    continue
            
                # #loop through EXCLUDED_FLAIRS and compare element as potential substring in current flair string 
                # #filter out if matching excluded flair
                if any(substring in flair for substring in EXCLUDED_FLAIRS): 
                    continue 

                ##################

                # Mark this post as seen
                seen_ids.add(post.id)

                #match post title to part type

                matched = False
                for kw, part in KEYWORD_TO_PART.items():
                    if kw in title:

                        # Check if post is in your target list
                        is_target = any(target in title for target in TARGET_MODELS)
                        
                        # If it is, send an email notification
                        if is_target:
                            post_url = post.url
                            post_title = post.title
                            email_subject = "🎯 Highlighted Deal Alert"
                            email_body = f"{post_title}\n{post_url}"
                            send_email(email_subject, email_body, os.getenv("EMAIL_ADDRESS"))  # or any email address you want

                        MATCHED_POSTS[part].append({
                            "title": post.title,
                            "url": post.url,
                            "subreddit": sub,
                            "flair": post.link_flair_text,
                            "created": formatted_time,
                            "highlight": "YES" if is_target else "",
                            "price": extract_price(post.title)
                        })

                        matched = True
                        break  # If you only want one part match per post

                if not matched:
                    pass  # Optional: track uncategorized posts


                # print(f"[{sub}] {post.link_flair_text}") #for filter by flair testing
                # print(f"[{sub}] {formatted_time} {post.title} {post.url}")

    except Exception as e:
        print("❌ Reddit connection failed:")
        print(e)

    # print(MATCHED_POSTS)

    def export_to_csv_append(matched_posts, filename="deals.csv"):
        file_exists = os.path.isfile(filename)
        fieldnames = ["highlight", "part", "created", "price", "title", "url", "subreddit", "flair"]

        with open(filename, mode='a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            # Write header only if file didn't exist before
            if not file_exists:
                writer.writeheader()

            for part, posts in matched_posts.items():
                for post in posts:
                    row = {"part": part}
                    row.update(post)
                    # row.pop("flair", None)
                    writer.writerow(row)


    # After your scraping logic finishes
    export_to_csv_append(MATCHED_POSTS)

    #Save all seen_ids to file
    save_seen_ids(seen_ids)

##########################################

# Main loop to run the scraper every 30 minutes

run_count=0 #track runs and send csv to email 1 time per day

while True:
    print("🔁 Running scraper at", datetime.now())

    try:
        run_scraper()
        run_count += 1

        if run_count >= 48:  # ~24 hours if running every 30 minutes
            send_csv_email()
            run_count = 0

    except Exception as e:
        print("❌ Unhandled error in run_scraper:")
        print(e)
        time.sleep(5 * 60) # Retry after 5 minutes if an error occurs
        continue

    print("✅ Done. Sleeping for 30 minutes.\n")
    time.sleep(30 * 60) # Sleep for 30 minutes

