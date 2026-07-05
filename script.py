import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import json
import os

# ==========================================
# НАСТРОЙКИ
# ==========================================

VK_TOKEN = os.getenv("VK_TOKEN")
DOMAIN = "foot_ball_today"
SPREADSHEET_NAME = "vk_analytics"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ==========================================
# GOOGLE SHEETS
# ==========================================
creds_json = os.getenv("CREDENTIALS")

creds_info = json.loads(creds_json)

creds = Credentials.from_service_account_info(
    creds_info,
    scopes=SCOPES
)

client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).sheet1

# ==========================================
# ЧИТАЕМ ТАБЛИЦУ
# ==========================================

records = sheet.get_all_records()

# post_id -> номер строки
existing_posts = {}

for row_number, record in enumerate(records, start=2):
    existing_posts[str(record["post_id"])] = row_number

# ==========================================
# ПОЛУЧАЕМ ПОСТЫ VK
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

if "response" not in data:
    raise Exception(data)

posts = data["response"]["items"]

# Сортировка по дате
posts.sort(key=lambda x: x["date"])

# ==========================================
# ГОТОВИМ ИЗМЕНЕНИЯ
# ==========================================

rows_to_add = []
batch_updates = []

new_posts = 0
updated_posts = 0

for post in posts:

    # Пропускаем закрепленный пост
    if post.get("is_pinned"):
        continue

    post_id = str(post["id"])

    date = datetime.fromtimestamp(
        post["date"]
    ).strftime("%Y-%m-%d %H:%M:%S")

    text = post.get("text", "")

    # 🚨 ПРОПУСК ПУСТЫХ ПОСТОВ
    if not text.strip():
        continue

    reactions = post.get("reactions", {}).get("count", 0)
    comments = post.get("comments", {}).get("count", 0)
    reposts = post.get("reposts", {}).get("count", 0)
    views = post.get("views", {}).get("count", 0)

    # ==========================================
    # СЧИТАЕМ CR
    # ==========================================

    if views > 0:
        cr = round(((reactions + comments + reposts) / views) * 100, 2)
    else:
        cr = 0

    # ==========================================
    # ОБНОВЛЕНИЕ
    # ==========================================

    if post_id in existing_posts:

        row = existing_posts[post_id]

        batch_updates.append({
            "range": f"C{row}:H{row}",
            "values": [[
                reactions,
                comments,
                reposts,
                views,
                cr,
                text
            ]]
        })

        updated_posts += 1

    # ==========================================
    # ДОБАВЛЕНИЕ
    # ==========================================

    else:

        rows_to_add.append([
            date,
            post_id,
            reactions,
            comments,
            reposts,
            views,
            cr,
            text
        ])

        new_posts += 1

# ==========================================
# ОТПРАВЛЯЕМ ОБНОВЛЕНИЯ
# ==========================================

if batch_updates:
    sheet.batch_update(batch_updates)

# ==========================================
# ДОБАВЛЯЕМ НОВЫЕ ПОСТЫ
# ==========================================

if rows_to_add:
    sheet.append_rows(
        rows_to_add,
        value_input_option="USER_ENTERED"
    )

# ==========================================
# ЛОГ
# ==========================================

print("-" * 40)
print(f"Всего постов VK: {len(posts)}")
print(f"Обновлено: {updated_posts}")
print(f"Добавлено: {new_posts}")
print("Готово.")