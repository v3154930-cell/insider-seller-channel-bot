#!/usr/bin/env python3
"""Find top problem RSS domains from DB - which domains have listing/aggregtor links"""
import sqlite3
import os
from urllib.parse import urlparse

try:
    conn = sqlite3.connect('news_queue.db')
    cur = conn.cursor()
    
    # Get recent links and analyze their domains
    cur.execute('''
        SELECT link, source, created_at 
        FROM news 
        WHERE link IS NOT NULL AND link != ''
        ORDER BY created_at DESC 
        LIMIT 50
    ''')
    
    rows = cur.fetchall()
    conn.close()
    
    # Analyze domains
    domain_stats = {}
    
    for row in rows:
        link = row[0] or ''
        source = row[1] or 'unknown'
        
        if not link:
            continue
            
        try:
            parsed = urlparse(link)
            domain = parsed.netloc.lower()
            
            # Categorize: is it a direct article or listing/aggregator?
            path = parsed.path.lower()
            
            # Heuristics for aggregator/listing:
            is_listing = any(x in path for x in ['/news/', '/rss/', '/feed/', '/blog/', '/articles', '/list'])
            is_aggregator = any(x in domain for x in ['retail.ru', 'oborot.ru', 'vc.ru', 'cnews.ru', 'rbc.ru', 'kommersant.ru'])
            
            if domain not in domain_stats:
                domain_stats[domain] = {'count': 0, 'listing': 0, 'sources': set()}
            
            domain_stats[domain]['count'] += 1
            if is_listing or is_aggregator:
                domain_stats[domain]['listing'] += 1
            domain_stats[domain]['sources'].add(source)
            
        except Exception:
            continue
    
    # Sort by count
    sorted_domains = sorted(domain_stats.items(), key=lambda x: x[1]['count'], reverse=True)
    
    # Write results
    with open('domain_analysis.txt', 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("TOP RSS DOMAINS ANALYSIS\n")
        f.write("=" * 70 + "\n\n")
        
        f.write(f"Total domains found: {len(sorted_domains)}\n\n")
        
        for domain, stats in sorted_domains[:15]:
            f.write(f"\n{domain}:\n")
            f.write(f"  Count: {stats['count']}\n")
            f.write(f"  Listing/aggregator: {stats['listing']}\n")
            f.write(f"  Sources: {', '.join(stats['sources'])}\n")
        
        f.write("\n" + "=" * 70 + "\n")
        f.write("TOP PROBLEM DOMAINS (most likely aggregators):\n")
        f.write("=" * 70 + "\n")
        
        for domain, stats in sorted_domains[:5]:
            if stats['listing'] > 0:
                f.write(f"\n{domain}: {stats['listing']}/{stats['count']} listing links\n")

except Exception as e:
    with open('domain_analysis.txt', 'w', encoding='utf-8') as f:
        f.write(f"Error: {e}")