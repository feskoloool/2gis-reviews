import os
import re
import json
import html
import requests
from datetime import datetime

# Настройки под ваш канал и репозиторий
CHANNEL_USERNAME = "vyshegolovynsk"
GITHUB_USER = "feskoloool"
GITHUB_REPO = "2gis-reviews"

IMAGES_DIR = "images"
OUTPUT_FILE = "photos.json"

os.makedirs(IMAGES_DIR, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

print(f"Подключение к каналу t.me/{CHANNEL_USERNAME}...")
url = f"https://t.me/s/{CHANNEL_USERNAME}"
response = requests.get(url, headers=headers, timeout=15)

if response.status_code != 200:
    print(f"Ошибка доступа к каналу: код {response.status_code}")
    exit(1)

page_html = response.text
raw_posts = page_html.split('<div class="tgme_widget_message ')
print(f"Найдено постов в ленте: {len(raw_posts) - 1}")

gallery_items = []
photo_counter = 1

for block in raw_posts[1:]:
    # 1. СТРОГО ПРОПУСКАЕМ ВИДЕО (обычные видеоролики и кружочки)
    if ("tgme_widget_message_video" in block or 
        "<video" in block or 
        "tgme_widget_message_roundvideo" in block):
        continue

    # 2. Ищем фотографии в посте
    img_urls = re.findall(r'class="[^"]*tgme_widget_message_photo_wrap[^"]*"[^>]*style="[^"]*background-image:\s*url\([\'"]?([^\'")]+)[\'"]?\)', block)
    if not img_urls:
        # Резервный поиск, исключая аватарки авторов
        found = re.findall(r'background-image:\s*url\([\'"]?(https://[^\'")]+)[\'"]?\)', block)
        img_urls = [u for u in found if "userpic" not in u and "avatar" not in u]

    if not img_urls:
        continue

    # 3. Извлекаем подпись к фотографии
    caption = ""
    caption_match = re.search(r'<div class="[^"]*tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
    if caption_match:
        raw_text = caption_match.group(1)
        raw_text = re.sub(r'<br\s*/?>', ' ', raw_text)
        clean_text = re.sub(r'<[^>]+>', '', raw_text)
        caption = html.unescape(clean_text).strip()

    # 4. Извлекаем дату
    date_str = ""
    time_match = re.search(r'<time\s+[^>]*datetime="([^"]+)"', block)
    if time_match:
        try:
            dt = datetime.fromisoformat(time_match.group(1).replace("Z", "+00:00"))
            date_str = dt.strftime("%d.%m.%Y")
        except Exception:
            date_str = time_match.group(1)[:10]

    # 5. Скачиваем фотографии поста
    for img_url in img_urls:
        filename = f"work_{photo_counter}.jpg"
        file_path = os.path.join(IMAGES_DIR, filename)

        try:
            img_res = requests.get(img_url, headers=headers, timeout=15)
            if img_res.status_code == 200:
                with open(file_path, "wb") as f:
                    f.write(img_res.content)

                web_url = f"https://{GITHUB_USER}.github.io/{GITHUB_REPO}/{IMAGES_DIR}/{filename}"

                gallery_items.append({
                    "id": photo_counter,
                    "url": web_url,
                    "caption": caption if caption else "Натяжной потолок (работа выполнена)",
                    "date": date_str
                })
                print(f"  [+] Скачано фото #{photo_counter}: {filename}")
                photo_counter += 1
        except Exception as e:
            print(f"  [-] Ошибка при скачивании фото: {e}")

# Новые работы показываем первыми
gallery_items.reverse()

payload = {
    "channel": CHANNEL_USERNAME,
    "updated_at": datetime.utcnow().strftime("%d.%m.%Y %H:%M"),
    "total_count": len(gallery_items),
    "photos": gallery_items
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

print(f"\nГотово! Скачано фотографий: {len(gallery_items)}. Файл {OUTPUT_FILE} успешно создан.")