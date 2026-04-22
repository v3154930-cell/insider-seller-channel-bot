#!/usr/bin/env python3
"""
Analyze what kind of links RSS feeds actually return.
This helps determine if we really have an aggregator problem.
"""
import feedparser
from urllib.parse import urlparse

RSS_FEEDS = [
    ("https://www.retail.ru/rss/news/", "Retail.ru"),
    ("https://oborot.ru/feed/", "Oborot.ru"),
    ("https://vc.ru/rss/all", "vc.ru"),
    ("https://www.cnews.ru/inc/rss/news.xml", "CNews"),
    ("https://rssexport.rbc.ru/rbcnews/news/30/full.rss", "RBC")
]

def analyze_rss_links():
    output = []
    output.append("=" * 70)
    output.append("RSS FEED LINK ANALYSIS")
    output.append("=" * 70)
    output.append("")
    
    for feed_url, feed_name in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            if not feed.entries:
                output.append(f"{feed_name}: NO ENTRIES")
                continue
                
            output.append(f"\n=== {feed_name} ===")
            output.append(f"Feed: {feed_url}")
            output.append(f"Total entries: {len(feed.entries)}")
            
            # Check first few links
            link_types = {'article': 0, 'listing': 0, 'unknown': 0}
            
            for entry in feed.entries[:5]:
                link = entry.get('link', '')
                if not link:
                    continue
                    
                parsed = urlparse(link)
                path = parsed.path.lower()
                domain = parsed.netloc
                
                # Heuristic classification
                if any(x in path for x in ['/news/', '/article/', '/v/', '/p/', '/story/', '/n/']):
                    link_type = 'article'
                elif any(x in path for x in ['/rss', '/feed', '/index', '/list', '/page']):
                    link_type = 'listing'
                else:
                    link_type = 'unknown'
                
                link_types[link_type] += 1
                
                output.append(f"  [{link_type:8}] {domain}{path[:50]}")
            
            output.append(f"  Summary: {link_types['article']} article, {link_types['listing']} listing")
            
        except Exception as e:
            output.append(f"\n{feed_name}: ERROR - {str(e)[:50]}")
    
    output.append("")
    output.append("=" * 70)
    output.append("CONCLUSION")
    output.append("=" * 70)
    output.append("")
    output.append("If most links are 'article' type -> no extraction needed")
    output.append("If many are 'listing' type -> need resolver")
    output.append("")
    
    return '\n'.join(output)

result = analyze_rss_links()

# Try to write to file
try:
    with open('rss_link_analysis.txt', 'w', encoding='utf-8') as f:
        f.write(result)
except:
    pass

print(result)