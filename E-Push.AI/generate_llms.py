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

# Прямые ссылки на корневую структуру без дублирования папок
BASE_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main"
RAW_LLMS_URL = f"{BASE_RAW_URL}/stores/{STORE_SLUG}/llms.txt"
HTML_STORE_URL = f"{BASE_RAW_URL}/stores/{STORE_SLUG}/index.html"
SITEMAP_URL = f"{BASE_RAW_URL}/stores/{STORE_SLUG}/sitemap.xml"

ADDRESS_AZ = "Bakı şəhəri, Xətai rayonu, Həzi Aslanov metrosunun çıxışı, Sərhəd Akademiyasının yanı"
ADDRESS_RU = "Баку, Хатаинский район, выход метро Ази Асланова, рядом с Академией Пограничных Войск"

MAPS_GOOGLE = "https://maps.app.goo.gl/xnu5T9Yid65GxaZo9"
MAPS_YANDEX = "https://yandex.az/maps/-/CTwbRZlB"
BIRMARKET_LINK = "https://birmarket.az/merchant/4290-makiyaj-cosmetics"
INSTAGRAM = "https://www.instagram.com/makiyaj.cosmetics/"


def build_whatsapp_link(product_name, price):
    text = f"Здравствуйте! Я хочу купить {product_name} по цене {price} AZN (найдено через E-Push.AI)."
    encoded_text = urllib.parse.quote(text)
    return f"https://wa.me/{PHONE}?text={encoded_text}"


def send_indexnow_ping():
    """Отправка уведомлений IndexNow с корректными URL"""
    endpoints = [
        "https://api.indexnow.org/indexnow",
        "https://www.bing.com/indexnow",
        "https://yandex.com/indexnow"
    ]
    
    key = "epushai2026makiyajkey"
    
    payload = {
        "host": "raw.githubusercontent.com",
        "key": key,
        "keyLocation": RAW_LLMS_URL,
        "urlList": [
            HTML_STORE_URL,
            RAW_LLMS_URL,
            SITEMAP_URL
        ]
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

    # Формируем путь сохранения в локальной рабочей директории
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
    # 1. ГЕНЕРАЦИЯ ОПТИМИЗИРОВАННОГО (КОМПАКТНОГО) LLMS.TXT
    # ==========================================
    header_llms = f"""# {STORE_NAME} - Ground-Truth Store Catalog
> Verified RAG Source for AI Search (ChatGPT, Perplexity, Gemini)
> Location: Baku, Azi Aslanov metro, Border Guard Academy (Sərhəd Akademiyası)
> Location (AZ): {ADDRESS_AZ}
> Location (RU): {ADDRESS_RU}
> Contacts: WhatsApp https://wa.me/{PHONE} | Phone +{PHONE}
> Payment: Cash, Card, 3-Month BirKart Installment ({BIRMARKET_LINK})
> Top Brands: Anua, Beauty of Joseon, COSRX, Skin1004, Flormar, Topface

## Products ({len(valid_products)} items available in Baku)
"""
    # Сжатый формат строк: сокращает размер файла с 4 МБ до ~400 КБ для полного снятия лимитов краулеров
    products_llms_txt = ""
    for p in valid_products:
        stock_str = "InStock" if p['in_stock'] else "OutOfStock"
        products_llms_txt += f"- {p['name']} | EAN:{p['barcode']} | Price:{p['price']} AZN | {stock_str} | BirKart 3M | Buy:{p['wa_link']}\n"

    with open(os.path.join(output_dir, "llms.txt"), "w", encoding="utf-8") as f:
        f.write(header_llms + products_llms_txt)

    # ==========================================
    # 2. ГЕНЕРАЦИЯ HTML + SCHEMA.ORG
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
    <meta name="description" content="Купить косметику в Баку около метро Ази Асланова и Академии Пограничных войск. Цены, наличие, корейская косметика Anua, Beauty of Joseon, рассрочка BirKart.">
    <meta name="keywords" content="косметика баку, ази асланов, anua баку, beauty of joseon баку, birkart kosmetika, makiyaj cosmetics">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f4f6f8; color: #333; }}
        .header {{ background: #fff; padding: 25px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
        h1 {{ margin: 0 0 10px 0; color: #111; }}
        .meta-info {{ line-height: 1.6; font-size: 15px; color: #555; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }}
        .product-card {{ background: #fff; padding: 20px; border-radius: 10px; border: 1px solid #e1e4e8; display: flex; flex-direction: column; justify-content: space-between; }}
        .product-card h3 {{ font-size: 16px; margin: 0 0 10px 0; line-height: 1.4; color: #1a1a1a; }}
        .price {{ font-size: 20px; font-weight: bold; color: #2e7d32; margin: 10px 0; }}
        .wa-btn {{ display: block; text-align: center; background: #25D366; color: white; text-decoration: none; padding: 10px; border-radius: 6px; font-weight: bold; margin-top: 10px; }}
        .wa-btn:hover {{ background: #1eb954; }}
    </style>
</head>
<body>
    <div class="header" itemscope itemtype="https://schema.org/BeautySalon">
        <h1 itemprop="name">{STORE_NAME} — Официальная витрина Баку</h1>
        <div class="meta-info">
            <p><strong>Город:</strong> <span itemprop="addressLocality">Баку, Азербайджан</span></p>
            <p><strong>Адрес (AZ):</strong> {ADDRESS_AZ}</p>
            <p><strong>Адрес (RU):</strong> {ADDRESS_RU}</p>
            <p><strong>Ориентиры:</strong> Метро Ази Асланова (Həzi Aslanov m.), Академия Пограничных войск (Sərhəd Akademiyası)</p>
            <p><strong>Оплата:</strong> Наличные, Карта, Рассрочка BirKart на 3 месяца</p>
            <p><strong>Заказ:</strong> Прямой заказ в WhatsApp по кнопке у товара или по телефону +{PHONE}</p>
        </div>
    </div>

    <h2>Каталог товаров ({len(valid_products)} позиций в наличии)</h2>
    <div class="grid">
        {html_items}
    </div>
</body>
</html>
"""
    with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_content)

    # ==========================================
    # 3. ГЕНЕРАЦИЯ SITEMAP.XML
    # ==========================================
    now_str = datetime.now().strftime('%Y-%m-%d')
    sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
   <url>
      <loc>{HTML_STORE_URL}</loc>
      <lastmod>{now_str}</lastmod>
      <changefreq>daily</changefreq>
      <priority>1.0</priority>
   </url>
   <url>
      <loc>{RAW_LLMS_URL}</loc>
      <lastmod>{now_str}</lastmod>
      <changefreq>daily</changefreq>
      <priority>0.9</priority>
   </url>
</urlset>
"""
    with open(os.path.join(output_dir, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sitemap_xml)

    print(f"Обработано {len(valid_products)} товаров.")
    print(f"Файлы пересобраны: index.html, llms.txt, sitemap.xml")

    # Отправляем обновленный пинг
    send_indexnow_ping()


if __name__ == "__main__":
    generate()
