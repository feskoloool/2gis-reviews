import json
import os
import requests
from datetime import datetime

# Идентификатор филиала из вашей ссылки
BRANCH_ID = "70000001118254057"
CITY = "novosibirsk"

# Фильтрация
MIN_RATING = 4           # Минимальная оценка (отсекаем ниже 4 звезд)
ONLY_WITH_TEXT = True    # Пропускать оценки без комментариев
LIMIT = 50               # Сколько последних отзывов запрашивать

OUTPUT_FILE = "reviews.json"

def fetch_from_reviews_api(branch_id: str, limit: int = 50):
    """Основной эндпоинт отзывов 2ГИС"""
    url = f"https://public-api.reviews.2gis.com/2.0/branches/{branch_id}/reviews"
    params = {
        "limit": limit,
        "is_advertiser": "false",
        "fields": "meta.branch_rating,meta.branch_reviews_count,meta.total_count"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://2gis.ru/",
    }
    
    res = requests.get(url, params=params, headers=headers, timeout=15)
    if res.status_code == 200:
        data = res.json()
        return data.get("reviews", []), data.get("meta", {})
    return None, None

def fetch_from_catalog_api(branch_id: str, limit: int = 50):
    """Резервный эндпоинт каталога"""
    url = f"https://catalog.api.2gis.ru/2.0/items/id/{branch_id}/reviews"
    params = {
        "key": "rurbbn3446",
        "page_size": limit,
        "sort_by": "date_edited",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://2gis.ru/",
    }
    
    res = requests.get(url, params=params, headers=headers, timeout=15)
    if res.status_code == 200:
        data = res.json()
        return data.get("result", {}).get("items", []), {}
    return None, None

def format_date(raw_date: str) -> str:
    if not raw_date:
        return ""
    try:
        dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y")
    except ValueError:
        return raw_date[:10]

def main():
    print(f"Запрос отзывов для карточки 2ГИС {BRANCH_ID}...")
    
    raw_reviews, meta = fetch_from_reviews_api(BRANCH_ID, LIMIT)
    if raw_reviews is None:
        print("Основной API вернул ошибку, переключение на каталог 2ГИС...")
        raw_reviews, meta = fetch_from_catalog_api(BRANCH_ID, LIMIT)

    if not raw_reviews:
        print("Отзывы не найдены или карточка закрыта от публичного чтения.")
        return

    clean_reviews = []
    for item in raw_reviews:
        rating = item.get("rating", 0)
        text = (item.get("text") or "").strip()

        if rating < MIN_RATING:
            continue
        if ONLY_WITH_TEXT and not text:
            continue

        user = item.get("user") or {}
        author_name = user.get("name") or user.get("first_name") or "Пользователь 2ГИС"
        avatar = user.get("photo_url") or ""

        date_val = format_date(item.get("date_created") or item.get("date_edited") or "")

        clean_reviews.append({
            "id": item.get("id"),
            "author": author_name,
            "avatar": avatar,
            "rating": rating,
            "text": text,
            "date": date_val,
            "url": f"https://2gis.ru/{CITY}/firm/{BRANCH_ID}"
        })

    payload = {
        "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "branch_id": BRANCH_ID,
        "city": CITY,
        "branch_url": f"https://2gis.ru/{CITY}/firm/{BRANCH_ID}",
        "branch_rating": meta.get("branch_rating"),
        "total_count": len(clean_reviews),
        "reviews": clean_reviews
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Готово! Сохранено {len(clean_reviews)} отзывов в {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
