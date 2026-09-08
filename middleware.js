export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};

const TELEGRAM_BOT_TOKEN = "8759672683:AAGMUfl2k51YT2I06MK1W9FZvOCD5cIVpfQ";
const TELEGRAM_CHAT_ID = "596455016";

export default async function middleware(request) {
  const userAgent = request.headers.get('user-agent') || '';
  const url = request.url;

  // ТЕСТОВЫЙ РЕЖИМ: отправляем сообщение при ЛЮБОМ замене
  const text = `🔔 <b>Тест логирования E-Push!</b>\n\n` +
               `📍 <b>URL:</b> <code>${url}</code>\n` +
               `🕵️‍♂️ <b>User-Agent:</b> <code>${userAgent}</code>`;

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
  } catch (e) {}
}
