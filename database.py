import sqlite3 

DB_FILE = "deals.db"

def get_connection():
        # create deals.db sql lite db file if it doesn't exist
        return sqlite3.connect(DB_FILE)

###########################
# init db and deals table
###########################

def initialize_database():
        
    conn = get_connection()
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

    conn.commit()
    conn.close()

###########################
# deal insert helper
###########################

def insert_deal(deal):

    conn = get_connection()
    cursor = conn.cursor()

    # OR IGNORE is added to prevent scraper crashes on duplicate records based on the table's UNIQUE(source, source_id). 
    # If any constraint fails (including uniqueness check) skip row
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

    conn.commit()
    conn.close()

    return inserted

###########################
# delete stale post helper
###########################
def cleanup_old_deals():

    conn = get_connection()
    cursor = conn.cursor()

    conn.execute("""
        DELETE FROM deals
        WHERE created_utc < datetime('now', '-30 days')
    """)

    conn.commit()
    conn.close()