import csv
import html
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import pandas as pd

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/14TseUjX-y0sn3fg2ovYtDQwRVGsMTpRujnE1ikIlHxw/export?format=csv&gid=0"
STORE_NAME = "Makiyaj Cosmetics"
STORE_SLUG = "makiyaj"
PART_SIZE = 200
# Одна HTML-страница на все 9000+ товаров весила ~9 МБ — Bing явно пометил
# это как проблему. Режем витрину на страницы по HTML_PAGE_SIZE товаров.
# Было 300: ChatGPT сослался на "не смог прочитать страницу" по прямой
# ссылке на store, хотя сервер отдавал её быстро и полностью — возможный
# (не подтверждённый) фактор: инструмент браузинга обрезает длинные страницы.
# Уменьшаем размер, чтобы снизить такой риск, гарантии это не даёт.
HTML_PAGE_SIZE = 150
BING_KEY = "CAFD35CF8A7F03B86A676AAEEA9F724F"
GOOGLE_VERIFY_FILE = "googled45868da9ece60dc.html"
WHATSAPP_NUMBER = "994515393778"  # настоящий номер Makiyaj Cosmetics
SITE_ROOT = "https://e-push-ai.vercel.app"
# IndexNow: по протоколу ключ публичный (лежит файлом на сайте), не секрет.
INDEXNOW_KEY = "8b2effb1df567e183bb7dc114cefcb35"
# index.html дублируется и в корне, и в stores/makiyaj/ (это один и тот же
# файл) — без canonical-тега Google видит дубликат контента и не знает, что
# из этого индексировать, поэтому вообще не индексирует ни одну версию.
STORE_CANONICAL_URL = f"{SITE_ROOT}/stores/{STORE_SLUG}/"
STORE_DESCRIPTION = (
    "Makiyaj Cosmetics — корейская косметика, уход и товары для макияжа "
    "рядом с метро Azi Aslanov, Баку. Актуальные цены, заказ через WhatsApp."
)


def parse_price_azn(price_val):
  """"5,5 AZN" -> 5.5; "По запросу" или нечисловая цена -> None."""
  if price_val == "По запросу" or "AZN" not in price_val:
    return None
  numeric = price_val.replace("AZN", "").strip().replace(",", ".")
  try:
    return float(numeric)
  except ValueError:
    return None


# Справочник штрихкод -> бренд/категория/объём. Собирается локально скриптом
# tools/build_name_map.py из каталога маркетплейса и хранится в репозитории
# маленьким файлом: GitHub Action не видит гигабайтную базу на компьютере.
NAME_MAP_FILE = "data/name_map.csv"

_SIZE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(мл|ml|гр|gr|г|g|кг|kg|л|l)\b", re.IGNORECASE)
_SIZE_UNITS = {
    "мл": "мл", "ml": "мл", "гр": "г", "gr": "г", "г": "г", "g": "г",
    "кг": "кг", "kg": "кг", "л": "л", "l": "л",
}


def normalize_barcode(value):
  """Ключ для сопоставления: только цифры, до 13 знаков дополняем нулями слева
  (UPC-12 и EAN-13 с ведущим нулём — один и тот же товар)."""
  digits = re.sub(r"\D", "", str(value or ""))
  return digits.zfill(13) if digits and len(digits) <= 13 else digits


def is_valid_gtin(digits):
  """Контрольная цифра GTIN-8/12/13/14 (в базах встречаются битые штрихкоды)."""
  if not digits.isdigit() or len(digits) not in (8, 12, 13, 14):
    return False
  total = sum(
      int(d) * (3 if i % 2 == 0 else 1)
      for i, d in enumerate(reversed(digits[:-1]))
  )
  return (10 - total % 10) % 10 == int(digits[-1])


def extract_size(text):
  m = _SIZE_RE.search(text or "")
  if not m:
    return None
  return f"{m.group(1)} {_SIZE_UNITS[m.group(2).lower()]}"


