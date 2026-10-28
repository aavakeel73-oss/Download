#!/usr/bin/env python3
"""
StreamRip Video Processing Engine
Integrates yt-dlp, FFmpeg, and FFprobe for rock-solid video extraction,
stream merging (H.264 + AAC), and rigorous media validation.
Includes structured safe error logging and distinct HTTP status categorization.
"""

import os
import sys
import json
import subprocess
import shutil
import re
from datetime import datetime

FFMPEG_PATH = shutil.which('ffmpeg') or '/usr/bin/ffmpeg'
FFPROBE_PATH = shutil.which('ffprobe') or '/usr/bin/ffprobe'
YTDLP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'yt-dlp_bin'))


def safe_log(level: str, message: str, meta: dict = None):
    """
    Logs structured, sanitized diagnostics without leaking credentials or private tokens.
    """
    payload = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'level': level,
        'message': message,
    }
    if meta:
        # Sanitize sensitive keys
        clean_meta = {}
        for k, v in meta.items():
            if 'token' in k.lower() or 'cookie' in k.lower() or 'auth' in k.lower():
                clean_meta[k] = '[REDACTED]'
            else:
                clean_meta[k] = v
        payload['meta'] = clean_meta

    print(json.dumps(payload), file=sys.stderr)


def run_ffprobe_validation(file_path: str):
    """
    Inspects media file using FFprobe to verify presence of valid video and audio streams,
    detect actual resolution, and prevent empty or HTML error files from being served.
    """
    if not os.path.exists(file_path):
        return False, "फ़ाइल डिस्क पर मौजूद नहीं है।"

    file_size = os.path.getsize(file_path)
    if file_size < 1000:
        return False, "अमान्य फ़ाइल आकार (खाली या दूषित फ़ाइल)।"

    # Check for HTML error pages masquerading as media
    try:
        with open(file_path, 'rb') as f:
            header = f.read(256)
            if b'<html' in header.lower() or b'<!doctype html' in header.lower() or b'<error>' in header.lower():
                return False, "सर्वर ने मीडिया के स्थान पर HTML/XML त्रुटि पृष्ठ लौटाया।"
    except Exception:
        pass

    cmd = [
        FFPROBE_PATH,
        '-v', 'error',
        '-show_entries', 'stream=index,codec_type,codec_name,width,height,duration',
        '-show_entries', 'format=duration,size,format_name',
        '-of', 'json',
        file_path
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if proc.returncode != 0:
            return False, f"FFprobe सत्यापन विफल: {proc.stderr[:100]}"

        data = json.loads(proc.stdout)
        streams = data.get('streams', [])
        
        has_video = any(s.get('codec_type') == 'video' for s in streams)
        has_audio = any(s.get('codec_type') == 'audio' for s in streams)
        
        video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
        width = video_stream.get('width', 0) if video_stream else 0
        height = video_stream.get('height', 0) if video_stream else 0

        audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
        audio_codec = audio_stream.get('codec_name', 'none') if audio_stream else 'none'

        return True, {
            'has_video': has_video,
            'has_audio': has_audio,
            'width': width,
            'height': height,
            'audio_codec': audio_codec,
            'size_bytes': file_size,
            'duration': float(data.get('format', {}).get('duration') or 0)
        }
    except Exception as e:
        return False, f"सत्यापन के दौरान अपवाद: {str(e)}"


def analyze_video(url: str):
    """
    Analyzes video or Shorts URL with yt-dlp.
    Categorizes errors accurately into HTTP 403, 404, or 500 with distinct Hindi messages.
    """
    safe_log('INFO', 'Starting video analysis', {'url': url})

    cmd = [
        YTDLP_PATH,
        '--dump-json',
        '--no-warnings',
        '--socket-timeout', '15',
        '--extractor-args', 'youtube:player_client=visionos,mweb,android,ios',
        url
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    
    if proc.returncode != 0:
        err = (proc.stderr or '').lower()
        safe_log('WARN', 'yt-dlp extraction failed', {'stderr': proc.stderr[:200]})

        # Categorization for HTTP 403 (Forbidden, BotGuard, IP rate-limit, Login requirement)
        if 'confirm you’re not a bot' in err or 'sign in' in err or 'bot' in err:
            return {
                'success': False,
                'statusCode': 403,
                'error': 'YouTube HTTP 403 (पहुंच अस्वीकृत): Google Cloud सर्वर IP पर YouTube की बॉट सुरक्षा (BotGuard/PO-Token) सक्रिय है। YouTube ने डेटा-सेंटर IP से इस वीडियो/Shorts के सीधे डाउनलोड पर रोक लगाई है (Sign in to confirm you’re not a bot)। केवल अधिकृत सार्वजनिक वीडियो समर्थित हैं।'
            }
        elif 'private' in err or 'login' in err or 'permission' in err:
            return {
                'success': False,
                'statusCode': 403,
                'error': 'YouTube HTTP 403 (निजी सामग्री): यह वीडियो या Shorts निजी (Private) है, आयु-प्रतिबंधित है या इसके देखने के लिए लॉगिन अनिवार्य है।'
            }
        elif 'copyright' in err:
            return {
                'success': False,
                'statusCode': 403,
                'error': 'YouTube HTTP 403 (कॉपीराइट अवरोध): कॉपीराइट प्रतिबंधों और सामग्री स्वामी के निर्देशों के कारण यह वीडियो डाउनलोड के लिए उपलब्ध नहीं है।'
            }
        # Categorization for HTTP 404 (Not Found, Unavailable, Deleted)
        elif 'video is unavailable' in err or 'not found' in err or 'does not exist' in err or '404' in err or 'cannot parse data' in err:
            return {
                'success': False,
                'statusCode': 404,
                'error': 'YouTube HTTP 404 (वीडियो अनुपलब्ध): यह YouTube वीडियो या Shorts लिंक मौजूद नहीं है, हटा दिया गया है या URL अमान्य है।'
            }
        # Categorization for HTTP 500 (Internal server or processing failure)
        else:
            return {
                'success': False,
                'statusCode': 500,
                'error': f'सर्वर त्रुटि (HTTP 500): वीडियो पार्स करने में तकनीकी समस्या आई ({proc.stderr[:90] or "अज्ञात त्रुटि"})। कृपया कुछ समय बाद पुनः प्रयास करें।'
            }

    try:
        info = json.loads(proc.stdout)
        safe_log('INFO', 'yt-dlp extraction succeeded', {
            'title': info.get('title'),
            'id': info.get('id'),
            'formats_count': len(info.get('formats', []))
        })
        return {'success': True, 'info': info}
    except Exception as e:
        safe_log('ERROR', 'JSON parse failure', {'exception': str(e)})
        return {
            'success': False,
            'statusCode': 500,
            'error': f'सर्वर त्रुटि (HTTP 500): मेटाडेटा JSON पार्स करने में विफल ({str(e)})।'
        }


if __name__ == '__main__':
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == 'analyze' and len(sys.argv) > 2:
            res = analyze_video(sys.argv[2])
            print(json.dumps(res))
        elif mode == 'validate' and len(sys.argv) > 2:
            ok, details = run_ffprobe_validation(sys.argv[2])
            print(json.dumps({'valid': ok, 'details': details}))
