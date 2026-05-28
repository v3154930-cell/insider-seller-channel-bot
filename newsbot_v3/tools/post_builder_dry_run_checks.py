#!/usr/bin/env python3
from app.models import NewsItem
from app.publisher.post_builder import build_post


def _mk_item(news_id: str, text: str, link: str = "https://example.com/news") -> NewsItem:
    return NewsItem(news_id=news_id, title="Test", text=text, link=link, source_name="Example", importance="🟡")


def main() -> int:
    long_item = _mk_item("1", "A" * 2200)
    short_item = _mk_item("2", "B" * 200)
    no_full_item = _mk_item("3", "")

    long_post = build_post(long_item)
    short_post = build_post(short_item)
    no_full_post = build_post(no_full_item)

    print(f"long_read_more={long_post['read_more_needed']}")
    print(f"long_callback_ok={str((long_post.get('callback_payload') or '').startswith('full_article:')).lower()}")
    print(f"short_read_more={short_post['read_more_needed']}")
    print(f"short_source_url_present={short_post['source_url_present']}")
    print(f"short_raw_source_url_in_main_post={str(short_post['raw_source_url_in_main_post']).lower()}")
    print(f"short_source_link_preview_suppressed={str(short_post['source_link_preview_suppressed']).lower()}")
    print(f"missing_fulltext_read_more={no_full_post['read_more_needed']}")
    print(f"no_external_url_button={str(long_post.get('source_url_button_used') is False and long_post.get('external_url_button_forbidden') is True).lower()}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
