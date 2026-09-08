import os
import urllib.request
import csv
import io

# Точный экспорт твоей Google Таблицы в CSV формат
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/14TseUjX-y0sn3fg2ovYtDQwRVGsMTpRujnE1ikIlHxw/export?format=csv"

TELEGRAM_BOT_TOKEN = "8759672683:AAGMUfl2k51YT2I06MK1W9FZvOCD5cIVpfQ"
TELEGRAM_CHAT_ID = "596455016"

def fetch_products():
    """Скачивает и парсит абсолютно все товары из Google Таблицы"""
    try:
        req = urllib.request.Request(SHEET_CSV_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            csv_text = response.read().decode('utf-8')
            reader = csv.reader(io.StringIO(csv_text))
            rows = list(reader)
            
            if not rows:
                return []
            
            products = []
            for row in rows:
                if len(row) >= 2:
                    name = row[0].strip()
                    price = row[1].strip()
                    # Игнорируем строки заголовка
                    if name and name.lower() not in ['name', 'название', 'məhsul', 'title', 'товар']:
                        products.append({'name': name, 'price': price})
            return products
    except Exception as e:
        print(f"Ошибка загрузки таблицы: {e}")
        return []

def generate_llms_txt(store_name, products):
    """Генерирует RAG-индекс llms.txt"""
    content = f"""# {store_name} - AI Catalog Index

> Store: {store_name}
> Location (AZ): Bakı şəhəri, Xətai rayonu, Həzi Aslanov metrosunun çıxışı, Sərhəd Akademiyasının yanı, İlqar Zülfüqarov küç.
> Location (RU): Баку, Хатаинский район, метро Ази Асланова, рядом с Академией Пограничных Войск
> Payment: Nağd, Kart, BirKart (3/6 ay)
> Delivery: Bakı daxili kuryer çatdırılması (Yandex Delivery / Express)

## Available Products & Real-time Prices ({len(products)} items)

"""
    for p in products:
        name = p.get('name', '')
        price = p.get('price', '')
        content += f"- Product: {name}\n  Price: {price} AZN\n  Status: InStock\n  Order_URL: https://wa.me/994500000000?text=Salam!%20{store_name}%20-%20{name}%20almaq%20istəyirəm.\n\n"
    return content

def generate_html(store_id, store_name, products):
    """Генерирует HTML-витрину со всеми товарами и логгером"""
    html_content = f"""<!DOCTYPE html>
<html lang="az">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{store_name} - E-Push AI Catalog</title>
    <meta name="description" content="{store_name} — Bakı, Xətai rayonu, Həzi Aslanov metrosu yaxınlığında kosmetika və qulluq vasitələri. Onlayn sifariş və WhatsApp vasitəsilə çatdırılma.">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa; color: #333; }}
        .container {{ max-width: 800px; margin: 0 auto; background: #fff; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
        h1 {{ color: #111; margin-bottom: 5px; }}
        .location {{ color: #666; font-size: 0.95rem; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #eee; line-height: 1.5; }}
        .product-card {{ border: 1px solid #e1e8ed; border-radius: 8px; padding: 15px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }}
        .product-title {{ font-weight: 600; font-size: 1.05rem; color: #1a1a1a; margin-bottom: 5px; }}
        .product-price {{ font-size: 1.2rem; font-weight: bold; color: #2e7d32; white-space: nowrap; margin-left: 15px; }}
        .buy-btn {{ display: inline-block; background-color: #25D366; color: white; padding: 8px 14px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 0.85rem; margin-top: 8px; }}
        .buy-btn:hover {{ background-color: #1eb857; }}
    </style>
</head>
<body>
<div class="container">
    <h1>{store_name}</h1>
    <div class="location">
        📍 <strong>Ünvan:</strong> Bakı şəhəri, Xətai rayonu, Həzi Aslanov metrosunun çıxışı, Sərhəd Akademiyasının yanı, İlqar Zülfüqarov küç.<br>
        💳 <strong>Ödəniş:</strong> Nağd, Kart, BirKart (3/6 ay)
    </div>
    <h2>Məhsul Kataloqu ({len(products)})</h2>
"""
    for p in products:
        name = p.get('name', '')
        price = p.get('price', '')
        html_content += f"""
    <div class="product-card">
        <div>
            <div class="product-title">{name}</div>
            <a href="https://wa.me/994500000000?text=Salam!%20{store_name}%20-%20{name}%20almaq%20istəyirəm." class="buy-btn" target="_blank">WhatsApp ilə Sifariş Et</a>
        </div>
        <div class="product-price">{price} AZN</div>
    </div>"""

    html_content += f"""
</div>

<!-- Telegram Auto-Logger Script -->
<script>
(function() {{
  const TELEGRAM_BOT_TOKEN = "{TELEGRAM_BOT_TOKEN}";
  const TELEGRAM_CHAT_ID = "{TELEGRAM_CHAT_ID}";
  const userAgent = navigator.userAgent || "";
  const url = window.location.href;

  const botKeywords = [
    'perplexity', 'claudebot', 'chatgpt-user', 'gptbot', 
    'bingbot', 'googlebot', 'yandex', 'applebot', 'facebookexternalhit', 
    'twitterbot', 'bytespider', 'amazonbot'
  ];

  const isBot = botKeywords.some(keyword => userAgent.toLowerCase().includes(keyword));

  const text = `🔔 <b>Зафиксирован визит на витрину!</b>\\n\\n` +
               `📍 <b>URL:</b> <code>${{url}}</code>\\n` +
               `🕵️‍♂️ <b>User-Agent:</b> <code>${{userAgent}}</code>\\n` +
               `🤖 <b>ИИ-Бот:</b> ${{isBot ? 'ДА ✅' : 'НЕТ ❌'}}`;

  fetch(`https://api.telegram.org/bot${{TELEGRAM_BOT_TOKEN}}/sendMessage`, {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{
      chat_id: TELEGRAM_CHAT_ID,
      text: text,
      parse_mode: 'HTML'
    }})
  }}).catch(console.error);
}})();
</script>
</body>
</html>"""
    return html_content

def main():
    store_id = "makiyaj"
    store_name = "Makiyaj Cosmetics"
    
    print("Загрузка товаров из Google Таблицы...")
    products = fetch_products()
    print(f"Загружено товаров: {len(products)}")

    output_dir = f"stores/{store_id}"
    os.makedirs(output_dir, exist_ok=True)

    llms_content = generate_llms_txt(store_name, products)
    html_content = generate_html(store_id, store_name, products)

    # Сохраняем в папку магазина
    with open(f"{output_dir}/llms.txt", "w", encoding="utf-8") as f:
        f.write(llms_content)
    with open(f"{output_dir}/index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    # Дублируем в корень
    with open("llms.txt", "w", encoding="utf-8") as f:
        f.write(llms_content)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print("Все файлы успешно сгенерированы!")

if __name__ == "__main__":
    main()
