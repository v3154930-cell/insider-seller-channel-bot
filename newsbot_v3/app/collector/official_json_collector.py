import hashlib, os
from typing import Any


def _pick(d:dict[str,Any],keys:list[str]):
    for k in keys:
        if d.get(k): return d[k]
    return None

def title_from_text(text:str)->str: return (text or "").strip().split("\n")[0][:100] or "Без заголовка"

def guess_marketplace(source:str,link:str,text:str)->str:
    s=f"{source} {link} {text}".lower()
    if "ozon" in s: return "ozon"
    if "wildberries" in s or "wb" in s: return "wb"
    if "yandex" in s: return "yandex"
    return "unknown"

def normalize_post(post:dict[str,Any])->dict[str,Any]:
    text=_pick(post,["text","raw_text","body","content","message"]) or ""
    title=_pick(post,["title","headline"]) or title_from_text(text)
    link=_pick(post,["link","raw_url","post_url","url","source_url"]) or ""
    source_name=_pick(post,["source_name","source"]) or "official_json"
    marketplace=_pick(post,["marketplace"]) or guess_marketplace(source_name,link,text)
    content_hash=_pick(post,["content_hash","hash"]) or hashlib.sha256(f"{title}|{text}|{link}".encode()).hexdigest()
    return {"title":title,"text":text,"link":link,"source_name":source_name,"marketplace":marketplace,"content_hash":content_hash,"post_id":_pick(post,["post_id","id"]),"published_at":_pick(post,["published_at","posted_at","date","created_at"]),"source_type":"official_channel","rag_layer":"official_signal","trust_level":"high"}

def parse_payload(payload:Any)->list[dict[str,Any]]:
    if isinstance(payload,list): return [normalize_post(p) for p in payload if isinstance(p,dict)]
    if isinstance(payload,dict):
        for key in ["posts","items","updates","data"]:
            if isinstance(payload.get(key),list): return [normalize_post(p) for p in payload[key] if isinstance(p,dict)]
    return []

def load_official_json_urls(env:dict[str,str]|None=None)->list[str]:
    env=env or os.environ
    urls=[]
    if env.get("OFFICIAL_JSON_URL"): urls.append(env["OFFICIAL_JSON_URL"])
    if env.get("OFFICIAL_JSON_URLS"): urls += [u.strip() for u in env["OFFICIAL_JSON_URLS"].split(",") if u.strip()]
    return urls

def dry_run()->dict[str,Any]:
    urls=load_official_json_urls()
    return {"official_json_dry_run":True,"official_json_primary":True,"official_json_sources_count":len(urls),"official_json_posts_seen":0,"official_json_seen":0,"official_json_inserted":0,"official_json_failed":0,"official_tg_fallback_used":False,"official_tg_fallback_mode":"explicit_only"}
