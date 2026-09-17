// Редирект-трекер для заказов через WhatsApp.
// Использование: /api/go?to=<encodeURIComponent(wa.me ссылка)>&t=<название товара>
const STATS_ENDPOINT = 'https://script.google.com/macros/s/AKfycbx7cmg-ylZ4HazmA6rpQY8STyBmD09i-AkenAVS46Qdo6FgKZlk0NAM3Fugh79-dmY0/exec';

// Тот же список, что в middleware.js: краулеры обходят все ссылки на странице
// (в т.ч. все 9000+ "Заказать"), и без этого их клики попадают в статистику
// как реальные покупательские намерения.
const BOT_PATTERNS = [
  /GPTBot/i, /ChatGPT-User/i, /OAI-SearchBot/i,
  /PerplexityBot/i, /Perplexity-User/i,
  /ClaudeBot/i, /Claude-User/i, /anthropic-ai/i,
  /Google-Extended/i, /Googlebot/i, /GoogleOther/i,
  /Bingbot/i, /CCBot/i, /Applebot/i, /YandexBot/i,
  /facebookexternalhit/i, /DuckDuckBot/i, /Bytespider/i, /cohere-ai/i,
];

module.exports = async (req, res) => {
  const { to, t } = req.query;
  const ua = req.headers['user-agent'] || '';

  // /api/go уже запрещён в robots.txt. Это — подстраховка на случай ботов,
  // которые его игнорируют или ещё не перечитали правила: не тратим вызов
  // Apps Script и не уводим их в WhatsApp, отвечаем сразу.
  if (BOT_PATTERNS.some((re) => re.test(ua))) {
    res.statusCode = 403;
    res.end('Disallowed for crawlers, see /robots.txt');
    return;
  }

  let target;
  try {
    target = decodeURIComponent(to || '');
  } catch (e) {
    target = '';
  }

  // Разрешаем редирект только на wa.me, чтобы этот эндпоинт нельзя было
  // использовать как открытый редиректор на произвольные сайты.
  if (!target.startsWith('https://wa.me/')) {
    res.statusCode = 400;
    res.end('Invalid target');
    return;
  }

  // См. middleware.js: настоящий переход по ссылке несёт Sec-Fetch-Mode: navigate,
  // простые скрипты — как правило, нет.
  const looksHuman = req.headers['sec-fetch-mode'] === 'navigate';

  try {
    await fetch(STATS_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: looksHuman ? 'click-real' : 'click-unclear',
        path: '/go',
        product: t || '',
        ua,
        ip: (req.headers['x-forwarded-for'] || '').split(',')[0].trim(),
        referrer: req.headers['referer'] || '',
        country: req.headers['x-vercel-ip-country'] || '',
        city: req.headers['x-vercel-ip-city'] || '',
      }),
    });
  } catch (e) {
    // логирование не должно блокировать переход в WhatsApp
  }

  res.writeHead(302, { Location: target });
  res.end();
};
