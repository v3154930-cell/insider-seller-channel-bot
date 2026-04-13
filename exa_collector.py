"""
Exa Collector - Search news via Exa API with daily rate limit.
"""

import os
import json
import requests
from datetime import datetime
from typing import List, Dict, Optional

USAGE_FILE = "exa_usage.json"
MAX_DAILY_REQUESTS = 10


def _get_usage() -> Dict[str, int]:
    """Load usage counter from file."""
    if not os.path.exists(USAGE_FILE):
        return {}
    try:
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_usage(usage: Dict[str, int]) -> None:
    """Save usage counter to file."""
    with open(USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(usage, f, ensure_ascii=False)


def _get_today() -> str:
    """Get today's date as YYYY-MM-DD string."""
    return datetime.now().strftime("%Y-%m-%d")


def _check_limit() -> bool:
    """Check if daily limit is reached. Returns True if can make request."""
    usage = _get_usage()
    today = _get_today()
    count = usage.get(today, 0)
    return count < MAX_DAILY_REQUESTS


def _increment_usage() -> None:
    """Increment today's usage counter."""
    usage = _get_usage()
    today = _get_today()
    usage[today] = usage.get(today, 0) + 1
    _save_usage(usage)


def search_exa(query: str, num_results: int = 10) -> List[Dict]:
    """
    Search news via Exa API with rate limiting.
    
    Args:
        query: Search query string
        num_results: Number of results to return (default: 10)
    
    Returns:
        List of news items with keys: title, raw_text, link, source
        Returns empty list if limit reached or API unavailable.
    """
    if not _check_limit():
        return []
    
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        return []
    
    url = "https://api.exa.ai/search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "query": query,
        "num_results": num_results,
        "text": True,
        "include_domains": ["news", "blog"]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code != 200:
            return []
        
        data = response.json()
        results = data.get("results", [])
        
        _increment_usage()
        
        news_items = []
        for item in results:
            news_items.append({
                "title": item.get("title", ""),
                "raw_text": item.get("text", ""),
                "link": item.get("url", ""),
                "source": "exa"
            })
        
        return news_items
        
    except (requests.RequestException, json.JSONDecodeError):
        return []


def get_marketplace_news(query: str = "marketplace sellers e-commerce Russia") -> List[Dict]:
    """
    Convenience function to search for marketplace/e-commerce news.
    
    Args:
        query: Search query (default: generic marketplace query)
    
    Returns:
        List of news items from Exa search.
    """
    return search_exa(query, num_results=10)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "Ozon Wildberries маркетплейс продавец"
    
    results = get_marketplace_news(query)
    print(f"Found {len(results)} items")
    for item in results:
        print(f"- {item.get('title', 'No title')[:60]}...")