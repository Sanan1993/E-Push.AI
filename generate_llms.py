import collections
import csv
import html
import io
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
import pandas as pd

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/14TseUjX-y0sn3fg2ovYtDQwRVGsMTpRujnE1ikIlHxw/export?format=csv&gid=0"
STORE_NAME = "Makiyaj Cosmetics"
STORE_SLUG = "makiyaj"
PART_SIZE = 200
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
STORE_PHONE_E164 = f"+{WHATSAPP_NUMBER}"
STORE_PHONE_DISPLAY = (
    f"+{WHATSAPP_NUMBER[:3]} {WHATSAPP_NUMBER[3:5]} {WHATSAPP_NUMBER[5:8]}"
    f" {WHATSAPP_NUMBER[8:10]} {WHATSAPP_NUMBER[10:]}"
)
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
  # lower() у азербайджанской "İ" оставляет отдельный значок-точку U+0307
  return token[:1] + token[1:].lower().replace("̇", "")


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


_RU_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "ə": "e", "ı": "i", "ö": "o", "ü": "u", "ş": "sh", "ç": "ch", "ğ": "g",
}

# Отдельная страница у категории/бренда — только от этого числа товаров
# (мелкие уходят в общую страницу "Прочие товары", иначе получаются тонкие
# страницы, которые Google не любит индексировать).
HUB_MIN_ITEMS = 10
HUB_PAGE_SIZE = 100
MIN_SANE_PRICE_AZN = 0.5

PAGE_CSS = """
body { font-family: system-ui, sans-serif; background: #f4f6f8; margin: 0; padding: 20px; color: #333; }
h1 { text-align: center; color: #111; margin: 10px 0 8px; font-size: 24px; }
h2 { max-width: 1200px; margin: 28px auto 10px; font-size: 18px; color: #222; }
.crumbs { max-width: 1200px; margin: 0 auto; font-size: 13px; color: #666; }
.crumbs a { color: #0d7a5f; text-decoration: none; }
.intro { max-width: 900px; margin: 0 auto 22px; text-align: center; color: #555; font-size: 14px; line-height: 1.5; }
.intro a { color: #0d7a5f; }
.hub-grid { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 8px; }
.hub-link { background: #fff; border: 1px solid #ddd; border-radius: 6px; padding: 9px 12px; color: #222; text-decoration: none; font-size: 14px; display: flex; justify-content: space-between; gap: 8px; }
.hub-link:hover { border-color: #0d7a5f; }
.hub-link span { color: #888; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 15px; max-width: 1200px; margin: 0 auto; }
.card { background: #fff; padding: 15px; border-radius: 8px; border: 1px solid #ddd; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.title { font-size: 14px; font-weight: 600; margin-bottom: 8px; color: #222; line-height: 1.3; }
.price { font-size: 16px; font-weight: bold; color: #0d7a5f; margin-bottom: 12px; }
.btn { text-align: center; background: #25D366; color: #fff; text-decoration: none; padding: 10px; border-radius: 6px; font-weight: bold; font-size: 13px; transition: background 0.2s; }
.btn:hover { background: #1eb857; }
.pagination { display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 12px; margin: 30px 0 10px; font-size: 14px; }
.page-link { color: #0d7a5f; text-decoration: none; font-weight: 600; }
.page-link:hover { text-decoration: underline; }
.page-current { font-weight: 700; color: #111; }
footer { max-width: 1200px; margin: 40px auto 0; padding-top: 16px; border-top: 1px solid #ddd; text-align: center; font-size: 13px; color: #666; }
footer a { color: #0d7a5f; }
"""


def slugify(text):
  latin = "".join(_RU_LAT.get(ch, ch) for ch in text.lower())
  return re.sub(r"[^a-z0-9]+", "-", latin).strip("-") or "x"


def unique_slug(base, used):
  slug, n = base, 2
  while slug in used:
    slug = f"{base}-{n}"
    n += 1
  used.add(slug)
  return slug


def build_known_brands(name_map):
  """Ключ (буквы без пробелов) -> самое частое написание бренда из справочника."""
  counts = collections.Counter(
      clean_brand(row.get("brand")) for row in name_map.values()
  )
  known = {}
  for brand, _ in counts.most_common():
    key = _letters_only(brand)
    if brand and len(key) >= 4 and key not in known:
      known[key] = brand
  return known


def infer_brand(raw_title, known_brands):
  """Бренд товара без записи в справочнике: в складских названиях он идёт
  первым, ищем точное совпадение с уже известными брендами по первым словам."""
  acc, found = "", None
  for token in raw_title.replace("¶", " ").split()[:4]:
    acc += _letters_only(token)
    if acc in known_brands:
      found = known_brands[acc]
  return found


