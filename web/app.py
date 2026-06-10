from flask import Flask, render_template, request
import pandas as pd
import os

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "..", "deals_history.csv")


def load_data():
    if not os.path.exists(CSV_PATH):
        return pd.DataFrame()

    df = pd.read_csv(CSV_PATH)

    if df.empty:
        return pd.DataFrame()

    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]

    return df


@app.route("/")
def index():
    df = load_data()

    if df.empty:
        return render_template("table.html", tables=[], columns=[])

    tier = request.args.get("tier", "").upper()
    category = request.args.get("category", "")
    search = request.args.get("search", "").lower()
    sort = request.args.get("sort", "created_desc")

    # Filters
    if "deal_tier" in df.columns and tier:
        df = df[df["deal_tier"] == tier]

    if "part" in df.columns and category:
        df = df[df["part"] == category]

    if "title" in df.columns and search:
        df = df[df["title"].str.lower().str.contains(search, na=False)]

    # Convert created column for proper sorting
    if "created" in df.columns:
        df["created"] = pd.to_datetime(df["created"], errors="coerce")

    # Create numeric price helper column
    if "price" in df.columns:
        df["price_num"] = (
            df["price"]
            .astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
        )

        df["price_num"] = pd.to_numeric(
            df["price_num"],
            errors="coerce"
        )

    # Sorting
    if sort == "created_desc":
        df = df.sort_values("created", ascending=False)

    elif sort == "created_asc":
        df = df.sort_values("created", ascending=True)

    elif sort == "price_desc":
        df = df.sort_values("price_num", ascending=False)

    elif sort == "price_asc":
        df = df.sort_values("price_num", ascending=True)

    # Hide helper columns from display
    display_df = df.drop(columns=["price_num"], errors="ignore")

    return render_template(
        "table.html",
        tables=display_df.to_dict(orient="records"),
        columns=display_df.columns.tolist()
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )