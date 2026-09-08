import os
import sys
import urllib.parse
import pandas as pd

# Google Sheets CSV URL
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/14TseUjX-y0sn3fg2ovYtDQwRVGsMTpRujnE1ikIlHxw/export?format=csv"
STORE_NAME = "Makiyaj Cosmetics"
STORE_SLUG = "makiyaj"
PART_SIZE = 1500  # Делим по 1500 строк для гарантированной генерации частей


def run():
  print("Скачивание данных из Google Таблицы...")
  try:
    df = pd.read_csv(SHEET_CSV_URL)
  except Exception as e:
    print(f"Ошибка скачивания: {e}")
    sys.exit(1)

  if df.empty:
    print("Ошибка: Таблица пустая!")
    sys.exit(1)

  # Прямой выбор первых двух колонок (Колонка 0: Название, Колонка 1: Цена)
  col_t = df.columns[0]
  col_p = df.columns[1] if len(df.columns) > 1 else df.columns[0]

  items = []
  for _, r in df.iterrows():
    raw_title = str(r.get(col_t)).strip() if pd.notna(r.get(col_t)) else ""
    raw_price = str(r.get(col_p)).strip() if pd.notna(r.get(col_p)) else ""

    # Игнорируем пустые элементы и служебные строки "nan"
    if not raw_title or raw_title.lower() in ["nan", "none"]:
      continue

    # Форматируем цену
    price_val = raw_price if raw_price and raw_price.lower() != "nan" else "По запросу"
    if price_val != "По запросу" and "azn" not in price_val.lower():
      price_val = f"{price_val} AZN"

    items.append({"title": raw_title, "price": price_val})

  print(f"Успешно обработано товаров: {len(items)}")

  cards = []
  llms_all_lines = []

  for i in items:
    wa_msg = urllib.parse.quote(
        f"Salam! {STORE_NAME} - {i['title']} ({i['price']}) almaq istəyirəm."
    )
    wa_link = f"https://wa.me/994500000000?text={wa_msg}"

    cards.append(f"""
        <div class="card">
            <div class="title">{i['title']}</div>
            <div class="price">{i['price']}</div>
            <a href="{wa_link}" target="_blank" class="btn">WhatsApp Sifariş</a>
        </div>""")
    llms_all_lines.append(f"- {i['title']} | {i['price']} | {wa_link}")

  html_content = f"""<!DOCTYPE html>
<html lang="az">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{STORE_NAME}</title>
    <style>
        body {{ font-family: system-ui, sans-serif; background: #f4f6f8; margin: 0; padding: 20px; }}
        h1 {{ text-align: center; color: #111; margin-bottom: 25px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 15px; max-width: 1200px; margin: 0 auto; }}
        .card {{ background: #fff; padding: 15px; border-radius: 8px; border: 1px solid #ddd; display: flex; flex-direction: column; justify-content: space-between; }}
        .title {{ font-size: 14px; font-weight: 600; margin-bottom: 8px; color: #222; }}
        .price {{ font-size: 16px; font-weight: bold; color: #0d7a5f; margin-bottom: 10px; }}
        .btn {{ text-align: center; background: #25D366; color: #fff; text-decoration: none; padding: 8px; border-radius: 5px; font-weight: bold; font-size: 13px; }}
    </style>
</head>
<body>
    <h1>{STORE_NAME}</h1>
    <div class="grid">{"".join(cards)}</div>
</body>
</html>"""

  # Создаем директории
  store_dir = f"stores/{STORE_SLUG}"
  os.makedirs(store_dir, exist_ok=True)

  # 1. Сохраняем HTML
  with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
  with open(f"{store_dir}/index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

  # 2. Сохраняем llms.txt и llms-full.txt
  full_llms = (
      f"# {STORE_NAME}\nLocation: Baku, Azerbaijan\nTotal:"
      f" {len(items)}\n\n"
      + "\n".join(llms_all_lines)
  )
  with open("llms.txt", "w", encoding="utf-8") as f:
    f.write(full_llms)
  with open(f"{store_dir}/llms.txt", "w", encoding="utf-8") as f:
    f.write(full_llms)
  with open(f"{store_dir}/llms-full.txt", "w", encoding="utf-8") as f:
    f.write(full_llms)

  # 3. Генерируем части catalog-part1.txt, catalog-part2.txt...
  part_num = 1
  for start_idx in range(0, len(llms_all_lines), PART_SIZE):
    chunk = llms_all_lines[start_idx : start_idx + PART_SIZE]
    part_content = (
        f"# {STORE_NAME} - Part {part_num}\nTotal in part:"
        f" {len(chunk)}\n\n"
        + "\n".join(chunk)
    )
    with open(
        f"{store_dir}/catalog-part{part_num}.txt", "w", encoding="utf-8"
    ) as f:
      f.write(part_content)
    part_num += 1

  # 4. Robots & Sitemap
  robots_txt = "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n"
  with open("robots.txt", "w", encoding="utf-8") as f:
    f.write(robots_txt)

  sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>/</loc></url>
  <url><loc>/stores/makiyaj/index.html</loc></url>
  <url><loc>/stores/makiyaj/llms.txt</loc></url>
</urlset>"""
  with open("sitemap.xml", "w", encoding="utf-8") as f:
    f.write(sitemap_xml)

  print(
      "Скрипт выполнен успешно! Сформировано частей каталога:"
      f" {part_num - 1}"
  )


if __name__ == "__main__":
  run()
