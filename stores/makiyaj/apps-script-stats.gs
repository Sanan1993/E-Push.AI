/**
 * E-Push.AI — сбор статистики (визиты ИИ-ботов/людей, клики по WhatsApp).
 *
 * Установка:
 * 1. Открой Google Таблицу с товарами (ту же, из которой generate_llms.py берёт каталог).
 * 2. Меню Extensions -> Apps Script.
 * 3. Удали содержимое Code.gs, вставь этот файл целиком, сохрани (Ctrl+S).
 * 4. Deploy -> New deployment -> шестерёнка -> Web app.
 *      Execute as: Me
 *      Who has access: Anyone
 * 5. Deploy -> Authorize access -> выбери свой аккаунт -> Advanced -> Go to project (unsafe) -> Allow.
 *    ("Unsafe" тут означает только то, что Google не проверял скрипт вручную — это твой код.)
 * 6. Скопируй URL Web app (заканчивается на /exec) и пришли его в чат.
 *
 * Логи появятся на новом листе "Stats" в этой же таблице.
 *
 * Обновление (IP-адрес): если "Stats" уже существует со старыми колонками —
 * добавь заголовок "IP" в ячейку I1 вручную один раз, дальше скрипт сам
 * будет писать туда значения.
 */

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var sheet = getStatsSheet_();
    sheet.appendRow([
      new Date(),
      data.type || '',
      data.path || '',
      data.product || '',
      data.ua || '',
      data.country || '',
      data.city || '',
      data.referrer || '',
      data.ip || '',
    ]);
    return ContentService.createTextOutput(JSON.stringify({ ok: true }))
        .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: String(err) }))
        .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService.createTextOutput('E-Push.AI stats endpoint is alive');
}

function getStatsSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('Stats');
  if (!sheet) {
    sheet = ss.insertSheet('Stats');
    sheet.appendRow(['Timestamp', 'Type', 'Path', 'Product', 'User-Agent', 'Country', 'City', 'Referrer', 'IP']);
    sheet.setFrozenRows(1);
  }
  return sheet;
}
