import os
import re
import time
import secrets
import tempfile
import threading
import subprocess
import shutil
import ipaddress
import socket
import importlib.util
from urllib.parse import urlparse
from flask import Flask, request, jsonify, render_template, send_file, abort
import yt_dlp

app = Flask(__name__)
OUT = tempfile.mkdtemp(prefix='video_out_')
JOBS = {}
LOCK = threading.Lock()
MAX_MB = int(os.getenv('MAX_MEDIA_MB', '150'))
MAX_DURATION = int(os.getenv('MAX_DURATION_SECONDS', '1200'))
HOSTS = (
    'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be',
    'www.youtu.be', 'facebook.com', 'www.facebook.com', 'm.facebook.com',
    'fb.watch', 'www.fb.watch', 'instagram.com', 'www.instagram.com'
)


def error(message, status=400):
    return jsonify(error=message), status


def check_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        parsed = urlparse(value)
        return (parsed.scheme == 'https' and parsed.hostname in HOSTS
                and not parsed.username and not parsed.password
                and parsed.port in (None, 443))
    except ValueError:
        return False


def public_dns(value):
    host = urlparse(value).hostname
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(
            ipaddress.ip_address(address[4][0]).is_global for address in addresses
        )
    except (socket.gaierror, ValueError):
        return False


def ydl_opts(extra=None):
    opts = {
        'quiet': False,
        'no_warnings': False,
        'verbose': False,
        'noplaylist': True,
        'socket_timeout': 18,
        'retries': 1,
        'fragment_retries': 1,
        'extractor_retries': 1,
        'skip_download': True,
        'cachedir': False,
        'ignoreerrors': False,
    }
    if extra:
        opts.update(extra)
    return opts


def acceptable_video_format(fmt):
    if not isinstance(fmt, dict) or fmt.get('vcodec') in (None, 'none'):
        return False
    if not fmt.get('format_id'):
        return False
    height = fmt.get('height')
    return height is None or (isinstance(height, (int, float)) and 144 <= height <= 1080)


def video_formats(info):
    result = []
    seen = set()
    for fmt in info.get('formats') or []:
        if not acceptable_video_format(fmt):
            continue
        fid = str(fmt['format_id'])
        if fid in seen:
            continue
        seen.add(fid)
        height = fmt.get('height')
        has_audio = fmt.get('acodec') not in (None, 'none')
        label = f'{int(height)}p' if height is not None else 'Auto Quality'
        result.append({
            'label': f"{label} · {'ऑडियो सहित' if has_audio else 'ऑडियो मर्ज होगा'} · {fmt.get('ext', 'video')}",
            'format_id': fid,
            'height': int(height) if height is not None else 0,
        })
    return sorted(result, key=lambda item: item['height'], reverse=True)[:18]


def prune():
    now = time.time()
    with LOCK:
        for job, (path, expiry) in list(JOBS.items()):
            if expiry < now:
                JOBS.pop(job, None)
                try:
                    os.unlink(path)
                except OSError:
                    pass


@app.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.get('/')
def home():
    return render_template('index.html')


@app.get('/health')
def health():
    deno_path = shutil.which('deno')
    deno_version = None
    if deno_path:
        try:
            result = subprocess.run(['deno', '--version'], capture_output=True,
                                    text=True, timeout=8)
            if result.returncode == 0:
                deno_version = result.stdout.splitlines()[0]
        except (OSError, subprocess.TimeoutExpired, IndexError):
            pass
    return jsonify(
        status='ok',
        backend='yt-dlp',
        yt_dlp_version=yt_dlp.version.__version__,
        deno_installed=bool(deno_path),
        deno_version=deno_version,
        ejs_installed=importlib.util.find_spec('yt_dlp_ejs') is not None,
        ffmpeg=bool(shutil.which('ffmpeg')),
        ffprobe=bool(shutil.which('ffprobe')),
    )


