#!/usr/bin/env python3
"""StreamRip media analysis and FFprobe validation.

CLI contract:
  python video_processor.py analyze URL
  python video_processor.py validate FILE

Outputs one JSON object on stdout; diagnostics go to stderr.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

FFMPEG_PATH = shutil.which('ffmpeg') or '/usr/bin/ffmpeg'
FFPROBE_PATH = shutil.which('ffprobe') or '/usr/bin/ffprobe'
LOCAL_YTDLP = Path(__file__).resolve().parent / 'yt-dlp'


def ytdlp_command():
    if LOCAL_YTDLP.is_file() and os.access(LOCAL_YTDLP, os.X_OK):
        return [str(LOCAL_YTDLP)]
    binary = shutil.which('yt-dlp')
    if binary:
        return [binary]
    # Allow a Python package installation when no executable is available.
    try:
        import yt_dlp  # noqa: F401
        return [sys.executable, '-m', 'yt_dlp']
    except ImportError:
        return None


def safe_log(level, message, meta=None):
    # Never print raw URLs, subprocess stderr or credentials to logs.
    record = {'timestamp': datetime.now(timezone.utc).isoformat(),
              'level': level, 'message': message}
    if meta:
        record['meta'] = {str(k): ('[REDACTED]' if any(s in str(k).lower() for s in
            ('token', 'cookie', 'auth', 'url', 'password', 'secret', 'stderr')) else v)
            for k, v in meta.items()}
    print(json.dumps(record, ensure_ascii=False, default=str), file=sys.stderr, flush=True)


def valid_source(url):
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or '').lower().rstrip('.')
        allowed = ('youtube.com', 'youtu.be', 'youtube-nocookie.com',
                   'facebook.com', 'fb.watch')
        return (parsed.scheme in ('https', 'http') and not parsed.username
                and not parsed.password and parsed.port in (None, 80, 443)
                and any(host == domain or host.endswith('.' + domain) for domain in allowed))
    except ValueError:
        return False


def run_ffprobe_validation(file_path):
    try:
        path = Path(file_path)
        if not path.is_file() or path.stat().st_size < 1000:
            return False, 'फ़ाइल मौजूद नहीं है या उसका आकार अमान्य है।'
        with path.open('rb') as f:
            head = f.read(512).lstrip().lower()
        if any(tag in head for tag in (b'<html', b'<!doctype html', b'<error', b'<?xml')):
            return False, 'मीडिया के बजाय HTML/XML त्रुटि पृष्ठ मिला।'
        cmd = [FFPROBE_PATH, '-v', 'error', '-show_entries',
               'stream=index,codec_type,codec_name,width,height,duration:format=duration,size,format_name',
               '-of', 'json', str(path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if result.returncode:
            safe_log('WARN', 'FFprobe failed', {'exit_code': result.returncode})
            return False, 'FFprobe मीडिया फ़ाइल नहीं पढ़ सका।'
        data = json.loads(result.stdout)
        streams = data.get('streams') or []
        video = next((s for s in streams if s.get('codec_type') == 'video'), None)
        audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
        if not video and not audio:
            return False, 'फ़ाइल में कोई वैध वीडियो या ऑडियो स्ट्रीम नहीं है।'
        duration = float((data.get('format') or {}).get('duration') or 0)
        return True, {
            'has_video': bool(video), 'has_audio': bool(audio),
            'width': int((video or {}).get('width') or 0),
            'height': int((video or {}).get('height') or 0),
            'audio_codec': (audio or {}).get('codec_name', 'none'),
            'size_bytes': path.stat().st_size,
            'duration': duration,
        }
    except subprocess.TimeoutExpired:
        return False, 'FFprobe की समय सीमा समाप्त हो गई।'
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        safe_log('ERROR', 'Validation failed', {'exception_type': type(exc).__name__})
        return False, 'मीडिया सत्यापन में तकनीकी समस्या आई।'


def classify_error(stderr):
    err = stderr.lower().replace('’', "'")
    if 'confirm you\'re not a bot' in err or 'confirm you are not a bot' in err:
        return 403, ('YouTube अतिरिक्त Bot Verification मांग रहा है। '
                     'यह सर्वर या नेटवर्क आधारित प्रतिबंध हो सकता है; केवल कोड अपडेट से समाधान की गारंटी नहीं है।')
    if any(x in err for x in ('private video', 'video is private', 'login required',
                              'sign in to confirm your age', 'age-restricted')):
        return 403, 'यह वीडियो निजी या आयु-प्रतिबंधित है और अधिकृत लॉगिन की जरूरत है।'
    if any(x in err for x in ('video unavailable', 'video is unavailable', 'not found',
                              'does not exist', 'http error 404')):
        return 404, 'वीडियो उपलब्ध नहीं है या लिंक अमान्य है।'
    if 'http error 429' in err or 'too many requests' in err:
        return 429, 'स्रोत ने बहुत अधिक अनुरोधों के कारण अस्थायी सीमा लगाई है।'
    if 'http error 403' in err or 'forbidden' in err:
        return 403, 'स्रोत सर्वर ने इस अनुरोध को अस्वीकार किया।'
    return 502, 'स्रोत से वीडियो जानकारी प्राप्त नहीं हो सकी।'


def analyze_video(url):
    if not isinstance(url, str) or len(url) > 2048 or not valid_source(url):
        return {'success': False, 'statusCode': 400, 'error': 'केवल मान्य YouTube/Facebook लिंक दें।'}
    executable = ytdlp_command()
    if not executable:
        safe_log('ERROR', 'yt-dlp is not installed')
        return {'success': False, 'statusCode': 500, 'error': 'सर्वर पर yt-dlp उपलब्ध नहीं है।'}
    safe_log('INFO', 'Starting media analysis', {'source': urlparse(url).hostname})
    cmd = executable + ['--dump-single-json', '--no-playlist', '--no-warnings',
                        '--no-progress', '--socket-timeout', '15', '--retries', '1',
                        '--skip-download', '--', url]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=65,
                              stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        safe_log('WARN', 'Analysis timed out')
        return {'success': False, 'statusCode': 504, 'error': 'वीडियो विश्लेषण की समय सीमा समाप्त हो गई।'}
    except OSError as exc:
        safe_log('ERROR', 'Could not execute yt-dlp', {'exception_type': type(exc).__name__})
        return {'success': False, 'statusCode': 500, 'error': 'yt-dlp चलाने में सर्वर त्रुटि हुई।'}
    if proc.returncode != 0:
        code, message = classify_error(proc.stderr or '')
        safe_log('WARN', 'Extraction failed', {'status_code': code, 'exit_code': proc.returncode})
        return {'success': False, 'statusCode': code, 'error': message}
    try:
        info = json.loads(proc.stdout)
        if not isinstance(info, dict):
            raise ValueError('metadata is not an object')
        safe_log('INFO', 'Analysis succeeded', {'id': info.get('id'),
                 'formats_count': len(info.get('formats') or [])})
        return {'success': True, 'info': info}
    except (ValueError, json.JSONDecodeError) as exc:
        safe_log('ERROR', 'Invalid metadata', {'exception_type': type(exc).__name__})
        return {'success': False, 'statusCode': 502, 'error': 'स्रोत से अमान्य वीडियो जानकारी मिली।'}


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ('analyze', 'validate'):
        print(json.dumps({'success': False, 'error': 'Usage: analyze URL | validate FILE'}, ensure_ascii=False))
        return 2
    if sys.argv[1] == 'analyze':
        result = analyze_video(sys.argv[2])
    else:
        ok, details = run_ffprobe_validation(sys.argv[2])
        result = {'valid': ok, 'details': details}
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
    
