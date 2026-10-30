#!/usr/bin/env python3
"""StreamRip video analysis and media validation.
Preserves analyze_video(url) and run_ffprobe_validation(path) interfaces.
No cookies, credentials, or bypass of platform verification are used.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit

FFPROBE_PATH = shutil.which('ffprobe') or '/usr/bin/ffprobe'
YTDLP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'yt-dlp')


def safe_log(level, message, meta=None):
    clean = {}
    for key, value in (meta or {}).items():
        if any(secret in key.lower() for secret in ('token', 'cookie', 'auth', 'url', 'password', 'secret', 'stderr')):
            clean[key] = '[REDACTED]'
        else:
            clean[key] = str(value)[:160]
    print(json.dumps({'timestamp': datetime.now(timezone.utc).isoformat(),
                      'level': level, 'message': message, 'meta': clean}, ensure_ascii=False), file=sys.stderr)


def run_ffprobe_validation(file_path):
    if not os.path.isfile(file_path):
        return False, 'फ़ाइल मौजूद नहीं है।'
    size = os.path.getsize(file_path)
    if size < 1000:
        return False, 'फ़ाइल खाली या अधूरी है।'
    try:
        with open(file_path, 'rb') as f:
            header = f.read(512).lstrip().lower()
        if header.startswith((b'<html', b'<!doctype html', b'<?xml', b'{"error"')):
            return False, 'मीडिया के बजाय त्रुटि पृष्ठ मिला।'
        proc = subprocess.run([FFPROBE_PATH, '-v', 'error', '-show_entries',
                               'stream=codec_type,codec_name,width,height:format=duration,format_name',
                               '-of', 'json', file_path], capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            return False, 'FFprobe मीडिया नहीं पढ़ पाया।'
        data = json.loads(proc.stdout)
        streams = data.get('streams') or []
        video = next((s for s in streams if s.get('codec_type') == 'video'), None)
        audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
        if not video and not audio:
            return False, 'मान्य वीडियो या ऑडियो स्ट्रीम नहीं मिली।'
        return True, {'has_video': bool(video), 'has_audio': bool(audio),
                      'width': (video or {}).get('width', 0),
                      'height': (video or {}).get('height', 0),
                      'audio_codec': (audio or {}).get('codec_name', 'none'),
                      'size_bytes': size,
                      'duration': float((data.get('format') or {}).get('duration') or 0)}
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        safe_log('ERROR', 'Media validation failed', {'exception_type': type(exc).__name__})
        return False, 'मीडिया सत्यापन पूरा नहीं हो सका।'


def _is_youtube_url(url):
    try:
        p = urlsplit(url)
        host = (p.hostname or '').lower()
        return (p.scheme == 'https' and not p.username and not p.password and
                host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'www.youtu.be', 'youtube-nocookie.com', 'www.youtube-nocookie.com') and
                len(url) <= 2048)
    except (TypeError, ValueError):
        return False


def _error_result(stderr):
    err = stderr.lower().replace('’', "'")
    if any(s in err for s in ("confirm you're not a bot", 'sign in to confirm', 'unusual traffic', 'captcha')):
        return {'success': False, 'statusCode': 403, 'errorCode': 'YOUTUBE_VERIFICATION_REQUIRED',
                'error': 'YouTube ने सर्वर से अतिरिक्त सत्यापन मांगा है। इस सर्वर से अभी वीडियो विश्लेषण उपलब्ध नहीं है। कृपया वीडियो YouTube पर खोलें या अनुमति प्राप्त डाउनलोड का तरीका इस्तेमाल करें।'}
    if any(s in err for s in ('private video', 'members-only', 'age-restricted', 'login required')):
        return {'success': False, 'statusCode': 403, 'errorCode': 'ACCESS_RESTRICTED',
                'error': 'इस वीडियो के लिए अधिकृत पहुंच आवश्यक है।'}
    if any(s in err for s in ('video unavailable', 'video is unavailable', 'not found', '404', 'has been removed')):
        return {'success': False, 'statusCode': 404, 'errorCode': 'VIDEO_UNAVAILABLE',
                'error': 'वीडियो उपलब्ध नहीं है या लिंक गलत है।'}
    if '429' in err or 'too many requests' in err:
        return {'success': False, 'statusCode': 429, 'errorCode': 'RATE_LIMITED',
                'error': 'YouTube ने अनुरोधों की दर सीमित की है। बाद में पुनः प्रयास करें।'}
    return {'success': False, 'statusCode': 502, 'errorCode': 'EXTRACTION_FAILED',
            'error': 'YouTube वीडियो का विश्लेषण नहीं हो सका। सर्वर लॉग देखें।'}


def analyze_video(url):
    if not isinstance(url, str) or not _is_youtube_url(url):
        return {'success': False, 'statusCode': 400, 'errorCode': 'INVALID_URL',
                'error': 'केवल मान्य HTTPS YouTube वीडियो या Shorts लिंक डालें।'}
    # Prefer the installed package; fall back to the repository binary.
    if shutil.which('python3'):
        command = [sys.executable, '-m', 'yt_dlp']
    elif os.path.isfile(YTDLP_PATH):
        command = [YTDLP_PATH]
    else:
        return {'success': False, 'statusCode': 503, 'errorCode': 'YTDLP_MISSING',
                'error': 'सर्वर पर yt-dlp उपलब्ध नहीं है।'}
    command += ['--dump-single-json', '--no-playlist', '--no-warnings',
                '--no-call-home', '--socket-timeout', '15', '--retries', '1', url]
    safe_log('INFO', 'Starting YouTube analysis', {'host': urlsplit(url).hostname})
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=55)
    except subprocess.TimeoutExpired:
        return {'success': False, 'statusCode': 504, 'errorCode': 'TIMEOUT',
                'error': 'YouTube सर्वर ने समय पर उत्तर नहीं दिया।'}
    except OSError as exc:
        safe_log('ERROR', 'yt-dlp execution failed', {'exception_type': type(exc).__name__})
        return {'success': False, 'statusCode': 503, 'errorCode': 'YTDLP_UNAVAILABLE',
                'error': 'वीडियो विश्लेषण सेवा उपलब्ध नहीं है।'}
    if proc.returncode != 0:
        result = _error_result(proc.stderr or '')
        safe_log('WARN', 'YouTube extraction failed', {'errorCode': result['errorCode']})
        return result
    try:
        info = json.loads(proc.stdout)
        if not isinstance(info, dict):
            raise ValueError('Unexpected metadata')
        safe_log('INFO', 'YouTube analysis succeeded', {'video_id': info.get('id'), 'formats_count': len(info.get('formats') or [])})
        return {'success': True, 'info': info}
    except (ValueError, TypeError):
        return {'success': False, 'statusCode': 502, 'errorCode': 'INVALID_METADATA',
                'error': 'वीडियो मेटाडेटा पढ़ा नहीं जा सका।'}


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] not in ('analyze', 'validate'):
        print(json.dumps({'error': 'Usage: video_processor.py analyze URL | validate FILE'}))
        sys.exit(2)
    if sys.argv[1] == 'analyze':
        print(json.dumps(analyze_video(sys.argv[2]), ensure_ascii=False))
    else:
        valid, details = run_ffprobe_validation(sys.argv[2])
        print(json.dumps({'valid': valid, 'details': details}, ensure_ascii=False))
      
