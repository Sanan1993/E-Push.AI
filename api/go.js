// Редирект-трекер для заказов через WhatsApp.
// Использование: /api/go?to=<encodeURIComponent(wa.me ссылка)>&t=<название товара>
const STATS_ENDPOINT = 'https://script.google.com/macros/s/AKfycbwCWuH3PKmOEc8ApiNBH4JXiIZjn_zYyZzdQE876BsMwyVR0iR1kHcmkwQsdmsoasqn/exec';

module.exports = async (req, res) => {
  const { to, t } = req.query;

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

  try {
    await fetch(STATS_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'click',
        path: '/go',
        product: t || '',
        ua: req.headers['user-agent'] || '',
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
