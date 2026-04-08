import os
import logging
import requests
from typing import Optional
import time

logger = logging.getLogger(__name__)

SALUTESPEECH_API_URL = "https://salutespeech.com/api"

SALUTE_CLIENT_ID = os.getenv("SALUTESPEECH_CLIENT_ID")
SALUTE_CLIENT_SECRET = os.getenv("SALUTESPEECH_CLIENT_SECRET")
SALUTE_SPEAKER = os.getenv("SALUTESPEECH_SPEAKER", "Aidar")

_access_token = None
_token_expires = 0

def get_salutespeech_token() -> Optional[str]:
    global _access_token, _token_expires
    
    if not SALUTE_CLIENT_ID or not SALUTE_CLIENT_SECRET:
        logger.warning("[SaluteSpeech] No credentials configured")
        return None
    
    if _access_token and time.time() < _token_expires - 60:
        return _access_token
    
    try:
        response = requests.post(
            f"{SALUTESPEECH_API_URL}/v1/auth",
            json={
                "client_id": SALUTE_CLIENT_ID,
                "client_secret": SALUTE_CLIENT_SECRET
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            _access_token = data.get('access_token')
            expires_in = data.get('expires_in', 3600)
            _token_expires = time.time() + expires_in
            
            logger.info("[SaluteSpeech] Token obtained successfully")
            return _access_token
        else:
            logger.warning(f"[SaluteSpeech] Auth failed: {response.status_code}")
            return None
            
    except Exception as e:
        logger.warning(f"[SaluteSpeech] Auth error: {e}")
        return None

def generate_audio(script: str, output_path: str = "digest_audio.mp3") -> Optional[str]:
    """Генерирует аудио из текста сценария"""
    token = get_salutespeech_token()
    
    if not token:
        logger.warning("[SaluteSpeech] No token, cannot generate audio")
        return None
    
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": script,
            "speaker": SALUTE_SPEAKER,
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
        return None
    except Exception as e:
        logger.warning(f"[SaluteSpeech] TTS error: {e}")
        return None

def is_available() -> bool:
    """Проверяет, настроены ли credentials"""
    return bool(SALUTE_CLIENT_ID and SALUTE_CLIENT_SECRET)
