"""Пилотный товарный фид (формат Google Shopping RSS 2.0) — всего 3 позиции,
для которых реально нашли и проверили официальные фото производителя
(см. изучение в сессии 2026-10-01, data/photo_pilot/).

Это НЕ подключено к основному 6-часовому пайплайну (generate_llms.py) —
осознанно отдельный скрипт, чтобы не тащить непроверенные данные/фото в
автоматику, пока формат и сама идея не проверены на практике.

Формат: тот же, что принимает Google Merchant Center и который Perplexity
прямо заявляет, что принимает "без изменений" (Google Shopping CSV/XML).
OpenAI просит похожий набор полей (id/title/description/link/image_link/
price/availability/brand/condition), просто в своей доставке (HTTPS push).

Запуск: python tools/build_feed_pilot.py
"""

import html
import os

SITE_ROOT = "https://e-push-ai.vercel.app"
STORE_NAME = "Makiyaj Cosmetics"

# Вручную собранные реальные данные (barcode, name, brand, category, price,
# availability page, image file) — три позиции, прошедшие проверку фото.
ITEMS = [
    {
        "gtin": "8806150614485",
        "title": "Missha Perfect Cover B.B. Cream SPF 42 NO.27, 50 мл",
        "description": "BB-крем Missha Perfect Cover SPF 42, оттенок NO.27, 50 мл. "
                        "В наличии в Makiyaj Cosmetics, Баку.",
        "brand": "Missha",
        "category": "BB и CC крем",
        "price": 21.0,
        "link": f"{SITE_ROOT}/stores/makiyaj/kategoriya/bb-i-cc-krem/",
        "image": "8806150614485.jpg",
    },
    {
        "gtin": "4005802324909",
        "title": "Nivea Бальзам для губ Strawberry",
        "description": "Бальзам для губ Nivea со вкусом клубники. "
                        "В наличии в Makiyaj Cosmetics, Баку.",
        "brand": "Nivea",
        "category": "Бальзам для губ",
        "price": 5.5,
        "link": f"{SITE_ROOT}/stores/makiyaj/kategoriya/balzam-dlya-gub/",
        "image": "4005802324909.png",
    },
    {
        "gtin": "3014260243531",
        "title": "Gillette Mach 3 — сменные кассеты, 4 шт.",
        "description": "Сменные кассеты для бритвы Gillette Mach 3, 4 штуки. "
                        "В наличии в Makiyaj Cosmetics, Баку.",
        "brand": "Gillette",
        "category": "Сменные кассеты для бритья",
        "price": 21.0,
        "link": f"{SITE_ROOT}/stores/makiyaj/brend/gillette/",
        "image": "3014260243531.jpg",
    },
]


def build_feed():
  entries = []
  for i in ITEMS:
    image_url = f"{SITE_ROOT}/images/products/{i['image']}"
    entries.append(f"""    <item>
      <g:id>{i['gtin']}</g:id>
      <title>{html.escape(i['title'])}</title>
      <description>{html.escape(i['description'])}</description>
      <link>{i['link']}</link>
      <g:image_link>{image_url}</g:image_link>
      <g:availability>in stock</g:availability>
      <g:price>{i['price']:.2f} AZN</g:price>
      <g:brand>{html.escape(i['brand'])}</g:brand>
      <g:condition>new</g:condition>
      <g:gtin>{i['gtin']}</g:gtin>
      <g:google_product_category>{html.escape(i['category'])}</g:google_product_category>
    </item>""")

  xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:g="http://base.google.com/ns/1.0" version="2.0">
  <channel>
    <title>{STORE_NAME} — product feed (pilot, 3 items)</title>
    <link>{SITE_ROOT}/stores/makiyaj/</link>
    <description>Pilot product feed for GEO/commerce-feed testing. Only items with
verified, legitimately-sourced manufacturer photos are included — see
tools/build_feed_pilot.py for sourcing notes.</description>
{chr(10).join(entries)}
  </channel>
</rss>
"""
  return xml


def main():
  xml = build_feed()
  out_path = "product-feed-pilot.xml"
  with open(out_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(xml)
  print(f"Written {out_path} with {len(ITEMS)} items.")


if __name__ == "__main__":
  main()