def load_name_map():
  if not os.path.exists(NAME_MAP_FILE):
    return {}
  with open(NAME_MAP_FILE, encoding="utf-8", newline="") as f:
    return {row["barcode"]: row for row in csv.DictReader(f)}


def _letters_only(text):
  return re.sub(r"[^a-z0-9а-яё]", "", text.lower())


# Маркетплейс пишет в brand и служебные значения — это не бренды.
_NOT_A_BRAND = {"no brand", "nobrand", "noname", "no name", "без бренда", "нет бренда", "1"}


def clean_brand(brand):
  brand = (brand or "").strip()
  return "" if brand.lower() in _NOT_A_BRAND else brand


def _strip_brand(tokens, brand):
  """Убирает бренд из начала названия (в т.ч. неполный: LOREAL -> L'Oreal Paris)."""
  target = _letters_only(brand)
  if not target:
    return tokens, False
  acc, consumed = "", 0
  for token in tokens:
    part = _letters_only(token)
    if not part or not target.startswith(acc + part):
      break
    acc += part
    consumed += 1
    if acc == target:
      break
  if consumed and len(acc) >= 3:
    return tokens[consumed:], True
  return tokens, False


def _smart_case(token):
  if token != token.upper() or re.search(r"\d", token):
    return token  # уже смешанный регистр или код (402, SPF50, PT110-069)
  letters = re.sub(r"[^A-Za-zА-Яа-яЁё]", "", token)
  if not letters:
    return token
  if re.search(r"[А-Яа-яЁё]", letters):
    return token.lower()
  if len(letters) <= 3:
    return token  # BB, CC, SPF, UV
  return token[:1] + token[1:].lower()


def build_display_title(raw_title, info):
  """Название для витрины и ИИ: бренд + модель, объём, тип товара.

  Только факты из справочника (бренд, категория, объём) — строку названия
  маркетплейса не копируем. Без справочника — просто чистка регистра/объёма.
  """
  info = info or {}
  brand = clean_brand(info.get("brand"))
  category = (info.get("category") or "").split(",")[0].strip()
  size = extract_size(raw_title) or (info.get("size") or "").strip() or None

  cleaned = raw_title.replace("¶", " ")
  tokens = _SIZE_RE.sub(" ", cleaned).split()

  prefix_brand = False
  if brand:
    tokens, stripped = _strip_brand(tokens, brand)
    # бренд нигде в названии не упомянут — добавим его в начало
    prefix_brand = stripped or _letters_only(brand) not in _letters_only(cleaned)

  model = " ".join(_smart_case(t) for t in tokens).strip(" ,.-/")
  parts = [brand] if brand and prefix_brand else []
  if model:
    parts.append(model)
  title = " ".join(parts) or raw_title.strip()
  if size:
    title += f", {size}"
  if category:
    title += f" — {category[:1].lower()}{category[1:]}"
  return title


