#!/usr/bin/env python3
"""Preview tool for Exa collector - prints results to console without publishing."""

from exa_collector import search_exa

def main():
    print("=" * 50)
    print("EXA Collector Preview")
    print("=" * 50)
    
    query = "Ozon sellers news Russia"
    print(f"\nQuery: {query}")
    
    results = search_exa(query, num_results=5)
    
    print(f"Found: {len(results)} items\n")
    
    for i, item in enumerate(results, 1):
        print(f"{i}. {item.get('title', 'No title')[:70]}")
        print(f"   Link: {item.get('link', 'No link')[:50]}")
        print()
    
    print("=" * 50)
    print("Preview complete - no DB writes, no MAX API calls")

if __name__ == "__main__":
    main()