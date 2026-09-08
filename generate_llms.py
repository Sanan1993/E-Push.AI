import os
import re
import sys
import urllib.parse
import pandas as pd

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/14TseUjX-y0sn3fg2ovYtDQwRVGsMTpRujnE1ikIlHxw/export?format=csv"
STORE_NAME = "Makiyaj Cosmetics"
STORE_SLUG = "makiyaj"
PART_SIZE = 2500


def clean_title(val):
  if pd.isna(val):
    return None
  t = str(val).strip()
  if re.search(
      r"Anbar|Склад|Итого|Total|Əsas", t, flags=re.IGNORECASE
  ):
    return None
  if not re.search(r"[a-zA-Zа-яА-ЯəƏıIöÖğĞşŞçÇüÜ]", t):
    return None
  return t


def clean_price(val):
  if pd.isna(val):
    return "По запросу"
  try:
    p = float(str(val).replace(",", ".").replace(" ", "").strip())
    if p > 10000 or p <= 0:
      return "По запросу"
    return f"{p:.2f} AZN"
  except ValueError:
    return "По запросу"


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

  col_t, col_p = (
      df.columns[0],
      df.columns[1] if len(df.columns) > 1 else df.columns[0],
  )
  for c in df.columns:
    c_lower = str(c).lower()
    if any(k in c_lower for k in ["название", "наименование", "title", "ad"]):
      col_t = c
    if any(k in c_lower for k in ["цена", "розница", "price", "qiymət"]):
      col_p = c

  items = []
  for _, r in df.iterrows():
    t, p = clean_title(r.get(col_t)), clean_price(r.get(col_p))
    if t:
      items.append({"title": t, "price": p})

  print(f"Обработано товаров: {len(items)}")

  cards, llms_all_lines = [], []
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
        h1 {{ text-align: center; color: #111; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 15px; max-width: 1200px; margin: 0 auto; }}
        .card {{ background: #fff; padding: 15px; border-radius: 8px; border: 1px solid #ddd; display: flex; flex-direction: column; justify-content: space-between; }}
        .title {{ font-size: 14px; font-weight: 600; margin-bottom: 8px; }}
        .price {{ font-size: 16px; font-weight: bold; color: #0d7a5f; margin-bottom: 10px; }}
        .btn {{ text-align: center; background: #25D366; color: #fff; text-decoration: none; padding: 8px; border-radius: 5px; font-weight: bold; font-size: 13px; }}
    </style>
</head>
<body>
    <h1>{STORE_NAME}</h1>
    <div class="grid">{"".join(cards)}</div>
</body>
</html>"""

  # Директории публикации
  targets = [".", "public", f"stores/{STORE_SLUG}", f"public/stores/{STORE_SLUG}"]
  for d in targets:
    os.makedirs(d, exist_ok=True)

  # 1. Сохраняем HTML
  for path in [
      "index.html",
      "public/index.html",
      f"stores/{STORE_SLUG}/index.html",
      f"public/stores/{STORE_SLUG}/index.html",
  ]:
    with open(path, "w", encoding="utf-8") as f:
      f.write(html_content)

  # 2. Сохраняем llms.txt
  full_llms = (
      f"# {STORE_NAME}\nLocation: Baku, Azerbaijan\nTotal:"
      f" {len(items)}\n\n"
      + "\n".join(llms_all_lines)
  )
  for path in [
      "llms.txt",
      "public/llms.txt",
      f"stores/{STORE_SLUG}/llms.txt",
      f"stores/{STORE_SLUG}/llms-full.txt",
      f"public/stores/{STORE_SLUG}/llms.txt",
      f"public/stores/{STORE_SLUG}/llms-full.txt",
  ]:
    with open(path, "w", encoding="utf-8") as f:
      f.write(full_llms)

  # 3. Генерируем части catalog-part1.txt...
  part_num = 1
  for start_idx in range(0, len(llms_all_lines), PART_SIZE):
    chunk = llms_all_lines[start_idx : start_idx + PART_SIZE]
    part_content = f"# {STORE_NAME} - Part {part_num}\n\n" + "\n".join(chunk)
    for p_dir in [f"stores/{STORE_SLUG}", f"public/stores/{STORE_SLUG}"]:
      with open(
          os.path.join(p_dir, f"catalog-part{part_num}.txt"),
          "w",
          encoding="utf-8",
      ) as f:
        f.write(part_content)
    part_num += 1

  # 4. Robots & Sitemap
  robots_txt = "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n"
  for p in ["robots.txt", "public/robots.txt"]:
    with open(p, "w", encoding="utf-8") as f:
      f.write(robots_txt)

  sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>/ </loc></url>
  <url><loc>/stores/makiyaj</loc></url>
  <url><loc>/stores/makiyaj/llms.txt</loc></url>
</urlset>"""
  for p in ["sitemap.xml", "public/sitemap.xml"]:
    with open(p, "w", encoding="utf-8") as f:
      f.write(sitemap_xml)

  print("Все файлы сгенерированы универсально!")


if __name__ == "__main__":
  run()
