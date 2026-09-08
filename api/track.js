import fs from 'fs';
import path from 'path';

export default async function handler(req, res) {
  try {
    // Достаем имя файла из URL напрямую
    const urlParts = req.url.split('?');
    const queryParams = new URLSearchParams(urlParts[1] || '');
    const fileName = queryParams.get('file') || 'llms.txt';

    const userAgent = req.headers['user-agent'] || 'Unknown';
    const ip = req.headers['x-forwarded-for'] || req.socket.remoteAddress || 'Unknown IP';

    let visitorType = "👤 Человек";
    const uaLower = userAgent.toLowerCase();
    
    if (uaLower.includes('gptbot') || uaLower.includes('chatgpt') || uaLower.includes('openai')) {
      visitorType = "🤖 OpenAI / ChatGPT Bot";
    } else if (uaLower.includes('anthropic') || uaLower.includes('claude')) {
      visitorType = "🤖 Anthropic / Claude Bot";
    } else if (uaLower.includes('googlebot') || uaLower.includes('google-extended')) {
      visitorType = "🤖 Google Bot / AI";
    } else if (uaLower.includes('bot') || uaLower.includes('crawl')) {
      visitorType = "🤖 Другой бот";
    }

    const message = `🔔 *Запрос к каталогу!*\n\n` +
                  `📁 *Файл:* \`${fileName}\`\n` +
                  `📌 *Кто:* ${visitorType}\n` +
                  `🌐 *IP:* \`${ip}\`\n` +
                  `💻 *UA:* \`${userAgent.substring(0, 80)}\``;

    const TG_BOT_TOKEN = "8759672683:AAGMUfl2k51YT2I06MK1W9FZvOCD5cIVpfQ";
    const TG_CHAT_ID = "596455016";

    // Пытаемся отправить сообщение в Telegram
    const tgResponse = await fetch(`https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: TG_CHAT_ID,
        text: message,
        parse_mode: 'Markdown'
      })
    });

    const tgResult = await tgResponse.json();
    if (!tgResult.ok) {
      return res.status(500).send(`Telegram API Error: ${JSON.stringify(tgResult)}`);
    }

    // Ищем и читаем файл каталога
    const filePath = path.join(process.cwd(), 'stores', 'makiyaj', fileName);
    if (!fs.existsSync(filePath)) {
      return res.status(404).send(`File not found at path: ${filePath}`);
    }

    const fileContent = fs.readFileSync(filePath, 'utf8');
    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    return res.status(200).send(fileContent);

  } catch (err) {
    return res.status(500).send(`Server Exception: ${err.message}`);
  }
}
