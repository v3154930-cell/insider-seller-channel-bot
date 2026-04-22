const sqlite3 = require('sqlite3');
const db = new sqlite3.Database('/opt/newsbot/data/ozon_public_commissions.db');
db.all('SELECT category, commission, source FROM commissions ORDER BY commission DESC LIMIT 20', (err, rows) => {
  if (err) {
    console.log('Error:', err.message);
  } else {
    console.log('Top commissions:');
    rows.forEach(r => console.log(r.category.substring(0,35) + ' ' + r.commission + '% (' + r.source + ')'));
  }
  db.close();
});