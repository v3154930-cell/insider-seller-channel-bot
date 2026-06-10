import json
from pathlib import Path
from urllib.parse import urlparse

SOURCE_PATH = Path(__file__).resolve().parents[1] / "config" / "legal_rag_sources_v1.json"

REQUIRED_FIELDS = {
    "source_key",
    "source_name",
    "source_url",
    "source_type",
    "marketplace",
    "rag_layer_requested",
    "production_rag_layer",
    "trust_level",
    "document_type",
    "document_number",
    "document_date",
    "court_name",
    "case_number",
    "instance",
    "topic_tags",
    "seller_relevance_reason",
    "notes",
    "ingest_mode",
}

BANNED_DOMAINS = {
    "consultant.ru",
    "www.consultant.ru",
    "garant.ru",
    "www.garant.ru",
    "base.garant.ru",
}

HOMEPAGE_ONLY_URLS = {
    "https://pravo.gov.ru",
    "http://pravo.gov.ru",
    "https://publication.pravo.gov.ru",
    "http://publication.pravo.gov.ru",
    "https://vsrf.ru",
    "https://www.vsrf.ru",
    "https://kad.arbitr.ru",
    "https://kad.arbitr.ru/",
    "https://nalog.gov.ru",
    "https://www.nalog.gov.ru",
}

COURT_SOURCE_TYPES = {
    "court_practice_public",
    "supreme_court_definition",
    "supreme_court_plenum",
    "supreme_court_review",
}


def _load_sources():
    with SOURCE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, list)
    return data


def test_legal_rag_sources_have_required_fields_and_unique_keys():
    sources = _load_sources()
    assert len(sources) >= 20
    keys = [entry.get("source_key") for entry in sources]
    assert len(keys) == len(set(keys))

    for entry in sources:
        missing = REQUIRED_FIELDS - set(entry)
        assert not missing, f"{entry.get('source_key')} missing {sorted(missing)}"
        for field in REQUIRED_FIELDS - {"notes", "court_name", "case_number", "instance"}:
            assert entry[field], f"{entry['source_key']} has empty {field}"
        assert isinstance(entry["topic_tags"], list) and entry["topic_tags"]
        assert entry["ingest_mode"] == "dry_run_first/manual_review_required"


def test_legal_rag_sources_reject_commercial_legal_database_domains_and_homepages():
    for entry in _load_sources():
        parsed = urlparse(entry["source_url"])
        host = parsed.netloc.lower()
        assert host not in BANNED_DOMAINS, f"commercial legal DB URL is not allowed: {entry['source_key']}"
        assert entry["source_url"].rstrip("/") not in {url.rstrip("/") for url in HOMEPAGE_ONLY_URLS}, (
            f"homepage-only URL is not allowed: {entry['source_key']}"
        )


def test_court_practice_entries_include_court_case_date_and_lower_trust_for_ordinary_courts():
    court_entries = [entry for entry in _load_sources() if entry["source_type"] in COURT_SOURCE_TYPES]
    assert court_entries

    for entry in court_entries:
        assert entry["court_name"], f"court source must include court_name: {entry['source_key']}"
        assert entry["document_date"], f"court source must include document_date: {entry['source_key']}"
        assert entry["seller_relevance_reason"], f"court source must explain seller relevance: {entry['source_key']}"
        if entry["source_type"] == "court_practice_public":
            assert entry["case_number"], f"ordinary court source must include case_number: {entry['source_key']}"
            assert entry["trust_level"].startswith("lower_court"), (
                f"ordinary court source must be lower trust than Supreme Court: {entry['source_key']}"
            )
        else:
            assert entry["trust_level"].startswith("supreme_court"), (
                f"Supreme Court source must be marked supreme_court trust: {entry['source_key']}"
            )
