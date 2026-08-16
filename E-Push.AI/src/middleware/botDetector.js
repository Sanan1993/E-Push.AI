const botDetector = (req, res, next) => {
  const userAgent = req.get('User-Agent') || '';
  
  const aiBots = [
    { name: 'ChatGPT', regex: /ChatGPT-User|GPTBot/i },
    { name: 'Perplexity', regex: /PerplexityBot/i },
    { name: 'Bingbot', regex: /bingbot/i },
    { name: 'Googlebot', regex: /Googlebot/i },
    { name: 'Claude', regex: /ClaudeBot|anthropic-ai/i }
  ];

  const matchedBot = aiBots.find(bot => bot.regex.test(userAgent));

  if (matchedBot) {
    req.isAIBot = true;
    req.botName = matchedBot.name;
    console.log(`[E-PUSH.AI BOT] ${new Date().toISOString()} | Bot: ${matchedBot.name} | IP: ${req.ip} | URL: ${req.originalUrl}`);
  } else {
    req.isAIBot = false;
  }

  next();
};

module.exports = botDetector;
