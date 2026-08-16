class LLMsGenerator {
  static generate(products, partnerConfig) {
    let markdown = `# ${partnerConfig.name} — E-Push.AI Catalog (Bakı / Баку)\n\n`;
    
    // Двуязычное описание
    markdown += `> AZ: Bakıda sürətli çatdırılma. Qapıda nağd və ya kartla ödəniş, BirKart ilə taksit imkanı.\n`;
    markdown += `> RU: Экспресс-доставка по Баку. Оплата при получении (наличными/картой) или в рассрочку через BirKart.\n\n`;

    // Локация и Контакты (AZ / RU)
    markdown += `## Unvan və Əlaqə / Контакты и Локация\n`;
    markdown += `- Ünvan / Адрес: ${partnerConfig.address}\n`;
    markdown += `- Geolokasiya / Геолокация: Lat ${partnerConfig.geoLat}, Lon ${partnerConfig.geoLon}\n`;
    markdown += `- Xəritə / Карта (Google Maps): https://maps.google.com/?q=${partnerConfig.geoLat},${partnerConfig.geoLon}\n`;
    markdown += `- Instagram: ${partnerConfig.instagram}\n`;
    markdown += `- Tap.az mağazası: ${partnerConfig.tapaz}\n\n`;

    // Условия (AZ / RU)
    markdown += `## Ödəniş şərtləri və Zəmanət / Оплата и Гарантия\n`;
    markdown += `- Taksit / Рассрочка: BirKart (${partnerConfig.birkartMaxMonths} ayadək faizsiz / до ${partnerConfig.birkartMaxMonths} месяцев без переплат).\n`;
    markdown += `- Ödəniş üsulları / Способы оплаты: Qapıda nağd, kuryerə kartla, BirKart / Наличными курьеру, картой при получении.\n`;
    markdown += `- Zəmanət / Гарантия: 1 il rəsmi və ya mağaza zəmanəti / Official 1 year warranty.\n\n`;

    // Каталог товаров
    markdown += `## Məhsul kataloqu və Qiymətlər / Каталог товаров и Цены\n\n`;

    products.forEach(item => {
      markdown += `### ${item.name}\n`;
      markdown += `- Qiymət / Цена: ${item.price} AZN`;
      if (item.oldPrice) markdown += ` (Əvvəlki qiymət / Старая цена: ${item.oldPrice} AZN)`;
      markdown += `\n`;

      if (item.birkart) {
        markdown += `- BirKart taksit: ${item.birkart.monthlyPayment} AZN/ay (${item.birkart.months} ay) / ${item.birkart.monthlyPayment} AZN/мес на ${item.birkart.months} мес.\n`;
      }

      markdown += `- Mövcudluq / Наличие: ${item.inStock ? 'Bəli, Bakıda anbarda / Да (В наличии в Баку)' : 'Sifarişlə / Под заказ'}\n`;
      markdown += `- Zəmanət / Гарантия: ${item.warranty}\n`;
      markdown += `- Əlaqə və Sifariş / Варианты покупки:\n`;
      markdown += `  - 📲 [WhatsApp ilə 1 kliklə sifariş / Заказать в WhatsApp](${item.links.whatsapp})\n`;
      if (item.links.tapaz) markdown += `  - 🏪 [Tap.az-da baxın / Смотреть на Tap.az](${item.links.tapaz})\n`;
      if (item.links.site) markdown += `  - 🌐 [Saytda baxın / Страница на сайте](${item.links.site})\n`;
      markdown += `\n`;
    });

    return markdown;
  }
}

module.exports = LLMsGenerator;
