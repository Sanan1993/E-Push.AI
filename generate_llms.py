import collections
import csv
import datetime
import hashlib
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
# Адрес как в карточке магазина в Google Картах, подтверждён 2026-10-10.
# Раньше на сайте стоял "ул. Илгара Зульфигарова, 7K" — Google такого адреса
# не знает, и ИИ из-за расхождения сайта с Картами принимал карточку за
# "другой магазин". Название, адрес и телефон должны совпадать везде.
STORE_ADDRESS = "ул. Худу Мамедова, 38"
STORE_ADDRESS_AZ = "Xudu Məmmədov küç., 38"
# Метка карточки в Google Картах и ссылка на неё по постоянному CID.
STORE_GEO = (40.3700622, 49.9557324)
STORE_MAP_URL = "https://maps.google.com/?cid=3095303606787661578"
# Подтверждено владельцем 2026-09-30 (ежедневно, без выходного дня не уточнён
# отдельно — обычный режим для такого магазина).
STORE_HOURS_DISPLAY = "09:00–21:00"
STORE_HOURS_SCHEMA = "Mo-Su 09:00-21:00"
# "sameAs" для Schema.org Store — ссылки на другие подтверждённые профили
# этого же магазина (Google Business, Instagram и т.п.), чтобы ИИ/поисковики
# увереннее связывали их как один и тот же реальный субъект. Пока пусто —
# ни один профиль ещё не заведён/не подтверждён; заполнить реальными
# ссылками, как только они появятся (НЕ добавлять неподтверждённые).
STORE_SAME_AS = [
    # Подтверждено владельцем проекта 2026-10-10.
    "https://www.instagram.com/makiyaj.cosmetics/",
    "https://birmarket.az/merchant/4290-makiyaj-cosmetics",
    STORE_MAP_URL,
]
# Момент генерации текущего запуска — один и тот же для всех страниц одного
# прогона (не пересчитывается на каждую страницу отдельно), показывается в
# подвале каждой страницы: "регулярно обновляемые данные" — подтверждённо
# значимый для AI-цитирования сигнал, раньше был виден только на /tseny/.
GENERATION_TIMESTAMP = ""
# Хеш содержимого каждой страницы этого прогона (без метки времени) — по нему
# в sitemap ставится реальная дата последнего изменения, а не "сегодня" всем.
PAGE_HASHES = {}
LASTMOD_STATE = os.path.join("data", "sitemap_lastmod.tsv")


def _remember_page(url, page_html):
  body = page_html.replace(GENERATION_TIMESTAMP, "") if GENERATION_TIMESTAMP else page_html
  PAGE_HASHES[url] = hashlib.sha1(body.encode("utf-8")).hexdigest()[:16]
STORE_PHONE_E164 = f"+{WHATSAPP_NUMBER}"
STORE_PHONE_DISPLAY = (
    f"+{WHATSAPP_NUMBER[:3]} {WHATSAPP_NUMBER[3:5]} {WHATSAPP_NUMBER[5:8]}"
    f" {WHATSAPP_NUMBER[8:10]} {WHATSAPP_NUMBER[10:]}"
)
STORE_DESCRIPTION = (
    "Makiyaj Cosmetics — корейская косметика и товары для макияжа. Баку, "
    f"{STORE_ADDRESS}, у метро Ази Асланов. Цены, заказ через WhatsApp."
)
STORE_DESCRIPTION_AZ = (
    "Makiyaj Cosmetics — Bakıda koreya kosmetikası və makiyaj məhsulları. "
    f"{STORE_ADDRESS_AZ}, Azi Aslanov metrosu yaxınlığında. Qiymətlər, WhatsApp"
    " ilə sifariş."
)

