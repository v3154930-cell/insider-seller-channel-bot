#!/usr/bin/env python3
import sqlite3
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

DB_PATH = '/opt/newsbot/data/ozon_public_commissions.db'

def get_chrome_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    options.binary_location = '/snap/bin/chromium'
    service = Service('/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            commission REAL,
            collected_at TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON commissions(category)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_collected_at ON commissions(collected_at)')
    conn.commit()
    conn.close()

def parse_tariffs_page(url):
    print(f'  Parsing: {url}')
    driver = None
    try:
        driver = get_chrome_driver()
        driver.get(url)
        time.sleep(3)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'body'))
        )
        html = driver.page_source
    except Exception as e:
        print(f'    Error: {e}')
        return {}
    finally:
        if driver:
            driver.quit()
    
    soup = BeautifulSoup(html, 'html.parser')
    commissions = {}
    
    tables = soup.find_all('table')
    print(f'    Found tables: {len(tables)}')
    
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                category = clean_text(cells[0].get_text())
                commission = extract_commission(cells[1].get_text())
                if category and commission:
                    commissions[category] = commission
                    print(f'      {category}: {commission}%')
    
    for div in soup.find_all(['div', 'section', 'article']):
        text = div.get_text()
        if 'комиссия' in text.lower() and '%' in text:
            extracted = parse_text_commissions(text)
            commissions.update(extracted)
    
    return commissions

def parse_text_commissions(text):
    results = {}
    patterns = [
        r'([А-Яа-я][А-Яа-я\s]+?)\s*[-–:]\s*(\d+(?:\.\d+)?)\s*%',
        r'(\d+(?:\.\d+)?)\s*%\s*[-–:]\s*([А-Яа-я][А-Яа-я\s]+)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if len(match) == 2:
                if match[0].replace('.', '').isdigit():
                    results[match[1].strip()] = float(match[0])
                else:
                    results[match[0].strip()] = float(match[1])
    
    return results

def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_commission(text):
    match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
    if match:
        return float(match.group(1))
    return None

def parse_all_sources():
    all_commissions = {}
    
    sources = [
        'https://seller.ozon.ru/help/tariffs',
        'https://docs.ozon.ru/common/tariffs/',
        'https://seller-edu.ozon.ru/tariffs'
    ]
    
    for url in sources:
        commissions = parse_tariffs_page(url)
        all_commissions.update(commissions)
        time.sleep(1)
    
    return all_commissions

def save_commissions(commissions):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now()
    
    for category, rate in commissions.items():
        cursor.execute('''
            INSERT INTO commissions (category, commission, collected_at)
            VALUES (?, ?, ?)
        ''', (category, rate, now))
    
    conn.commit()
    conn.close()
    print(f'  Saved {len(commissions)} records')

def get_latest_commissions():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT category, commission, MAX(collected_at)
        FROM commissions
        GROUP BY category
    ''')
    results = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return results

def get_changes(current, previous):
    changes = []
    for category, rate in current.items():
        old_rate = previous.get(category)
        if old_rate and abs(rate - old_rate) > 0.1:
            changes.append({
                'category': category,
                'old': old_rate,
                'new': rate,
                'diff': round(rate - old_rate, 1)
            })
    changes.sort(key=lambda x: abs(x['diff']), reverse=True)
    return changes

def format_changes_for_digest(changes, limit=10):
    if not changes:
        return 'No commission changes detected\n'
    
    up = [c for c in changes if c['diff'] > 0][:5]
    down = [c for c in changes if c['diff'] < 0][:5]
    
    result = 'OZON COMMISSIONS CHANGES:\n\n'
    
    if up:
        result += 'INCREASED:\n'
        for c in up:
            result += f"  - {c['category'][:35]}: {c['old']} -> {c['new']} (+{c['diff']})\n"
        result += '\n'
    
    if down:
        result += 'DECREASED:\n'
        for c in down:
            result += f"  - {c['category'][:35]}: {c['old']} -> {c['new']} ({c['diff']})\n"
        result += '\n'
    
    if len(changes) > 10:
        result += f'_and {len(changes) - 10} more changes_'
    
    return result

def main():
    print(f'\nOzon Commission Parser - {datetime.now()}')
    print('=' * 60)
    
    init_db()
    
    previous = get_latest_commissions()
    print(f'Previous records: {len(previous)}')
    
    print('\nParsing sources...')
    current = parse_all_sources()
    print(f'\nFound commissions: {len(current)}')
    
    save_commissions(current)
    
    changes = get_changes(current, previous)
    print('\n' + '=' * 60)
    print(format_changes_for_digest(changes))
    print('=' * 60)

if __name__ == '__main__':
    main()