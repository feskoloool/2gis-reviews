import os
import re
import json
import html
import requests
from datetime import datetime

CHANNEL_USERNAME = "vyshegolovynsk"
GITHUB_USER = "feskoloool"
GITHUB_REPO = "2gis-reviews"

# Сколько страниц истории пролистать назад (каждая страница — около 15-20 постов)
PAGES_TO_FETCH = 5

IMAGES_DIR = "images"
OUTPUT_FILE = "photos.json"

os.makedirs(IMAGES_DIR, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

print(f"Подключение к Telegram-каналу t.me/{CHANNEL_USERNAME}...")

raw_posts_dict = {}
before_param = ""

for page in range(1, PAGES_TO_FETCH + 1):
    url = f"https://t.me/s/{CHANNEL_USERNAME}"
    if before_param:
        url += f"?before={before_param}"

    print(f"Загрузка страницы {page}/{PAGES_TO_FETCH}...")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"  Ошибка загрузки: код {response.status_code}")
            break
    except Exception as e:
        print(f"  Ошибка запроса: {e}")
        break

    page_html = response.text
    blocks = page_html.split('<div class="tgme_widget_message ')
    if len(blocks) <= 1:
        break

    page_post_ids = []
    for block in blocks[1:]:
        post_id_match = re.search(rf'data-post="{CHANNEL_USERNAME}/(\d+)"', block)
        if post_id_match:
            pid = int(post_id_match.group(1))
            page_post_ids.append(pid)
            if pid not in raw_posts_dict:
                raw_posts_dict[pid] = block

    if not page_post_ids:
        break

    min_id = min(page_post_ids)
    if str(min_id) == before_param:
        break
    before_param = str(min_id)

print(f"Всего получено уникальных постов: {len(raw_posts_dict)}")

# Сортируем посты по возрастанию ID для корректной склейки альбомов
sorted_post_ids = sorted(raw_posts_dict.keys())

projects = []

for pid in sorted_post_ids:
    block = raw_posts_dict[pid]

    # 1. Пропускаем посты с видео и кружочками
    if ("tgme_widget_message_video" in block or 
        "<video" in block or 
        "tgme_widget_message_roundvideo" in block):
        continue

    # 2. Ищем фотографии в посте
    img_urls = re.findall(r'class="[^"]*tgme_widget_message_photo_wrap[^"]*"[^>]*style="[^"]*background-image:\s*url\([\'"]?([^\'")]+)[\'"]?\)', block)
    if not img_urls:
        found = re.findall(r'background-image:\s*url\([\'"]?(https://[^\'")]+)[\'"]?\)', block)
        img_urls = [u for u in found if "userpic" not in u and "avatar" not in u]

    if not img_urls:
        continue

    # 3. Извлечение текста (адрес и описание)
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

    # 5. Скачивание фотографий (с защитой от повторного скачивания)
    post_photos = []
    for idx, img_url in enumerate(img_urls, 1):
        filename = f"work_{pid}_{idx}.jpg"
        file_path = os.path.join(IMAGES_DIR, filename)

        if not os.path.exists(file_path):
            try:
                res = requests.get(img_url, headers=headers, timeout=15)
                if res.status_code == 200:
                    with open(file_path, "wb") as f:
                        f.write(res.content)
            except Exception as e:
                print(f"  [-] Ошибка скачивания фото {pid}: {e}")

        if os.path.exists(file_path):
            web_url = f"https://{GITHUB_USER}.github.io/{GITHUB_REPO}/{IMAGES_DIR}/{filename}"
            post_photos.append(web_url)

    if not post_photos:
        continue

    # Объединение одинаковых объектов (если один альбом разбит на несколько постов)
    if projects and caption and projects[-1]["caption"] == caption:
        projects[-1]["photos"].extend(post_photos)
        projects[-1]["post_id"] = pid
        if date_str:
            projects[-1]["date"] = date_str
    else:
        projects.append({
            "post_id": pid,
            "caption": caption if caption else "Натяжной потолок (выполненная работа)",
            "date": date_str,
            "photos": post_photos
        })

# СТРОГАЯ СОРТИРОВКА: СВЕЖИЕ СВЕРХУ (по убыванию номера поста)
projects.sort(key=lambda p: p["post_id"], reverse=True)

# Переназначаем порядковые ID для слайдера
for idx, proj in enumerate(projects, 1):
    proj["id"] = idx

payload = {
    "channel": CHANNEL_USERNAME,
    "updated_at": datetime.utcnow().strftime("%d.%m.%Y %H:%M"),
    "total_projects": len(projects),
    "projects": projects
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

print(f"\nГотово! Сформировано проектов: {len(projects)} (порядок: свежие -> старые).")
