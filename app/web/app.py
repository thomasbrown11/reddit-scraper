from flask import Flask, render_template, request
import sqlite3
import pandas as pd
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

#import database init and db location from database.py
from database import initialize_database, DB_FILE

initialize_database()

app = Flask(__name__)

# import deals.db path from database.py
DB_PATH = DB_FILE

@app.route("/")
def index():

    tier = request.args.get("tier", "").upper()
    category = request.args.get("category", "")
    search = request.args.get("search", "")
    sort = request.args.get("sort", "created_desc")

    # ---------------------------------------------------
    # Base query
    # ---------------------------------------------------

    query = """
        SELECT *
        FROM deals
        WHERE 1=1
    """

    params = []

    # ---------------------------------------------------
    # Filters
    # ---------------------------------------------------

    if tier:
        query += " AND deal_tier = ?"
        params.append(tier)

    if category:
        query += " AND part = ?"
        params.append(category)

    if search:
        query += " AND lower(title) LIKE ?"
        params.append(f"%{search.lower()}%")

    # ---------------------------------------------------
    # Sorting
    # ---------------------------------------------------

    if sort == "created_desc":

        query += """
            ORDER BY created_utc DESC
        """

    elif sort == "created_asc":

        query += """
            ORDER BY created_utc ASC
        """

    elif sort == "price_desc":

        query += """
            ORDER BY
                CAST(
                    REPLACE(
                        REPLACE(price, '$', ''),
                        ',', ''
                    ) AS REAL
                ) DESC
        """

    elif sort == "price_asc":

        query += """
            ORDER BY
                CAST(
                    REPLACE(
                        REPLACE(price, '$', ''),
                        ',', ''
                    ) AS REAL
                ) ASC
        """

    elif sort == "deal_tier":

        query += """
            ORDER BY
                CASE deal_tier
                    WHEN 'GREAT' THEN 3
                    WHEN 'GOOD'  THEN 2
                    WHEN 'OK'    THEN 1
                    ELSE 0
                END DESC,
                created_utc DESC
        """

    elif sort == "highlight":

        query += """
            ORDER BY
                CASE
                    WHEN highlight = 'YES' THEN 1
                    ELSE 0
                END DESC,
                created_utc DESC
        """

    else:

        query += """
            ORDER BY created_utc DESC
        """

    # ---------------------------------------------------
    # Execute SQL
    # ---------------------------------------------------

    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            query,
            conn,
            params=params
        )

    if df.empty:
        return render_template(
            "table.html",
            tables=[],
            columns=[]
        )

    return render_template(
        "table.html",
        tables=df.to_dict(orient="records"),
        columns=df.columns.tolist()
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )