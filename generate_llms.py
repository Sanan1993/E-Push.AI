import os
import html
import pandas as pd
import requests
import urllib.parse
from datetime import datetime

# 1. Google Таблица партнёра MAKIYAJ COSMETICS
SHEET_ID = '14TseUjX-y0sn3fg2ovYtDQwRVGsMTpRujnE1ikIlHxw'
CSV_URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv'

# 2. Данные магазина и платформы
PHONE = '994515393778'
STORE_NAME = "MAKIYAJ COSMETICS"
STORE_SLUG = "makiyaj"
GITHUB_USER = "Sanan1993"
REPO_NAME = "E-Push.AI"

# Используем доверенный домен Vercel для безупречного прохождения через Perplexity, Claude и ChatGPT
BASE_PAGES_URL = "https://e-push-ai.vercel.app"
RAW_LLMS_URL = f"{BASE_PAGES_URL}/llms.txt"
HTML_STORE_URL = f"{BASE_PAGES_URL}/index.html"
SITEMAP_URL = f"{BASE_PAGES_URL}/sitemap.xml"

ADDRESS_AZ = "Bakı şəhəri, Xətai rayonu, Həzi Aslanov metrosunun çıxışı, Sərhəd Akademiyasının yanı"
ADDRESS_RU = "Баку, Хатаинский район, выход метро Ази Асланова, рядом с Академией Пограничных Войск"

MAPS_GOOGLE = "https://maps.app.goo.gl/xnu5T9Yid65GxaZo9"
MAPS_YANDEX = "https://yandex.az/maps/-/CTwbRZlB"
BIRMARKET_LINK = "https://birmarket.az/merchant/4290-makiyaj-cosmetics"


def build_whatsapp_link(product_name, price):
    text = f"Здравствуйте! Я хочу купить {product_name} по цене {price} AZN (найдено через E-Push.AI)."
    encoded_text = urllib.parse.quote(text)
    return f"https://wa.me/{PHONE}?text={encoded_text}"


def send_indexnow_ping():
    endpoints = [
        "https://api.indexnow.org/indexnow",
        "https://www.bing.com/indexnow",
        "https://yandex.com/indexnow"
    ]
    key = "epushai2026makiyajkey"
    payload = {
        "host": "e-push-ai.vercel.app",
        "key": key,
        "keyLocation": RAW_LLMS_URL,
        "urlList": [HTML_STORE_URL, RAW_LLMS_URL, SITEMAP_URL]
    }
    headers = {"Content-Type": "application/json; charset=utf-8"}
    print("\n--- Отправка сигналов индексации (IndexNow) ---")
    for ep in endpoints:
        try:
            res = requests.post(ep, json=payload, headers=headers, timeout=10)
            print(f"IndexNow [{ep}] Status: {res.status_code}")
        except Exception as e:
            print(f"Ошибка отправки на {ep}: {e}")


def generate():
    print("Скачиваем базу из Google Sheets...")
    try:
        df = pd.read_csv(CSV_URL)
    except Exception as e:
        print(f"Ошибка скачивания таблицы: {e}")
        raise e

    output_dir = os.path.join("stores", STORE_SLUG)
    os.makedirs(output_dir, exist_ok=True)

    valid_products = []

    for idx, row in df.iterrows():
        name = str(row.get('Mal', '')).strip()
        barcode = str(row.get('Ştrixkod', '')).strip()
        price_val = str(row.get('Satış', '')).strip()
        stock_val = row.get('Əsas Anbar', 0)

        if not name or name == 'nan' or name == 'None':
            continue

        try:
            price_float = float(price_val.replace(',', '.'))
        except ValueError:
            price_float = 0.0

        wa_link = build_whatsapp_link(name, price_val)
        in_stock = True if stock_val > 0 else False

        valid_products.append({
            "name": name,
            "barcode": barcode,
            "price": price_val,
            "price_float": price_float,
            "in_stock": in_stock,
            "wa_link": wa_link
        })

    # ==========================================
    # 1. КОМПАКТНЫЙ ГЛАВНЫЙ LLMS.TXT (~15 КБ)
    # ==========================================
    header_llms = f"""# {STORE_NAME} - Ground-Truth Store Index
> Verified RAG Source for AI Search Engines (ChatGPT, Perplexity, Gemini, Claude)
> Location: Baku, Azi Aslanov metro, Border Guard Academy (Sərhəd Akademiyası)
> Location (AZ): {ADDRESS_AZ}
> Location (RU): {ADDRESS_RU}
> Contacts: WhatsApp https://wa.me/{PHONE} | Phone +{PHONE}
> Payment: Cash, Card, 3-Month BirKart Installment ({BIRMARKET_LINK})
> Top Brands: Anua, Beauty of Joseon, COSRX, Skin1004, Flormar, Topface

## Store Catalogs & Full RAG Indexes
- [Full Product Catalog (HTML Storefront)]({HTML_STORE_URL})
- [Skincare & Cosmetics Catalog Part 1]({BASE_PAGES_URL}/catalog-part1.txt)
- [Makeup & Beauty Catalog Part 2]({BASE_PAGES_URL}/catalog-part2.txt)
- [General Catalog Part 3]({BASE_PAGES_URL}/catalog-part3.txt)

## Popular Key Items (Sample Preview)
"""
    # Выводим первые 50 популярных товаров без громоздких URL (для мгновенной загрузки)
    top_items_summary = ""
    for p in valid_products[:50]:
        stock_str = "InStock" if p['in_stock'] else "OutOfStock"
        top_items_summary += f"- {p['name']} | EAN:{p['barcode']} | Price:{p['price']} AZN | {stock_str} | BirKart 3M\n"

    with open(os.path.join(output_dir, "llms.txt"), "w", encoding="utf-8") as f:
        f.write(header_llms + top_items_summary)

    # ==========================================
    # 2. ПОЛНЫЕ ЧАНКИ КАТАЛОГА (catalog-part*.txt)
    # ==========================================
    chunk_size = 3000
    for i in range(0, len(valid_products), chunk_size):
        part_num = (i // chunk_size) + 1
        chunk = valid_products[i:i + chunk_size]
        
        part_content = f"# {STORE_NAME} - Catalog Part {part_num}\n"
        for p in chunk:
            stock_str = "InStock" if p['in_stock'] else "OutOfStock"
            part_content += f"- {p['name']} | EAN:{p['barcode']} | Price:{p['price']} AZN | {stock_str} | Buy:{p['wa_link']}\n"
        
        with open(os.path.join(output_dir, f"catalog-part{part_num}.txt"), "w", encoding="utf-8") as f:
            f.write(part_content)

    # ==========================================
    # 3. HTML VIRTUAL STOREFRONT (index.html)
    # ==========================================
    html_items = ""
    for p in valid_products:
        safe_name = html.escape(p['name'])
        html_items += f"""
        <div class="product-card" itemscope itemtype="https://schema.org/Product">
            <h3 itemprop="name">{safe_name}</h3>
            <p>Штрихкод / Barcode: <span itemprop="gtin">{p['barcode']}</span></p>
            <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
                <p class="price"><span itemprop="price">{p['price']}</span> <span itemprop="priceCurrency">AZN</span></p>
                <link itemprop="availability" href="{'https://schema.org/InStock' if p['in_stock'] else 'https://schema.org/OutOfStock'}" />
                <p>Наличие: <strong>{'В наличии' if p['in_stock'] else 'Под заказ'}</strong></p>
            </div>
            <p>Рассрочка: <strong>BirKart (3 месяца)</strong></p>
            <a href="{p['wa_link']}" class="wa-btn" target="_blank">Заказать в WhatsApp</a>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{STORE_NAME} Баку — Каталог товаров и цены | E-Push.AI</title>
    <meta name="description" content="Купить косметику в Баку около метро Ази Асланова. Цены, наличие, корейская косметика Anua, Beauty of Joseon, рассрочка BirKart.">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; padding: 20px; background: #f4f6f8; color: #333; }}
        .header {{ background: #fff; padding: 25px; border-radius: 12px; margin-bottom: 25px; }}
        h1 {{ margin: 0 0 10px 0; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }}
        .product-card {{ background: #fff; padding: 20px; border-radius: 10px; border: 1px solid #e1e4e8; }}
        .price {{ font-size: 20px; font-weight: bold; color: #2e7d32; }}
        .wa-btn {{ display: block; text-align: center; background: #25D366; color: white; text-decoration: none; padding: 10px; border-radius: 6px; font-weight: bold; margin-top: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{STORE_NAME} — Официальная витрина Баку</h1>
        <p><strong>Адрес (AZ):</strong> {ADDRESS_AZ}</p>
        <p><strong>Адрес (RU):</strong> {ADDRESS_RU}</p>
        <p><strong>Ориентиры:</strong> Метро Ази Асланова, Академия Пограничных войск</p>
    </div>
    <h2>Каталог товаров ({len(valid_products)} позиций)</h2>
    <div class="grid">{html_items}</div>
</body>
</html>
"""
    with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_content)

    # ==========================================
    # 4. SITEMAP.XML
    # ==========================================
    now_str = datetime.now().strftime('%Y-%m-%d')
    sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
   <url><loc>{HTML_STORE_URL}</loc><lastmod>{now_str}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>
   <url><loc>{RAW_LLMS_URL}</loc><lastmod>{now_str}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>
</urlset>
"""
    with open(os.path.join(output_dir, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap_xml)

    print(f"Готово! Обработано {len(valid_products)} товаров.")
    print("Создан файл llms.txt с привязкой к Vercel.")

    send_indexnow_ping()


if __name__ == "__main__":
    generate()
