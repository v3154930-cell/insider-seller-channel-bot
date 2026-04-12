import os
import sys
import logging
import requests
import argparse
from datetime import datetime
from config import get_sent_links, save_link
from formatters import format_news
from db import init_db, get_pending_news, mark_published, mark_dropped, get_all_pending_count, set_digest_sent, is_digest_sent_today, cleanup_by_retention_policy, get_top_news_for_digest, mark_news_in_digest, get_critical_news_hours, get_today_published
from llm import enhance_post_with_llm, USE_LLM, GITHUB_TOKEN, select_best_items_for_publishing
from scheduler import get_morning_summary, get_evening_digest, get_audio_digest_script, now_moscow, FORCE_AUDIO_DIGEST, SALUTESPEECH_VOICE, MOSCOW_TZ
from tts import generate_audio, is_available as tts_available

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("MAX_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
MAX_POSTS_PER_RUN = 2

logger.info(f"USE_LLM = {USE_LLM}")
logger.info(f"GITHUB_TOKEN configured = {bool(GITHUB_TOKEN)}")
logger.info(f"FORCE_AUDIO_DIGEST = {FORCE_AUDIO_DIGEST}")
logger.info(f"SALUTESPEECH_VOICE = {SALUTESPEECH_VOICE}")

def send_message(token, chat_id, text, format: str = "html"):
    url = f"https://platform-api.max.ru/messages?chat_id={chat_id}"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }
    payload = {"text": text, "format": format, "disable_link_preview": False}
    
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

def run_regular_publisher():
    """Regular mode: publish posts without any time checks"""
    logger.info("=== Regular Publisher mode ===")
    logger.info(f"Time (Moscow): {now_moscow().strftime('%Y-%m-%d %H:%M:%S')}")
    
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
    
    cleanup_results = cleanup_by_retention_policy()
    if cleanup_results:
        logger.info(f"Cleanup: {cleanup_results}")
    else:
        logger.info("Cleanup: nothing to clean")
    
    pending_count = get_all_pending_count()
    logger.info(f"Queue size: {pending_count} pending items")
    
    candidate_count = min(25, pending_count)
    pending = get_pending_news(candidate_count)
    
    if not pending:
        logger.info("No pending posts to send")
        return
    
    logger.info(f"Loaded candidate items: {len(pending)}")
    
    logger.info("Batch selection started")
    selected = select_best_items_for_publishing(pending, MAX_POSTS_PER_RUN)
    
    if not selected:
        all_pending_ids = [item['id'] for item in pending]
        mark_dropped(all_pending_ids)
        logger.warning(f"Selection LLM failed or no relevant items, marked {len(all_pending_ids)} as dropped, skipping run")
        return
    
    selected_ids = [item['id'] for item in selected]
    rejected_ids = [item['id'] for item in pending if item['id'] not in selected_ids]
    rejected_count = len(rejected_ids)
    logger.info(f"Batch selection ok: selected={selected_ids}, rejected={rejected_count}")
    
    if rejected_ids:
        mark_dropped(rejected_ids)
        logger.info(f"Marked {len(rejected_ids)} items as dropped for cleanup")
    
    for i, item in enumerate(selected):
        logger.info(f"Selected for publish: id={item['id']}")
    
    new_posts = 0
    
    for item in selected:
        link = item.get('link', '')
        
        raw_text = item.get('raw_text', '')
        logger.info(f"Processing item: id={item.get('id')}, raw_text_len={len(raw_text)}")
        
        has_raw_text = bool(raw_text)
        enhance_success = False
        
        if USE_LLM and has_raw_text:
            logger.info("Final enhance started")
            enhanced = enhance_post_with_llm(item)
            if enhanced:
                formatted_message = enhanced
                enhance_success = True
                logger.info(f"Final enhance ok: id={item['id']}")
            else:
                formatted_message = format_news(item)
                logger.warning(f"Final enhance failed: id={item['id']}, using fallback")
        else:
            formatted_message = format_news(item)
        
        success = send_message(token, channel_id, formatted_message)
        
        if success:
            save_link(link)
            mark_published(item['id'])
            new_posts += 1
            logger.info(f"Posted: id={item['id']}")
        else:
            logger.error(f"Failed: id={item['id']}")
    
    final_pending = get_all_pending_count()
    logger.info(f"=== Regular Publisher finished. Sent: {new_posts}, Remaining in queue: {final_pending} ===")