def _fmt_price(value):
  return f"{value:g}".replace(".", ",")


def _shorten(text, limit=158):
  return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _json_script(data):
  return (
      '<script type="application/ld+json">'
      + json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
      + "</script>"
  )


def pagination_html(base_path, page_num, total_pages):
  if total_pages <= 1:
    return ""

  def url(n):
    return base_path if n == 1 else f"{base_path}page-{n}.html"

  shown = sorted(
      {1, total_pages}
      | {n for n in range(page_num - 2, page_num + 3) if 1 <= n <= total_pages}
  )
  parts = []
  if page_num > 1:
    parts.append(f'<a href="{url(page_num - 1)}" class="page-link">&larr; Назад</a>')
  previous = 0
  for n in shown:
    if n - previous > 1:
      parts.append("<span>…</span>")
    if n == page_num:
      parts.append(f'<span class="page-current">{n}</span>')
    else:
      parts.append(f'<a href="{url(n)}" class="page-link">{n}</a>')
    previous = n
  if page_num < total_pages:
    parts.append(f'<a href="{url(page_num + 1)}" class="page-link">Вперёд &rarr;</a>')
  return f'<div class="pagination">{"".join(parts)}</div>'


def render_page(title, description, canonical, h1, intro_html, main_html,
                breadcrumbs, offers=None, pagination=""):
  store_ld = {
      "@context": "https://schema.org",
      "@type": "Store",
      "name": STORE_NAME,
      "telephone": STORE_PHONE_E164,
      "address": {
          "@type": "PostalAddress",
          "addressLocality": "Baku",
          "addressCountry": "AZ",
      },
  }
  if offers:
    store_ld["makesOffer"] = offers
  crumb_ld = {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
          {"@type": "ListItem", "position": n, "name": name, "item": url}
          for n, (name, url) in enumerate(breadcrumbs, start=1)
      ],
  }
  crumbs = " › ".join(
      f'<a href="{url}">{html.escape(name)}</a>' for name, url in breadcrumbs[:-1]
  )
  crumbs += (" › " if crumbs else "") + f"<span>{html.escape(breadcrumbs[-1][0])}</span>"

  return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="msvalidate.01" content="{BING_KEY}">
    <title>{html.escape(title)}</title>
    <meta name="description" content="{html.escape(description, quote=True)}">
    <link rel="canonical" href="{canonical}">
    {_json_script(store_ld)}
    {_json_script(crumb_ld)}
    <style>{PAGE_CSS}</style>
</head>
<body>
    <nav class="crumbs">{crumbs}</nav>
    <h1>{html.escape(h1)}</h1>
    <div class="intro">{intro_html}</div>
    {main_html}
    {pagination}
    <footer>{html.escape(STORE_NAME)} · Баку, рядом с метро Ази Асланов · WhatsApp: <a href="tel:{STORE_PHONE_E164}">{STORE_PHONE_DISPLAY}</a> · <a href="/llms.txt">Каталог в текстовом виде</a></footer>
