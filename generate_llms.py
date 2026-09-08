import os
import sys
import urllib.parse
import pandas as pd

# Твоя Google Таблица
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/14TseUjX-y0sn3fg2ovYtDQwRVGsMTpRujnE1ikIlHxw/export?format=csv"

STORE_NAME = "Makiyaj Cosmetics"
STORE_SLUG = "makiyaj"


def run():
  print("Скачивание данных...")
  try:
    df = pd.read_csv(SHEET_CSV_URL)
  except Exception as e:
    print(f"Ошибка скачивания: {e}")
    sys.exit(1)

  if df.empty:
    print("Таблица пустая!")
    sys.exit(1)

  # Берем тупо первую и вторую колонки из таблицы
  col_title = df.columns[0]
  col_price = df.columns[1] if len(df.columns) > 1 else df.columns[0]

  cards = []
  llms_lines = [
      f"# {STORE_NAME}",
      "Location: Baku, Azerbaijan",
      f"Total items: {len(df)}\n",
  ]

  for _, row in df.iterrows():
    title = str(row[col_title]).strip() if pd.notna(row[col_title]) else ""
    price = str(row[col_price]).strip() if pd.notna(row[col_price]) else ""

    # Пропускаем только совсем пустые строки
    if not title or title.lower() in ["nan", "none"]:
      continue

    wa_msg = urllib.parse.quote(
        f"Salam! {STORE_NAME} - {title} ({price}) almaq istəyirəm."
    )
    wa_link = f"https://wa.me/994500000000?text={wa_msg}"

    cards.append(f"""
        <div class="card">
            <div class="title">{title}</div>
            <div class="price">{price} AZN</div>
            <a href="{wa_link}" target="_blank" class="btn">WhatsApp Sifariş</a>
        </div>""")

    llms_lines.append(f"- {title} | {price} AZN | {wa_link}")

  html_content = f"""<!DOCTYPE html>
<html lang="az">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{STORE_NAME}</title>
    <style>
        body {{ font-family: system-ui, sans-serif; background: #f4f6f8; margin: 0; padding: 20px; }}
        h1 {{ text-align: center; color: #111; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 15px; max-width: 1200px; margin: 20px auto; }}
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

  # Создаем папку stores/makiyaj
  os.makedirs(f"stores/{STORE_SLUG}", exist_ok=True)

  # Сохраняем в корень и в stores/makiyaj
  with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

  with open(f"stores/{STORE_SLUG}/index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

  llms_txt = "\n".join(llms_lines)
  with open("llms.txt", "w", encoding="utf-8") as f:
    f.write(llms_txt)

  with open(f"stores/{STORE_SLUG}/llms.txt", "w", encoding="utf-8") as f:
    f.write(llms_txt)

  print(f"Успешно обработано товаров: {len(cards)}")


if __name__ == "__main__":
  run()
