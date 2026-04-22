const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  try {
    await page.goto('https://seller-edu.ozon.ru/tariffs', { timeout: 30000, waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);
    
    const title = await page.title();
    const content = await page.content();
    
    console.log('Title:', title);
    console.log('Length:', content.length);
    console.log('First 1000:', content.substring(0, 1000));
  } catch (e) {
    console.log('Error:', e.message);
  } finally {
    await browser.close();
  }
})();