</body>
</html>"""


def hub_texts(hub):
  """Заголовок, H1, вводный текст и description: только факты из данных, чтобы
  каждая страница получалась уникальной, а не шаблонной болванкой."""
  group = hub["items"]
  prices = [p for p in (parse_price_azn(i["price"]) for i in group) if p is not None]
  price_txt = (
      f"Цены от {_fmt_price(min(prices))} до {_fmt_price(max(prices))} AZN. "
      if prices else ""
  )
  name = hub["name"]
  if hub["kind"] == "kategoriya":
    others = collections.Counter(i["brand"] for i in group if i["brand"]).most_common(3)
    extra = f"Бренды: {', '.join(b for b, _ in others)}. " if others else ""
    title = f"{name} — цены в Баку | {STORE_NAME}"
    h1 = f"{name}: цены и наличие в Баку"
  elif hub["kind"] == "brend":
    others = collections.Counter(i["category"] for i in group if i["category"]).most_common(3)
    extra = f"Категории: {', '.join(c for c, _ in others)}. " if others else ""
    title = f"{name} — купить в Баку, цены | {STORE_NAME}"
    h1 = f"{name}: цены и наличие в Баку"
  else:
    extra = "Товары, не вошедшие в отдельные категории и бренды. "
    title = f"{name} | {STORE_NAME}"
    h1 = f"{name}: цены и наличие в Баку"
  plain = (
      f"Товаров в наличии: {len(group)}. {price_txt}{extra}"
      f"Магазин {STORE_NAME}, Баку, рядом с метро Ази Асланов. "
      f"Заказ через WhatsApp: {STORE_PHONE_DISPLAY}."
  )
  intro_html = (
      f"{html.escape(plain.rsplit(' Заказ через WhatsApp', 1)[0])} "
      f'Цены и остатки обновляются каждые 6 часов. '
      f'Заказ через WhatsApp: <a href="tel:{STORE_PHONE_E164}">{STORE_PHONE_DISPLAY}</a>.'
  )
  return title, h1, intro_html, _shorten(plain)


def hub_grid(heading, hubs):
  links = "".join(
      f'<a class="hub-link" href="{h["path"]}">{html.escape(h["name"])}'
      f' <span>{len(h["items"])}</span></a>'
      for h in hubs
  )
  return f"<section><h2>{heading}</h2><div class=\"hub-grid\">{links}</div></section>"


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
  known_brands = build_known_brands(name_map)
  skipped_no_stock = 0
  mapped_count = 0
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
    # В таблице партнёра встречаются цены-заглушки (0,01 AZN при остатке 34 шт.).
    # Ложную цену не публикуем — лучше честное "по запросу".
    price_check = parse_price_azn(price_val)
    if price_check is not None and price_check < MIN_SANE_PRICE_AZN:
      price_val = "По запросу"

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
    info = dict(name_map.get(normalize_barcode(digits)) or {})
    if info:
      mapped_count += 1
    brand = clean_brand(info.get("brand"))
    if not brand:
      brand = infer_brand(raw_title, known_brands) or ""
      if brand:
        info["brand"] = brand
    items.append({
        "title": raw_title,
        "price": price_val,
        "gtin": digits if is_valid_gtin(digits) else "",
        "display": build_display_title(raw_title, info),
        "info": info,
        "brand": brand,
        "category": (info.get("category") or "").split(",")[0].strip(),
    })

  if len(items) == 0:
    print("Внимание: Ни один товар не найден.")
    sys.exit(1)
  print(
      f"Товаров: {len(items)} | пропущено без остатка: {skipped_no_stock} |"
      f" названий из справочника: {mapped_count}"
  )

  llms_all_lines = []
  for n, i in enumerate(items):
    i["idx"] = n
    wa_msg = urllib.parse.quote(f"Salam! Makiyaj almaq istəyirəm: {i['title']}")
    real_wa_link = f"https://wa.me/{WHATSAPP_NUMBER}?text={wa_msg}"
    # Отдаём ссылку на свой трекинг-редирект вместо прямой wa.me, чтобы считать
    # клики (в т.ч. когда ссылку пользователю показывает ИИ из llms.txt).
    wa_link = (
        f"{SITE_ROOT}/api/go?to={urllib.parse.quote(real_wa_link, safe='')}"
        f"&t={urllib.parse.quote(i['title'])}"
    )

    i["card"] = f"""
        <div class="card">
            <div class="title">{html.escape(i['display'])}</div>
            <div class="price">{i['price']}</div>
            <a href="{wa_link}" target="_blank" class="btn">WhatsApp Sifariş</a>
        </div>"""

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
    i["offer"] = offer

  store_dir = f"stores/{STORE_SLUG}"
  os.makedirs(store_dir, exist_ok=True)

  # 1. Витрина: главная-хаб + страницы категорий и брендов. Раньше был плоский
  # список из 60+ одинаковых страниц "по алфавиту" — Google складывал их в
  # "обнаружена, не проиндексирована": ни одна не отвечала на конкретный запрос.
  for old_file in os.listdir(store_dir):
    if re.fullmatch(r"page-\d+\.html", old_file):
      os.remove(os.path.join(store_dir, old_file))  # старые плоские страницы
  for sub in ("kategoriya", "brend", "prochee"):
    shutil.rmtree(os.path.join(store_dir, sub), ignore_errors=True)

  by_category = collections.defaultdict(list)
  by_brand = collections.defaultdict(list)
  for i in items:
    if i["category"]:
      by_category[i["category"]].append(i)
    if i["brand"]:
      by_brand[_letters_only(i["brand"])].append(i)

  def make_hubs(groups, kind, name_of):
    used, hubs = set(), []
    for key, group in groups.items():
      if len(group) < HUB_MIN_ITEMS:
        continue
      name = name_of(key, group)
      slug = unique_slug(slugify(name), used)
      hubs.append({
          "kind": kind, "name": name, "slug": slug,
          "items": sorted(group, key=lambda x: x["display"].lower()),
          "path": f"/stores/{STORE_SLUG}/{kind}/{slug}/",
      })
    hubs.sort(key=lambda h: (-len(h["items"]), h["name"].lower()))
    return hubs

  category_hubs = make_hubs(by_category, "kategoriya", lambda key, group: key)
  brand_hubs = make_hubs(
      by_brand, "brend",
      lambda key, group: collections.Counter(i["brand"] for i in group).most_common(1)[0][0],
  )

  covered = {i["idx"] for hub in category_hubs + brand_hubs for i in hub["items"]}
  leftovers = [i for i in items if i["idx"] not in covered]
  hubs = category_hubs + brand_hubs
  if leftovers:
    hubs.append({
        "kind": "prochee", "name": "Прочие товары", "slug": "",
        "items": sorted(leftovers, key=lambda x: x["display"].lower()),
        "path": f"/stores/{STORE_SLUG}/prochee/",
    })
  print(
      f"Категорий-страниц: {len(category_hubs)} | брендов-страниц: {len(brand_hubs)}"
      f" | в 'Прочее': {len(leftovers)}"
  )

  sitemap_urls = [STORE_CANONICAL_URL]
  home_crumb = (STORE_NAME, STORE_CANONICAL_URL)

  for hub in hubs:
    title, h1, intro_html, description = hub_texts(hub)
    total_pages = max(1, (len(hub["items"]) + HUB_PAGE_SIZE - 1) // HUB_PAGE_SIZE)
    hub_dir = os.path.join(store_dir, hub["kind"], hub["slug"]).rstrip("\\/")
    os.makedirs(hub_dir, exist_ok=True)
    for page_num in range(1, total_pages + 1):
      chunk = hub["items"][(page_num - 1) * HUB_PAGE_SIZE : page_num * HUB_PAGE_SIZE]
      if page_num == 1:
        page_path, filename = hub["path"], "index.html"
      else:
        page_path, filename = f"{hub['path']}page-{page_num}.html", f"page-{page_num}.html"
      canonical = SITE_ROOT + page_path
      suffix = "" if page_num == 1 else f" — стр. {page_num}"
      page_html = render_page(
          title=title + suffix,
          description=(
              description if page_num == 1
              else _shorten(f"Страница {page_num}. {description}")
          ),
          canonical=canonical,
          h1=h1,
          intro_html=intro_html,
          main_html=f'<div class="grid">{"".join(i["card"] for i in chunk)}</div>',
          breadcrumbs=[home_crumb, (hub["name"], SITE_ROOT + hub["path"])]
          + ([(f"Страница {page_num}", canonical)] if page_num > 1 else []),
          offers=[i["offer"] for i in chunk],
          pagination=pagination_html(hub["path"], page_num, total_pages),
      )
      with open(os.path.join(hub_dir, filename), "w", encoding="utf-8", newline="\n") as f:
        f.write(page_html)
      sitemap_urls.append(canonical)

  home_intro = (
      f"{html.escape(STORE_NAME)} — магазин косметики и товаров для красоты в Баку, "
      "рядом с метро Ази Асланов (Хатаинский район). "
      f"В наличии {len(items)} товаров: корейская косметика, макияж, уход за кожей "
      "и волосами, парфюмерия. Цены в манатах (AZN), цены и остатки обновляются "
      "каждые 6 часов. Заказ через WhatsApp: "
      f'<a href="tel:{STORE_PHONE_E164}">{STORE_PHONE_DISPLAY}</a>.'
  )
  home_main = hub_grid("Категории", category_hubs) + hub_grid("Бренды", brand_hubs)
  if leftovers:
    home_main += hub_grid("Ещё", [h for h in hubs if h["kind"] == "prochee"])
  home_html = render_page(
      title=f"{STORE_NAME} — косметика в Баку, м. Ази Асланов: каталог и цены",
      description=STORE_DESCRIPTION,
      canonical=STORE_CANONICAL_URL,
      h1=STORE_NAME,
      intro_html=home_intro,
      main_html=home_main,
      breadcrumbs=[home_crumb],
  )
  # Главная — canonical-адрес витрины, дублируется и в корень, и в папку магазина
  # (см. STORE_CANONICAL_URL выше).
  with open("index.html", "w", encoding="utf-8", newline="\n") as f:
    f.write(home_html)
  with open(f"{store_dir}/index.html", "w", encoding="utf-8", newline="\n") as f:
    f.write(home_html)

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

  # Только реальные страницы. "/" (редирект) и служебные файлы верификации
  # в sitemap не нужны — они лишь плодили "обнаружена, не проиндексирована".
  sitemap_lines = "\n".join(f"  <url><loc>{u}</loc></url>" for u in sitemap_urls)
  sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{sitemap_lines}
  <url><loc>{SITE_ROOT}/stores/makiyaj/llms.txt</loc></url>
  <url><loc>{SITE_ROOT}/llms.txt</loc></url>
</urlset>
"""
  with open("sitemap.xml", "w", encoding="utf-8", newline="\n") as f:
    f.write(sitemap_xml)

  print("Все файлы витрины и файлы для ИИ успешно сгенерированы!")


if __name__ == "__main__":
  run()
