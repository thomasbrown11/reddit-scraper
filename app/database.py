from pathlib import Path
import sqlite3 

# Go up two directories from current file and then into a 'data' folder
DATA_DIR = Path(__file__).parent.parent / "data"
# make data directory if it doesn't exist, don't crash if it exists. make parent directories as well if missing (not relevant)
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_FILE = DATA_DIR / "deals.db"

def get_connection():
    # create deals.db sql lite db file if it doesn't exist
    return sqlite3.connect(DB_FILE)

##############################
# init db and deals table
##############################

def initialize_database():
    
    # Using with/as context manager to prevent orphan sql sessions
    with get_connection() as conn:
        cursor = conn.cursor()

        # create deals table
        # PK is db id only
        # UNIQUE tracks source + source_id meaning that the scraper db can expand to more sources
        # EX: reddit + abc123, then amazon + abc123
        # keeping subreddit and flair as optional enrichment to avoid overcomplicating with expanded normalization tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                        
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                        
                part TEXT,
                created_utc TEXT,
                price REAL,
                title TEXT,
                url TEXT,
                        
                subreddit TEXT,
                flair TEXT,
                        
                highlight TEXT,
                deal_tier TEXT,
                        
                UNIQUE(source, source_id)
                        
                        
            )
        """)

##############################
# deal insert helper
##############################

def insert_deal(deal):

    # Insert a deal row into the database.
    # Uses INSERT OR IGNORE so duplicates (based on UNIQUE source + source_id)
    # do not raise errors and are safely skipped.
    # The context manager ensures the transaction is committed on success,
    # or rolled back automatically if an error occurs.
    # note: insert_deal assumes deal dict contains all required fields and valid values;
    # no validation is performed here.
    with get_connection() as conn:

        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR IGNORE INTO deals (
                source,
                source_id,
                part,
                created_utc,
                price,
                title,
                url,
                subreddit,
                flair,
                highlight,
                deal_tier
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            deal["source"],
            deal["source_id"],
            deal["part"],
            deal["created_utc"],
            deal["price"],
            deal["title"],
            deal["url"],
            deal["subreddit"],
            deal["flair"],
            deal["highlight"],
            deal["deal_tier"]
        ))

        # make and return inserted boolean to check if row was added in scraper ((insert_deal(deal) = true)
        # cursor is temp sql session reference only and remembers the execute command result above only
        inserted = cursor.rowcount > 0

        return inserted

##############################
# delete stale post helper
##############################

def cleanup_old_deals():
    
    # Open SQLite connection using context manager (python 'with')
    # commit is called automatically if the DELETE succeeds
    # rollback is triggered if an exception occurs
    # connection is always closed at the end of the block
    with get_connection() as conn:

        # Delete all posts with created_utc older than 30 days
        # Prevents unbounded db growth
        conn.execute("""
            DELETE FROM deals
            WHERE created_utc < datetime('now', '-30 days')
        """)

    

##############################
# duplicate check for scraper
##############################

def already_seen(source, source_id):

    # Open SQLite database connection
    # The "with" context manager automatically closes the connection
    # when this block exits, even if an exception occurs
    # The returned connection object is assigned locally to "conn"
    with get_connection() as conn:

        # cursor here is an SQL command interface
        cursor = conn.cursor()

        # Check whether a deal already exists with this source + source_id combination.
        # SELECT 1 returns a constant value instead of full row data because we only need
        # to know whether a matching record exists, not retrieve the record itself
        # ? placeholders are parameterized values supplied separately below, so the input
        # is treated as data rather than executable SQL syntax
        # Parameterized queries intended to prevent SQL injection patterns 
        cursor.execute("""
            SELECT 1
            FROM deals
            WHERE source = ?
            AND source_id = ?
            LIMIT 1
        """, (
            source,
            source_id
        ))

        # returns true or false based on deals sql passing 1 or not
        return cursor.fetchone() is not None