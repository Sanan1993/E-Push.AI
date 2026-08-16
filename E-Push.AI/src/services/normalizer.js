class Normalizer {
  static cleanTitle(rawTitle) {
    if (!rawTitle) return "Без названия";
    return rawTitle
      .replace(/\s+/g, ' ')
      .replace(/iPh\b/g, 'Apple iPhone')
      .replace(/Pr\b/g, 'Pro')
      .replace(/PM\b/g, 'Pro Max')
      .trim();
  }

  static calculateBirKart(price, maxMonths = 12) {
    if (!price || isNaN(price)) return null;
    const monthly = (price / maxMonths).toFixed(1);
    return {
      months: maxMonths,
      monthlyPayment: monthly
    };
  }

  // Текст сообщения для WhatsApp в бакинском формате (универсальный AZ/RU)
  static generateWhatsAppLink(phone, productName, price, partnerCode = "EPUSH-AI") {
    const text = `Salam! E-Push.AI vasitəsilə ${productName} (${price} AZN) haqqında məlumat aldım (Kod: ${partnerCode}). Mövcudluğu və çatdırılmanı təsdiqləyin müəllim.\n\nЗдравствуйте! Нашёл у вас ${productName} за ${price} AZN. Подтвердите наличие.`;
    return `https://wa.me/${phone}?text=${encodeURIComponent(text)}`;
  }

  static processProduct(rawProduct, partnerConfig) {
    const cleanName = this.cleanTitle(rawProduct.name || rawProduct.title);
    const price = parseFloat(rawProduct.price) || 0;
    const birkart = this.calculateBirKart(price, partnerConfig.birkartMaxMonths || 12);
    
    const waLink = this.generateWhatsAppLink(
      partnerConfig.whatsapp,
      cleanName,
      price
    );

    return {
      id: rawProduct.id || Math.random().toString(36).substr(2, 9),
      name: cleanName,
      price: price,
      oldPrice: rawProduct.oldPrice || null,
      inStock: rawProduct.inStock !== undefined ? rawProduct.inStock : true,
      warranty: rawProduct.warranty || "1 il rəsmi zəmanət / 1 год официальной гарантии",
      birkart: birkart,
      links: {
        whatsapp: waLink,
        site: rawProduct.url || null,
        tapaz: partnerConfig.tapaz || null,
        instagram: partnerConfig.instagram || null
      }
    };
  }
}

module.exports = Normalizer;
