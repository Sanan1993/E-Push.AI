import io
import os
import re
import sys
import urllib.parse
import urllib.request
import pandas as pd

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/14TseUjX-y0sn3fg2ovYtDQwRVGsMTpRujnE1ikIlHxw/export?format=csv&gid=0"
STORE_NAME = "Makiyaj Cosmetics"
STORE_SLUG = "makiyaj"
PART_SIZE = 200  # Снизили лимит товаров на один файл, чтобы файлы весили мало и ИИ их не терял


def run():
  print("1. Скачивание данных из Google Таблицы...")
  try:
    req = urllib.request.Request(
        SHEET_CSV_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
        },
    )
    with urllib.request.urlopen(req) as response:
      csv_data = response.read().decode("utf-8")

    df = pd.read_csv(io.StringIO(csv_data), header=None, dtype=str)
  except Exception as e:
    print(f"Ошибка скачивания: {e}")
    sys.exit(1)

  if df.empty:
    print("Ошибка: Таблица пустая!")
    sys.exit(1)

  print(f"Загружено строк из таблицы: {len(df)}")

  items = []
  for _, r in df.iterrows():
    if len(r) < 2:
      continue

    raw_title = str(r[0]).strip()
    raw_price = str(r[1]).strip()

    if raw_title.lower() in [
        "nan",
        "none",
        "",
        "название",
        "ad",
        "title",
        "наименование",
    ]:
      continue
    if re.search(r"Anbar|Склад|Итого|Total|Əsas", raw_title, flags=re.IGNORECASE):
      continue

    price_val = (
        raw_price
        if raw_price.lower() not in ["nan", "none", ""]
        else "По запросу"
    )
    if price_val != "По запросу" and "azn" not in price_val.lower():
      price_val = f"{price_val} AZN"

    items.append({"title": raw_title, "price": price_val})

  print(f"Успешно обработано товаров: {len(items)}")

  if len(items) == 0:
    print("Внимание: Ни один товар не найден.")
    sys.exit(1)

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

  store_dir = f"stores/{STORE_SLUG}"
  os.makedirs(store_dir, exist_ok=True)

  # Сохраняем файлы
  with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
  with open(f"{store_dir}/index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

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

  print(f"Скрипт выполнен! Создано компактных частей каталога: {part_num - 1}")


if __name__ == "__main__":
  run()
