const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const sqlite3 = require('sqlite3');

puppeteer.use(StealthPlugin());

const DB_PATH = '/opt/newsbot/data/ozon_public_commissions.db';

const SOURCES = [
    { url: 'https://guruseller.ru/ozon-novye-komissii-i-tarify-s-6-04-2026/', name: 'GuruSeller' },
    { url: 'https://split80.ru/news/Povyshenie-komissij-Ozon-s-6-aprelya-2026-goda-Polnyj-razbor-novyh-tarifov-i-strategii-dlya-sellerov', name: 'Split80' },
    { url: 'https://vc.ru/marketplace/2855253-novye-tarify-ozon-dlya-sellerov', name: 'VCru' }
];

async function parseSource(url) {
    console.log(`  Parsing: ${url}`);
    let browser;
    try {
        browser = await puppeteer.launch({ 
            headless: true,
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled']
        });
        const page = await browser.newPage();
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
        await page.goto(url, { timeout: 60000, waitUntil: 'networkidle2' });
        
        // Wait for content to load
        try {
            await page.waitForSelector('table, article, .content, main', { timeout: 5000 });
        } catch (e) {}
        
        await new Promise(r => setTimeout(r, 5000));
        
        const title = await page.title();
        console.log(`    Page title: ${title}`);
        
        const html = await page.content();
        await browser.close();
        return html;
    } catch (e) {
        console.log(`    Error: ${e.message}`);
        if (browser) await browser.close();
        return '';
    }
}

function extractCommissions(html) {
    const commissions = {};
    if (!html) return commissions;
    
    // Extract plain text
    const text = html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
    
    // Match category + percentage patterns
    const patterns = [
        /(\p\d+(?:\.\d+)?)\s*%/gi,
        /(\d+(?:\.\d+)?)\s*(?:%|процент)/gi,
    ];
    
    // First, get all numbers with % after them
    const percentMatches = [];
    const matchPattern = /([А-Яа-яё][А-Яа-яё\s]{2,30}?)\s*[-–:.]?\s*(\d+(?:\.\d+)?)\s*%/gi;
    let m;
    while ((m = matchPattern.exec(text)) !== null) {
        if (m[1] && m[2]) {
            const value = parseFloat(m[2]);
            if (value >= 1 && value <= 60) {
                const category = m[1].trim();
                if (category.length > 2 && category.length < 40) {
                    commissions[category] = value;
                }
            }
        }
    }
    
    return commissions;
}

function initDb() {
    const db = new sqlite3.Database(DB_PATH);
    try {
        db.run('DROP TABLE IF EXISTS commissions');
    } catch (e) {}
    db.run(`
        CREATE TABLE IF NOT EXISTS commissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            commission REAL,
            source TEXT,
            collected_at TIMESTAMP
        )
    `);
    db.run('CREATE INDEX IF NOT EXISTS idx_category ON commissions(category)');
    db.close();
}

function saveCommissions(commissions, sourceName) {
    const db = new sqlite3.Database(DB_PATH);
    const now = new Date().toISOString();
    
    for (const [category, rate] of Object.entries(commissions)) {
        db.run(
            'INSERT INTO commissions (category, commission, source, collected_at) VALUES (?, ?, ?, ?)',
            [category, rate, sourceName, now]
        );
    }
    
    db.close();
    console.log(`  Saved ${Object.keys(commissions).length} records from ${sourceName}`);
}

async function main() {
    console.log(`\nOzon Commission Parser - ${new Date()}`);
    console.log('='.repeat(60));
    
    initDb();
    
    console.log('\nParsing sources...');
    let allCommissions = {};
    
    for (const source of SOURCES) {
        const html = await parseSource(source.url);
        const commissions = extractCommissions(html);
        console.log(`    Found: ${Object.keys(commissions).length} commissions`);
        allCommissions = { ...allCommissions, ...commissions };
        await new Promise(r => setTimeout(r, 1000));
    }
    
    console.log(`\nTotal found: ${Object.keys(allCommissions).length}`);
    saveCommissions(allCommissions, 'Multiple');
    
    console.log('\n' + '='.repeat(60));
}

main().catch(console.error);