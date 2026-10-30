#!/usr/bin/env python3
"""StreamRip analysis helpers and strict media validation."""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit
import yt_dlp

YOUTUBE_HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'www.youtu.be'}


def safe_log(level, message, meta=None):
    clean = {}
    for key, value in (meta or {}).items():
        if any(x in key.lower() for x in ('token', 'cookie', 'auth', 'url', 'password', 'secret', 'stderr')):
            clean[key] = '[REDACTED]'
        else:
            clean[key] = str(value)[:120]
    print(json.dumps({'timestamp': datetime.now(timezone.utc).isoformat(), 'level': level,
                      'message': message, 'meta': clean}, ensure_ascii=False), file=sys.stderr)


def youtube_url(url):
    try:
        p = urlsplit(url)
        return (isinstance(url, str) and len(url) <= 2048 and p.scheme == 'https'
                and p.hostname in YOUTUBE_HOSTS and not p.username and not p.password
                and p.port in (None, 443))
    except (ValueError, TypeError):
        return False


def error_result(error):
    err = str(error).lower().replace('’', "'")
    if any(x in err for x in ("confirm you're not a bot", 'sign in to confirm', 'captcha', 'unusual traffic')):
        code, status, message = 'YOUTUBE_VERIFICATION_REQUIRED', 403, 'YouTube इस सर्वर से अतिरिक्त सत्यापन मांग रहा है। इस सर्वर से फिलहाल वीडियो उपलब्ध नहीं है।'
    elif any(x in err for x in ('private video', 'members-only', 'age-restricted', 'login required')):
        code, status, message = 'ACCESS_RESTRICTED', 403, 'इस वीडियो के लिए अधिकृत पहुंच आवश्यक है।'
    elif any(x in err for x in ('video unavailable', 'video is unavailable', 'not found', '404', 'has been removed')):
        code, status, message = 'VIDEO_UNAVAILABLE', 404, 'वीडियो उपलब्ध नहीं है या लिंक गलत है।'
    elif '429' in err or 'too many requests' in err:
        code, status, message = 'RATE_LIMITED', 429, 'बहुत अधिक अनुरोध हुए हैं। कुछ समय बाद प्रयास करें।'
    else:
        code, status, message = 'EXTRACTION_FAILED', 502, 'वीडियो विश्लेषण विफल हुआ। सर्वर लॉग जाँचें।'
    return {'success': False, 'statusCode': status, 'errorCode': code, 'error': message}


def analyze_video(url):
    if not youtube_url(url):
        return {'success': False, 'statusCode': 400, 'errorCode': 'INVALID_URL',
                'error': 'मान्य HTTPS YouTube वीडियो या Shorts लिंक दें।'}
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'noplaylist': True,
                               'skip_download': True, 'socket_timeout': 15, 'retries': 1}) as ydl:
            info = ydl.extract_info(url, download=False)
        if not isinstance(info, dict):
            return error_result('metadata missing')
        return {'success': True, 'info': info}
    except yt_dlp.utils.DownloadError as exc:
        result = error_result(exc)
        safe_log('WARN', 'YouTube analysis failed', {'errorCode': result['errorCode']})
        return result
    except Exception as exc:
        safe_log('ERROR', 'YouTube analysis exception', {'exception_type': type(exc).__name__})
        return {'success': False, 'statusCode': 502, 'errorCode': 'ANALYSIS_FAILED',
                'error': 'वीडियो विश्लेषण में तकनीकी समस्या आई।'}


def run_ffprobe_validation(file_path):
    if not os.path.isfile(file_path) or os.path.getsize(file_path) < 1000:
        return False, 'फ़ाइल मौजूद नहीं है या अधूरी है।'
    try:
        with open(file_path, 'rb') as stream:
            header = stream.read(512).lstrip().lower()
        if header.startswith((b'<html', b'<!doctype html', b'<?xml', b'{"error"')):
            return False, 'मीडिया के बजाय त्रुटि पृष्ठ मिला।'
        proc = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                               'stream=codec_type,codec_name,width,height:format=duration,format_name',
                               '-of', 'json', file_path], capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            return False, 'FFprobe मीडिया नहीं पढ़ पाया।'
        data = json.loads(proc.stdout)
        streams = data.get('streams') or []
        video = next((s for s in streams if s.get('codec_type') == 'video'), None)
        audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
        if not video and not audio:
            return False, 'कोई वीडियो या ऑडियो स्ट्रीम नहीं मिली।'
        return True, {'has_video': bool(video), 'has_audio': bool(audio),
                      'width': (video or {}).get('width', 0), 'height': (video or {}).get('height', 0),
                      'audio_codec': (audio or {}).get('codec_name', 'none'),
                      'size_bytes': os.path.getsize(file_path),
                      'duration': float((data.get('format') or {}).get('duration') or 0)}
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        safe_log('ERROR', 'Media validation failed', {'exception_type': type(exc).__name__})
        return False, 'मीडिया सत्यापन पूरा नहीं हुआ।'


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] not in ('analyze', 'validate'):
        sys.exit('Usage: video_processor.py analyze URL | validate FILE')
    if sys.argv[1] == 'analyze':
        print(json.dumps(analyze_video(sys.argv[2]), ensure_ascii=False))
    else:
        ok, details = run_ffprobe_validation(sys.argv[2])
        print(json.dumps({'valid': ok, 'details': details}, ensure_ascii=False))
