from flask import Flask, request, jsonify
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import json
import os

app = Flask(__name__)

VK_TOKEN = os.getenv("VK_TOKEN")
DOMAIN = "foot_ball_today"
SPREADSHEET_NAME = "vk_analytics"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ==========================================
# GOOGLE SHEETS AUTH
# ==========================================

creds_info = json.loads(os.getenv("CREDENTIALS"))

creds = Credentials.from_service_account_info(
    creds_info,
    scopes=SCOPES
)

client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).sheet1


# ==========================================
# WEBHOOK
# ==========================================

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        run_sync()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==========================================
# MAIN LOGIC
# ==========================================

def run_sync():

    # ✔ читаем только колонку post_id (B)
    values = sheet.col_values(2)[1:]

    existing_posts = {}
    for i, post_id in enumerate(values, start=1):
        if post_id:
            existing_posts[str(post_id)] = i

    # ==========================================
    # VK API
    # ==========================================

    url = "https://api.vk.com/method/wall.get"

    params = {
        "domain": DOMAIN,
        "count": 100,
        "access_token": VK_TOKEN,
        "v": "5.199"
    }

    response = requests.get(url, params=params)
    data = response.json()

    posts = data["response"]["items"]
    posts.sort(key=lambda x: x["date"])

    # ==========================================
    # COLLECT UPDATES
    # ==========================================

    batch_updates = []
    rows_to_add = []

    for post in posts:

        if post.get("is_pinned"):
            continue

        post_id = str(post["id"])
        date = datetime.fromtimestamp(post["date"]).strftime("%Y-%m-%d %H:%M:%S")
        text = post.get("text", "")

        if not text.strip():
            continue

        reactions = post.get("reactions", {}).get("count", 0)
        comments = post.get("comments", {}).get("count", 0)
        reposts = post.get("reposts", {}).get("count", 0)
        views = post.get("views", {}).get("count", 0)

        cr = round(((reactions + comments + reposts) / views), 2) if views else 0

        # ==========================================
        # UPDATE OR INSERT
        # ==========================================

        if post_id in existing_posts:

            row = existing_posts[post_id]

            batch_updates.append({
                "range": f"C{row}:H{row}",
                "values": [[reactions, comments, reposts, views, cr, text]]
            })

        else:

            rows_to_add.append([
                date, post_id,
                reactions, comments, reposts,
                views, cr, text
            ])

    # ==========================================
    # SINGLE BATCH REQUESTS (IMPORTANT)
    # ==========================================

    if batch_updates:
        sheet.batch_update(batch_updates)

    if rows_to_add:
        sheet.append_rows(rows_to_add)
    

# ==========================================
# HEALTH CHECK
# ==========================================

@app.route("/", methods=["GET"])
def home():
    return "VK bot running"


# ==========================================
# START
# ==========================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)