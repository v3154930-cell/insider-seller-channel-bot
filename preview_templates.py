#!/usr/bin/env python3
"""Preview tool for digest templates - prints to console without publishing to MAX."""

from message_templates import (
    get_morning_empty_template,
    get_morning_fallback_template,
    get_evening_empty_template,
    get_evening_fallback_template,
    get_evening_no_critical_template,
)

def main():
    print("=" * 60)
    print("DIGEST TEMPLATES PREVIEW")
    print("=" * 60)
    
    print("\n--- MORNING DIGEST: Empty (no news) ---")
    print(get_morning_empty_template())
    
    print("\n--- MORNING DIGEST: With sample items ---")
    sample_items = "- Ozon raises commission rates for electronics by 3%\n- Wildberries launches new logistics hub in Kazan"
    print(get_morning_fallback_template(sample_items))
    
    print("\n--- EVENING DIGEST: Empty (no news) ---")
    print(get_evening_empty_template("13.04.2026"))
    
    print("\n--- EVENING DIGEST: With CRITICAL items ---")
    sample_critical = "[*] Court rules against seller in trademark dispute - 500K fine\n[*] Ozon blocks 200 accounts for document violations"
    print(get_evening_fallback_template("13.04.2026", sample_critical, 15))
    
    print("\n--- EVENING DIGEST: No critical (normal day) ---")
    print(get_evening_no_critical_template("13.04.2026", 8))
    
    print("\n" + "=" * 60)
    print("Preview complete - no data posted, no MAX API called")
    print("=" * 60)

if __name__ == "__main__":
    main()