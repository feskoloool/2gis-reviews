import os
import re
import json
import html
import requests
from datetime import datetime

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

print(f"Подключение к Telegram-каналу t.me/{CHANNEL_USERNAME}...")
url = f"https://t.me/s/{CHANNEL_USERNAME}"
response = requests.get(url, headers=headers, timeout=15)

if response.status_code != 200:
    print(f"Ошибка доступа к каналу: код {response.status_code}")
    exit(1)

page_html = response.text
raw_posts = page_html.split('<div class="tgme_widget_message ')
print(f"Найдено постов в ленте: {len(raw_posts) - 1}")

projects = []
photo_global_counter = 1

for block in raw_posts[1:]:
    # 1. Пропускаем посты с видео
    if ("tgme_widget_message_video" in block or 
        "<video" in block or 
        "tgme_widget_message_roundvideo" in block):
        continue

    # 2. Поиск картинок в сообщении
    img_urls = re.findall(r'class="[^"]*tgme_widget_message_photo_wrap[^"]*"[^>]*style="[^"]*background-image:\s*url\([\'"]?([^\'")]+)[\'"]?\)', block)
    if not img_urls:
        found = re.findall(r'background-image:\s*url\([\'"]?(https://[^\'")]+)[\'"]?\)', block)
        img_urls = [u for u in found if "userpic" not in u and "avatar" not in u]

    if not img_urls:
        continue

    # 3. Извлечение текста (адреса и описания)
    caption = ""
    caption_match = re.search(r'<div class="[^"]*tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
    if caption_match:
        raw_text = caption_match.group(1)
        raw_text = re.sub(r'<br\s*/?>', ' ', raw_text)
        clean_text = re.sub(r'<[^>]+>', '', raw_text)
        caption = html.unescape(clean_text).strip()

    # 4. Извлечение даты
    date_str = ""
    time_match = re.search(r'<time\s+[^>]*datetime="([^"]+)"', block)
    if time_match:
        try:
            dt = datetime.fromisoformat(time_match.group(1).replace("Z", "+00:00"))
            date_str = dt.strftime("%d.%m.%Y")
        except Exception:
            date_str = time_match.group(1)[:10]

    # 5. Скачивание всех фотографий этого объекта
    current_post_photos = []
    for img_url in img_urls:
        filename = f"work_{photo_global_counter}.jpg"
        file_path = os.path.join(IMAGES_DIR, filename)

        try:
            img_res = requests.get(img_url, headers=headers, timeout=15)
            if img_res.status_code == 200:
                with open(file_path, "wb") as f:
                    f.write(img_res.content)

                web_url = f"https://{GITHUB_USER}.github.io/{GITHUB_REPO}/{IMAGES_DIR}/{filename}"
                current_post_photos.append(web_url)
                photo_global_counter += 1
        except Exception as e:
            print(f"  [-] Ошибка при скачивании фото: {e}")

    if not current_post_photos:
        continue

    # Если Telegram разбил альбом на несколько сообщений с одинаковым текстом — объединяем их
    if projects and caption and projects[-1]["caption"] == caption:
        projects[-1]["photos"].extend(current_post_photos)
        print(f"  [+] Добавлено {len(current_post_photos)} фото к уже существующему объекту: {caption[:30]}...")
    else:
        projects.append({
            "id": len(projects) + 1,
            "caption": caption if caption else "Натяжной потолок (выполненная работа)",
            "date": date_str,
            "photos": current_post_photos
        })
        print(f"  [+] Создан новый объект ({len(current_post_photos)} фото): {caption[:30]}...")

# Свежие работы сверху
projects.reverse()

payload = {
    "channel": CHANNEL_USERNAME,
    "updated_at": datetime.utcnow().strftime("%d.%m.%Y %H:%M"),
    "total_projects": len(projects),
    "projects": projects
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

print(f"\nГотово! Сформировано объектов: {len(projects)}. Файл {OUTPUT_FILE} успешно обновлен.")
