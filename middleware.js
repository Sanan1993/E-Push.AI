import { next } from '@vercel/edge';

const STATS_ENDPOINT = 'https://script.google.com/macros/s/AKfycbx7cmg-ylZ4HazmA6rpQY8STyBmD09i-AkenAVS46Qdo6FgKZlk0NAM3Fugh79-dmY0/exec';

const BOT_PATTERNS = [
  /GPTBot/i, /ChatGPT-User/i, /OAI-SearchBot/i,
  /PerplexityBot/i, /Perplexity-User/i,
  /ClaudeBot/i, /Claude-User/i, /anthropic-ai/i,
  /Google-Extended/i, /Googlebot/i, /GoogleOther/i,
  /Bingbot/i, /CCBot/i, /Applebot/i, /YandexBot/i,
  /facebookexternalhit/i, /DuckDuckBot/i, /Bytespider/i, /cohere-ai/i,
];

// НЕ полная/официальная база облачных диапазонов (такой бесплатно и без
// внешнего API не существует) — эвристический, растущий список, куда
// добавляем то, что реально встречаем в логах (см. Stats: 34.215.144.217,
// Boardman OR — бот с настоящим браузерным движком, который прошёл проверку
// Sec-Fetch-Mode). Ловит очевидные случаи, не заменяет полноценный анализ.
// Намеренно узкий список — беру только диапазоны, в которых почти не бывает
// обычных домашних/мобильных пользователей (это снижает риск случайно
// пометить настоящего человека как дата-центр), а не пытаюсь угадать все
// границы владения /8-блоками, в которых не уверен.
const DATACENTER_IP_PREFIXES = [
  '34.', '35.', '52.', '54.', // AWS EC2 / Google Cloud compute
  '138.68.', '159.65.', '164.90.', '167.71.', '178.62.', // DigitalOcean
  '5.9.', '78.46.', '88.99.', '94.130.', '116.202.', '135.181.', // Hetzner
  '51.68.', '54.36.', '137.74.', '141.94.', '145.239.', '151.80.', // OVH
];

function isDatacenterIp(ip) {
  return DATACENTER_IP_PREFIXES.some((prefix) => ip.startsWith(prefix));
}

export const config = {
  matcher: ['/', '/robots.txt', '/sitemap.xml', '/llms.txt', '/stores/:path*'],
};

export default function middleware(request, event) {
  const ua = request.headers.get('user-agent') || '';
  const isBot = BOT_PATTERNS.some((re) => re.test(ua));
  // Реальные браузеры при обычном переходе по ссылке/адресу сами добавляют
  // Sec-Fetch-Mode: navigate. Простые скрипты и большинство краулеров это не
  // умеют — используем как признак "похоже на живого человека".
  const looksHuman = request.headers.get('sec-fetch-mode') === 'navigate';
  const ip = (request.headers.get('x-forwarded-for') || '').split(',')[0].trim();

  let type;
  if (isBot) {
    type = 'bot';
  } else if (looksHuman && isDatacenterIp(ip)) {
    // Настоящие браузерные заголовки, но IP из облака/хостинга — скорее всего,
    // бот с полноценным браузерным движком (headless Chrome и т.п.), а не
    // человек. Реальный кейс, из-за которого добавили эту проверку: 34.215.x.x.
    type = 'visit-datacenter';
  } else if (looksHuman) {
    type = 'visit-real';
  } else {
    type = 'visit-unclear';
  }

  const payload = {
    type,
    path: new URL(request.url).pathname,
    ua,
    ip,
    country: request.headers.get('x-vercel-ip-country') || '',
    city: request.headers.get('x-vercel-ip-city') || '',
    referrer: request.headers.get('referer') || '',
  };

  const logPromise = fetch(STATS_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).catch(() => {});

  if (event && typeof event.waitUntil === 'function') {
    event.waitUntil(logPromise);
  }

  return next();
}
