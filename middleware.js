import { next } from '@vercel/edge';

const STATS_ENDPOINT = 'https://script.google.com/macros/s/AKfycbwCWuH3PKmOEc8ApiNBH4JXiIZjn_zYyZzdQE876BsMwyVR0iR1kHcmkwQsdmsoasqn/exec';

const BOT_PATTERNS = [
  /GPTBot/i, /ChatGPT-User/i, /OAI-SearchBot/i,
  /PerplexityBot/i, /Perplexity-User/i,
  /ClaudeBot/i, /Claude-User/i, /anthropic-ai/i,
  /Google-Extended/i, /Googlebot/i,
  /Bingbot/i, /CCBot/i, /Applebot/i, /YandexBot/i,
  /facebookexternalhit/i, /DuckDuckBot/i, /Bytespider/i, /cohere-ai/i,
];

export const config = {
  matcher: ['/', '/robots.txt', '/sitemap.xml', '/llms.txt', '/stores/:path*'],
};

export default function middleware(request, event) {
  const ua = request.headers.get('user-agent') || '';
  const isBot = BOT_PATTERNS.some((re) => re.test(ua));
  const geo = request.geo || {};

  const payload = {
    type: isBot ? 'bot' : 'visit',
    path: new URL(request.url).pathname,
    ua,
    country: geo.country || '',
    city: geo.city || '',
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
