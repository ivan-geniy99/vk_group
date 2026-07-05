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

# GOOGLE SHEETS
creds_info = json.loads(os.getenv("CREDENTIALS"))

creds = Credentials.from_service_account_info(
    creds_info,
    scopes=SCOPES
)

client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).sheet1


# ==========================================
# WEBHOOK ENDPOINT
# ==========================================

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    # сюда ты будешь дергать триггер

    try:
        run_sync()   # запускаем твой старый код
        return jsonify({"status": "ok"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==========================================
# ТВОЙ ОСНОВНОЙ КОД (обернут в функцию)
# ==========================================

def run_sync():

    records = sheet.get_all_records()

    existing_posts = {}

    for row_number, record in enumerate(records, start=2):
        existing_posts[str(record["post_id"])] = row_number

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

        cr = round(((reactions + comments + reposts) / views) * 100, 2) if views else 0

        if post_id in existing_posts:
            row = existing_posts[post_id]

            sheet.batch_update([{
                "range": f"C{row}:H{row}",
                "values": [[reactions, comments, reposts, views, cr, text]]
            }])

        else:
            sheet.append_row([
                date, post_id, reactions, comments, reposts, views, cr, text
            ])


# ==========================================
# HEALTH CHECK (обязательно для Render)
# ==========================================

@app.route("/", methods=["GET"])
def home():
    return "VK bot running"


# ==========================================
# START
# ==========================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)