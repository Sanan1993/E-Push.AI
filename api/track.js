export default async function handler(req, res) {
  const userAgent = req.headers['user-agent'] || 'Unknown';
  const ip = req.headers['x-forwarded-for'] || 'Unknown IP';
  const fileName = req.query.file || 'unknown';

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

  // Отправляем уведомление в твой Telegram
  const TG_BOT_TOKEN = "8759672683:AAGMUfl2k51YT2I06MK1W9FZvOCD5cIVpfQ";
  const TG_CHAT_ID = "596455016";

  try {
    await fetch(`https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: TG_CHAT_ID,
        text: message,
        parse_mode: 'Markdown'
      })
    });
  } catch (e) {
    console.error(e);
  }

  // Перенаправляем запрос на реальный файл, чтобы ИИ или человек получил данные
  const fs = require('fs');
  const path = require('path');
  
  try {
    const filePath = path.join(process.cwd(), 'stores', 'makiyaj', fileName);
    const fileContent = fs.readFileSync(filePath, 'utf8');
    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    return res.status(200).send(fileContent);
  } catch (err) {
    return res.status(404).send('File not found');
  }
}
