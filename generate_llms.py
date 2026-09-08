import math
import os
import re
import urllib.parse
import pandas as pd

# ==========================================
# 1. КОНФИГУРАЦИЯ И ПУТИ
# ==========================================
EXCEL_FILE = "catalog.xlsx"  # Путь к вашему исходному прайсу
STORE_NAME = "Makiyaj Cosmetics"
STORE_SLUG = "makiyaj"
OUTPUT_DIR = os.path.join("stores", STORE_SLUG)

# Поля в вашем Excel (измените наименования колонок при необходимости)
COL_TITLE = "Название_Товара"
COL_PRICE = "Розничная_Цена"

# ==========================================
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ОЧИСТКИ
# ==========================================


def clean_title(val):
  """Очистка названий от технических данных, складов и одиночных чисел."""
  if pd.isna(val):
    return None
  title_str = str(val).strip()

  # Исключаем служебные заголовки складов
  if re.search(
      r"Anbar|Склад|Итого|Total|Əsas", title_str, flags=re.IGNORECASE
  ):
    return None

  # Если название состоит только из цифр/знаков препинания (например "10,9") — пропускаем
  clean_num_check = re.sub(r"[\d\.,\s]", "", title_str)
  if not clean_num_check:
    return None

  return title_str


def clean_price(val):
  """Очистка цен и фильтрация штрихкодов."""
  if pd.isna(val):
    return "По запросу"
  try:
    # Замена запятой на точку
    price_num = float(str(val).replace(",", ".").strip())

    # Защита от штрихкодов (EAN-13) и номеров телефонов
    if price_num > 10000 or price_num <= 0:
      return "По запросу"

    return f"{price_num:.2f} AZN"
  except ValueError:
    return "По запросу"


# ==========================================
# 3. ОСНОВНАЯ ЛОГИКА ГЕНЕРАЦИИ
# ==========================================


def generate_site_and_llms():
  os.makedirs(OUTPUT_DIR, exist_ok=True)

  # Загрузка прайса
  df = pd.read_excel(EXCEL_FILE)

  # Обработка данных
  valid_products = []
  for _, row in df.iterrows():
    title = clean_title(row.get(COL_TITLE))
    price = clean_price(row.get(COL_PRICE))

    if title:
      valid_products.append({"title": title, "price": price})

  print(f"Успешно обработано товаров: {len(valid_products)}")

  # ------------------------------------------
  # A. Генерация index.html
  # ------------------------------------------
  cards_html = []
  llms_txt_lines = [
      f"# {STORE_NAME} Catalog",
      f"Location: Baku, Azerbaijan",
      f"Total products: {len(valid_products)}",
      "\n## Products List:\n",
  ]

  for item in valid_products:
    title = item["title"]
    price = item["price"]

    # WhatsApp URL
    wa_msg = urllib.parse.quote(
        f"Salam! {STORE_NAME} - {title} ({price}) almaq istəyirəm."
    )
    wa_link = f"https://wa.me/994500000000?text={wa_msg}"  # Укажите ваш номер

    # HTML Карточка
    card = f"""
        <div class="product-card">
            <div class="product-info">
                <div class="product-title">{title}</div>
                <div class="product-price">{price}</div>
            </div>
            <a href="{wa_link}" class="buy-btn" target="_blank" rel="noopener">WhatsApp ilə Sifariş Et</a>
        </div>"""
    cards_html.append(card)

    # Строка для llms.txt
    llms_txt_lines.append(f"- {title} | Price: {price} | Order: {wa_link}")

  full_cards_str = "\n".join(cards_html)

  html_content = f"""<!DOCTYPE html>
<html lang="az">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{STORE_NAME} — Kataloq</title>
    <meta name="description" content="{STORE_NAME} məhsul kataloqu və qiymətləri. Bakı, Azərbaycan.">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        body {{ background-color: #f4f6f8; color: #333; padding: 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ font-size: 24px; color: #111; margin-bottom: 8px; }}
        .catalog-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; max-width: 1200px; margin: 0 auto; }}
        .product-card {{ background: #fff; border-radius: 8px; padding: 16px; display: flex; flex-direction: column; justify-content: space-between; border: 1px solid #e1e4e8; }}
        .product-title {{ font-size: 15px; font-weight: 600; margin-bottom: 8px; line-height: 1.4; color: #222; }}
        .product-price {{ font-size: 16px; font-weight: 700; color: #0d7a5f; margin-bottom: 12px; }}
        .buy-btn {{ display: block; text-align: center; background-color: #25D366; color: #fff; text-decoration: none; padding: 10px; border-radius: 6px; font-weight: 600; font-size: 14px; transition: background 0.2s; }}
        .buy-btn:hover {{ background-color: #1eb956; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{STORE_NAME}</h1>
        <p>Bakı, Azərbaycan | Onlayn Kataloq</p>
    </div>
    <div class="catalog-grid">
        {full_cards_str}
    </div>
</body>
</html>"""

  # Сохраняем index.html
  index_path = os.path.join(OUTPUT_DIR, "index.html")
  with open(index_path, "w", encoding="utf-8") as f:
    f.write(html_content)

  # ------------------------------------------
  # B. Генерация llms.txt и llms-full.txt
  # ------------------------------------------
  llms_path = os.path.join(OUTPUT_DIR, "llms.txt")
  with open(llms_path, "w", encoding="utf-8") as f:
    f.write("\n".join(llms_txt_lines))

  print(f"Готово!")
  print(f"HTML сохранен в: {index_path}")
  print(f"LLMS.txt сохранен в: {llms_path}")


if __name__ == "__main__":
  generate_site_and_llms()
