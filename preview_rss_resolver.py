#!/usr/bin/env python3
"""Preview-only resolver for RSS article URLs.
Test which RSS links need resolution and which are already direct articles."""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import time

RSS_LINKS_TO_TEST = [
    # Retail.ru - most common
    "https://www.retail.ru/news/ozon-snizil-komissiyu-novym-prodavtsam/",
    "https://www.retail.ru/news/wildberries-zapustil-novuyu-programmu-logistiki/",
    "https://www.retail.ru/news/yandex-market-izmenil-pravila-prodavtsov/",
    # Oborot.ru
    "https://oborot.ru/news/ozon-tariffs",
    "https://oborot.ru/news/wb-new-rules",
    # vc.ru
    "https://vc.ru/new/123456",
    "https://vc.ru/news/789012",
    # cnews
    "https://www.cnews.ru/news/line/2024-01-01",
    # rbc
    "https://www.rbc.ru/business/news/123456789",
]

def extract_direct_url(link: str) -> dict:
    """Try to extract direct article URL from RSS/listing link.
    Returns: {success: bool, url: str or None, method: str, reason: str}"""
    
    if not link:
        return {'success': False, 'url': None, 'method': 'none', 'reason': 'empty link'}
    
    # Fast path: check if link already looks like direct article
    path = urlparse(link).path.lower()
    if '/news/' in path or '/article/' in path or '/v/' in path or '/p/' in path:
        # Likely already direct article
        if not any(x in path for x in ['/rss', '/feed', '/list', '/page']):
            return {'success': True, 'url': link, 'method': 'already_direct', 'reason': 'path looks like article'}
    
    # Try to fetch and extract
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        resp = requests.get(link, headers=headers, timeout=10, allow_redirects=True)
        
        if resp.status_code != 200:
            return {'success': False, 'url': None, 'method': 'http_error', 'reason': f'status {resp.status_code}'}
        
        final_url = resp.url
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Method 1: link rel=canonical
        canonical = soup.find('link', rel='canonical')
        if canonical and canonical.get('href'):
            return {'success': True, 'url': canonical['href'], 'method': 'canonical', 'reason': 'found in rel=canonical'}
        
        # Method 2: meta property="og:url"
        og_url = soup.find('meta', property='og:url')
        if og_url and og_url.get('content'):
            return {'success': True, 'url': og_url['content'], 'method': 'og:url', 'reason': 'found in og:url'}
        
        # Method 3: meta http-equiv="refresh" (rare)
        refresh = soup.find('meta', http_equiv='refresh')
        if refresh and refresh.get('content'):
            content = refresh['content']
            if 'url=' in content.lower():
                url_part = content.split('url=')[1].split(' ')[0].split(';')[0]
                return {'success': True, 'url': url_part, 'method': 'refresh', 'reason': 'found in meta refresh'}
        
        # Method 4: check final URL after redirect
        if final_url != link:
            return {'success': True, 'url': final_url, 'method': 'redirect', 'reason': 'URL changed after redirect'}
        
        # Method 5: if it's already on article path, keep it
        if '/news/' in final_url or '/article/' in final_url:
            return {'success': True, 'url': final_url, 'method': 'path_check', 'reason': 'article path detected'}
        
        return {'success': False, 'url': final_url, 'method': 'none', 'reason': 'no extraction method worked'}
        
    except requests.Timeout:
        return {'success': False, 'url': None, 'method': 'timeout', 'reason': 'request timeout'}
    except requests.RequestException as e:
        return {'success': False, 'url': None, 'method': 'error', 'reason': str(e)[:50]}
    except Exception as e:
        return {'success': False, 'url': None, 'method': 'exception', 'reason': str(e)[:50]}


# Run preview on sample links
print("=" * 70)
print("RSS URL EXTRACTION PREVIEW")
print("=" * 70)
print()

results = []
for link in RSS_LINKS_TO_TEST[:5]:  # Test first 5
    result = extract_direct_url(link)
    result['original'] = link
    results.append(result)
    
    parsed = urlparse(link)
    domain = parsed.netloc
    
    status = "✅" if result['success'] else "❌"
    print(f"{status} {domain}")
    print(f"   Original: {link[:60]}...")
    print(f"   Resolved: {result['url'][:60] if result['url'] else 'None'}..." if result['url'] else f"   Resolved: None")
    print(f"   Method:   {result['method']}")
    print(f"   Reason:   {result['reason']}")
    print()
    
    time.sleep(0.5)  # Rate limit

# Summary
success_count = sum(1 for r in results if r['success'])
print("=" * 70)
print(f"SUMMARY: {success_count}/{len(results)} successfully extracted")
print("=" * 70)