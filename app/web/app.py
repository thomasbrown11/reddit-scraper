from flask import Flask, render_template, request # web framework for dashboard. handle http request, route urls to functions, render
import sqlite3 # db handler
import pandas as pd #data manipulation libray. convert SQL rows to DataFrame for Flask HTML template
import sys
from pathlib import Path

# add app parent directory to Python's module search path. 
# allows import of database.py from app.py from set location 
sys.path.append(str(Path(__file__).resolve().parent.parent))

# import database functions and db file
from database import initialize_database, DB_FILE

# Ensure SQLite db and deals table exist before Flask begins serving requests
initialize_database()

# init a Flask app object using this file as the reference location
# __name__ outputs 'app' in this context from this file when seen from another file
# tells Flask where module exists so it can locate resources like templates and static files
app = Flask(__name__)

# import deals.db path from database.py
DB_PATH = DB_FILE

# Flask decorator. Short hand for def index(): ... ; index = app.route("/")(index)
# app.route() expects a python function declaration immediately after and associates the route to that route handler
# define main route via index function  
@app.route("/")
def index():

    # Read query parameters from the URL after user interaction.
    # Example:
    # localhost:5000/?tier=GREAT
    #
    # request.args retrieves values from the URL query string:
    # "tier" -> "GREAT"
    #
    # These values are then used below to build SQL filters/sorting logic
    # before querying the database.
    tier = request.args.get("tier", "").upper()
    category = request.args.get("category", "")
    search = request.args.get("search", "")
    sort = request.args.get("sort", "created_desc")

    # ---------------------------------------------------
    # Base query
    # ---------------------------------------------------

    # WHERE 1=1 is always true and acts as a palceholder so dynamic filters can safely append additional AND conditions below
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
