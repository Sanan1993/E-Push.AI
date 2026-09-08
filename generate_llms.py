import os
import re
import sys
import urllib.parse
import pandas as pd

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/14TseUjX-y0sn3fg2ovYtDQwRVGsMTpRujnE1ikIlHxw/export?format=csv"
STORE_NAME = "Makiyaj Cosmetics"
STORE_SLUG = "makiyaj"
PART_SIZE = 2500  # Лимит строк на один файл для ChatGPT


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

  col_t = df.columns[0]
  col_p = df.columns[1] if len(df.columns) > 1 else df.columns[0]

  for c in df.columns:
    c_str = str(c).lower()
    if any(k in c_str for k in ["название", "наименование", "title", "ad"]):
      col_t = c
    if any(k in c_str for k in ["цена", "розница", "price", "qiymət"]):
      col_p = c

  items = []
  for _, r in df.iterrows():
    t = clean_title(r.get(col_t))
    p = clean_price(r.get(col_p))
    if t:
      items.append({"title": t, "price": p})

  print(f"Успешно обработано товаров: {len(items)}")

  # 1. Формирование HTML
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
    <title>{STORE_NAME} — Kataloq</title>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; background: #f4f6f8; margin: 0; padding: 20px; }}
        h1 {{ text-align: center; color: #111; font-size: 28px; margin-bottom: 20px; }}
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
  dirs = ["public", f"stores/{STORE_SLUG}", f"public/stores/{STORE_SLUG}"]
  for d in dirs:
    os.makedirs(d, exist_ok=True)

  # Сохраняем HTML
  for path in [
      "index.html",
      "public/index.html",
      f"stores/{STORE_SLUG}/index.html",
      f"public/stores/{STORE_SLUG}/index.html",
  ]:
    with open(path, "w", encoding="utf-8") as f:
      f.write(html_content)

  # 2. Сохраняем единый llms.txt и llms-full.txt
  header_text = f"# {STORE_NAME}\nLocation: Baku, Azerbaijan\nTotal items: {len(items)}\n\n"
  full_llms_content = header_text + "\n".join(llms_all_lines)

  for path in [
      "llms.txt",
      "public/llms.txt",
      f"stores/{STORE_SLUG}/llms.txt",
      f"stores/{STORE_SLUG}/llms-full.txt",
      f"public/stores/{STORE_SLUG}/llms.txt",
  ]:
    with open(path, "w", encoding="utf-8") as f:
      f.write(full_llms_content)

  # 3. Разбиваем каталог на части catalog-part1.txt, part2.txt ...
  part_num = 1
  for start_idx in range(0, len(llms_all_lines), PART_SIZE):
    chunk = llms_all_lines[start_idx : start_idx + PART_SIZE]
    part_filename = f"catalog-part{part_num}.txt"
    part_content = (
        f"# {STORE_NAME} - Part {part_num}\nItems:"
        f" {start_idx + 1}-{start_idx + len(chunk)}\n\n"
        + "\n".join(chunk)
    )

    for p_dir in [f"stores/{STORE_SLUG}", f"public/stores/{STORE_SLUG}"]:
      with open(
          os.path.join(p_dir, part_filename), "w", encoding="utf-8"
      ) as f:
        f.write(part_content)

    part_num += 1

  print(
      f"Генерация завершена успешно! Создано частей каталога: {part_num - 1}"
  )


if __name__ == "__main__":
  run()
