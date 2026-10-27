import os
import re
import time
import secrets
import tempfile
import threading
import subprocess
import shutil
from urllib.parse import urlparse

import yt_dlp
from flask import Flask, request, jsonify, render_template, send_file, abort

app = Flask(__name__)
OUT = tempfile.mkdtemp(prefix='youtube_out_')
JOBS = {}
LOCK = threading.Lock()
MAX_MB = int(os.getenv('MAX_MEDIA_MB', '150'))
MAX_DURATION = int(os.getenv('MAX_DURATION_SECONDS', '1200'))
HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'www.youtu.be', 'music.youtube.com', 'www.youtube-nocookie.com'}


def error(message, status=400):
    return jsonify(error=message), status


def check_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        u = urlparse(value)
        if u.scheme != 'https' or u.hostname not in HOSTS or u.username or u.password or u.port not in (None, 443):
            return False
        if u.hostname in ('youtu.be', 'www.youtu.be'):
            return bool(re.fullmatch(r'/[A-Za-z0-9_-]{11}/?', u.path))
        return u.path in ('/watch', '/live') or bool(re.fullmatch(r'/(shorts|live|embed)/[A-Za-z0-9_-]{11}/?', u.path))
    except ValueError:
        return False


def opts(extra=None):
    settings = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'socket_timeout': 20,
        'retries': 2,
        'fragment_retries': 2,
        'extractor_retries': 2,
        'cachedir': False,
        'ignoreerrors': False,
    }
    if extra:
        settings.update(extra)
    return settings


def acceptable(fmt):
    if not isinstance(fmt, dict) or fmt.get('vcodec') in (None, 'none') or not fmt.get('format_id'):
        return False
    h = fmt.get('height')
    return h is None or (isinstance(h, (int, float)) and 144 <= h <= 1080)


def available_formats(info):
    result = []
    seen = set()
    for f in info.get('formats') or []:
        if not acceptable(f):
            continue
        fid = str(f['format_id'])
        if fid in seen:
            continue
        seen.add(fid)
        h = f.get('height')
        quality = f'{int(h)}p' if isinstance(h, (int, float)) else 'ऑटो'
        audio = 'ऑडियो सहित' if f.get('acodec') not in (None, 'none') else 'ऑडियो मर्ज होगा'
        result.append({'format_id': fid, 'label': f'{quality} · {audio} · {f.get("ext", "video")}', 'height': h or 0})
    return sorted(result, key=lambda x: x['height'], reverse=True)[:18]


def prune():
    now = time.time()
    with LOCK:
        for key, (path, expiry) in list(JOBS.items()):
            if expiry < now:
                JOBS.pop(key, None)
                try:
                    os.unlink(path)
                except OSError:
                    pass


@app.after_request
def headers(resp):
    resp.headers['Cache-Control'] = 'no-store'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


@app.get('/')
def home():
    return render_template('index.html')


@app.get('/health')
def health():
    return jsonify(status='ok', platform='YouTube', yt_dlp_version=yt_dlp.version.__version__, ffmpeg=bool(shutil.which('ffmpeg')))


@app.post('/api/inspect')
def inspect():
    url = (request.get_json(silent=True) or {}).get('url', '')
    if not check_url(url):
        return error('केवल सही YouTube या YouTube Shorts HTTPS लिंक डालें।')
    try:
        with yt_dlp.YoutubeDL(opts()) as ydl:
            info = ydl.extract_info(url, download=False)
        if not isinstance(info, dict):
            return error('वीडियो की जानकारी नहीं मिली।', 404)
        if info.get('duration') and info['duration'] > MAX_DURATION:
            return error('20 मिनट तक का वीडियो चुनें।', 413)
        formats = available_formats(info)
        if not formats:
            return error('इस YouTube वीडियो के डाउनलोड फॉर्मेट उपलब्ध नहीं हैं।', 404)
        return jsonify(title=str(info.get('title') or 'YouTube Video')[:160], thumbnail=info.get('thumbnail') or '', videos=[{'index': i, 'label': f['label'], 'format_id': f['format_id']} for i, f in enumerate(formats)], source=url)
    except Exception as exc:
        app.logger.warning('YouTube inspect error: %s', str(exc)[:400])
        return error('YouTube से जानकारी नहीं मिली। वीडियो प्रतिबंधित हो सकता है या सर्वर अनुरोध ब्लॉक हुआ है।', 422)


@app.post('/api/merge')
def merge():
    if not shutil.which('ffmpeg'):
        return error('FFmpeg सर्वर पर उपलब्ध नहीं है।', 503)
    data = request.get_json(silent=True) or {}
    url = data.get('source', '')
    fmt = data.get('format_id', '')
    if not check_url(url) or not isinstance(fmt, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', fmt):
        return error('अमान्य YouTube लिंक या क्वालिटी।')
    prune()
    folder = tempfile.mkdtemp(prefix='yt_download_')
    try:
        with yt_dlp.YoutubeDL(opts()) as ydl:
            info = ydl.extract_info(url, download=False)
        if not isinstance(info, dict):
            return error('वीडियो उपलब्ध नहीं है।', 404)
        if info.get('duration') and info['duration'] > MAX_DURATION:
            return error('वीडियो बहुत लंबा है।', 413)
        valid = {f['format_id'] for f in available_formats(info)}
        if fmt not in valid:
            return error('क्वालिटी बदल गई है। वीडियो दोबारा खोजें।', 400)
        options = opts({
            'format': f'{fmt}+bestaudio/best',
            'outtmpl': os.path.join(folder, 'source.%(ext)s'),
            'merge_output_format': 'mp4',
            'max_filesize': MAX_MB * 1024 * 1024,
            'nopart': True,
        })
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])
        candidates = [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)) and not f.endswith(('.part', '.ytdl'))]
        if not candidates:
            raise ValueError('No video file')
        source = max(candidates, key=os.path.getsize)
        if os.path.getsize(source) > MAX_MB * 1024 * 1024:
            return error('वीडियो 150 MB सीमा से बड़ा है।', 413)
        job = secrets.token_urlsafe(18)
        dest = os.path.join(OUT, job + '.mp4')
        result = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-i', source, '-map', '0:v:0', '-map', '0:a:0?', '-c:v', 'copy', '-c:a', 'aac', '-movflags', '+faststart', dest], capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            app.logger.warning('FFmpeg error: %s', result.stderr[:350])
            raise ValueError('FFmpeg conversion failed')
        if os.path.getsize(dest) > MAX_MB * 1024 * 1024:
            os.unlink(dest)
            return error('तैयार MP4 आकार सीमा से बड़ा है।', 413)
        with LOCK:
            JOBS[job] = (dest, time.time() + 600)
        return jsonify(success=True, download='/api/download/' + job)
    except Exception as exc:
        app.logger.warning('YouTube download error: %s', str(exc)[:400])
        return error('डाउनलोड असफल। YouTube ने सर्वर को रोका हो सकता है।', 422)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


@app.get('/api/download/<job>')
def download(job):
    prune()
    with LOCK:
        item = JOBS.get(job)
    if not item or item[1] < time.time() or not os.path.isfile(item[0]):
        abort(404)
    return send_file(item[0], as_attachment=True, download_name='youtube-video.mp4', mimetype='video/mp4')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '10000')))
