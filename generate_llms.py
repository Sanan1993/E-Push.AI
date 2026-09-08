import os
import re
import sys
import urllib.parse
import pandas as pd

# Google Sheets CSV Link
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/14TseUjX-y0sn3fg2ovYtDQwRVGsMTpRujnE1ikIlHxw/export?format=csv"

STORE_NAME = "Makiyaj Cosmetics"
STORE_SLUG = "makiyaj"


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

  # Если таблица пустая
  if df.empty:
    print("Ошибка: Таблица пустая!")
    sys.exit(1)

  # Автоопределение: берем колонки или по названию, или тупо 1-ю и 2-ю
  col_t = df.columns[0]
  col_p = df.columns[1] if len(df.columns) > 1 else df.columns[0]

  for c in df.columns:
    c_str = str(c).lower()
    if any(k in c_str for k in ["название", "наименование", "title", "ad"]):
      col_t = c
    if any(k in c_str for k in ["цена", "розница", "price", "qiymət"]):
      col_p = c

  print(f"Используем столбцы: '{col_t}' (Название) и '{col_p}' (Цена)")

  items = []
  for _, r in df.iterrows():
    t = clean_title(r.get(col_t))
    p = clean_price(r.get(col_p))
    if t:
      items.append({"title": t, "price": p})

  print(f"Успешно обработано товаров: {len(items)}")

  cards, llms_lines = [], [
      f"# {STORE_NAME}\nLocation: Baku, Azerbaijan\nTotal items: {len(items)}\n"
  ]
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
    llms_lines.append(f"- {i['title']} | {i['price']} | {wa_link}")

  # Скрипт логгера ботов (если у вас есть эндпоинт трекера, он сработает при загрузке)
  bot_tracker_script = """
    <script>
        fetch('/api/track-bot', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                path: window.location.pathname,
                ua: navigator.userAgent
            })
        }).catch(()=>{});
    </script>
    """

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
    {bot_tracker_script}
</head>
<body>
    <h1>{STORE_NAME}</h1>
    <div class="grid">{"".join(cards)}</div>
</body>
</html>"""

  # Создаем директории
  directories = ["public", f"stores/{STORE_SLUG}", f"public/stores/{STORE_SLUG}"]
  for d in directories:
    os.makedirs(d, exist_ok=True)

  # Сохраняем HTML во все места
  html_paths = [
      "index.html",
      "public/index.html",
      f"stores/{STORE_SLUG}/index.html",
      f"public/stores/{STORE_SLUG}/index.html",
  ]
  for p in html_paths:
    with open(p, "w", encoding="utf-8") as f:
      f.write(html_content)

  # Сохраняем llms.txt во все места
  llms_txt = "\n".join(llms_lines)
  llms_paths = [
      "llms.txt",
      "public/llms.txt",
      f"stores/{STORE_SLUG}/llms.txt",
      f"public/stores/{STORE_SLUG}/llms.txt",
  ]
  for p in llms_paths:
    with open(p, "w", encoding="utf-8") as f:
      f.write(llms_txt)

  print("Успешно сгенерировано!")


if __name__ == "__main__":
  run()
