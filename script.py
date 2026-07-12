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

    # ==========================================
    # TEXT NORMALIZATION
    # ==========================================

    def normalize_text(text):
        return " ".join(text.split()).strip()


    # ==========================================
    # READ EXISTING SHEET DATA
    # ==========================================

    all_rows = sheet.get_all_values()

    if not all_rows:
        return


    existing_posts = {}
    existing_texts = {}


    # пропускаем первую строку (заголовки)
    # реальные строки начинаются с 2
    for row_index, row in enumerate(all_rows[1:], start=2):

        if len(row) < 8:
            continue


        post_id = row[1].strip()
        text = row[7].strip()


        if post_id:
            existing_posts[post_id] = row_index


        if text:
            text_key = normalize_text(text)
            existing_texts[text_key] = row_index



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


    response = requests.get(
        url,
        params=params
    )

    data = response.json()


    if "error" in data:
        raise Exception(data["error"])



    posts = data["response"]["items"]


    posts.sort(
        key=lambda x: x["date"]
    )



    # ==========================================
    # PREPARE CHANGES
    # ==========================================

    batch_updates = []
    rows_to_add = []



    for post in posts:


        if post.get("is_pinned"):
            continue



        # обычный ID поста
        post_id = str(post["id"])



        date = datetime.fromtimestamp(
            post["date"]
        ).strftime("%Y-%m-%d %H:%M:%S")



        # оригинальный текст сохраняем как есть
        text = post.get(
            "text",
            ""
        ).strip()



        if not text:
            continue



        # нормализованный текст только для поиска
        text_key = normalize_text(text)



        reactions = post.get(
            "reactions",
            {}
        ).get(
            "count",
            0
        )


        comments = post.get(
            "comments",
            {}
        ).get(
            "count",
            0
        )


        reposts = post.get(
            "reposts",
            {}
        ).get(
            "count",
            0
        )


        views = post.get(
            "views",
            {}
        ).get(
            "count",
            0
        )



        cr = round(
            ((reactions + comments + reposts) / views),
            2
        ) if views else 0



        # ======================================
        # FIND EXISTING POST
        # ======================================

        row = None



        # сначала ищем по ID
        if post_id in existing_posts:

            row = existing_posts[post_id]



        # если ID новый - ищем по тексту
        elif text_key in existing_texts:

            row = existing_texts[text_key]



        # ======================================
        # UPDATE EXISTING
        # ======================================

        if row:


            batch_updates.append({

                "range": f"A{row}:H{row}",

                "values": [[

                    date,
                    post_id,
                    reactions,
                    comments,
                    reposts,
                    views,
                    cr,

                    # записываем оригинальный текст
                    text

                ]]

            })



        # ======================================
        # INSERT NEW
        # ======================================

        else:


            rows_to_add.append([

                date,
                post_id,
                reactions,
                comments,
                reposts,
                views,
                cr,

                # оригинальный текст
                text

            ])




    # ==========================================
    # WRITE TO GOOGLE SHEETS
    # ==========================================


    if batch_updates:

        sheet.batch_update(
            batch_updates
        )


    if rows_to_add:

        sheet.append_rows(
            rows_to_add
        )

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