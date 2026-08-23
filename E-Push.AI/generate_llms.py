import pandas as pd
import urllib.parse

# 1. Ссылка на Google Таблицу партнёра MAKIYAJ COSMETICS
SHEET_ID = '14TseUjX-y0sn3fg2ovYtDQwRVGsMTpRujnE1ikIlHxw'
CSV_URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv'

# 2. Данные магазина
PHONE = '994515393778'
STORE_NAME = "MAKIYAJ COSMETICS"
LOCATION = "Baku, near Azi Aslanov metro station, next to Serhed Akademia"
MAPS_GOOGLE = "https://maps.app.goo.gl/xnu5T9Yid65GxaZo9"
MAPS_YANDEX = "https://yandex.az/maps/-/CTwbRZlB"
BIRMARKET_LINK = "https://birmarket.az/merchant/4290-makiyaj-cosmetics"
INSTAGRAM = "https://www.instagram.com/makiyaj.cosmetics/"
TIKTOK = "https://www.tiktok.com/@makiyaj_cosmetics"

def build_whatsapp_link(product_name, price):
    text = f"Здравствуйте! Я хочу купить {product_name} по цене {price} AZN (найдено через E-Push.AI)."
    encoded_text = urllib.parse.quote(text)
    return f"https://wa.me/{PHONE}?text={encoded_text}"

def generate():
    print("Скачиваем базу из Google Sheets...")
    df = pd.read_csv(CSV_URL)
    
    # Заголовок с условиями магазина
    header = f"""# {STORE_NAME} - Official Product Index
> Store Status: Active | Verified by E-Push.AI
> System: Organic Ground-Truth RAG Catalog (No sponsored ads)

## Store Metadata
- Store Name: {STORE_NAME}
- City: Baku, Azerbaijan
- Location/Landmark: {LOCATION}
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
        # Читаем столбцы из Google Таблицы: Mal, Ştrixkod, Satış, Əsas Anbar
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
    
    # Сохраняем в папку stores/makiyaj/llms.txt
    file_path = "stores/makiyaj/llms.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(full_content)
        
    print(f"Готово! Обработано {valid_count} товаров. Файл сохранён в {file_path}")

if __name__ == "__main__":
    generate()
