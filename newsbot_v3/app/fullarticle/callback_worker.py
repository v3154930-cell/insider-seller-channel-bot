from app.fullarticle.delivery import choose_target
from app.fullarticle.article_builder import build_full_article

def handle_callback(callback:dict,news:dict,max_client)->dict:
    payload=callback.get("payload","")
    news_id=payload.split(":",1)[1] if payload.startswith("full_article:") else None
    target,cands=choose_target(callback,news.get("max_message_id"))
    if not news_id or not target:
        return {"full_article_callback_received":bool(payload),"news_id":news_id,"callback_id":callback.get("callback_id"),"delivery_target_candidates":cands,"full_article_send_status":"error","full_article_visible_delivery":False}
    text=build_full_article(news)
    resp=max_client.send_visible_message(target,text)
    visible=max_client.validate_visible_delivery(resp)
    return {"full_article_callback_received":True,"news_id":news_id,"callback_id":callback.get("callback_id"),"delivery_target_candidates":cands,"full_article_delivery_target":target,"full_article_send_mode":"visible_message","full_article_api_status":"ok" if resp.get("ok") else "error","full_article_visible_delivery":visible,"full_article_result_message_id":max_client.extract_message_id(resp),"full_article_send_status":"ok" if visible else "error"}