def run_morning_digest():
    """Morning digest mode"""
    from scheduler import ENABLE_MORNING_DIGEST
    
    if not ENABLE_MORNING_DIGEST:
        logger.info("Morning digest disabled by ENABLE_MORNING_DIGEST flag - skipping")
        return
    
    logger.info("=== Morning Digest mode ===")
    logger.info(f"Time (Moscow): {now_moscow().strftime('%Y-%m-%d %H:%M:%S')}")
    
    token = TOKEN
    channel_id = CHANNEL_ID
    
    if channel_id:
        if channel_id.startswith('@'):
            channel_id = "-73160979033512"
        elif channel_id.isdigit():
            channel_id = f"-{channel_id}"
    
    if not token or not channel_id:
        logger.error("MAX_BOT_TOKEN or CHANNEL_ID not set")
        sys.exit(1)
    
    init_db()
    logger.info("Database initialized")
    
    logger.info("Generating morning digest summary...")
    summary = get_morning_summary()
    
    if summary:
        logger.info(f"Morning summary generated (length: {len(summary)} chars)")
        logger.info("Sending morning digest to channel...")
        send_message(token, channel_id, summary)
        logger.info("Morning digest sent successfully")
    else:
        logger.warning("Morning summary generation failed or returned empty")

def run_audio_digest():
    """Audio digest mode"""
    from scheduler import ENABLE_AUDIO_DIGEST
    
    if not ENABLE_AUDIO_DIGEST:
        logger.info("Audio digest disabled by ENABLE_AUDIO_DIGEST flag - skipping")
        return
    
    logger.info("=== Audio Digest mode ===")
    logger.info(f"Time (Moscow): {now_moscow().strftime('%Y-%m-%d %H:%M:%S')}")
    
    token = TOKEN
    channel_id = CHANNEL_ID
    
    if channel_id:
        if channel_id.startswith('@'):
            channel_id = "-73160979033512"
        elif channel_id.isdigit():
            channel_id = f"-{channel_id}"
    
    if not token or not channel_id:
        logger.error("MAX_BOT_TOKEN or CHANNEL_ID not set")
        sys.exit(1)
    
    init_db()
    logger.info("Database initialized")
    
    logger.info("Fetching top news for audio digest...")
    top_news = get_top_news_for_digest(limit=5)
    logger.info(f"Selected top news for digest: {len(top_news)}")
    
    if not top_news:
        logger.warning("No top news available for audio digest - skipping")
        return
    
    logger.info("Generating audio digest script...")
    script = get_audio_digest_script(top_news)
    
    if not script:
        logger.error("FAILURE: Audio script generation failed - no script returned")
        return
    
    logger.info(f"Audio script generated: yes (length: {len(script)} chars)")
    
    if tts_available():
        logger.info("SaluteSpeech available: yes, generating audio...")
        audio_path = generate_audio(script, "daily_digest.mp3")
        
        if audio_path:
            logger.info(f"Audio mp3 generated: yes (path: {audio_path})")
            logger.info("Sending audio message to channel...")
            send_audio_message(token, channel_id, audio_path, script)
        else:
            logger.warning("Audio mp3 generation FAILED, falling back to text")
            send_message(token, channel_id, f"🎙️ Daily Digest\n\n{script}")
    else:
        logger.warning("SaluteSpeech NOT configured, sending text digest")
        send_message(token, channel_id, f"🎙️ Daily Digest\n\n{script}")
    
    news_ids = [n['id'] for n in top_news]
    mark_news_in_digest(news_ids)
    set_digest_sent('audio')
    logger.info("Audio digest sent - digest marked as sent")

def run_final_digest():
    """Final (evening) text digest mode"""
    from scheduler import ENABLE_EVENING_DIGEST
    
    if not ENABLE_EVENING_DIGEST:
        logger.info("Evening digest disabled by ENABLE_EVENING_DIGEST flag - skipping")
        return
    
    logger.info("=== Final Digest mode ===")
    logger.info(f"Time (Moscow): {now_moscow().strftime('%Y-%m-%d %H:%M:%S')}")
    
    token = TOKEN
    channel_id = CHANNEL_ID
    
    if channel_id:
        if channel_id.startswith('@'):
            channel_id = "-73160979033512"
        elif channel_id.isdigit():
            channel_id = f"-{channel_id}"
    
    if not token or not channel_id:
        logger.error("MAX_BOT_TOKEN or CHANNEL_ID not set")
        sys.exit(1)
    
    init_db()
    logger.info("Database initialized")
    
    logger.info("Generating final digest summary...")
    digest = get_evening_digest()
    
    if digest:
        logger.info(f"Final digest generated (length: {len(digest)} chars)")
        logger.info("Sending final digest to channel...")
        send_message(token, channel_id, digest)
        logger.info("Final digest sent successfully")
    else:
        logger.warning("Final digest generation failed or returned empty")

def main():
    parser = argparse.ArgumentParser(description='Publisher mode selector')
    parser.add_argument(
        '--mode',
        type=str,
        default='regular',
        choices=['regular', 'morning_digest', 'audio_digest', 'final_digest'],
        help='Publisher mode: regular, morning_digest, audio_digest, final_digest'
    )
    
    args = parser.parse_args()
    
    logger.info(f"Starting in mode: {args.mode}")
    logger.info(f"Current Moscow time: {now_moscow().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    if args.mode == 'regular':
        run_regular_publisher()
    elif args.mode == 'morning_digest':
        run_morning_digest()
    elif args.mode == 'audio_digest':
        run_audio_digest()
    elif args.mode == 'final_digest':
        run_final_digest()

if __name__ == "__main__":
    main()