@app.post('/api/inspect')
def inspect():
    data = request.get_json(silent=True) or {}
    url = data.get('url', '')
    if not check_url(url) or not public_dns(url):
        return error('सही और समर्थित HTTPS वीडियो लिंक डालें।')
    try:
        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
        if not isinstance(info, dict):
            return error('वीडियो की जानकारी नहीं मिली।', 404)
        duration = info.get('duration')
        if duration and duration > MAX_DURATION:
            return error('वीडियो बहुत लंबा है; 20 मिनट तक का वीडियो चुनें।', 413)
        formats = video_formats(info)
        app.logger.info('Inspect platform=%s formats=%s accepted=%s',
                        info.get('extractor_key'), len(info.get('formats') or []), len(formats))
        if not formats:
            return error('इस वीडियो के डाउनलोड फॉर्मेट उपलब्ध नहीं हैं।', 404)
        return jsonify(
            title=str(info.get('title') or 'Video')[:160],
            thumbnail=info.get('thumbnail') or '',
            platform=info.get('extractor_key') or 'Video',
            videos=[{'index': i, 'label': fmt['label']} for i, fmt in enumerate(formats)],
            token=None,
            formats=[fmt['format_id'] for fmt in formats],
            source=url,
        )
    except Exception as exc:
        app.logger.warning('Inspect error: %s', str(exc)[:400])
        return error('वीडियो जानकारी नहीं मिल सकी। वीडियो निजी, प्रतिबंधित या स्रोत द्वारा ब्लॉक हो सकता है।', 422)


@app.post('/api/merge')
def merge():
    if not shutil.which('ffmpeg'):
        return error('FFmpeg उपलब्ध नहीं है।', 503)
    data = request.get_json(silent=True) or {}
    url = data.get('source', '')
    fmt = data.get('format_id', '')
    if (not check_url(url) or not public_dns(url)
            or not isinstance(fmt, str)
            or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', fmt)):
        return error('अमान्य चयन।')
    prune()
    job = secrets.token_urlsafe(18)
    folder = tempfile.mkdtemp(prefix='download_')
    dest = os.path.join(OUT, job + '.mp4')
    try:
        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
        if not isinstance(info, dict):
            return error('वीडियो की जानकारी नहीं मिली।', 404)
        if info.get('duration') and info['duration'] > MAX_DURATION:
            return error('वीडियो बहुत लंबा है।', 413)
        valid = {item['format_id'] for item in video_formats(info)}
        if fmt not in valid:
            return error('वीडियो क्वालिटी बदल गई है, दोबारा खोजें।')
        template = os.path.join(folder, 'source.%(ext)s')
        opts = ydl_opts({
            'skip_download': False,
            'format': fmt + '+bestaudio/best',
            'outtmpl': template,
            'merge_output_format': 'mp4',
            'max_filesize': MAX_MB * 1024 * 1024,
            'overwrites': True,
            'nopart': True,
        })
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        candidates = [
            os.path.join(folder, name) for name in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, name))
            and not name.endswith(('.part', '.ytdl'))
        ]
        if not candidates:
            raise ValueError('कोई वीडियो फाइल नहीं बनी')
        source = max(candidates, key=os.path.getsize)
        if os.path.getsize(source) > MAX_MB * 1024 * 1024:
            raise ValueError('वीडियो निर्धारित साइज से बड़ा है')
        result = subprocess.run([
            'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
            '-i', source, '-map', '0:v:0', '-map', '0:a:0?',
            '-c:v', 'copy', '-c:a', 'aac', '-movflags', '+faststart', dest,
        ], capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise ValueError('MP4 प्रोसेसिंग असफल: ' + result.stderr[:200])
        if os.path.getsize(dest) > MAX_MB * 1024 * 1024:
            raise ValueError('MP4 निर्धारित साइज से बड़ा है')
        with LOCK:
            JOBS[job] = (dest, time.time() + 600)
        return jsonify(success=True, download='/api/download/' + job)
    except Exception as exc:
        app.logger.warning('Download error: %s', str(exc)[:400])
        return error('डाउनलोड असफल। स्रोत ने सर्वर अनुरोध रोका हो सकता है, या वीडियो बहुत बड़ा है।', 422)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
        with LOCK:
            saved = job in JOBS
        if not saved:
            try:
                os.unlink(dest)
            except OSError:
                pass


@app.get('/api/download/<job>')
def download(job):
    prune()
    with LOCK:
        item = JOBS.get(job)
    if not item or item[1] < time.time() or not os.path.isfile(item[0]):
        abort(404)
    return send_file(item[0], as_attachment=True,
                     download_name='video.mp4', mimetype='video/mp4')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '10000')))
    
