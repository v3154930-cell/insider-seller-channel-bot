import os
import logging
import requests
from typing import Optional
import time
import base64
import uuid

logger = logging.getLogger(__name__)

SALUTESPEECH_API_URL = "https://salutespeech.com/api"

SALUTE_AUTH_KEY = os.getenv("SALUTE_AUTH_KEY")
SALUTESPEECH_VOICE = os.getenv("SALUTESPEECH_VOICE") or "Tur_24000"

ACCESS_TOKEN = None
TOKEN_EXPIRES = 0

MAX_WORD_COUNT = 400

def get_salutespeech_token() -> Optional[str]:
    global ACCESS_TOKEN, TOKEN_EXPIRES
    
    if not SALUTE_AUTH_KEY:
        logger.warning("[SaluteSpeech] No SALUTE_AUTH_KEY configured")
        return None
    
    if ACCESS_TOKEN and time.time() < TOKEN_EXPIRES - 60:
        return ACCESS_TOKEN
    
    try:
        auth_header = base64.b64encode(f"{SALUTE_AUTH_KEY}:".encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        payload = {
            "scope": "SALUTE_SPEECH_PERS",
            "RqUID": str(uuid.uuid4())
        }
        
        logger.info("[SaluteSpeech] Requesting token...")
        
        response = requests.post(
            f"{SALUTESPEECH_API_URL}/v2/oauth",
            headers=headers,
            data=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            ACCESS_TOKEN = data.get('access_token')
            expires_in = data.get('expires_in', 1800)
            TOKEN_EXPIRES = time.time() + expires_in
            
            logger.info("[SaluteSpeech] Token obtained successfully")
            return ACCESS_TOKEN
        else:
            logger.warning(f"[SaluteSpeech] Auth failed: {response.status_code} - {response.text[:100]}")
            return None
            
    except Exception as e:
        logger.warning(f"[SaluteSpeech] Auth error: {e}")
        return None

def generate_audio(script: str, output_path: str = "digest_audio.mp3") -> Optional[str]:
    """Генерирует аудио из текста сценария с SSML"""
    token = get_salutespeech_token()
    
    if not token:
        logger.warning("[SaluteSpeech] No token, cannot generate audio")
        return None
    
    word_count = len(script.split())
    if word_count > MAX_WORD_COUNT:
        logger.warning(f"Script too long ({word_count} words), truncating to {MAX_WORD_COUNT}")
        words = script.split()
        script = ' '.join(words[:MAX_WORD_COUNT])
    
    ssml_script = f"""<speak>
<voice name="{SALUTESPEECH_VOICE}" lang="ru">
{script}
</voice>
</speak>"""
    
    logger.info(f"[SaluteSpeech] Using voice: {SALUTESPEECH_VOICE}")
    logger.info(f"[SaluteSpeech] SSML prepared: yes (word count: {len(script.split())})")
    
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": ssml_script,
            "format": "mp3",
            "lang": "ru-RU"
        }
        
        logger.info("[SaluteSpeech] Generating audio...")
        
        response = requests.post(
            f"{SALUTESPEECH_API_URL}/v1/tts",
            headers=headers,
            json=payload,
            timeout=120
        )
        
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            logger.info(f"[SaluteSpeech] Audio saved to {output_path}")
            return output_path
        else:
            logger.warning(f"[SaluteSpeech] TTS failed: {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        logger.warning("[SaluteSpeech] TTS timeout")
    except Exception as e:
        logger.warning(f"[SaluteSpeech] TTS error: {e}")
    
    return None

def is_available() -> bool:
    """Проверяет, настроены ли credentials"""
    return bool(SALUTE_AUTH_KEY)