def build_html_page(page_cards, page_offers, page_num, total_pages):
  """Одна страница витрины: свой canonical и свой JSON-LD только на её товары
  (иначе разбиение теряет смысл — весь Schema.org дублировался бы на каждой
  странице)."""
  if page_num == 1:
    canonical_url = STORE_CANONICAL_URL
  else:
    canonical_url = f"{SITE_ROOT}/stores/{STORE_SLUG}/page-{page_num}.html"

  json_ld = {
      "@context": "https://schema.org",
      "@type": "Store",
      "name": STORE_NAME,
      "address": {
          "@type": "PostalAddress",
          "addressLocality": "Baku",
          "addressCountry": "AZ",
      },
      "makesOffer": page_offers,
  }
  json_ld_script = (
      '<script type="application/ld+json">'
      + json.dumps(json_ld, ensure_ascii=False).replace("</", "<\\/")
      + "</script>"
  )

  nav_links = []
  if page_num > 1:
    prev_href = STORE_CANONICAL_URL if page_num == 2 else f"page-{page_num - 1}.html"
    nav_links.append(f'<a href="{prev_href}" class="page-link">&larr; Əvvəlki</a>')
  if page_num < total_pages:
    nav_links.append(
        f'<a href="page-{page_num + 1}.html" class="page-link">Növbəti &rarr;</a>'
    )
  pagination_html = (
      f'<div class="pagination">{"".join(nav_links)}'
      f'<span class="page-info">Səhifə {page_num}/{total_pages}</span></div>'
  )

  title_suffix = "" if page_num == 1 else f" - Səhifə {page_num}"

  return f"""<!DOCTYPE html>
<html lang="az">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="msvalidate.01" content="{BING_KEY}">
    <meta name="description" content="{STORE_DESCRIPTION}">
    <link rel="canonical" href="{canonical_url}">
    <title>{STORE_NAME} - Azi Aslanov, Baku{title_suffix}</title>
    {json_ld_script}
    <style>
        body {{ font-family: system-ui, sans-serif; background: #f4f6f8; margin: 0; padding: 20px; color: #333; }}
        h1 {{ text-align: center; color: #111; margin-bottom: 5px; }}
        p.subtitle {{ text-align: center; color: #666; margin-bottom: 25px; font-size: 14px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 15px; max-width: 1200px; margin: 0 auto; }}
        .card {{ background: #fff; padding: 15px; border-radius: 8px; border: 1px solid #ddd; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
        .title {{ font-size: 14px; font-weight: 600; margin-bottom: 8px; color: #222; line-height: 1.3; }}
        .price {{ font-size: 16px; font-weight: bold; color: #0d7a5f; margin-bottom: 12px; }}
        .btn {{ text-align: center; background: #25D366; color: #fff; text-decoration: none; padding: 10px; border-radius: 6px; font-weight: bold; font-size: 13px; transition: background 0.2s; }}
        .btn:hover {{ background: #1eb857; }}
        .pagination {{ display: flex; justify-content: center; align-items: center; gap: 20px; margin: 30px 0 10px; font-size: 14px; }}
        .page-link {{ color: #0d7a5f; text-decoration: none; font-weight: 600; }}
        .page-link:hover {{ text-decoration: underline; }}
        .page-info {{ color: #666; }}
    </style>
</head>
<body>
    <h1>{STORE_NAME}</h1>
    <p class="subtitle">Bakı, Həzi Aslanov metrosu yaxınlığı | Koreya kosmetikası və makiyaj malları</p>
    <div class="grid">{"".join(page_cards)}</div>
    {pagination_html}
</body>
</html>"""


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

  name_map = load_name_map()
  skipped_no_stock = 0
  items = []
  for idx, r in df.iterrows():
    if len(r) < 4:
      continue

    raw_title = str(r[1]).strip()
    raw_price = str(r[3]).strip()

    if idx == 0 or raw_title.lower() in [
        "nan",
        "none",
        "",
        "mal",
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

    # Остаток (колонка 5): 0 и отрицательные значения — складские артефакты,
    # такой товар нельзя публиковать как "в наличии".
    if len(r) > 4:
      try:
        if float(str(r[4]).replace(",", ".")) <= 0:
          skipped_no_stock += 1
          continue
      except ValueError:
        pass

    digits = re.sub(r"\D", "", str(r[2])) if len(r) > 2 else ""
    items.append({
        "title": raw_title,
        "price": price_val,
        "gtin": digits if is_valid_gtin(digits) else "",
        "display": build_display_title(
            raw_title, name_map.get(normalize_barcode(digits))
        ),
        "info": name_map.get(normalize_barcode(digits)) or {},
    })

  if len(items) == 0:
    print("Внимание: Ни один товар не найден.")
    sys.exit(1)
  print(
      f"Товаров: {len(items)} | пропущено без остатка: {skipped_no_stock} |"
      f" названий из справочника: {sum(1 for i in items if i['info'])}"
  )

  cards = []
  llms_all_lines = []
  offers = []

  for i in items:
    wa_msg = urllib.parse.quote(f"Salam! Makiyaj almaq istəyirəm: {i['title']}")
    real_wa_link = f"https://wa.me/{WHATSAPP_NUMBER}?text={wa_msg}"
    # Отдаём ссылку на свой трекинг-редирект вместо прямой wa.me, чтобы считать
    # клики (в т.ч. когда ссылку пользователю показывает ИИ из llms.txt).
    wa_link = (
        f"{SITE_ROOT}/api/go?to={urllib.parse.quote(real_wa_link, safe='')}"
        f"&t={urllib.parse.quote(i['title'])}"
    )

    cards.append(f"""
        <div class="card">
            <div class="title">{html.escape(i['display'])}</div>
            <div class="price">{i['price']}</div>
            <a href="{wa_link}" target="_blank" class="btn">WhatsApp Sifariş</a>
        </div>""")

    llms_all_lines.append(f"- {i['display']} | {i['price']} | Заказать: {wa_link}")

    product = {"@type": "Product", "name": i["display"]}
    if i["gtin"]:
      product["gtin"] = i["gtin"]
    if clean_brand(i["info"].get("brand")):
      product["brand"] = {"@type": "Brand", "name": clean_brand(i["info"]["brand"])}
    if i["info"].get("category"):
      product["category"] = i["info"]["category"]
    offer = {
        "@type": "Offer",
        "itemOffered": product,
        "priceCurrency": "AZN",
        "availability": "https://schema.org/InStock",
        "url": wa_link,
    }
    price_num = parse_price_azn(i["price"])
    if price_num is not None:
      offer["price"] = price_num
    offers.append(offer)

  store_dir = f"stores/{STORE_SLUG}"
  os.makedirs(store_dir, exist_ok=True)

  # 1. Разбиваем витрину на страницы по HTML_PAGE_SIZE товаров (была одна
  # страница на ~9 МБ — Bing явно отметил это как проблему).
  total_pages = max(1, (len(cards) + HTML_PAGE_SIZE - 1) // HTML_PAGE_SIZE)

  # Подчищаем "лишние" страницы с прошлых запусков, если товаров стало меньше
  # (иначе старые page-N.html останутся висеть с устаревшим содержимым).
  for old_file in os.listdir(store_dir):
    m = re.match(r"^page-(\d+)\.html$", old_file)
    if m and int(m.group(1)) > total_pages:
      os.remove(os.path.join(store_dir, old_file))
  for page_num in range(1, total_pages + 1):
    start = (page_num - 1) * HTML_PAGE_SIZE
    end = start + HTML_PAGE_SIZE
    page_html = build_html_page(
        cards[start:end], offers[start:end], page_num, total_pages
    )
    if page_num == 1:
      # Страница 1 — она же canonical-адрес витрины, дублируется и в корень,
      # и в папку магазина (см. STORE_CANONICAL_URL выше).
      with open("index.html", "w", encoding="utf-8", newline="\n") as f:
        f.write(page_html)
      with open(f"{store_dir}/index.html", "w", encoding="utf-8", newline="\n") as f:
        f.write(page_html)
    else:
      with open(
          f"{store_dir}/page-{page_num}.html", "w", encoding="utf-8", newline="\n"
      ) as f:
        f.write(page_html)

  # 2. Создаем файл верификации Google Search Console
  google_html_content = f"google-site-verification: {GOOGLE_VERIFY_FILE}"
  with open(GOOGLE_VERIFY_FILE, "w", encoding="utf-8", newline="\n") as f:
    f.write(google_html_content)

  # 2b. Файл-ключ IndexNow: подтверждает поисковикам, что сайт наш
  with open(f"{INDEXNOW_KEY}.txt", "w", encoding="utf-8", newline="\n") as f:
    f.write(INDEXNOW_KEY)

  # 3. Создаем XML-файл верификации BingSiteAuth.xml
  bing_xml = f"""<?xml version="1.0"?>
<users>
	<user>{BING_KEY}</user>
</users>"""

  with open("BingSiteAuth.xml", "w", encoding="utf-8", newline="\n") as f:
    f.write(bing_xml)

  with open(f"{store_dir}/BingSiteAuth.xml", "w", encoding="utf-8", newline="\n") as f:
    f.write(bing_xml)

  # 4. Генерация llms.txt с расширенным гео-контекстом для ИИ
  ai_instruction = (
      f"# {STORE_NAME}\n"
      "Location: Baku, Azerbaijan\n"
      "Metro Station: Azi Aslanov (Həzi Aslanov m/s, Ази Асланов)\n"
      "Area: Near Azi Aslanov metro station, Khatai district, Baku\n"
      "Assortment: Korean Cosmetics, Anua, Beauty of Joseon, Makeup, Skincare,"
      " Beauty Products\n"
      # Только описание формата, без императивов в адрес ИИ: такие вставки
      # читаются как prompt injection и ничего не дают (Google их игнорирует).
      "Format: each line is '- <product> | <price> | Заказать: <order link>'."
      " Prices are in AZN. The order link opens a WhatsApp chat with the"
      " store.\n\n"
      f"Total items in store: {len(items)}\n\n"
  )

  full_llms = ai_instruction + "\n".join(llms_all_lines)

  with open("llms.txt", "w", encoding="utf-8", newline="\n") as f:
    f.write(full_llms)
  with open(f"{store_dir}/llms.txt", "w", encoding="utf-8", newline="\n") as f:
    f.write(full_llms)

  part_num = 1
  for start_idx in range(0, len(llms_all_lines), PART_SIZE):
    chunk = llms_all_lines[start_idx : start_idx + PART_SIZE]
    part_content = (
        f"# {STORE_NAME} (Azi Aslanov) - Part {part_num}\n"
        "Location: Azi Aslanov metro, Baku\n"
        "Format: '- <product> | <price in AZN> | Заказать: <WhatsApp order"
        f" link>'.\nTotal in part: {len(chunk)}\n\n"
        + "\n".join(chunk)
    )
    with open(
        f"{store_dir}/catalog-part{part_num}.txt", "w", encoding="utf-8", newline="\n"
    ) as f:
      f.write(part_content)
    part_num += 1

  # 5. Служебные файлы (Sitemap/robots.txt требуют АБСОЛЮТНЫХ URL, иначе Google/Bing их игнорируют)
  robots_txt = (
      "User-agent: *\n"
      "Allow: /\n"
      # /api/go — служебный трекинг-редирект на WhatsApp, не для обхода ботами
      # (иначе краулер кликает по всем 9000+ ссылкам "Заказать" на странице
      # и засоряет статистику кликов).
      "Disallow: /api/go\n"
      f"Sitemap: {SITE_ROOT}/sitemap.xml\n"
  )
  with open("robots.txt", "w", encoding="utf-8", newline="\n") as f:
    f.write(robots_txt)

  # "/" не включаем: это редирект на STORE_CANONICAL_URL (см. vercel.json), а не
  # самостоятельная страница — держать редиректящий URL в sitemap сбивает Google.
  page_urls = "\n".join(
      f"  <url><loc>{SITE_ROOT}/stores/{STORE_SLUG}/page-{n}.html</loc></url>"
      for n in range(2, total_pages + 1)
  )
  sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{STORE_CANONICAL_URL}</loc></url>
{page_urls}
  <url><loc>{SITE_ROOT}/stores/makiyaj/llms.txt</loc></url>
  <url><loc>{SITE_ROOT}/llms.txt</loc></url>
  <url><loc>{SITE_ROOT}/BingSiteAuth.xml</loc></url>
  <url><loc>{SITE_ROOT}/{GOOGLE_VERIFY_FILE}</loc></url>
</urlset>
"""
  with open("sitemap.xml", "w", encoding="utf-8", newline="\n") as f:
    f.write(sitemap_xml)

  print("Все файлы витрины и файлы для ИИ успешно сгенерированы!")


if __name__ == "__main__":
  run()