# Кроме перевода названий категорий (data/category_az.csv), всё остальное —
# заголовки, хлебные крошки, подвал — переведено вручную здесь: объём
# фиксированных фраз маленький, спец. API/кэш под это не нужен.
UI = {
  "ru": {
      "home_name": STORE_NAME,
      "categories": "Категории",
      "brands": "Бренды",
      "more": "Ещё",
      "other_goods": "Прочие товары",
      "other_desc": "Товары, не вошедшие в отдельные категории и бренды. ",
      "back": "&larr; Назад",
      "forward": "Вперёд &rarr;",
      "page": "Страница",
      "in_stock": "Товаров в наличии",
      "prices_from": lambda lo, hi: (
          f"Цены от {lo} до {hi} AZN. " if lo != hi else f"Цена {lo} AZN. "
      ),
      "brands_label": lambda names: f"Бренды: {names}. ",
      "categories_label": lambda names: f"Категории: {names}. ",
      "updated": "Цены и остатки обновляются каждые 6 часов. ",
      "order_via": "Заказ через WhatsApp",
      "near_metro": "рядом с метро Ази Асланов",
      "baku": "Баку",
      "store_phrase": f"Магазин {STORE_NAME}",
      "cat_title": lambda name: f"{name} — цены в Баку | {STORE_NAME}",
      "product_title": lambda name: f"{name} — купить в Баку, цена | {STORE_NAME}",
      "product_in_stock": "В наличии",
      "product_price_label": lambda price: f"Цена: {price}. ",
      "cat_h1": lambda name: f"{name}: цены и наличие в Баку",
      "brand_title": lambda name: f"{name} — купить в Баку, цены | {STORE_NAME}",
      "podborka_examples": lambda names, more: (
          "Модели и оттенки: " + "; ".join(names) + (f" и ещё {more}" if more else "") + ". "
      ),
      "podborka_alt": lambda alt: f"Также ищут: {alt}. ",
      "podborki_heading": "Подборки",
      "other_title": lambda name: f"{name} | {STORE_NAME}",
      "footer": lambda stamp=True: (
          f"{html.escape(STORE_NAME)} · Баку, {html.escape(STORE_ADDRESS)}"
          f" (рядом с метро Ази Асланов) · WhatsApp:"
          f' <a href="tel:{STORE_PHONE_E164}">{STORE_PHONE_DISPLAY}</a> ·'
          ' <a href="/llms.txt">Каталог в текстовом виде</a> ·'
          f' <a href="/stores/{STORE_SLUG}/tseny/">Актуальные цены</a>'
          + (f' · Обновлено: {GENERATION_TIMESTAMP}' if stamp else '')
      ),
      "home_title": (
          f"{STORE_NAME} — косметика в Баку, м. Ази Асланов: каталог и цены"
      ),
      "home_intro": lambda n: (
          f"{html.escape(STORE_NAME)} — магазин косметики и товаров для красоты"
          f" в Баку. Адрес: {html.escape(STORE_ADDRESS)}, рядом с метро Ази"
          f" Асланов (Хатаинский район). Часы работы: {STORE_HOURS_DISPLAY}. "
          f"В наличии {n} товаров: корейская косметика, макияж, уход за кожей"
          " и волосами, парфюмерия. Цены в манатах (AZN), цены и остатки"
          " обновляются каждые 6 часов. Заказ через WhatsApp:"
          f' <a href="tel:{STORE_PHONE_E164}">{STORE_PHONE_DISPLAY}</a>.'
      ),
      "store_description": STORE_DESCRIPTION,
      "lang_switch": "Русский",
      "faq_heading": "Частые вопросы",
      "faq_cheap_q": lambda name: f"Где недорого купить {name} в Баку?",
      "faq_cheap_a": lambda name, count, price_txt: (
          f"В {STORE_NAME} сейчас {count} товаров в категории «{name}». {price_txt}"
          f"Заказ через WhatsApp: {STORE_PHONE_DISPLAY}."
      ),
      "faq_price_q": lambda name: f"Сколько стоит {name} в Баку?",
      "faq_price_a_known": lambda price_txt: price_txt,
      "faq_price_a_unknown": f"Цены в {STORE_NAME} обновляются каждые 6 часов.",
      "prices_page_title": f"Актуальные цены — {STORE_NAME}",
      "prices_page_h1": "Актуальные цены по категориям",
      "prices_page_updated": lambda ts: f"Обновлено: {ts} (данные обновляются каждые 6 часов).",
      "prices_col_category": "Категория",
      "prices_col_range": "Цены, AZN",
      "prices_col_count": "Товаров",
      "prices_link_label": "Актуальные цены",
      "home_faq_q1": f"Что такое {STORE_NAME}?",
      "home_faq_a1": lambda n: (
          f"{STORE_NAME} — магазин косметики и товаров для красоты в Баку, {n} товаров"
          " в наличии: корейская косметика, макияж, уход за кожей и волосами,"
          " парфюмерия."
      ),
      "home_faq_q2": f"Где находится {STORE_NAME}?",
      "home_faq_a2": (
          f"{STORE_ADDRESS}, рядом с метро Ази Асланов (Хатаинский район), Баку."
      ),
      "home_faq_q3": f"Как сделать заказ в {STORE_NAME}?",
      "home_faq_a3": f"Через WhatsApp: {STORE_PHONE_DISPLAY}.",
      "home_faq_q4": f"Какие часы работы у {STORE_NAME}?",
      "home_faq_a4": f"{STORE_HOURS_DISPLAY}, ежедневно.",
  },
  "az": {
      "home_name": STORE_NAME,
      "categories": "Kateqoriyalar",
      "brands": "Brendlər",
      "more": "Digər",
      "other_goods": "Digər mallar",
      "other_desc": "Ayrıca kateqoriyaya və ya brendə düşməyən mallar. ",
      "back": "&larr; Geri",
      "forward": "İrəli &rarr;",
      "page": "Səhifə",
      "in_stock": "Anbarda olan mallar",
      "prices_from": lambda lo, hi: (
          f"Qiymətlər {lo}-dan {hi} AZN-ə qədər. " if lo != hi else f"Qiymət {lo} AZN. "
      ),
      "brands_label": lambda names: f"Brendlər: {names}. ",
      "categories_label": lambda names: f"Kateqoriyalar: {names}. ",
      "updated": "Qiymətlər və qalıqlar hər 6 saatdan bir yenilənir. ",
      "order_via": "WhatsApp ilə sifariş",
      "near_metro": "Azi Aslanov metrosu yaxınlığında",
      "baku": "Bakı",
      "store_phrase": f"{STORE_NAME} mağazası",
      "cat_title": lambda name: f"{name} — Bakıda qiymətlər | {STORE_NAME}",
      "product_title": lambda name: f"{name} — Bakıda al, qiymət | {STORE_NAME}",
      "product_in_stock": "Anbarda var",
      "product_price_label": lambda price: f"Qiymət: {price}. ",
      "cat_h1": lambda name: f"{name}: Bakıda qiymət və mövcudluq",
      "brand_title": lambda name: f"{name} — Bakıda al, qiymətlər | {STORE_NAME}",
      "podborka_examples": lambda names, more: (
          "Modellər və çalarlar: " + "; ".join(names) + (f" və daha {more}" if more else "") + ". "
      ),
      "podborka_alt": lambda alt: "",
      "podborki_heading": "Seçimlər",
      "other_title": lambda name: f"{name} | {STORE_NAME}",
      "footer": lambda stamp=True: (
          f"{html.escape(STORE_NAME)} · Bakı, {html.escape(STORE_ADDRESS_AZ)}"
          f" (Azi Aslanov metrosu yaxınlığında) · WhatsApp:"
          f' <a href="tel:{STORE_PHONE_E164}">{STORE_PHONE_DISPLAY}</a> ·'
          ' <a href="/llms.txt">Mətn formatında katalog</a> ·'
          f' <a href="/stores/{STORE_SLUG}/az/tseny/">Cari qiymətlər</a>'
          + (f' · Yenilənib: {GENERATION_TIMESTAMP}' if stamp else '')
      ),
      "home_title": (
          f"{STORE_NAME} — Bakıda kosmetika, Azi Aslanov m.: kataloq və qiymətlər"
      ),
      "home_intro": lambda n: (
          f"{html.escape(STORE_NAME)} — Bakıda kosmetika və gözəllik mağazası."
          f" Ünvan: {html.escape(STORE_ADDRESS_AZ)}, Azi Aslanov metrosu"
          f" yaxınlığında (Xətai rayonu). İş saatları: {STORE_HOURS_DISPLAY}. "
          f"Anbarda {n} mal: koreya kosmetikası, makiyaj, dəri və saç qulluğu,"
          " ətriyyat. Qiymətlər manatla (AZN), qiymətlər və qalıqlar hər 6"
          " saatdan bir yenilənir. WhatsApp ilə sifariş:"
          f' <a href="tel:{STORE_PHONE_E164}">{STORE_PHONE_DISPLAY}</a>.'
      ),
      "store_description": STORE_DESCRIPTION_AZ,
      "lang_switch": "Azərbaycan",
      "faq_heading": "Tez-tez verilən suallar",
      "faq_cheap_q": lambda name: f"Bakıda {name} haradan ucuz almaq olar?",
      "faq_cheap_a": lambda name, count, price_txt: (
          f"{STORE_NAME}-də hazırda «{name}» kateqoriyasında {count} məhsul var. {price_txt}"
          f"WhatsApp ilə sifariş: {STORE_PHONE_DISPLAY}."
      ),
      "faq_price_q": lambda name: f"Bakıda {name} neçəyədir?",
      "faq_price_a_known": lambda price_txt: price_txt,
      "faq_price_a_unknown": f"{STORE_NAME}-də qiymətlər hər 6 saatdan bir yenilənir.",
      "prices_page_title": f"Cari qiymətlər — {STORE_NAME}",
      "prices_page_h1": "Kateqoriyalar üzrə cari qiymətlər",
      "prices_page_updated": lambda ts: f"Yenilənib: {ts} (məlumatlar hər 6 saatdan bir yenilənir).",
      "prices_col_category": "Kateqoriya",
      "prices_col_range": "Qiymət, AZN",
      "prices_col_count": "Mal sayı",
      "prices_link_label": "Cari qiymətlər",
      "home_faq_q1": f"{STORE_NAME} nədir?",
      "home_faq_a1": lambda n: (
          f"{STORE_NAME} — Bakıda kosmetika və gözəllik mağazası, anbarda {n} mal:"
          " koreya kosmetikası, makiyaj, dəri və saç qulluğu, ətriyyat."
      ),
      "home_faq_q2": f"{STORE_NAME} haradadır?",
      "home_faq_a2": (
          f"{STORE_ADDRESS_AZ}, Azi Aslanov metrosu yaxınlığında (Xətai rayonu), Bakı."
      ),
      "home_faq_q3": f"{STORE_NAME}-də necə sifariş vermək olar?",
      "home_faq_a3": f"WhatsApp ilə: {STORE_PHONE_DISPLAY}.",
      "home_faq_q4": f"{STORE_NAME}-nin iş saatları hansıdır?",
      "home_faq_a4": f"{STORE_HOURS_DISPLAY}, hər gün.",
  },
}


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
_SIZE_UNITS_AZ = {
    "мл": "ml", "ml": "ml", "гр": "q", "gr": "q", "г": "q", "g": "q",
    "кг": "kq", "kg": "kq", "л": "l", "l": "l",
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


def extract_size(text, lang="ru"):
  m = _SIZE_RE.search(text or "")
  if not m:
    return None
  units = _SIZE_UNITS_AZ if lang == "az" else _SIZE_UNITS
  return f"{m.group(1)} {units[m.group(2).lower()]}"


def load_name_map():
  if not os.path.exists(NAME_MAP_FILE):
    return {}
  with open(NAME_MAP_FILE, encoding="utf-8", newline="") as f:
    return {row["barcode"]: row for row in csv.DictReader(f)}


# Перевод названий категорий на азербайджанский. Ключ — уже ОБРЕЗАННАЯ до
# первого слова/фразы перед запятой форма (как её возвращает
# `category.split(",")[0]` в build_display_title/run — сайт везде показывает
# именно её, а не полную формулировку из справочника), собран и сверен
# вручную 2026-09-27 (см. data/category_az_draft.csv — черновик с проверкой
# по полным названиям из партнёрского каталога).
CATEGORY_AZ_FILE = "data/category_az.csv"


def load_category_az():
  if not os.path.exists(CATEGORY_AZ_FILE):
    return {}
  with open(CATEGORY_AZ_FILE, encoding="utf-8", newline="") as f:
    return {row["category_ru"]: row["category_az"] for row in csv.DictReader(f)}


def category_display(category, lang, category_az):
  if lang == "az" and category:
    return category_az.get(category, category)
  return category


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


# Складские названия смешивают русскую транслитерацию ("Dlya Lica"), азербайджан-
# ские слова ("Uchun", "Dirnaq Boyasi") и КАПС. Покупатель пишет "для лица",
# "лак для ногтей" — приводим к нормальным словам. Только однозначные слова.
_TRANSLIT_RU = {
    "dlya": "для", "krem": "крем", "kremi": "кремы", "maska": "маска",
    "maski": "маски", "balzam": "бальзам", "skrab": "скраб", "pomada": "помада",
    "blesk": "блеск", "lica": "лица", "volos": "волос", "dusha": "душа",
    "tela": "тела", "ruk": "рук", "gub": "губ", "glaz": "глаз",
    "shampun": "шампунь", "sprey": "спрей", "loson": "лосьон", "tonik": "тоник",
    "tush": "тушь", "karandash": "карандаш", "maslo": "масло", "i": "и",
    "pitaniye": "питание", "dezodorant": "дезодорант", "pena": "пена",
    "penka": "пенка",
}
_ALWAYS_LOWER = {"для", "и", "лица", "рук", "волос", "душа", "тела", "губ", "глаз",
                 "və", "üçün", "üz", "saç", "duş", "bədən", "dodaq", "göz", "əl"}
# В азербайджанском порядок слов обратный ("üz üçün krem"), поэтому пословная
# подстановка портит текст — переводим только союз, остальное не трогаем.
_TRANSLIT_AZ = {"i": "və"}
_LOWER_WORDS = {"for", "and", "the", "de", "di", "up", "on", "of", "in", "to", "with"}
_TITLE_WORDS = {"oil", "sun", "dry", "lip", "eye", "gel", "top", "new", "hair"}


def _normalize_tokens(tokens, lang):
  table = _TRANSLIT_AZ if lang == "az" else _TRANSLIT_RU
  out, n = [], 0
  while n < len(tokens):
    t = tokens[n]
    key = t.lower().strip(",.;:")
    nxt = tokens[n + 1].lower().strip(",.;:") if n + 1 < len(tokens) else ""
    if key == "dirnaq" and nxt == "boyasi":
      out.append("dırnaq boyası" if lang == "az" else "лак для ногтей")
      n += 2
      continue
    if key in table:
      word = table[key]
      out.append(word.capitalize() if t[:1].isupper() and word not in _ALWAYS_LOWER else word)
    elif t.isupper() and key in _LOWER_WORDS:
      out.append(key)
    elif t.isupper() and key in _TITLE_WORDS:
      out.append(key.capitalize())
    else:
      out.append(t)
    n += 1
  return out


def build_display_title(raw_title, info, lang="ru", category_az=None, normalize=True):
  """Название для витрины и ИИ: бренд + модель, объём, тип товара.

  Только факты из справочника (бренд, категория, объём) — строку названия
  маркетплейса не копируем. Без справочника — просто чистка регистра/объёма.
  """
  info = info or {}
  brand = clean_brand(info.get("brand"))
  category = (info.get("category") or "").split(",")[0].strip()
  category = category_display(category, lang, category_az or {})
  size = extract_size(raw_title, lang) or (info.get("size") or "").strip() or None

  cleaned = raw_title.replace("¶", " ")
  tokens = _SIZE_RE.sub(" ", cleaned).split()

  prefix_brand = False
  if brand:
    tokens, stripped = _strip_brand(tokens, brand)
    # бренд нигде в названии не упомянут — добавим его в начало
    prefix_brand = stripped or _letters_only(brand) not in _letters_only(cleaned)

  if normalize:
    tokens = _normalize_tokens(tokens, lang)
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

# Подборки "бренд × тип" и "колготки N DEN": точное совпадение с запросами
# уровня "бренд + тип" ("краска для волос Ollin Баку") — отдельная страница
# со списком моделей/оттенков и ценами, а не только общий хаб бренда.
PODBORKA_MIN_ITEMS = 10
PODBORKA_EXAMPLES = 12
DEN_RE = re.compile(r"(\d{1,3})\s*(?:den|daino|денье)", re.IGNORECASE)
# Как покупатели пишут эти бренды кириллицей (ключ — _letters_only(бренд)).
BRAND_CYR_RU = {
    "conte": "Конте", "goldenrose": "Голден Роуз", "relouis": "Релуи",
    "pastel": "Пастель", "ollinprofessional": "Оллин Профессионал",
    "lattafaperfumes": "Латтафа", "garnier": "Гарнье",
    "lorealparis": "Лореаль Париж", "maybellinenewyork": "Мейбеллин",
    "topface": "Топфейс", "luxvisage": "Люкс Визаж",
    "evelinecosmetics": "Эвелин", "flormar": "Фломар",
    "compliment": "Комплимент", "nivea": "Нивея", "bioderma": "Биодерма",
    "goldenlady": "Голден Леди", "viviennesabo": "Вивьен Сабо",
    "innamore": "Иннаморе", "incanto": "Инканто", "rexona": "Рексона",
    "dove": "Дав", "gillette": "Жиллет", "catrice": "Катрис",
    "estelprofessional": "Эстель Профессионал", "lakme": "Лакме",
}
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
a.title { text-decoration: none; display: block; }
.price { font-size: 16px; font-weight: bold; color: #0d7a5f; margin-bottom: 12px; }
.btn { text-align: center; background: #25D366; color: #fff; text-decoration: none; padding: 10px; border-radius: 6px; font-weight: bold; font-size: 13px; transition: background 0.2s; }
.btn:hover { background: #1eb857; }
.pagination { display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 12px; margin: 30px 0 10px; font-size: 14px; }
.page-link { color: #0d7a5f; text-decoration: none; font-weight: 600; }
.page-link:hover { text-decoration: underline; }
.page-current { font-weight: 700; color: #111; }
footer { max-width: 1200px; margin: 40px auto 0; padding-top: 16px; border-top: 1px solid #ddd; text-align: center; font-size: 13px; color: #666; }
footer a { color: #0d7a5f; }
.faq { max-width: 900px; margin: 30px auto 0; }
.faq h2 { margin: 0 0 12px; }
.faq-item { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 12px 16px; margin-bottom: 10px; }
.faq-item h3 { margin: 0 0 6px; font-size: 15px; color: #111; }
.faq-item p { margin: 0; font-size: 14px; color: #555; line-height: 1.5; }
.prices-table { max-width: 900px; margin: 0 auto; width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }
.prices-table th, .prices-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; font-size: 14px; }
.prices-table th { background: #eef1f0; color: #333; }
.prices-table a { color: #0d7a5f; text-decoration: none; }
.prices-updated { text-align: center; color: #777; font-size: 13px; margin: 10px 0 20px; }
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


def pagination_html(base_path, page_num, total_pages, lang="ru"):
  if total_pages <= 1:
    return ""
  strings = UI[lang]

  def url(n):
    return base_path if n == 1 else f"{base_path}page-{n}.html"

  shown = sorted(
      {1, total_pages}
      | {n for n in range(page_num - 2, page_num + 3) if 1 <= n <= total_pages}
  )
  parts = []
  if page_num > 1:
    parts.append(f'<a href="{url(page_num - 1)}" class="page-link">{strings["back"]}</a>')
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
    parts.append(f'<a href="{url(page_num + 1)}" class="page-link">{strings["forward"]}</a>')
  return f'<div class="pagination">{"".join(parts)}</div>'


def render_page(title, description, canonical, h1, intro_html, main_html,
                breadcrumbs, offers=None, pagination="", lang="ru", alt_links=None,
                faq_html="", extra_ld=None, stamp=True):
  # stamp=False у страниц товаров: метка времени в подвале меняла бы все
  # ~18,6 тыс. файлов при каждом прогоне и раздувала авто-коммиты cron.
  store_ld = {
      "@context": "https://schema.org",
      "@type": "Store",
      "name": STORE_NAME,
      "telephone": STORE_PHONE_E164,
      "openingHours": STORE_HOURS_SCHEMA,
      "address": {
          "@type": "PostalAddress",
          "streetAddress": STORE_ADDRESS_AZ if lang == "az" else STORE_ADDRESS,
          "addressLocality": "Baku",
          "addressCountry": "AZ",
      },
      "geo": {
          "@type": "GeoCoordinates",
          "latitude": STORE_GEO[0],
          "longitude": STORE_GEO[1],
      },
      "hasMap": STORE_MAP_URL,
  }
  if STORE_SAME_AS:
    store_ld["sameAs"] = STORE_SAME_AS
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

  # hreflang: обе языковые версии остаются self-canonical и просто ссылаются
  # друг на друга — принудительного редиректа по IP/языку браузера нет
  # (боты ходят в основном с американских IP независимо от того, кто реально
  # спрашивает, форсированный редирект их бы путал).
  alt_html = "".join(
      f'<link rel="alternate" hreflang="{hl}" href="{url}">'
      for hl, url in (alt_links or [])
  )
  extra_ld_html = "".join(_json_script(ld) for ld in (extra_ld or []))

  return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="msvalidate.01" content="{BING_KEY}">
    <title>{html.escape(title)}</title>
    <meta name="description" content="{html.escape(description, quote=True)}">
    <link rel="canonical" href="{canonical}">
    {alt_html}
    {_json_script(store_ld)}
    {_json_script(crumb_ld)}
    {extra_ld_html}
    <style>{PAGE_CSS}</style>
</head>
<body>
    <nav class="crumbs">{crumbs}</nav>
    <h1>{html.escape(h1)}</h1>
    <div class="intro">{intro_html}</div>
    {main_html}
    {pagination}
    {faq_html}
    <footer>{UI[lang]["footer"](stamp)}</footer>
</body>
</html>"""


def hub_texts(hub, lang="ru", category_az=None, display_name=None):
  """Заголовок, H1, вводный текст и description: только факты из данных, чтобы
  каждая страница получалась уникальной, а не шаблонной болванкой."""
  strings = UI[lang]
  group = hub["items"]
  prices = [p for p in (parse_price_azn(i["price"]) for i in group) if p is not None]
  price_txt = (
      strings["prices_from"](_fmt_price(min(prices)), _fmt_price(max(prices)))
      if prices else ""
  )
  # Название бренда не переводится, название категории — переводится (если
  # есть в словаре), берём его из display_name, посчитанного вызывающим кодом.
  name = display_name if display_name is not None else hub["name"]
  if hub["kind"] == "kategoriya":
    others = collections.Counter(i["brand"] for i in group if i["brand"]).most_common(3)
    extra = strings["brands_label"](", ".join(b for b, _ in others)) if others else ""
    title = strings["cat_title"](name)
    h1 = strings["cat_h1"](name)
  elif hub["kind"] == "brend":
    cats = collections.Counter(
        category_display(i["category"], lang, category_az or {})
        for i in group if i["category"]
    ).most_common(3)
    extra = strings["categories_label"](", ".join(c for c, _ in cats)) if cats else ""
    title = strings["brand_title"](name)
    h1 = strings["cat_h1"](name)
  elif hub["kind"] == "podborka":
    # Размеры и цвета одной модели ("Conte Active 20 DEN 2 S Mocca", "... 3 M
    # Natural") схлопываем по первым четырём словам, чтобы список показывал
    # разные модели/оттенки, а не 12 вариантов одного товара.
    models = {}
    for i in group:
      short = (i["display_az"] if lang == "az" else i["display"]).split(" — ")[0]
      models.setdefault(" ".join(short.split()[:4]).lower(), short)
    short_names = list(models.values())
    shown = short_names[:PODBORKA_EXAMPLES]
    extra = strings["podborka_examples"](shown, len(short_names) - len(shown))
    if hub.get("alt_name"):
      extra = strings["podborka_alt"](hub["alt_name"]) + extra
    title = strings["brand_title"](name)
    h1 = strings["cat_h1"](name)
  else:
    extra = strings["other_desc"]
    title = strings["other_title"](name)
    h1 = strings["cat_h1"](name)
  plain = (
      f"{strings['in_stock']}: {len(group)}. {price_txt}{extra}"
      f"{strings['store_phrase']}, {strings['baku']}, {strings['near_metro']}. "
      f"{strings['order_via']}: {STORE_PHONE_DISPLAY}."
  )
  intro_html = (
      f"{html.escape(plain.rsplit(' ' + strings['order_via'], 1)[0])} "
      f"{strings['updated']}"
      f'{strings["order_via"]}: <a href="tel:{STORE_PHONE_E164}">{STORE_PHONE_DISPLAY}</a>.'
  )
  return title, h1, intro_html, _shorten(plain)


def faq_block(hub, lang, display_name):
  """FAQPage JSON-LD + видимый блок вопрос-ответ на странице категории/бренда.

  Только для kategoriya/brend (у "Прочее" нет осмысленного "сколько стоит X").
  Данные те же, что в hub_texts, но текст сформулирован как самостоятельный,
  цитируемый кусок факта — а не предложение внутри абзаца витрины: по GEO-
  исследованиям именно такие явные вопрос-ответ фрагменты чаще попадают в
  ответы ИИ-ассистентов, чем тот же факт внутри сплошного текста.
  """
  if hub["kind"] not in ("kategoriya", "brend", "podborka"):
    return "", None
  strings = UI[lang]
  group = hub["items"]
  prices = [p for p in (parse_price_azn(i["price"]) for i in group) if p is not None]
  price_txt = (
      strings["prices_from"](_fmt_price(min(prices)), _fmt_price(max(prices)))
      if prices else ""
  )
  name = display_name
  # В вопросах категория идёт строчными буквами ("недорого купить тушь..."),
  # как и в build_display_title; название бренда регистр не меняет.
  if hub["kind"] == "podborka":
    name_lc = hub["name_lc_az"] if lang == "az" else hub["name_lc"]
  else:
    name_lc = (name[:1].lower() + name[1:]) if hub["kind"] == "kategoriya" else name

  q1 = strings["faq_cheap_q"](name_lc)
  a1 = strings["faq_cheap_a"](name, len(group), price_txt)
  q2 = strings["faq_price_q"](name_lc)
  a2 = strings["faq_price_a_known"](price_txt) if price_txt else strings["faq_price_a_unknown"]

  faq_ld = {
      "@context": "https://schema.org",
      "@type": "FAQPage",
      "mainEntity": [
          {
              "@type": "Question", "name": q,
              "acceptedAnswer": {"@type": "Answer", "text": a},
          }
          for q, a in ((q1, a1), (q2, a2))
      ],
  }
  faq_html = (
      f'<section class="faq"><h2>{html.escape(strings["faq_heading"])}</h2>'
      f'<div class="faq-item"><h3>{html.escape(q1)}</h3><p>{html.escape(a1)}</p></div>'
      f'<div class="faq-item"><h3>{html.escape(q2)}</h3><p>{html.escape(a2)}</p></div>'
      f"</section>"
  )
  return faq_html, faq_ld


def home_faq_block(lang, item_count):
  """FAQ-блок для главной страницы: закрывает "около-брендовые" вопросы
  (что это, где, как заказать, часы) — ровно тот тип вопроса, который уже
  подтверждённо даёт цитирование (3-4 из 4 в трекере), только теперь ещё и
  на самой часто обходимой краулерами странице сайта."""
  strings = UI[lang]
  qa = [
      (strings["home_faq_q1"], strings["home_faq_a1"](item_count)),
      (strings["home_faq_q2"], strings["home_faq_a2"]),
      (strings["home_faq_q3"], strings["home_faq_a3"]),
      (strings["home_faq_q4"], strings["home_faq_a4"]),
  ]
  faq_ld = {
      "@context": "https://schema.org",
      "@type": "FAQPage",
      "mainEntity": [
          {
              "@type": "Question", "name": q,
              "acceptedAnswer": {"@type": "Answer", "text": a},
          }
          for q, a in qa
      ],
  }
  items_html = "".join(
      f'<div class="faq-item"><h3>{html.escape(q)}</h3><p>{html.escape(a)}</p></div>'
      for q, a in qa
  )
  faq_html = (
      f'<section class="faq"><h2>{html.escape(strings["faq_heading"])}</h2>'
      f"{items_html}</section>"
  )
  return faq_html, faq_ld


def lang_path(path, lang):
  """RU-путь /stores/<slug>/... -> AZ-путь /stores/<slug>/az/... (RU без изменений)."""
  if lang == "ru":
    return path
  return path.replace(f"/stores/{STORE_SLUG}/", f"/stores/{STORE_SLUG}/az/", 1)


def prices_table_html(category_hubs, lang, category_az):
  strings = UI[lang]
  rows = []
  for hub in category_hubs:
    group = hub["items"]
    prices = [p for p in (parse_price_azn(i["price"]) for i in group) if p is not None]
    if not prices:
      continue
    name = category_az.get(hub["name"], hub["name"]) if lang == "az" else hub["name"]
    rows.append((name, min(prices), max(prices), len(group), lang_path(hub["path"], lang)))
  rows.sort(key=lambda r: r[0].lower())
  body = "".join(
      f'<tr><td><a href="{path}">{html.escape(name)}</a></td>'
      f"<td>{_fmt_price(lo)}–{_fmt_price(hi)}</td><td>{count}</td></tr>"
      for name, lo, hi, count, path in rows
  )
  return (
      f'<table class="prices-table"><thead><tr>'
      f'<th>{html.escape(strings["prices_col_category"])}</th>'
      f'<th>{html.escape(strings["prices_col_range"])}</th>'
      f'<th>{html.escape(strings["prices_col_count"])}</th>'
      f"</tr></thead><tbody>{body}</tbody></table>"
  )


def hub_grid(heading, hubs, lang="ru", category_az=None):
  def name_of(h):
    if lang == "az" and h["kind"] == "kategoriya":
      return (category_az or {}).get(h["name"], h["name"])
    if lang == "az" and h["kind"] == "podborka":
      return h["name_az"]
    return h["name"]

  links = "".join(
      f'<a class="hub-link" href="{lang_path(h["path"], lang)}">{html.escape(name_of(h))}'
      f' <span>{len(h["items"])}</span></a>'
      for h in hubs
  )
  return f"<section><h2>{heading}</h2><div class=\"hub-grid\">{links}</div></section>"


def run():
  global GENERATION_TIMESTAMP
  GENERATION_TIMESTAMP = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
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
  category_az = load_category_az()
  known_brands = build_known_brands(name_map)
  skipped_no_stock = 0
  skipped_bad_price = 0
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
    # Ложную цену не публикуем, товар целиком не выводим, пока партнёр не
    # исправит цену в таблице.
    price_check = parse_price_azn(price_val)
    if price_check is not None and price_check < MIN_SANE_PRICE_AZN:
      skipped_bad_price += 1
      continue

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
        "display_az": build_display_title(raw_title, info, "az", category_az),
        # старое (до чистки) название — только для slug, чтобы URL страниц
        # товаров, уже отправленные в IndexNow, не менялись
        "display_legacy": build_display_title(raw_title, info, normalize=False),
        "info": info,
        "brand": brand,
        "category": (info.get("category") or "").split(",")[0].strip(),
    })

  if len(items) == 0:
    print("Внимание: Ни один товар не найден.")
    sys.exit(1)
  print(
      f"Товаров: {len(items)} | пропущено без остатка: {skipped_no_stock} |"
      f" с ценой-заглушкой: {skipped_bad_price} |"
      f" названий из справочника: {mapped_count}"
  )

  llms_all_lines = []
  used_product_slugs = set()
  for n, i in enumerate(items):
    i["idx"] = n
    # Отдельная страница на каждый товар (не только карточка внутри хаба
    # категории/бренда) — без неё у конкретного SKU нет своего URL, который
    # можно процитировать как самостоятельный, извлекаемый кусок факта
    # (название + объём + цена), а именно такие страницы реально выигрывают
    # generic-запросы у конкурентов (см. tools/geo_tracker round 3, 2026-10-01).
    # Если название уже начинается с бренда (обычный случай), не дублируем
    # бренд в slug второй раз (иначе получалось "3w-clinic-3w-clinic-...").
    has_brand_prefix = i["brand"] and i["display_legacy"].lower().startswith(i["brand"].lower())
    base_slug = slugify(
        i["display_legacy"] if not i["brand"] or has_brand_prefix
        else f"{i['brand']} {i['display_legacy']}"
    )
    i["product_slug"] = unique_slug(base_slug, used_product_slugs)
    i["product_path"] = f"/stores/{STORE_SLUG}/tovar/{i['product_slug']}/"

    wa_msg = urllib.parse.quote(f"Salam! Makiyaj almaq istəyirəm: {i['title']}")
    real_wa_link = f"https://wa.me/{WHATSAPP_NUMBER}?text={wa_msg}"
    # Отдаём ссылку на свой трекинг-редирект вместо прямой wa.me, чтобы считать
    # клики (в т.ч. когда ссылку пользователю показывает ИИ из llms.txt).
    wa_link = (
        f"{SITE_ROOT}/api/go?to={urllib.parse.quote(real_wa_link, safe='')}"
        f"&t={urllib.parse.quote(i['title'])}"
    )
    i["wa_link"] = wa_link
    product_url_ru = SITE_ROOT + i["product_path"]
    product_url_az = SITE_ROOT + lang_path(i["product_path"], "az")

    i["card"] = f"""
        <div class="card">
            <a class="title" href="{product_url_ru}">{html.escape(i['display'])}</a>
            <div class="price">{i['price']}</div>
            <a href="{wa_link}" target="_blank" class="btn">WhatsApp Sifariş</a>
        </div>"""
    i["card_az"] = f"""
        <div class="card">
            <a class="title" href="{product_url_az}">{html.escape(i['display_az'])}</a>
            <div class="price">{i['price']}</div>
            <a href="{wa_link}" target="_blank" class="btn">WhatsApp Sifariş</a>
        </div>"""

    llms_all_lines.append(f"- {i['display']} | {i['price']} | Заказать: {wa_link}")

    price_num = parse_price_azn(i["price"])
    for lang, offer_key, display_key in (
        ("ru", "offer", "display"), ("az", "offer_az", "display_az"),
    ):
      product = {"@type": "Product", "name": i[display_key]}
      if i["gtin"]:
        product["gtin"] = i["gtin"]
      if clean_brand(i["info"].get("brand")):
        product["brand"] = {"@type": "Brand", "name": clean_brand(i["info"]["brand"])}
      if i["info"].get("category"):
        cat = i["info"]["category"].split(",")[0].strip()
        product["category"] = category_display(cat, lang, category_az)
      offer = {
          "@type": "Offer",
          "itemOffered": product,
          "priceCurrency": "AZN",
          "availability": "https://schema.org/InStock",
          "url": wa_link,
      }
      if price_num is not None:
        offer["price"] = price_num
      i[offer_key] = offer

  store_dir = f"stores/{STORE_SLUG}"
  os.makedirs(store_dir, exist_ok=True)

  # 1. Витрина: главная-хаб + страницы категорий и брендов. Раньше был плоский
  # список из 60+ одинаковых страниц "по алфавиту" — Google складывал их в
  # "обнаружена, не проиндексирована": ни одна не отвечала на конкретный запрос.
  for old_file in os.listdir(store_dir):
    if re.fullmatch(r"page-\d+\.html", old_file):
      os.remove(os.path.join(store_dir, old_file))  # старые плоские страницы
  for sub in ("kategoriya", "brend", "prochee", "podborka", "az"):
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

  # Подборки: "бренд × тип" (например "Краска для волос Ollin Professional")
  # и "Колготки N DEN". Добавляются в hubs после "Прочего", поэтому на
  # родителя товара в хлебных крошках (idx_to_hub, setdefault) не влияют.
  def _lc_first(text):
    return text[:1].lower() + text[1:]

  brand_hub_by_key = {_letters_only(h["name"]): h for h in brand_hubs}
  category_hub_by_name = {h["name"]: h for h in category_hubs}
  podborki, related = [], collections.defaultdict(list)
  used_podborka = set()

  def add_podborka(name_ru, name_az, name_lc, name_lc_az, group, parents, alt_name=""):
    slug = unique_slug(slugify(name_ru), used_podborka)
    p = {
        "kind": "podborka", "name": name_ru, "name_az": name_az,
        "name_lc": name_lc, "name_lc_az": name_lc_az, "slug": slug,
        "alt_name": alt_name,
        "items": sorted(group, key=lambda x: x["display"].lower()),
        "path": f"/stores/{STORE_SLUG}/podborka/{slug}/",
        "parent": parents[0],
    }
    podborki.append(p)
    for parent in parents:
      related[(parent["kind"], parent["slug"])].append(p)

  pair_groups = collections.defaultdict(list)
  for i in items:
    if i["brand"] and i["category"]:
      pair_groups[(_letters_only(i["brand"]), i["category"])].append(i)
  for (bkey, cat), group in sorted(pair_groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
    bhub, chub = brand_hub_by_key.get(bkey), category_hub_by_name.get(cat)
    if len(group) < PODBORKA_MIN_ITEMS or not bhub or not chub:
      continue
    # Если пара покрывает весь бренд или всю категорию — это дубль уже
    # существующего хаба, отдельная страница ничего не добавит.
    if len(group) >= len(bhub["items"]) or len(group) >= len(chub["items"]):
      continue
    cat_ru = "Колготки" if cat == "Колготки и чулки" else cat
    cat_az_name = category_az.get(cat, cat)
    brand_name = bhub["name"]
    add_podborka(
        f"{cat_ru} {brand_name}", f"{brand_name} {_lc_first(cat_az_name)}",
        f"{_lc_first(cat_ru)} {brand_name}", f"{brand_name} {_lc_first(cat_az_name)}",
        group, [bhub, chub], alt_name=BRAND_CYR_RU.get(bkey, ""),
    )

  tights_hub = category_hub_by_name.get("Колготки и чулки")
  if tights_hub:
    den_groups = collections.defaultdict(list)
    for i in tights_hub["items"]:
      m = DEN_RE.search(i["display"])
      if m:
        den_groups[int(m.group(1))].append(i)
    tights_az = category_az.get("Колготки и чулки", "Колготки и чулки")
    for den, group in sorted(den_groups.items()):
      if len(group) < PODBORKA_MIN_ITEMS:
        continue
      add_podborka(
          f"Колготки {den} DEN", f"{tights_az} {den} DEN",
          f"колготки {den} DEN", f"{_lc_first(tights_az)} {den} DEN",
          group, [tights_hub],
      )
  for lst in related.values():
    lst.sort(key=lambda p: (-len(p["items"]), p["name"].lower()))
  hubs = hubs + podborki
  print(f"Подборок: {len(podborki)}")

  def hub_display_name(hub, lang):
    if hub["kind"] == "podborka":
      return hub["name_az"] if lang == "az" else hub["name"]
    if hub["kind"] == "prochee":
      return UI[lang]["other_goods"]
    if hub["kind"] == "kategoriya" and lang == "az":
      return category_az.get(hub["name"], hub["name"])
    return hub["name"]

  # Родитель для хлебных крошек на странице товара: категория приоритетнее
  # бренда (порядок hubs = category_hubs + brand_hubs + "Прочее"), у каждого
  # товара гарантированно есть ровно один родитель — "Прочее" покрывает всех,
  # кто не попал ни в одну категорию/бренд.
  idx_to_hub = {}
  for hub in hubs:
    for it in hub["items"]:
      idx_to_hub.setdefault(it["idx"], hub)

  az_home_url = SITE_ROOT + lang_path(f"/stores/{STORE_SLUG}/", "az")
  sitemap_urls = [STORE_CANONICAL_URL, az_home_url]
  home_crumb = {
      "ru": (STORE_NAME, STORE_CANONICAL_URL),
      "az": (STORE_NAME, SITE_ROOT + lang_path(f"/stores/{STORE_SLUG}/", "az")),
  }

  # Каждый хаб рендерится дважды — RU (как раньше, без изменений в путях,
  # чтобы не сбросить уже начавшуюся индексацию) и AZ (зеркально, под /az/).
  # Оба варианта self-canonical и связаны через hreflang, без принудительного
  # редиректа по IP — боты в основном ходят с американских IP независимо от
  # того, кто реально спрашивает, форсированный редирект их бы только путал.
  for hub in hubs:
    total_pages = max(1, (len(hub["items"]) + HUB_PAGE_SIZE - 1) // HUB_PAGE_SIZE)
    for lang in ("ru", "az"):
      strings = UI[lang]
      display_name = hub_display_name(hub, lang)
      title, h1, intro_html, description = hub_texts(
          hub, lang=lang, category_az=category_az, display_name=display_name
      )
      hub_path = lang_path(hub["path"], lang)
      hub_dir = (
          os.path.join(store_dir, hub["kind"], hub["slug"]) if lang == "ru"
          else os.path.join(store_dir, "az", hub["kind"], hub["slug"])
      ).rstrip("\\/")
      os.makedirs(hub_dir, exist_ok=True)
      card_key = "card" if lang == "ru" else "card_az"
      offer_key = "offer" if lang == "ru" else "offer_az"
      for page_num in range(1, total_pages + 1):
        chunk = hub["items"][(page_num - 1) * HUB_PAGE_SIZE : page_num * HUB_PAGE_SIZE]
        page_suffix = "" if page_num == 1 else f"page-{page_num}.html"
        # hreflang считаем от языка-нейтрального hub["path"] (RU-форма без
        # /az/), а не от уже сконвертированного hub_path — иначе на AZ-версии
        # получалось /az/az/... (двойная вставка).
        base_page_path = hub["path"] + page_suffix
        if page_num == 1:
          page_path, filename = hub_path, "index.html"
        else:
          page_path, filename = f"{hub_path}page-{page_num}.html", f"page-{page_num}.html"
        canonical = SITE_ROOT + page_path
        suffix = "" if page_num == 1 else f" — {strings['page']} {page_num}"
        alt_links = [
            ("ru", SITE_ROOT + lang_path(base_page_path, "ru")),
            ("az", SITE_ROOT + lang_path(base_page_path, "az")),
        ]
        # FAQ-блок только на первой странице хаба (не на page-2/3...) — иначе
        # одинаковый вопрос-ответ дублировался бы на каждой странице пагинации.
        faq_html, faq_ld = faq_block(hub, lang, display_name) if page_num == 1 else ("", None)
        parent_crumbs = []
        if hub["kind"] == "podborka":
          ph = hub["parent"]
          parent_crumbs = [(hub_display_name(ph, lang), SITE_ROOT + lang_path(ph["path"], lang))]
        related_html = ""
        if page_num == 1 and hub["kind"] in ("kategoriya", "brend"):
          rel = related.get((hub["kind"], hub["slug"]), [])[:40]
          if rel:
            related_html = hub_grid(strings["podborki_heading"], rel, lang, category_az)
        page_html = render_page(
            title=title + suffix,
            description=(
                description if page_num == 1
                else _shorten(f"{strings['page']} {page_num}. {description}")
            ),
            canonical=canonical,
            h1=h1,
            intro_html=intro_html,
            main_html=related_html
            + f'<div class="grid">{"".join(i[card_key] for i in chunk)}</div>',
            breadcrumbs=[home_crumb[lang]] + parent_crumbs
            + [(display_name, SITE_ROOT + hub_path)]
            + ([(f"{strings['page']} {page_num}", canonical)] if page_num > 1 else []),
            offers=[i[offer_key] for i in chunk],
            pagination=pagination_html(hub_path, page_num, total_pages, lang=lang),
            lang=lang,
            alt_links=alt_links,
            faq_html=faq_html,
            extra_ld=[faq_ld] if faq_ld else None,
        )
        with open(os.path.join(hub_dir, filename), "w", encoding="utf-8", newline="\n") as f:
          f.write(page_html)
        _remember_page(canonical, page_html)
        sitemap_urls.append(canonical)

  # 2. Персональная страница на каждый товар: один URL = одно название +
  # объём + цена + магазин — самостоятельный, извлекаемый кусок факта, а не
  # карточка внутри общей страницы категории на 50+ товаров. Это то, чем
  # реально выигрывают конкуренты в ИИ-ответах на generic-запросы (Wolt,
  # Rossmann, Bazarstore — у каждого SKU своя страница), см. tools/geo_tracker
  # round 3 (2026-10-01).
  product_dir_base = os.path.join(store_dir, "tovar")
  shutil.rmtree(product_dir_base, ignore_errors=True)
  shutil.rmtree(os.path.join(store_dir, "az", "tovar"), ignore_errors=True)
  for i in items:
    parent_hub = idx_to_hub[i["idx"]]
    for lang in ("ru", "az"):
      strings = UI[lang]
      display_key = "display" if lang == "ru" else "display_az"
      offer_key = "offer" if lang == "ru" else "offer_az"
      name = i[display_key]
      parent_name = hub_display_name(parent_hub, lang)
      parent_path = SITE_ROOT + lang_path(parent_hub["path"], lang)
      product_path = lang_path(i["product_path"], lang)
      canonical = SITE_ROOT + product_path
      alt_links = [
          ("ru", SITE_ROOT + lang_path(i["product_path"], "ru")),
          ("az", SITE_ROOT + lang_path(i["product_path"], "az")),
      ]
      plain = (
          f"{strings['product_in_stock']}. {strings['product_price_label'](i['price'])}"
          f"{strings['store_phrase']}, {strings['baku']}, {strings['near_metro']}. "
          f"{strings['order_via']}: {STORE_PHONE_DISPLAY}."
      )
      intro_html = (
          f"{html.escape(plain.rsplit(' ' + strings['order_via'], 1)[0])} "
          f'{strings["order_via"]}: <a href="tel:{STORE_PHONE_E164}">{STORE_PHONE_DISPLAY}</a>.'
      )
      main_html = (
          '<div class="card">'
          f'<div class="price">{html.escape(i["price"])}</div>'
          f'<a href="{i["wa_link"]}" target="_blank" class="btn">{strings["order_via"]}</a>'
          "</div>"
      )
      page_html = render_page(
          title=strings["product_title"](name),
          description=_shorten(plain),
          canonical=canonical,
          h1=name,
          intro_html=intro_html,
          main_html=main_html,
          breadcrumbs=[home_crumb[lang], (parent_name, parent_path), (name, canonical)],
          offers=[i[offer_key]],
          lang=lang,
          alt_links=alt_links,
          stamp=False,
      )
      product_dir = (
          os.path.join(store_dir, "tovar", i["product_slug"]) if lang == "ru"
          else os.path.join(store_dir, "az", "tovar", i["product_slug"])
      )
      os.makedirs(product_dir, exist_ok=True)
      with open(os.path.join(product_dir, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page_html)
      _remember_page(canonical, page_html)
      sitemap_urls.append(canonical)
  print(f"Страниц товаров: {len(items)} x 2 языка = {len(items) * 2}")

  # Инструмент 1: отдельная страница "живых цен" по всем категориям — не
  # спрятанное предложение внутри карточек товара, а самостоятельный,
  # регулярно обновляемый источник данных. По GEO-исследованиям именно такой
  # тип контента (оригинальные, обновляемые данные) чаще всего попадает в
  # ответы ИИ-ассистентов, а плотный список карточек товаров — плохо
  # извлекаемый фрагмент текста.
  now_ts = GENERATION_TIMESTAMP
  prices_alt_links = [
      ("ru", SITE_ROOT + f"/stores/{STORE_SLUG}/tseny/"),
      ("az", SITE_ROOT + f"/stores/{STORE_SLUG}/az/tseny/"),
  ]
  for lang in ("ru", "az"):
    strings = UI[lang]
    table_html = prices_table_html(category_hubs, lang, category_az)
    prices_path = lang_path(f"/stores/{STORE_SLUG}/tseny/", lang)
    prices_dir = os.path.join(store_dir, "az", "tseny") if lang == "az" else os.path.join(store_dir, "tseny")
    os.makedirs(prices_dir, exist_ok=True)
    prices_canonical = SITE_ROOT + prices_path
    updated_line = strings["prices_page_updated"](now_ts)
    prices_html = render_page(
        title=strings["prices_page_title"],
        description=_shorten(f"{strings['prices_page_h1']}. {updated_line}"),
        canonical=prices_canonical,
        h1=strings["prices_page_h1"],
        intro_html=html.escape(updated_line),
        main_html=table_html,
        breadcrumbs=[home_crumb[lang], (strings["prices_link_label"], prices_canonical)],
        lang=lang,
        alt_links=prices_alt_links,
    )
    with open(os.path.join(prices_dir, "index.html"), "w", encoding="utf-8", newline="\n") as f:
      f.write(prices_html)
    _remember_page(prices_canonical, prices_html)
    sitemap_urls.append(prices_canonical)

  home_alt_links = [("ru", STORE_CANONICAL_URL), ("az", az_home_url)]
  for lang in ("ru", "az"):
    strings = UI[lang]
    home_main = (
        hub_grid(strings["categories"], category_hubs, lang=lang, category_az=category_az)
        + hub_grid(strings["brands"], brand_hubs, lang=lang, category_az=category_az)
    )
    if leftovers:
      home_main += hub_grid(
          strings["more"], [h for h in hubs if h["kind"] == "prochee"],
          lang=lang, category_az=category_az,
      )
    home_faq_html, home_faq_ld = home_faq_block(lang, len(items))
    home_html = render_page(
        title=strings["home_title"],
        description=strings["store_description"],
        canonical=STORE_CANONICAL_URL if lang == "ru" else az_home_url,
        h1=STORE_NAME,
        intro_html=strings["home_intro"](len(items)),
        main_html=home_main,
        breadcrumbs=[home_crumb[lang]],
        lang=lang,
        alt_links=home_alt_links,
        faq_html=home_faq_html,
        extra_ld=[home_faq_ld],
    )
    _remember_page(STORE_CANONICAL_URL if lang == "ru" else az_home_url, home_html)
    if lang == "ru":
      # Главная — canonical-адрес витрины, дублируется и в корень, и в папку
      # магазина (см. STORE_CANONICAL_URL выше). AZ-версии корневого дубля не
      # нужно — она открывается только по /stores/makiyaj/az/.
      with open("index.html", "w", encoding="utf-8", newline="\n") as f:
        f.write(home_html)
      with open(f"{store_dir}/index.html", "w", encoding="utf-8", newline="\n") as f:
        f.write(home_html)
    else:
      az_home_dir = os.path.join(store_dir, "az")
      os.makedirs(az_home_dir, exist_ok=True)
      with open(f"{az_home_dir}/index.html", "w", encoding="utf-8", newline="\n") as f:
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
      f"Address: {STORE_ADDRESS}, Baku\n"
      f"Phone / WhatsApp: {STORE_PHONE_DISPLAY}\n"
      f"Hours: {STORE_HOURS_DISPLAY} daily\n"
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
  # lastmod = дата, когда содержимое страницы последний раз реально менялось
  # (хеш без метки времени сравнивается с прошлым прогоном, состояние лежит в
  # data/sitemap_lastmod.tsv и коммитится cron'ом вместе с сайтом). Раньше
  # всем 19 тыс. адресов ставилась сегодняшняя дата — поисковики видят, что
  # такая дата ничего не значит, и перестают ей верить.
  sitemap_date = datetime.datetime.now().strftime("%Y-%m-%d")
  previous = {}
  if os.path.exists(LASTMOD_STATE):
    with open(LASTMOD_STATE, encoding="utf-8") as f:
      for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) == 3:
          previous[parts[0]] = (parts[1], parts[2])
  lastmod = {}
  for u in sitemap_urls:
    h = PAGE_HASHES.get(u, "")
    old = previous.get(u)
    lastmod[u] = old[1] if old and h and old[0] == h else sitemap_date
  with open(LASTMOD_STATE, "w", encoding="utf-8", newline="\n") as f:
    for u in sorted(lastmod):
      f.write(f"{u}\t{PAGE_HASHES.get(u, '')}\t{lastmod[u]}\n")
  sitemap_lines = "\n".join(
      f"  <url><loc>{u}</loc><lastmod>{lastmod[u]}</lastmod></url>" for u in sitemap_urls
  )
  sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{sitemap_lines}
  <url><loc>{SITE_ROOT}/stores/makiyaj/llms.txt</loc><lastmod>{sitemap_date}</lastmod></url>
  <url><loc>{SITE_ROOT}/llms.txt</loc><lastmod>{sitemap_date}</lastmod></url>
</urlset>
"""
  with open("sitemap.xml", "w", encoding="utf-8", newline="\n") as f:
    f.write(sitemap_xml)

  print("Все файлы витрины и файлы для ИИ успешно сгенерированы!")


if __name__ == "__main__":
  run()
