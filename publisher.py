import os
import sys
import logging
import requests
from datetime import datetime
from config import get_sent_links, save_link
from formatters import format_news
from db import init_db, get_pending_news, mark_published, get_all_pending_count, set_digest_sent, is_digest_sent_today
from llm import enhance_post_with_llm, USE_LLM, GITHUB_TOKEN
from scheduler import should_send_morning_digest, should_send_evening_digest, should_send_audio_digest, get_morning_summary, get_evening_digest, get_audio_digest_script, now_moscow, FORCE_AUDIO_DIGEST, SALUTESPEECH_VOICE
from tts import generate_audio, is_available as tts_available

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info(f"DEBUG CHECKPOINT: publisher started from updated code")
logger.info(f"DEBUG CHECKPOINT: GITHUB_ACTIONS={os.getenv('GITHUB_ACTIONS')}")

TOKEN = os.getenv("MAX_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
MAX_POSTS_PER_RUN = 2

logger.info(f"USE_LLM = {USE_LLM}")
logger.info(f"GITHUB_TOKEN configured = {bool(GITHUB_TOKEN)}")
logger.info(f"FORCE_AUDIO_DIGEST = {FORCE_AUDIO_DIGEST}")
logger.info(f"SALUTESPEECH_VOICE = {SALUTESPEECH_VOICE}")

def send_message(token, chat_id, text):
    url = f"https://platform-api.max.ru/messages?chat_id={chat_id}"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }
    payload = {"text": text}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return True
        else:
            logger.error(f"API error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False

def send_audio_message(token, chat_id, audio_path, text_announce):
    import time
    
    try:
        upload_url = f"https://platform-api.max.ru/messages/upload?chat_id={chat_id}"
        
        with open(audio_path, 'rb') as f:
            files = {'file': f}
            upload_response = requests.post(upload_url, headers={"Authorization": token}, files=files, timeout=60)
        
        if upload_response.status_code != 200:
            logger.error(f"Audio upload failed: {upload_response.status_code}")
            send_message(token, chat_id, text_announce)
            return False
        
        file_id = upload_response.json().get('file', {}).get('id')
        
        if not file_id:
            logger.error("No file_id in upload response")
            send_message(token, chat_id, text_announce)
            return False
        
        logger.info(f"MAX audio uploaded: yes, file_id={file_id}")
        
        max_retries = 3
        for attempt in range(max_retries):
            message_url = f"https://platform-api.max.ru/messages?chat_id={chat_id}"
            
            payload = {
                "text": text_announce,
                "attachment": {
                    "type": "audio",
                    "file_id": file_id
                }
            }
            
            response = requests.post(message_url, headers={"Authorization": token, "Content-Type": "application/json"}, json=payload, timeout=30)
            
            if response.status_code == 200:
                logger.info("MAX audio posted: yes")
                return True
            elif response.status_code == 400 and 'attachment.not.ready' in response.text:
                logger.warning(f"attachment.not.ready retry: {attempt + 1}")
                time.sleep(2)
                continue
            else:
                logger.error(f"Audio message failed: {response.status_code} - {response.text[:100]}")
                send_message(token, chat_id, text_announce)
                return False
        
        logger.error("MAX audio posted: failed after retries")
        send_message(token, chat_id, text_announce)
        return False
        
    except Exception as e:
        logger.error(f"Error sending audio: {e}")
        send_message(token, chat_id, text_announce)
        return False

def run_publisher():
    """Публикация постов из очереди SQLite"""
    logger.info("=== Publisher mode ===")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    token = TOKEN
    channel_id = CHANNEL_ID
    
    if channel_id:
        if channel_id.startswith('@'):
            channel_id = "-73160979033512"
        elif channel_id.isdigit():
            channel_id = f"-{channel_id}"
    
    if not token:
        logger.error("MAX_BOT_TOKEN not set in environment")
        sys.exit(1)
    
    if not channel_id:
        logger.error("CHANNEL_ID not set in environment")
        sys.exit(1)
    
    init_db()
    logger.info("Database initialized")
    logger.info(f"Current time (Moscow): {now_moscow().strftime('%Y-%m-%d %H:%M:%S')}")
    
    logger.info(f"Morning digest check: {'yes' if should_send_morning_digest() else 'no'}")
    logger.info(f"Evening digest check: {'yes' if should_send_evening_digest() else 'no'}")
    logger.info(f"Audio digest check: {'yes' if should_send_audio_digest() else 'no'}")
    
    if should_send_morning_digest():
        logger.info("Morning digest time matched: yes")
        summary = get_morning_summary()
        if summary:
            send_message(token, channel_id, summary)
            logger.info("Morning summary sent")
        return
    
    if should_send_evening_digest():
        logger.info("Evening digest time matched: yes")
        digest = get_evening_digest()
        if digest:
            send_message(token, channel_id, digest)
            logger.info("Evening digest sent")
        return
    
    if should_send_audio_digest():
        logger.info("Audio digest time matched: yes")
        from db import get_top_news_for_digest
        top_news = get_top_news_for_digest(limit=5)
        logger.info(f"Selected top news for digest: {len(top_news)}")
        
        if top_news:
            script = get_audio_digest_script(top_news)
            
            if script:
                logger.info("Audio script generated: yes")
                
                if tts_available():
                    logger.info("SaluteSpeech token obtained: yes")
                    audio_path = generate_audio(script, "daily_digest.mp3")
                    
                    if audio_path:
                        logger.info("Audio mp3 generated: yes")
                        send_audio_message(token, channel_id, audio_path, script)
                    else:
                        logger.warning("Audio mp3 generation failed, falling back to text")
                        send_message(token, channel_id, f"🎙️ Daily Digest\n\n{script}")
                else:
                    logger.info("SaluteSpeech not configured, sending text digest")
                    send_message(token, channel_id, f"🎙️ Daily Digest\n\n{script}")
                
                news_ids = [n['id'] for n in top_news]
                from db import mark_news_in_digest
                mark_news_in_digest(news_ids)
                set_digest_sent('audio')
            else:
                logger.warning("Audio script generation failed")
        else:
            logger.info("No top news for audio digest")
        return
    
    pending_count = get_all_pending_count()
    logger.info(f"Queue size: {pending_count} pending items")
    logger.info("Parsing skipped: yes")
    
    pending = get_pending_news(MAX_POSTS_PER_RUN)
    if pending:
        logger.info(f"Selected pending item: id={pending[0]['id']}, title={pending[0]['title'][:50]}...")
    else:
        logger.info("Selected pending item: none")
    
    if not pending:
        logger.info("No pending posts to send")
        return
    
    new_posts = 0
    
    for item in pending:
        link = item.get('link', '')
        
        raw_text = item.get('raw_text', '')
        logger.info(f"Processing item: id={item.get('id')}, raw_text_len={len(raw_text)}")
        
        has_raw_text = bool(raw_text)
        
        if USE_LLM and has_raw_text:
            enhanced = enhance_post_with_llm(item)
            if enhanced:
                formatted_message = enhanced
                logger.info(f"LLM enhanced post successfully")
            else:
                formatted_message = format_news(item)
                logger.info(f"LLM unavailable, using fallback formatter")
        else:
            formatted_message = format_news(item)
        
        success = send_message(token, channel_id, formatted_message)
        
        if success:
            save_link(link)
            mark_published(item['id'])
            logger.info(f"DEBUG CHECKPOINT: mark_published done for id={item['id']}")
            new_posts += 1
            logger.info(f"✓ Posted: id={item['id']}, title={item['title'][:50]}...")
            logger.info(f"  -> Item marked as sent")
        else:
            logger.error(f"✗ Failed: id={item['id']}, title={item['title'][:50]}...")
    
    final_pending = get_all_pending_count()
    logger.info(f"=== Publisher finished. Sent: {new_posts}, Remaining in queue: {final_pending} ===")

if __name__ == "__main__":
    run_publisher()
