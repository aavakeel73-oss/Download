import os, re, time, json, hmac, hashlib, base64, tempfile, subprocess, secrets, threading, shutil, ipaddress, socket, logging
from urllib.parse import urlparse, urljoin, parse_qs
import requests
from flask import Flask, request, jsonify, send_file, render_template, abort

app = Flask(__name__)
API_HOST = 'social-media-video-downloader.p.rapidapi.com'
API_KEY = os.getenv('RAPIDAPI_KEY', '')
SIGN_KEY = os.getenv('SIGNING_SECRET', '')
MAX_BYTES = int(os.getenv('MAX_MEDIA_MB', '75')) * 1024 * 1024
OUT_DIR = tempfile.mkdtemp(prefix='social_output_')
JOBS = {}
LOCK = threading.Lock()
MAX_REDIRECTS = 10
MEDIA_HOSTS = ('googlevideo.com', 'fbcdn.net', 'fbsbx.com', 'cdninstagram.com', 'googleusercontent.com', 'smvd.xyz')
SOURCE_HOSTS = ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be', 'www.youtu.be', 'facebook.com', 'www.facebook.com', 'm.facebook.com', 'web.facebook.com', 'fb.watch', 'www.fb.watch')

@app.after_request
def headers(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

def fail(message, status=400):
    return jsonify(error=message), status

def allowed_host(host, hosts):
    return any(host == suffix or host.endswith('.' + suffix) for suffix in hosts)

def safe_url(raw, source=False):
    try:
        u = urlparse(raw)
        if u.scheme != 'https' or not u.hostname or u.username or u.password or u.port not in (None, 443):
            return False
        host = u.hostname.lower().rstrip('.')
        if source:
            return host in SOURCE_HOSTS
        return allowed_host(host, MEDIA_HOSTS)
    except (ValueError, TypeError):
        return False

def validate_dns(url):
    """Reject private/loopback DNS answers. DNS rebinding needs network-level egress rules too."""
    host = urlparse(url).hostname
    try:
        results = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not results:
            raise ValueError('Media host DNS lookup failed')
        for info in results:
            ip = ipaddress.ip_address(info[4][0])
            if not ip.is_global:
                raise ValueError('Media host resolves to a non-public IP')
    except socket.gaierror as exc:
        raise ValueError('Media host DNS lookup failed') from exc

def youtube_id(url):
    p = urlparse(url)
    host = (p.hostname or '').lower()
    if host in ('youtu.be', 'www.youtu.be'):
        vid = p.path.strip('/').split('/')[0]
    elif re.match(r'^/(shorts|live|embed)/', p.path):
        vid = p.path.split('/')[2]
    else:
        vid = parse_qs(p.query).get('v', [''])[0]
    return vid if re.fullmatch(r'[A-Za-z0-9_-]{11}', vid) else None

def sign(payload):
    raw = json.dumps(payload, separators=(',', ':')).encode()
    sig = hmac.new(SIGN_KEY.encode(), raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw + sig).decode().rstrip('=')

def unsign(token):
    if not token or len(token) > 150000:
        raise ValueError('Invalid token')
    data = base64.urlsafe_b64decode(token + '=' * (-len(token) % 4))
    if len(data) < 33:
        raise ValueError('Invalid token')
    raw, sig = data[:-32], data[-32:]
    expected = hmac.new(SIGN_KEY.encode(), raw, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, sig):
        raise ValueError('Invalid token signature')
    payload = json.loads(raw)
    if payload['exp'] < time.time():
        raise ValueError('Links expired; search again')
    return payload

def clean_items(data, kind):
    items = []
    for entry in data.get('contents', []) or []:
        if not isinstance(entry, dict):
            continue
        for item in entry.get(kind, []) or []:
            if not isinstance(item, dict):
                continue
            url = item.get('url')
            if isinstance(url, str) and safe_url(url):
                items.append({'url': url, 'label': str(item.get('label') or 'Unknown')[:70]})
    return items[:30]

@app.get('/')
def home():
    return render_template('index.html')

@app.get('/health')
def health():
    return jsonify(status='ok', ffmpeg=bool(shutil.which('ffmpeg')), ffprobe=bool(shutil.which('ffprobe')), configured=bool(API_KEY and len(SIGN_KEY) >= 24))

@app.post('/api/inspect')
def inspect():
    if not API_KEY or len(SIGN_KEY) < 24:
        return fail('Configure RAPIDAPI_KEY and SIGNING_SECRET (24+ characters) in Render', 503)
    source = (request.get_json(silent=True) or {}).get('url', '')
    if not isinstance(source, str) or len(source) > 2500 or not safe_url(source, True):
        return fail('Enter a supported YouTube or Facebook HTTPS link')
    host = urlparse(source).hostname.lower()
    is_youtube = host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be', 'www.youtu.be')
    if is_youtube:
        vid = youtube_id(source)
        if not vid:
            return fail('Invalid YouTube video ID')
        path = '/youtube/v3/video/details'
        params = {'videoId': vid, 'urlAccess': 'normal', 'getTranscript': 'false'}
    else:
        path = '/facebook/v3/post/details'
        params = {'url': source}
    try:
        r = requests.get('https://' + API_HOST + path, params=params,
                         headers={'x-rapidapi-key': API_KEY, 'x-rapidapi-host': API_HOST}, timeout=(10, 35))
        if not r.ok:
            return fail('RapidAPI returned HTTP ' + str(r.status_code), 502)
        data = r.json()
    except (requests.RequestException, ValueError):
        return fail('RapidAPI connection or response error', 502)
    videos, audios = clean_items(data, 'videos'), clean_items(data, 'audios')
    if not videos:
        return fail('No usable video links returned. API or media access may be restricted', 404)
    token = sign({'videos': videos, 'audios': audios, 'exp': int(time.time()) + 600})
    return jsonify(videos=[{'label': v['label'], 'index': i} for i, v in enumerate(videos)],
                   audios=[{'label': a['label'], 'index': i} for i, a in enumerate(audios)],
                   token=token, platform='YouTube' if is_youtube else 'Facebook')

def download_stream(url, destination):
    """Follow bounded, validated redirects, detect loops, and never silently accept HTML."""
    seen = set()
    session = requests.Session()
    session.trust_env = False
    try:
        for hop in range(MAX_REDIRECTS + 1):
            if not safe_url(url):
                raise ValueError('Unsupported media redirect host: ' + str(urlparse(url).hostname))
            if url in seen:
                raise ValueError('Media redirect loop detected; API URL may be expired or blocked')
            seen.add(url)
            validate_dns(url)
            with session.get(url, stream=True, allow_redirects=False, timeout=(10, 45),
                             headers={'User-Agent': 'Mozilla/5.0', 'Accept': '*/*'}) as r:
                if r.status_code in (301, 302, 303, 307, 308):
                    target = r.headers.get('Location')
                    if not target:
                        raise ValueError('Media redirect has no Location header')
                    url = urljoin(r.url, target)
                    continue
                if r.status_code in (401, 403, 404, 410, 429):
                    raise ValueError('Media server returned HTTP ' + str(r.status_code) + '; link may have expired or require proxy access')
                r.raise_for_status()
                content_type = r.headers.get('Content-Type', '').lower()
                if 'text/html' in content_type or 'application/json' in content_type:
                    raise ValueError('Media URL returned a web page instead of video/audio')
                length = r.headers.get('Content-Length')
                if length and length.isdigit() and int(length) > MAX_BYTES:
                    raise ValueError('Media exceeds server size limit')
                total = 0
                with open(destination, 'wb') as f:
                    for chunk in r.iter_content(256 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > MAX_BYTES:
                            raise ValueError('Media exceeds server size limit')
                        f.write(chunk)
                if total < 100:
                    raise ValueError('Empty media stream')
                return
        raise ValueError('Too many media redirects; source URL may require proxied access')
    finally:
        session.close()

def cleanup():
    now = time.time()
    with LOCK:
        for key, expiry in list(JOBS.items()):
            if expiry < now:
                JOBS.pop(key, None)
                try:
                    os.unlink(os.path.join(OUT_DIR, key + '.mp4'))
                except OSError:
                    pass

@app.post('/api/merge')
def merge():
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        return fail('FFmpeg/FFprobe missing in Render image', 503)
    data = request.get_json(silent=True) or {}
    try:
        payload = unsign(str(data.get('token', '')))
        vi = int(data.get('video', -1))
        ai = int(data.get('audio', -1))
        if not 0 <= vi < len(payload['videos']):
            raise ValueError('Invalid video selection')
        if ai < -1 or ai >= len(payload['audios']):
            raise ValueError('Invalid audio selection')
        video = payload['videos'][vi]['url']
        audio = payload['audios'][ai]['url'] if ai >= 0 else None
    except (ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError):
        return fail('Invalid or expired selection. Search again')
    cleanup()
    with LOCK:
        if len(JOBS) >= 10:
            return fail('Server busy; try again later', 429)
    job = secrets.token_urlsafe(18)
    directory = tempfile.mkdtemp(prefix='merge_')
    output = os.path.join(OUT_DIR, job + '.mp4')
    try:
        video_path = os.path.join(directory, 'video.bin')
        download_stream(video, video_path)
        cmd = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-i', video_path]
        if audio:
            audio_path = os.path.join(directory, 'audio.bin')
            download_stream(audio, audio_path)
            cmd += ['-i', audio_path, '-map', '0:v:0', '-map', '1:a:0']
        else:
            cmd += ['-map', '0:v:0', '-map', '0:a:0?']
        cmd += ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '-t', '1800', output]
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=105)
        if run.returncode:
            raise ValueError('FFmpeg failed: ' + run.stderr[-250:])
        probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a',
                                '-show_entries', 'stream=index', '-of', 'csv=p=0', output],
                               capture_output=True, text=True, timeout=10)
        if not probe.stdout.strip():
            raise ValueError('No audio track in output. Select a separate audio stream and retry')
        with LOCK:
            JOBS[job] = time.time() + 600
        return jsonify(success=True, download='/api/download/' + job)
    except (requests.RequestException, subprocess.TimeoutExpired, ValueError, OSError) as exc:
        app.logger.warning('Merge failed: %s', str(exc)[:300])
        try:
            os.unlink(output)
        except OSError:
            pass
        return fail(str(exc)[:350], 422)
    finally:
        shutil.rmtree(directory, ignore_errors=True)

@app.get('/api/download/<job>')
def download(job):
    cleanup()
    with LOCK:
        valid = JOBS.get(job, 0) > time.time()
    if not valid or not os.path.isfile(os.path.join(OUT_DIR, job + '.mp4')):
        abort(404)
    return send_file(os.path.join(OUT_DIR, job + '.mp4'), as_attachment=True,
                     download_name='video_with_audio.mp4', mimetype='video/mp4')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '10000')))
