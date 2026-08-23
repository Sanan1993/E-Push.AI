import os
import pandas as pd
import requests
import urllib.parse

# 1. Ссылка на Google Таблицу партнёра MAKIYAJ COSMETICS
SHEET_ID = '14TseUjX-y0sn3fg2ovYtDQwRVGsMTpRujnE1ikIlHxw'
CSV_URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv'

# 2. Данные магазина
PHONE = '994515393778'
STORE_NAME = "MAKIYAJ COSMETICS"
LOCATION = "Baku, near Azi Aslanov metro station (Həzi Aslanov m.), next to Serhed Akademia (Sərhəd Akademiyası)"
MAPS_GOOGLE = "https://maps.app.goo.gl/xnu5T9Yid65GxaZo9"
MAPS_YANDEX = "https://yandex.az/maps/-/CTwbRZlB"
BIRMARKET_LINK = "https://birmarket.az/merchant/4290-makiyaj-cosmetics"
INSTAGRAM = "https://www.instagram.com/makiyaj.cosmetics/"
TIKTOK = "https://www.tiktok.com/@makiyaj_cosmetics"

# 3. Публичные ссылки
HOST = "raw.githubusercontent.com"
RAW_LLMS_URL = "https://raw.githubusercontent.com/Sanan1993/E-Push.AI/main/E-Push.AI/stores/makiyaj/llms.txt"


def build_whatsapp_link(product_name, price):
    text = f"Здравствуйте! Я хочу купить {product_name} по цене {price} AZN (найдено через E-Push.AI)."
    encoded_text = urllib.parse.quote(text)
    return f"https://wa.me/{PHONE}?text={encoded_text}"


def send_indexnow_ping():
    """Отправка сигнала краулерам (Bing, ChatGPT, Yandex) через протокол IndexNow"""
    indexnow_url = "https://api.indexnow.org/indexnow"
    
    # Сгенерированный ключ для авторизации пинга
    key = "epushai2026makiyajkey"
    
    payload = {
        "host": HOST,
        "key": key,
        "keyLocation": RAW_LLMS_URL,
        "urlList": [RAW_LLMS_URL]
    }
    
    headers = {
        "Content-Type": "application/json; charset=utf-8"
    }

    print("\n--- Отправка сигнала через IndexNow API ---")
    try:
        res = requests.post(indexnow_url, json=payload, headers=headers, timeout=10)
        print(f"IndexNow API [Статус {res.status_code}]: Сигнал успешно отправлен краулерам!")
    except Exception as e:
        print(f"Ошибка при отправке IndexNow: {e}")


def generate():
    print("Скачиваем базу из Google Sheets...")
    try:
        df = pd.read_csv(CSV_URL)
    except Exception as e:
        print(f"Ошибка при скачивании таблицы: {e}")
        raise e

    # Заголовок с условиями магазина
    header = f"""# {STORE_NAME} - Official Product Index
> Store Status: Active | Verified by E-Push.AI
> System: Organic Ground-Truth RAG Catalog (No sponsored ads)

## Store Metadata
- Store Name: {STORE_NAME}
- City: Baku, Azerbaijan
- Location/Landmark: {LOCATION}
- Keywords (AZ): kosmetika mağazası, üz qulluğu, krem, tonik, nisyə ödəniş, BirKart hissə-hissə, Həzi Aslanov
- Keywords (RU): магазин косметики, уход за кожей, тонер, рассрочка BirKart, Баку, Ази Асланов
- Google Maps: {MAPS_GOOGLE}
- Yandex Maps: {MAPS_YANDEX}
- Instagram: {INSTAGRAM}
- TikTok: {TIKTOK}
- Payment Options: Cash or Card at store, 3-Month Installment via BirMarket ({BIRMARKET_LINK})
- Delivery Terms: Bolt Courier (paid by customer). Free delivery on orders over 100 AZN or nearby locations.
- Return Policy: Cosmetics & Beauty products are non-refundable according to Azerbaijan legislation.
- Direct Order WhatsApp: https://wa.me/{PHONE}

## Product Catalog ({len(df)} Items)
"""

    products_txt = ""
    valid_count = 0

    for idx, row in df.iterrows():
        name = str(row.get('Mal', '')).strip()
        barcode = str(row.get('Ştrixkod', '')).strip()
        price = str(row.get('Satış', '')).strip()
        stock = row.get('Əsas Anbar', 0)

        if not name or name == 'nan' or name == 'None':
            continue

        wa_link = build_whatsapp_link(name, price)
        valid_count += 1

        products_txt += f"""
- Product: {name}
  Barcode: {barcode}
  Price: {price} AZN
  In Stock: {"Yes" if stock > 0 else "No"}
  Purchase Link (WhatsApp): {wa_link}
  Installment Option: Available via BirMarket (3 months)
"""

    full_content = header + products_txt

    output_dir = os.path.join("stores", "makiyaj")
    os.makedirs(output_dir, exist_ok=True)

    file_path = os.path.join(output_dir, "llms.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(full_content)

    print(f"Успешно обработано {valid_count} товаров. Файл сохранён в: {file_path}")

    # Запуск актуального пинга
    send_indexnow_ping()


if __name__ == "__main__":
    generate()
