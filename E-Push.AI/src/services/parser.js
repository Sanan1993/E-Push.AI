const xml2js = require('xml2js');

class UniversalParser {
  static async parse(inputData, type = 'json') {
    try {
      if (type === 'json' || Array.isArray(inputData)) {
        return Array.isArray(inputData) ? inputData : [inputData];
      }
      
      if (type === 'yml' || type === 'xml') {
        return await this.parseYML(inputData);
      }

      return [];
    } catch (error) {
      console.error('[E-PUSH.AI PARSER ERROR]', error);
      return [];
    }
  }

  static parseYML(xmlContent) {
    return new Promise((resolve, reject) => {
      xml2js.parseString(xmlContent, { explicitArray: false }, (err, result) => {
        if (err) return reject(err);
        
        try {
          const offers = result.yml_catalog.shop.offers.offer;
          const items = Array.isArray(offers) ? offers : [offers];
          
          const normalized = items.map(item => ({
            id: item.$.id,
            name: item.name || item.model,
            price: item.price,
            oldPrice: item.oldprice || null,
            inStock: item.$.available === 'true',
            url: item.url || null
          }));
          
          resolve(normalized);
        } catch (e) {
          resolve([]);
        }
      });
    });
  }
}

module.exports = UniversalParser;
