import requests
import json

token = "1a1f57f01a1f57f01a1f57f0a7195d4e7511a1f1a1f57f070599a63c5e247d1920712a9"
group_id = "-239816613"
domain = "foot_ball_today"

url = "https://api.vk.com/method/wall.get"

params = {
    "domain": domain,
    "count": 0,
    "access_token": token,
    "v": "5.199"
}

response = requests.get(url, params=params)
data = response.json()

with open("vk_response2.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print('Готово')