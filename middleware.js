export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};

const TELEGRAM_BOT_TOKEN = "8759672683:AAGMUfl2k51YT2I06MK1W9FZvOCD5cIVpfQ";
const TELEGRAM_CHAT_ID = "596455016";

export default async function middleware(request) {
  const userAgent = request.headers.get('user-agent') || '';
  const url = request.url;

  // Список ботов поисковиков и ИИ-систем
  const botKeywords = [
    'perplexity', 'claudebot', 'chatgpt-user', 'gptbot', 
    'bingbot', 'googlebot', 'yandex', 'applebot', 'facebookexternalhit', 
    'twitterbot', 'bytespider', 'amazonbot'
  ];

  const lowerUA = userAgent.toLowerCase();
  const isBot = botKeywords.some(keyword => lowerUA.includes(keyword));

  if (isBot) {
    const text = `🤖 <b>Зафиксирован визит ИИ-бота!</b>\n\n` +
                 `📍 <b>URL:</b> <code>${url}</code>\n` +
                 `🕵️‍♂️ <b>User-Agent:</b> <code>${userAgent}</code>\n` +
                 `⏰ <b>Время:</b> ${new Date().toISOString()}`;

    try {
      fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: TELEGRAM_CHAT_ID,
          text: text,
          parse_mode: 'HTML'
        })
      }).catch(() => {});
    } catch (e) {
      // Фоновое выполнение без блокировки ответа
    }
  }
}
